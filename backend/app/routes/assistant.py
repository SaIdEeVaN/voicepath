"""Follow-up voice Q&A route (PRD section 4.6)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import schemas
from app.services import assistant, schemes, repository, taxonomy
from app.services.assistant import QueryContext
from app.services.ratelimit import assistant_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post(
    "/query",
    response_model=schemas.AssistantQueryResponse,
    dependencies=[Depends(assistant_limit)],
)
async def query(payload: schemas.AssistantQueryRequest) -> schemas.AssistantQueryResponse:
    question = payload.question_text.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There was no question to answer.",
        )

    context = QueryContext()
    language = payload.language

    if payload.scheme_id is not None:
        found = await schemes.get(payload.scheme_id)
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="That scheme was not found.",
            )
        context.scheme = found

    if payload.session_id is not None:
        session = await repository.get_session(payload.session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="That session was not found.",
            )
        context.audio_retained = session.audio_retained
        if payload.language == "en" and session.language_detected:
            language = session.language_detected.split("-")[0]  # type: ignore[assignment]

        profile = await repository.get_profile(payload.session_id)
        if profile is not None:
            context.experience_years = profile.experience_years
            context.location = profile.location
            context.certifications = profile.certifications

        rows = await repository.get_skills(payload.session_id)
        lookup = await taxonomy.get_by_ids(
            [r.normalized_skill_id for r in rows if r.normalized_skill_id]
        )
        context.skill_names = [
            lookup[r.normalized_skill_id].name
            if r.normalized_skill_id in lookup
            else r.raw_name
            for r in rows
        ]

        if payload.scheme_id is not None:
            stored = await repository.get_match(payload.session_id, payload.scheme_id)
            if stored is not None:
                context.overall_score = stored.overall_score
                # Only the skills that actually carried this match, so the
                # answer to "why do I match?" cannot drift onto skills that
                # played no part.
                context.matched_skill_names = [
                    lookup[r.normalized_skill_id].name
                    for r in rows
                    if r.normalized_skill_id in lookup
                ]

    result = await assistant.answer(question, context, language=language)

    if payload.session_id is not None:
        await repository.log_assistant_query(
            payload.session_id,
            scheme_id=payload.scheme_id,
            question_text=question,
            answer_text=result.answer_text,
            source_note=result.source_note,
        )

    return schemas.AssistantQueryResponse(
        question_text=question,
        answer_text=result.answer_text,
        source_note=result.source_note,
        provider=result.provider,
        answered_from_data=result.answered_from_data,
    )
