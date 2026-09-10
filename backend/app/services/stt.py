"""Speech to text (PRD section 4.1).

Whisper (MIT) either way; ``STT_PROVIDER`` decides whose hardware runs it.

``groq``   Whisper on Groq. Measured on a 5.8s clip: 1.1s.
``local``  faster-whisper on this CPU. The same clip: 32.5s, which is 5.6x
           slower than realtime and turns a 30s answer into a 3-minute wait.
           Nothing leaves the process on this path, which is the reason to
           accept that cost.

Same open weights in both cases. The difference is latency against privacy,
and /health names which one is actually running.

``mode=transcribe`` in the PRD's terms means: keep the words in the language
they were spoken in. We never ask for a translation, because extraction runs on
the source-language transcript (section 4.2) and translating first would throw
away exactly the code-switched detail the platform exists to handle. Whisper is
capable of translating; we deliberately do not use that mode.

When ``STT_PROVIDER`` resolves to ``offline`` -- the package is missing, or the
model has not been fetched -- this module says so plainly and the client falls
back to the browser's own ``SpeechRecognition``, which is real on-device
recognition rather than a stand-in. See ``frontend/lib/browser-speech.ts``.

Known limit: Whisper's Tamil is weaker than its Hindi, and it mishears English
loanwords inside Tamil speech -- "பைக் ரிப்பேர்" (bike repair) comes back as
"பைக்குப் பேர்" (bike name). Because extraction only accepts evidence it can
find verbatim in the transcript, a mangled skill word means the skill is
dropped rather than guessed at. That is the safe failure, but it is a real
recall loss on precisely the phrases this app cares about.
"""

from __future__ import annotations

import asyncio
import io
import logging
import threading
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class STTUnavailable(RuntimeError):
    """No server-side transcriber is configured or reachable."""


@dataclass(frozen=True)
class Transcription:
    transcript: str
    language_detected: str
    provider: str
    # Populated when the provider reports one; nothing downstream depends on it.
    confidence: float | None = None


# Whisper takes bare ISO codes rather than locales. ``auto`` means "detect",
# which Whisper does natively -- the one case where we want it to decide.
LANGUAGE_CODES: dict[str, str] = {
    "ta": "ta",
    "hi": "hi",
    "en": "en",
    "auto": "auto",
}


def normalise_language(code: str | None) -> str:
    """Map a UI language choice onto a provider language code."""
    if not code:
        return LANGUAGE_CODES["auto"]
    return LANGUAGE_CODES.get(code.strip().lower(), LANGUAGE_CODES["auto"])


def _short_language(provider_code: str | None, requested: str | None) -> str:
    """Collapse a provider code back to the app's short form.

    Falls back to what the user asked for rather than guessing, so
    ``sessions.language_detected`` is never a fabricated detection.
    """
    if provider_code:
        head = provider_code.split("-")[0].strip().lower()
        if head and head != "unknown":
            return head
    return (requested or "auto").strip().lower()


def is_available() -> bool:
    return get_settings().stt_provider != "offline"


def provider_name() -> str:
    return get_settings().stt_provider


# The model costs 60-90s to load and hundreds of MB of RAM, so it is loaded once
# and shared. The lock matters: two requests arriving before the first load
# finishes would otherwise each build their own copy.
_model = None
_model_key: tuple[str, str, str] | None = None
_model_lock = threading.Lock()


def _load_model():
    global _model, _model_key
    settings = get_settings()
    key = (settings.stt_model, settings.stt_device, settings.stt_compute_type)

    with _model_lock:
        if _model is not None and _model_key == key:
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - depends on install
            raise STTUnavailable(
                "faster-whisper is not installed. Run "
                "`pip install -r requirements-ml.txt`, or let the browser "
                "transcribe on-device."
            ) from exc

        logger.info(
            "Loading Whisper %s on %s (%s)",
            settings.stt_model, settings.stt_device, settings.stt_compute_type,
        )
        _model = WhisperModel(
            settings.stt_model,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
        )
        _model_key = key
        return _model


def _transcribe_sync(audio: bytes, language: str) -> tuple[str, str | None, float | None]:
    """Blocking transcription. Called through a thread, never on the loop."""
    model = _load_model()
    segments, info = model.transcribe(
        io.BytesIO(audio),
        language=None if language == "auto" else language,
        beam_size=5,
        # Whisper will happily hallucinate fluent text over silence. This makes
        # it return nothing instead, which the caller reports honestly.
        vad_filter=True,
        condition_on_previous_text=False,
    )
    parts = [segment.text.strip() for segment in segments]
    transcript = " ".join(p for p in parts if p).strip()

    confidence = None
    probability = getattr(info, "language_probability", None)
    if isinstance(probability, (int, float)):
        confidence = float(probability)

    return transcript, getattr(info, "language", None), confidence


async def _transcribe_groq(
    audio: bytes, filename: str, content_type: str, language: str
) -> tuple[str, str | None, float | None]:
    """Whisper on Groq's hardware -- same open weights, someone else's GPU.

    Measured against the local path on a 5.8s clip: 1.1s versus 32.5s. The audio
    does leave the machine here, which the local provider avoids; that is the
    trade this provider exists to offer, and /health names which one is running.
    """
    settings = get_settings()
    data = {"model": settings.stt_groq_model, "response_format": "json"}
    if language != "auto":
        data["language"] = language

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.llm_api_key or ''}"},
                files={"file": (filename, audio, content_type)},
                data=data,
            )
    except httpx.HTTPError as exc:
        raise STTUnavailable(f"Groq transcription request failed: {exc}") from exc

    if response.status_code >= 400:
        raise STTUnavailable(
            f"Groq returned {response.status_code}: {response.text[:300]}"
        )

    payload = response.json()
    # Groq echoes no language when one was supplied, so fall back to the ask.
    return (payload.get("text") or "").strip(), payload.get("language"), None


async def transcribe(
    audio: bytes,
    *,
    filename: str = "speech.wav",
    content_type: str = "audio/wav",
    language: str | None = None,
) -> Transcription:
    settings = get_settings()

    if settings.stt_provider == "offline":
        raise STTUnavailable(
            "No server-side speech-to-text is configured. Install "
            "faster-whisper, or let the browser transcribe on-device."
        )

    if not audio:
        raise ValueError("Empty audio payload")
    if len(audio) > settings.max_audio_bytes:
        raise ValueError(
            f"Audio is {len(audio)} bytes; the limit is {settings.max_audio_bytes}."
        )

    requested = normalise_language(language)
    try:
        if settings.stt_provider == "groq":
            transcript, detected, confidence = await _transcribe_groq(
                audio, filename, content_type, requested
            )
        else:
            transcript, detected, confidence = await asyncio.to_thread(
                _transcribe_sync, audio, requested
            )
    except STTUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - any decode/model failure is the same to the caller
        raise STTUnavailable(f"Whisper transcription failed: {exc}") from exc

    if not transcript:
        raise STTUnavailable("Nothing was recognised in that recording")

    return Transcription(
        transcript=transcript,
        language_detected=_short_language(detected, language),
        provider=settings.stt_provider,
        confidence=confidence,
    )
