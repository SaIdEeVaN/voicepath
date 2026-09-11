"""Glue between stored rows, service dataclasses and wire schemas.

Routes stay thin by delegating the shape-shifting here. The one piece of real
logic is ``load_profile_input``: rebuilding a scoreable profile from storage,
including re-embedding skills whose vectors were not carried through the
request, since embeddings are deliberately not persisted per skill.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.models import schemas
from app.services import embeddings, repository, taxonomy
from app.services.matching import ProfileInput
from app.services.normalization import NormalizedSkill
from app.services.schemes import Scheme
from app.services.taxonomy import ScoredSkill, TaxonomySkill

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rows -> wire
# ---------------------------------------------------------------------------


def profile_to_schema(profile: repository.ProfileRow | None) -> schemas.ExtractedProfile:
    if profile is None:
        return schemas.ExtractedProfile()
    return schemas.ExtractedProfile(
        id=profile.id,
        session_id=profile.session_id,
        experience_years=profile.experience_years,
        experience_context=profile.experience_context,
        education=profile.education,
        certifications=profile.certifications,
        location=profile.location,
        work_preferences=profile.work_preferences,
        uncertainty_flags=profile.uncertainty_flags,
    )


def skill_rows_to_schema(
    rows: list[repository.SkillRow],
    lookup: dict[int, TaxonomySkill] | None = None,
) -> list[schemas.ExtractedSkill]:
    lookup = lookup or {}
    out: list[schemas.ExtractedSkill] = []
    for row in rows:
        entry = lookup.get(row.normalized_skill_id) if row.normalized_skill_id else None
        out.append(
            schemas.ExtractedSkill(
                id=row.id,
                raw_name=row.raw_name,
                evidence_phrase=row.evidence_phrase,
                normalized_skill_id=row.normalized_skill_id,
                normalized_code=entry.code if entry else None,
                normalized_name=entry.name if entry else None,
                display_names=dict(entry.display_names or {}) if entry else {},
                category=entry.category if entry else None,
                match_confidence=row.match_confidence,
                needs_disambiguation=row.needs_disambiguation,
                candidates=[
                    schemas.SkillCandidate(**c) for c in row.candidates if isinstance(c, dict)
                ],
                user_confirmed=row.user_confirmed,
            )
        )
    return out


def normalized_to_schema(skills: list[NormalizedSkill]) -> list[schemas.ExtractedSkill]:
    return [
        schemas.ExtractedSkill(
            raw_name=s.raw_name,
            evidence_phrase=s.evidence_phrase,
            normalized_skill_id=s.skill_id,
            normalized_code=s.code,
            normalized_name=s.name,
            display_names=dict(s.display_names or {}),
            category=s.category,
            match_confidence=s.confidence,
            needs_disambiguation=s.needs_disambiguation,
            candidates=[
                schemas.SkillCandidate(
                    id=c.skill.id,
                    code=c.skill.code,
                    name=c.skill.name,
                    category=c.skill.category,
                    hint=c.skill.hint,
                    similarity=round(c.similarity, 4),
                    display_names=dict(c.skill.display_names or {}),
                )
                for c in s.candidates
            ],
            user_confirmed=s.user_confirmed,
        )
        for s in skills
    ]


def scheme_to_summary(scheme: Scheme) -> schemas.SchemeSummary:
    return schemas.SchemeSummary(
        id=scheme.id,
        title=scheme.title,
        organization=scheme.organization,
        location=scheme.location,
        district=scheme.district,
        type=scheme.type,
        minimum_experience=scheme.minimum_experience,
        certifications_required=scheme.certifications_required,
        salary_min=scheme.salary_min,
        salary_max=scheme.salary_max,
        nsqf_level=scheme.nsqf_level,
        source_reference=scheme.source_reference,
        official_url=scheme.official_url,
    )


def scheme_to_detail(scheme: Scheme) -> schemas.SchemeDetail:
    return schemas.SchemeDetail(
        **scheme_to_summary(scheme).model_dump(),
        description=scheme.description,
        is_active=scheme.is_active,
        required_skills=[
            schemas.SkillCandidate(
                id=r.skill_id,
                code=r.code,
                name=r.name,
                category="",
                hint=None,
                similarity=r.weight,
            )
            for r in scheme.required_skills
        ],
    )


def session_to_schema(session: repository.SessionRow) -> schemas.SessionSummary:
    return schemas.SessionSummary(
        id=session.id,
        created_at=session.created_at,
        language_detected=session.language_detected,
        transcript=session.transcript,
        audio_retained=session.audio_retained,
        audio_url=session.audio_url,
    )


# ---------------------------------------------------------------------------
# Wire / rows -> scoreable profile
# ---------------------------------------------------------------------------


async def rows_to_normalized(rows: list[repository.SkillRow]) -> list[NormalizedSkill]:
    """Rebuild normalized skills from storage, restoring their embeddings.

    Skill embeddings are not stored per row -- they are derivable, and storing
    them would mean a re-embed migration every time the model changes. Rebuilding
    is one batched call.
    """
    if not rows:
        return []

    ids = [r.normalized_skill_id for r in rows if r.normalized_skill_id]
    lookup = await taxonomy.get_by_ids(ids)

    # Prefer the taxonomy vector for a normalized skill: it is the canonical
    # point for that concept. Fall back to embedding the raw phrase.
    taxonomy_vectors = await taxonomy.embedding_for_skill_ids(ids)

    needs_embedding = [
        r for r in rows
        if r.embedding is None
        and (not r.normalized_skill_id or r.normalized_skill_id not in taxonomy_vectors)
    ]
    fresh: dict[str, list[float]] = {}
    if needs_embedding:
        vectors = await asyncio.to_thread(
            embeddings.embed_queries, [r.raw_name for r in needs_embedding]
        )
        fresh = {r.raw_name: v for r, v in zip(needs_embedding, vectors)}

    out: list[NormalizedSkill] = []
    for row in rows:
        entry = lookup.get(row.normalized_skill_id) if row.normalized_skill_id else None
        vector = row.embedding
        if vector is None and row.normalized_skill_id:
            vector = taxonomy_vectors.get(row.normalized_skill_id)
        if vector is None:
            vector = fresh.get(row.raw_name)

        out.append(
            NormalizedSkill(
                raw_name=row.raw_name,
                evidence_phrase=row.evidence_phrase,
                skill_id=row.normalized_skill_id,
                code=entry.code if entry else None,
                name=entry.name if entry else None,
                category=entry.category if entry else None,
                # Without this, an explanation rebuilt from storage loses the
                # Tamil and Hindi labels and drops English nouns into
                # non-English sentences.
                display_names=dict(entry.display_names or {}) if entry else {},
                confidence=row.match_confidence,
                needs_disambiguation=row.needs_disambiguation,
                candidates=[
                    ScoredSkill(
                        skill=TaxonomySkill(
                            id=c["id"], code=c["code"], name=c["name"],
                            category=c.get("category", ""), hint=c.get("hint"),
                        ),
                        similarity=float(c.get("similarity", 0.0)),
                    )
                    for c in row.candidates
                    if isinstance(c, dict) and "id" in c
                ],
                user_confirmed=row.user_confirmed,
                embedding=vector,
            )
        )
    return out


async def schema_skills_to_normalized(
    skills: list[schemas.ExtractedSkill],
) -> list[NormalizedSkill]:
    """Build scoreable skills from a request body (no session involved)."""
    rows = [
        repository.SkillRow(
            id=s.id or UUID(int=0),
            profile_id=UUID(int=0),
            raw_name=s.raw_name,
            evidence_phrase=s.evidence_phrase,
            normalized_skill_id=s.normalized_skill_id,
            match_confidence=s.match_confidence,
            needs_disambiguation=s.needs_disambiguation,
            candidates=[c.model_dump() for c in s.candidates],
            user_confirmed=s.user_confirmed,
        )
        for s in skills
    ]
    return await rows_to_normalized(rows)


def to_profile_input(
    profile: repository.ProfileRow | schemas.ExtractedProfile | None,
    skills: list[NormalizedSkill],
) -> ProfileInput:
    if profile is None:
        return ProfileInput(skills=skills)
    location = profile.location
    return ProfileInput(
        experience_years=profile.experience_years,
        location=location,
        # District is not extracted separately; the stated place stands in for
        # it, and matching treats "town inside the district" as same-district.
        district=location,
        certifications=list(profile.certifications or []),
        skills=skills,
    )


async def load_profile_input(session_id: UUID) -> tuple[ProfileInput, repository.ProfileRow | None]:
    profile = await repository.get_profile(session_id)
    rows = await repository.get_skills(session_id)
    normalized = await rows_to_normalized(rows)
    return to_profile_input(profile, normalized), profile
