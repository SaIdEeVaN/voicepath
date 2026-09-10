"""Speech routes (PRD sections 4.1 and 4.6).

The data-minimisation rule of section 7 is implemented here, in the only place
audio ever exists server-side: the bytes are read into memory, passed to the
transcriber, and go out of scope. Nothing writes them to disk, and there is no
code path from this module to Storage. Opting into evidence playback is a
separate, later action on the passport screen -- it does not retroactively
resurrect a recording that was never kept.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.config import get_settings
from app.models import schemas
from app.services import repository, stt, tts
from app.services.ratelimit import speech_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.post(
    "/transcribe",
    response_model=schemas.TranscribeResponse,
    dependencies=[Depends(speech_limit)],
)
async def transcribe(
    request: Request,
    file: UploadFile = File(..., description="Recorded audio blob"),
    language: str = Form("auto"),
) -> schemas.TranscribeResponse:
    settings = get_settings()

    audio = await file.read()
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio was received.",
        )
    if len(audio) > settings.max_audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="That recording is too long. Try a shorter one.",
        )

    try:
        result = await stt.transcribe(
            audio,
            filename=file.filename or "speech.webm",
            content_type=file.content_type or "audio/webm",
            language=language,
        )
    except stt.STTUnavailable as exc:
        # 503 rather than 500: the client has a real alternative (on-device
        # recognition) and needs to be able to tell the difference.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    finally:
        # Explicit, so the intent is visible at the point it matters.
        del audio

    session = await repository.create_session(
        transcript=result.transcript,
        language_detected=result.language_detected,
        stt_provider=result.provider,
    )

    return schemas.TranscribeResponse(
        session_id=session.id,
        transcript=result.transcript,
        language_detected=result.language_detected,
        provider=result.provider,
        audio_retained=False,
    )


@router.post(
    "/client-transcript",
    response_model=schemas.TranscribeResponse,
    dependencies=[Depends(speech_limit)],
)
async def client_transcript(
    payload: schemas.ClientTranscriptRequest,
) -> schemas.TranscribeResponse:
    """Register a transcript the browser produced on-device.

    Used when server-side STT is unavailable. Strictly more private than the
    default path -- the audio never leaves the device at all.
    """
    transcript = payload.transcript.strip()
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The transcript was empty.",
        )

    session = await repository.create_session(
        transcript=transcript,
        language_detected=payload.language_detected,
        stt_provider="browser",
    )
    return schemas.TranscribeResponse(
        session_id=session.id,
        transcript=transcript,
        language_detected=payload.language_detected,
        provider="browser",
        audio_retained=False,
    )


@router.post(
    "/synthesize",
    response_model=schemas.SynthesizeResponse,
    dependencies=[Depends(speech_limit)],
)
async def synthesize(payload: schemas.SynthesizeRequest) -> schemas.SynthesizeResponse:
    try:
        result = await tts.synthesize(payload.text, language=payload.language)
    except tts.TTSUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return schemas.SynthesizeResponse(
        provider=result.provider,
        audio_base64=result.audio_base64,
        speech_locale=result.speech_locale,
        use_browser_tts=result.use_browser_tts,
    )
