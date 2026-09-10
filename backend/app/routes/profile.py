"""Extraction and normalization routes (PRD sections 4.2 and 4.3)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import schemas
from app.services import extraction, normalization, pipeline, repository, taxonomy
from app.services.ratelimit import default_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.post(
    "/extract",
    response_model=schemas.ExtractResponse,
    dependencies=[Depends(default_limit)],
)
async def extract(payload: schemas.ExtractRequest) -> schemas.ExtractResponse:
    """Transcript to structured profile, then a first normalization pass.

    Normalization runs here rather than waiting for an explicit call, because
    the /understanding screen needs the taxonomy category and the
    low-confidence flags to render at all. ``/normalize`` stays available for
    re-running after the user edits.
    """
    transcript = (payload.transcript or "").strip()
    session = None

    if payload.session_id:
        session = await repository.get_session(payload.session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="That session was not found.",
            )
        transcript = transcript or (session.transcript or "")

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is nothing to read yet.",
        )

    language = payload.language
    if session and session.language_detected:
        language = session.language_detected  # type: ignore[assignment]

    result = await extraction.extract(transcript, language=language)

    normalized = await normalization.normalize_many(
        [(s.raw_name, s.evidence_phrase) for s in result.skills]
    )

    if session is None and payload.session_id is None:
        # Extraction without a prior transcribe call: create the session so the
        # rest of the pipeline has something to hang on to.
        session = await repository.create_session(
            transcript=transcript,
            language_detected=language,
            stt_provider="client",
        )

    profile_row = None
    if session is not None:
        profile_row = await repository.upsert_profile(
            session.id,
            experience_years=result.experience_years,
            experience_context=result.experience_context,
            education=result.education,
            certifications=result.certifications,
            location=result.location,
            work_preferences=result.work_preferences,
            uncertainty_flags=result.uncertainty_flags,
        )
        stored = await repository.replace_skills(
            profile_row.id, normalized, session_id=session.id
        )
        lookup = await taxonomy.get_by_ids(
            [s.normalized_skill_id for s in stored if s.normalized_skill_id]
        )
        skills_out = pipeline.skill_rows_to_schema(stored, lookup)
    else:
        skills_out = pipeline.normalized_to_schema(normalized)

    return schemas.ExtractResponse(
        session_id=session.id if session else None,
        profile=pipeline.profile_to_schema(profile_row)
        if profile_row
        else schemas.ExtractedProfile(
            experience_years=result.experience_years,
            experience_context=result.experience_context,
            education=result.education,
            certifications=result.certifications,
            location=result.location,
            work_preferences=result.work_preferences,
            uncertainty_flags=result.uncertainty_flags,
        ),
        skills=skills_out,
        provider=result.provider,
        degraded=result.degraded,
    )


@router.post(
    "/normalize",
    response_model=schemas.NormalizeResponse,
    dependencies=[Depends(default_limit)],
)
async def normalize(payload: schemas.NormalizeRequest) -> schemas.NormalizeResponse:
    """Re-normalize after the user edits, removes or disambiguates a skill.

    The request carries the full corrected list, and it replaces what was
    stored -- a merge would bring back skills the user deleted.
    """
    session_id = payload.session_id
    edits = payload.skills

    if edits is None:
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Send either a session_id or a list of skills.",
            )
        rows = await repository.get_skills(session_id)
        edits = [
            schemas.SkillEdit(
                id=r.id, raw_name=r.raw_name, evidence_phrase=r.evidence_phrase
            )
            for r in rows
        ]

    kept = [e for e in edits if not e.removed]
    if not kept:
        if session_id is not None:
            profile = await repository.get_profile(session_id)
            if profile is not None:
                await repository.replace_skills(profile.id, [], session_id=session_id)
        return schemas.NormalizeResponse(
            session_id=session_id,
            skills=[],
            provider=normalization.provider_name(),
        )

    normalized = await normalization.normalize_many(
        [(e.raw_name, e.evidence_phrase) for e in kept]
    )

    # A user's pick on the disambiguation screen overrides the model outright.
    for edit, entry in zip(kept, normalized):
        if edit.chosen_skill_id is not None:
            await normalization.apply_user_choice(entry, edit.chosen_skill_id)

    if session_id is not None:
        profile = await repository.get_profile(session_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nothing has been understood for this session yet.",
            )
        stored = await repository.replace_skills(
            profile.id, normalized, session_id=session_id
        )
        lookup = await taxonomy.get_by_ids(
            [s.normalized_skill_id for s in stored if s.normalized_skill_id]
        )
        return schemas.NormalizeResponse(
            session_id=session_id,
            skills=pipeline.skill_rows_to_schema(stored, lookup),
            provider=normalization.provider_name(),
        )

    return schemas.NormalizeResponse(
        session_id=None,
        skills=pipeline.normalized_to_schema(normalized),
        provider=normalization.provider_name(),
    )


@router.get("/taxonomy", response_model=list[schemas.SkillCandidate])
async def list_taxonomy() -> list[schemas.SkillCandidate]:
    """The skill vocabulary, for the disambiguation picker.

    The frontend never hardcodes a skill list (PRD section 6.1); it reads this.
    """
    skills = await taxonomy.list_all()
    return [
        schemas.SkillCandidate(
            id=s.id, code=s.code, name=s.name, category=s.category,
            hint=s.hint, similarity=1.0,
            display_names=dict(s.display_names or {}),
        )
        for s in skills
    ]
