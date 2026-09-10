"""Text to speech (PRD section 4.6).

Piper (MIT) synthesises locally on the CPU. Nothing leaves this process, and
there is no per-call cost, which matters for a service meant to run on district
hardware rather than a metered API budget.

One voice per language lives in ``backend/models/piper``. If the voice file for
a language is missing, the response tells the client to speak the text with the
browser's own ``speechSynthesis`` -- real device-local TTS in the user's
language, not silence dressed up as audio.

Voice licensing is not uniform, and the difference is worth keeping visible:
the Hindi and English voices are MIT, from the Piper project itself. The Tamil
voice is a community model trained on AI4Bharat Rasa and carries CC-BY-4.0, so
shipping it obliges you to attribute it.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


class TTSUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Synthesis:
    provider: str
    # base64-encoded WAV, or None when the client should speak it itself.
    audio_base64: str | None
    # BCP-47-ish tag the browser needs to pick a voice.
    speech_locale: str
    use_browser_tts: bool


LANGUAGE_CODES: dict[str, str] = {
    "ta": "ta-IN",
    "hi": "hi-IN",
    "en": "en-IN",
}

# One Piper voice per language. Female throughout, so switching language does
# not also switch who appears to be speaking.
VOICE_FILES: dict[str, str] = {
    "ta": "ta_IN-rasa_female-medium.onnx",
    "hi": "hi_IN-priyamvada-medium.onnx",
    "en": "en_GB-alba-medium.onnx",
}

# Answers are short by design, so this only ever bites on a malformed caller.
MAX_CHARS = 1500


def is_available() -> bool:
    return get_settings().tts_provider != "offline"


def provider_name() -> str:
    return get_settings().tts_provider


def locale_for(language: str | None) -> str:
    return LANGUAGE_CODES.get((language or "en").split("-")[0].lower(), "en-IN")


def _short(language: str | None) -> str:
    return (language or "en").split("-")[0].lower()


def voice_path(language: str | None) -> Path:
    settings = get_settings()
    name = VOICE_FILES.get(_short(language), VOICE_FILES["en"])
    return Path(settings.piper_voice_dir) / name


def has_voice(language: str | None) -> bool:
    return voice_path(language).is_file()


# Loading a voice reads a 63 MB ONNX graph, so each is loaded once and kept.
_voices: dict[str, object] = {}
_voice_lock = threading.Lock()


def _load_voice(language: str):
    with _voice_lock:
        cached = _voices.get(language)
        if cached is not None:
            return cached
        try:
            from piper import PiperVoice
        except ImportError as exc:  # pragma: no cover - depends on install
            raise TTSUnavailable(
                "piper-tts is not installed. Run "
                "`pip install -r requirements-ml.txt`."
            ) from exc

        path = voice_path(language)
        if not path.is_file():
            raise TTSUnavailable(f"No Piper voice for '{language}' at {path}")

        logger.info("Loading Piper voice %s", path.name)
        voice = PiperVoice.load(str(path))
        _voices[language] = voice
        return voice


def _synthesize_sync(text: str, language: str) -> str:
    """Blocking synthesis to base64 WAV. Called through a thread."""
    voice = _load_voice(language)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


async def synthesize(text: str, *, language: str | None = None) -> Synthesis:
    settings = get_settings()
    locale = locale_for(language)
    short = _short(language)
    clean = (text or "").strip()

    if not clean:
        raise ValueError("Nothing to speak")

    # Either the provider is switched off, or this particular language has no
    # voice installed. Both mean the same thing to the client, and neither is
    # worth failing the request over when the browser can speak instead.
    if settings.tts_provider == "offline" or not has_voice(short):
        return Synthesis(
            provider="offline",
            audio_base64=None,
            speech_locale=locale,
            use_browser_tts=True,
        )

    try:
        audio_base64 = await asyncio.to_thread(
            _synthesize_sync, clean[:MAX_CHARS], short
        )
    except TTSUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - any synthesis failure reads the same
        raise TTSUnavailable(f"Piper synthesis failed: {exc}") from exc

    if not audio_base64:
        raise TTSUnavailable("Piper produced no audio")

    return Synthesis(
        provider="local",
        audio_base64=audio_base64,
        speech_locale=locale,
        use_browser_tts=False,
    )
