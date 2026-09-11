"""Matching and scheme routes (PRD sections 4.4 and 4.5)."""

from __future__ import annotations

import logging
from uuid import UUID

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

    explained_in = (payload.language or language).split("-")[0]

    explanations: dict[int, explanation.Explanation] = {}
    if payload.explain:
        explanations = await explanation.explain_many(ranked, language=explained_in)

    if payload.session_id is not None:
        # The language goes in with the prose. Without it a later read
        # cannot tell whether the stored sentences are the ones this
        # reader can read.
        await repository.replace_matches(
            payload.session_id, ranked, explanations, language=explained_in
        )

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
async def get_stored_match(
    scheme_id: int,
    session_id: str,
    language: str | None = Query(
        None, description="Language to read the explanation in (ta, hi, en)."
    ),
) -> schemas.MatchResult:
    """The stored match for one session and one scheme.

    Reads the persisted row rather than re-scoring, so the detail screen shows
    exactly the numbers that were computed and audited, not a fresh computation
    that might differ if the catalogue moved underneath it.

    ``language`` rewrites the *sentences* only. A person who switches to
    Tamil on this screen was previously left reading English reasons under a
    Tamil interface, because the stored prose had no language recorded and
    so could never be recognised as the wrong one.

    The scores are not recomputed. They are the audited numbers, and an
    explanation has never been allowed to move one -- re-explaining in
    another language must not become the exception.
    """
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

    text = stored.explanation_text
    bullets = list(stored.explanation_bullets)

    wanted = (language or "").split("-")[0]
    if wanted and wanted != stored.explanation_language:
        rewritten = await _reexplain(parsed, stored, found, language=wanted)
        if rewritten is not None:
            text, bullets = rewritten.summary, list(rewritten.bullets)

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
        explanation_text=text,
        explanation_bullets=bullets,
    )


async def _reexplain(
    session_id: UUID,
    stored: repository.MatchRow,
    scheme: schemes.Scheme,
    *,
    language: str,
) -> explanation.Explanation | None:
    """Rewrite one stored match's sentences in another language.

    The explanation layer needs a ``ScoredMatch`` -- specifically its
    ``grounding``, the closed set of facts it is allowed to draw on. Grounding
    is derived, not stored, so it is rebuilt here from the profile and the
    scheme.

    Rebuilding it also recomputes the scores, and those are discarded: the
    stored ones are written back over the top before anything is explained. If
    the catalogue moved since the match was persisted, the numbers a person
    sees stay the numbers that were audited, and only the wording is new.

    Returns None when the explanation cannot be produced, in which case the
    caller keeps the stored prose. Text in the wrong language is a worse
    outcome than no screen at all only if the screen still works -- so it does.
    """
    try:
        profile_input, _ = await pipeline.load_profile_input(session_id)
        if not profile_input.skills:
            return None

        rebuilt = matching.score_one(profile_input, scheme)
        rebuilt.skill_similarity_score = stored.skill_similarity_score
        rebuilt.experience_score = stored.experience_score
        rebuilt.eligibility_score = stored.eligibility_score
        rebuilt.location_score = stored.location_score
        rebuilt.overall_score = stored.overall_score
        rebuilt.rank = stored.rank

        return await explanation.explain(rebuilt, language=language)
    except Exception as exc:  # noqa: BLE001 - a re-read must not 500
        logger.warning(
            "Could not re-explain match %s/%s in %s (%s); serving stored text",
            session_id, scheme.id, language, exc,
        )
        return None
