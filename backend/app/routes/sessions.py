"""Session and Skill Passport routes."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models import schemas
from app.services import pipeline, repository, taxonomy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_missing(session_id) -> HTTPException:
    """404 for an unknown session; 410, with a plain reason, for one started
    in memory during a database outage and retired when the database came back."""
    code, message = repository.missing_session(session_id)
    return HTTPException(status_code=code, detail=message)


@router.get("/{session_id}", response_model=schemas.PassportResponse)
async def get_passport(session_id: UUID) -> schemas.PassportResponse:
    session = await repository.get_session(session_id)
    if session is None:
        raise _session_missing(session_id)

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


@router.get("/{session_id}/questions", response_model=list[schemas.AssistantQueryLog])
async def list_questions(session_id: UUID) -> list[schemas.AssistantQueryLog]:
    rows = await repository.list_assistant_queries(session_id)
    return [schemas.AssistantQueryLog(**row) for row in rows]
