"""Session and Skill Passport routes."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.models import schemas
from app.services import pipeline, repository, taxonomy
from app.services.ratelimit import default_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=schemas.PassportResponse)
async def get_passport(session_id: UUID) -> schemas.PassportResponse:
    session = await repository.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That session was not found.",
        )

    profile = await repository.get_profile(session_id)
    rows = await repository.get_skills(session_id)
    lookup = await taxonomy.get_by_ids(
        [r.normalized_skill_id for r in rows if r.normalized_skill_id]
    )

    return schemas.PassportResponse(
        session=pipeline.session_to_schema(session),
        profile=pipeline.profile_to_schema(profile) if profile else None,
        skills=pipeline.skill_rows_to_schema(rows, lookup),
    )


@router.post(
    "/{session_id}/audio-retention",
    response_model=schemas.SessionSummary,
    dependencies=[Depends(default_limit)],
)
async def set_audio_retention(
    session_id: UUID, payload: schemas.AudioRetentionRequest
) -> schemas.SessionSummary:
    """The evidence-playback opt-in on the Skill Passport (PRD section 7).

    Turning it on records consent for clips captured from now on. It cannot
    resurrect the original recording -- that was discarded at transcription, and
    nothing here can undo that. Turning it off clears the flag and the URL in
    one statement.
    """
    settings = get_settings()
    if payload.audio_retained and not settings.allow_audio_retention:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keeping voice clips is switched off for this deployment.",
        )

    updated = await repository.set_audio_retention(session_id, payload.audio_retained)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That session was not found.",
        )
    return pipeline.session_to_schema(updated)


@router.get("/{session_id}/questions", response_model=list[schemas.AssistantQueryLog])
async def list_questions(session_id: UUID) -> list[schemas.AssistantQueryLog]:
    rows = await repository.list_assistant_queries(session_id)
    return [schemas.AssistantQueryLog(**row) for row in rows]
