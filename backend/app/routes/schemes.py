"""Matching and scheme routes (PRD sections 4.4 and 4.5)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.models import schemas
from app.services import explanation, matching, schemes, pipeline, repository
from app.services.ratelimit import default_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schemes", tags=["schemes"])


@router.post(
    "/match",
    response_model=schemas.MatchResponse,
    dependencies=[Depends(default_limit)],
)
async def match(payload: schemas.MatchRequest) -> schemas.MatchResponse:
    """Score, rank, then explain -- strictly in that order.

    The ranking is complete before ``explain_many`` is called, and the
    explanations are attached to matches that already carry their rank. There
    is no path by which an explanation could reorder anything.
    """
    settings = get_settings()

    if payload.session_id is not None:
        profile_input, profile_row = await pipeline.load_profile_input(payload.session_id)
        session = await repository.get_session(payload.session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="That session was not found.",
            )
        language = (session.language_detected or "en").split("-")[0]
    elif payload.skills is not None:
        normalized = await pipeline.schema_skills_to_normalized(payload.skills)
        profile_input = pipeline.to_profile_input(payload.profile, normalized)
        profile_row = None
        language = "en"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Send either a session_id or a profile with skills.",
        )

    if not profile_input.skills:
        return schemas.MatchResponse(
            session_id=payload.session_id,
            matches=[],
            explanation_provider=explanation.provider_name(),
        )

    catalogue = await schemes.list_active()
    ranked = matching.rank(
        profile_input, catalogue, limit=payload.limit or settings.match_result_limit
    )

    explanations: dict[int, explanation.Explanation] = {}
    if payload.explain:
        explanations = await explanation.explain_many(
            ranked, language=(payload.language or language)
        )

    if payload.session_id is not None:
        await repository.replace_matches(payload.session_id, ranked, explanations)

    # Report what actually wrote the explanations, not what is configured. The
    # LLM can be configured and still have failed on this request, and a
    # response claiming otherwise would misreport its own provenance.
    used = {e.provider for e in explanations.values()}
    actual_provider = (
        "offline" if used == {"offline"}
        else "+".join(sorted(used)) if used
        else explanation.provider_name()
    )
    degraded = "offline" in used

    return schemas.MatchResponse(
        session_id=payload.session_id,
        matches=[
            schemas.MatchResult(
                scheme=pipeline.scheme_to_summary(m.scheme),
                rank=m.rank,
                overall_score=m.overall_score,
                breakdown=schemas.ScoreBreakdown(
                    skill_similarity_score=m.skill_similarity_score,
                    experience_score=m.experience_score,
                    eligibility_score=m.eligibility_score,
                    location_score=m.location_score,
                ),
                explanation_text=explanations[m.scheme.id].summary
                if m.scheme.id in explanations else None,
                explanation_bullets=explanations[m.scheme.id].bullets
                if m.scheme.id in explanations else [],
                matched_skill_codes=m.matched_skill_codes,
            )
            for m in ranked
        ],
        explanation_provider=actual_provider,
        degraded=degraded,
    )


@router.get("", response_model=list[schemas.SchemeSummary])
async def list_schemes(
    district: str | None = Query(default=None),
) -> list[schemas.SchemeSummary]:
    catalogue = await schemes.list_active(district)
    return [pipeline.scheme_to_summary(o) for o in catalogue]


@router.get("/{scheme_id}", response_model=schemas.SchemeDetail)
async def get_scheme(scheme_id: int) -> schemas.SchemeDetail:
    found = await schemes.get(scheme_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That scheme was not found.",
        )
    return pipeline.scheme_to_detail(found)


@router.get("/{scheme_id}/match/{session_id}", response_model=schemas.MatchResult)
async def get_stored_match(scheme_id: int, session_id: str) -> schemas.MatchResult:
    """The stored match for one session and one scheme.

    Reads the persisted row rather than re-scoring, so the detail screen shows
    exactly the numbers that were computed and audited, not a fresh computation
    that might differ if the catalogue moved underneath it.
    """
    from uuid import UUID

    try:
        parsed = UUID(session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad session id."
        ) from exc

    stored = await repository.get_match(parsed, scheme_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This scheme has not been matched for that session.",
        )
    found = await schemes.get(scheme_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That scheme was not found.",
        )

    return schemas.MatchResult(
        scheme=pipeline.scheme_to_summary(found),
        rank=stored.rank,
        overall_score=stored.overall_score,
        breakdown=schemas.ScoreBreakdown(
            skill_similarity_score=stored.skill_similarity_score,
            experience_score=stored.experience_score,
            eligibility_score=stored.eligibility_score,
            location_score=stored.location_score,
        ),
        explanation_text=stored.explanation_text,
        explanation_bullets=stored.explanation_bullets,
    )
