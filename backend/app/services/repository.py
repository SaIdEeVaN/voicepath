"""Persistence for sessions, profiles, skills, matches and questions.

Two backends behind one interface: Postgres when ``DATABASE_URL`` is set, and a
process-local dict when it is not. The in-memory backend exists so the pipeline
is runnable and testable without Supabase; it is bounded and evicts oldest-first
so a long-running dev server cannot grow without limit.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.services import db
from app.services.matching import ScoredMatch
from app.services.normalization import NormalizedSkill

logger = logging.getLogger(__name__)

MEMORY_SESSION_LIMIT = 500


# ---------------------------------------------------------------------------
# Row shapes
# ---------------------------------------------------------------------------


@dataclass
class SessionRow:
    id: UUID
    created_at: datetime
    language_detected: str | None = None
    transcript: str | None = None
    audio_retained: bool = False
    audio_url: str | None = None
    stt_provider: str | None = None


@dataclass
class ProfileRow:
    id: UUID
    session_id: UUID
    experience_years: float | None = None
    experience_context: str | None = None
    education: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    location: str | None = None
    work_preferences: list[str] = field(default_factory=list)
    uncertainty_flags: list[str] = field(default_factory=list)


@dataclass
class SkillRow:
    id: UUID
    profile_id: UUID
    raw_name: str
    evidence_phrase: str
    normalized_skill_id: int | None = None
    match_confidence: float | None = None
    needs_disambiguation: bool = False
    candidates: list[dict[str, Any]] = field(default_factory=list)
    user_confirmed: bool = False
    # Not persisted: recomputed on load, cached within a request.
    embedding: list[float] | None = None


@dataclass
class MatchRow:
    id: UUID
    session_id: UUID
    scheme_id: int
    skill_similarity_score: float
    experience_score: float
    eligibility_score: float
    location_score: float
    overall_score: float
    rank: int
    explanation_text: str | None = None
    explanation_bullets: list[str] = field(default_factory=list)


@dataclass
class _MemorySession:
    session: SessionRow
    profile: ProfileRow | None = None
    skills: list[SkillRow] = field(default_factory=list)
    matches: list[MatchRow] = field(default_factory=list)
    questions: list[dict[str, Any]] = field(default_factory=list)


_memory: "OrderedDict[UUID, _MemorySession]" = OrderedDict()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _remember(entry: _MemorySession) -> None:
    _memory[entry.session.id] = entry
    _memory.move_to_end(entry.session.id)
    while len(_memory) > MEMORY_SESSION_LIMIT:
        _memory.popitem(last=False)


def reset_memory() -> None:
    _memory.clear()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


async def create_session(
    *,
    transcript: str | None,
    language_detected: str | None,
    stt_provider: str | None = None,
    audio_retained: bool = False,
    audio_url: str | None = None,
) -> SessionRow:
    if audio_url and not audio_retained:
        # Mirrors the database check constraint so both backends behave alike.
        raise ValueError("audio_url requires audio_retained=True")

    if db.is_available():
        row = await db.fetchrow(
            "insert into sessions "
            "(transcript, language_detected, stt_provider, audio_retained, audio_url) "
            "values ($1, $2, $3, $4, $5) "
            "returning id, created_at, language_detected, transcript, "
            "audio_retained, audio_url, stt_provider",
            transcript, language_detected, stt_provider, audio_retained, audio_url,
        )
        return _session_from_row(row)

    session = SessionRow(
        id=uuid4(),
        created_at=_now(),
        language_detected=language_detected,
        transcript=transcript,
        audio_retained=audio_retained,
        audio_url=audio_url,
        stt_provider=stt_provider,
    )
    _remember(_MemorySession(session=session))
    return session


def _session_from_row(row) -> SessionRow:
    return SessionRow(
        id=row["id"],
        created_at=row["created_at"],
        language_detected=row["language_detected"],
        transcript=row["transcript"],
        audio_retained=row["audio_retained"],
        audio_url=row["audio_url"],
        stt_provider=row["stt_provider"],
    )


async def get_session(session_id: UUID) -> SessionRow | None:
    if db.is_available():
        row = await db.fetchrow(
            "select id, created_at, language_detected, transcript, audio_retained, "
            "audio_url, stt_provider from sessions where id = $1",
            session_id,
        )
        return _session_from_row(row) if row else None
    entry = _memory.get(session_id)
    return entry.session if entry else None


async def set_audio_retention(session_id: UUID, retained: bool) -> SessionRow | None:
    """Toggle the Skill Passport playback opt-in.

    Turning it off clears the URL in the same statement, so there is no window
    in which a row says "not retained" while still pointing at a clip.
    """
    if db.is_available():
        row = await db.fetchrow(
            "update sessions set audio_retained = $2, "
            "audio_url = case when $2 then audio_url else null end "
            "where id = $1 "
            "returning id, created_at, language_detected, transcript, "
            "audio_retained, audio_url, stt_provider",
            session_id, retained,
        )
        return _session_from_row(row) if row else None

    entry = _memory.get(session_id)
    if entry is None:
        return None
    entry.session.audio_retained = retained
    if not retained:
        entry.session.audio_url = None
    return entry.session


# ---------------------------------------------------------------------------
# Profiles and skills
# ---------------------------------------------------------------------------


async def upsert_profile(
    session_id: UUID,
    *,
    experience_years: float | None,
    experience_context: str | None,
    education: list[str],
    certifications: list[str],
    location: str | None,
    work_preferences: list[str],
    uncertainty_flags: list[str],
) -> ProfileRow:
    if db.is_available():
        row = await db.fetchrow(
            "insert into extracted_profiles "
            "(session_id, experience_years, experience_context, education, "
            " certifications, location, work_preferences, uncertainty_flags) "
            "values ($1, $2, $3, $4, $5, $6, $7, $8) "
            "on conflict (session_id) do update set "
            "  experience_years = excluded.experience_years, "
            "  experience_context = excluded.experience_context, "
            "  education = excluded.education, "
            "  certifications = excluded.certifications, "
            "  location = excluded.location, "
            "  work_preferences = excluded.work_preferences, "
            "  uncertainty_flags = excluded.uncertainty_flags "
            "returning id, session_id, experience_years, experience_context, "
            "education, certifications, location, work_preferences, uncertainty_flags",
            session_id, experience_years, experience_context, education,
            certifications, location, work_preferences, uncertainty_flags,
        )
        return _profile_from_row(row)

    entry = _memory.get(session_id)
    if entry is None:
        raise ValueError(f"Unknown session {session_id}")
    profile = ProfileRow(
        id=entry.profile.id if entry.profile else uuid4(),
        session_id=session_id,
        experience_years=experience_years,
        experience_context=experience_context,
        education=list(education),
        certifications=list(certifications),
        location=location,
        work_preferences=list(work_preferences),
        uncertainty_flags=list(uncertainty_flags),
    )
    entry.profile = profile
    return profile


def _profile_from_row(row) -> ProfileRow:
    return ProfileRow(
        id=row["id"],
        session_id=row["session_id"],
        experience_years=float(row["experience_years"])
        if row["experience_years"] is not None else None,
        experience_context=row["experience_context"],
        education=list(row["education"] or []),
        certifications=list(row["certifications"] or []),
        location=row["location"],
        work_preferences=list(row["work_preferences"] or []),
        uncertainty_flags=list(row["uncertainty_flags"] or []),
    )


async def get_profile(session_id: UUID) -> ProfileRow | None:
    if db.is_available():
        row = await db.fetchrow(
            "select id, session_id, experience_years, experience_context, education, "
            "certifications, location, work_preferences, uncertainty_flags "
            "from extracted_profiles where session_id = $1",
            session_id,
        )
        return _profile_from_row(row) if row else None
    entry = _memory.get(session_id)
    return entry.profile if entry else None


async def replace_skills(
    profile_id: UUID, skills: list[NormalizedSkill], *, session_id: UUID | None = None
) -> list[SkillRow]:
    """Write the skill set for a profile, replacing whatever was there.

    Replacement rather than merge: the /understanding screen sends the full
    corrected list, and a merge would resurrect skills the user deleted.
    """
    if db.is_available():
        async with db.transaction() as conn:
            await conn.execute(
                "delete from extracted_skills where profile_id = $1", profile_id
            )
            rows = []
            for skill in skills:
                row = await conn.fetchrow(
                    "insert into extracted_skills "
                    "(profile_id, raw_name, evidence_phrase, normalized_skill_id, "
                    " match_confidence, needs_disambiguation, candidates, user_confirmed) "
                    "values ($1, $2, $3, $4, $5, $6, $7, $8) "
                    "returning id, profile_id, raw_name, evidence_phrase, "
                    "normalized_skill_id, match_confidence, needs_disambiguation, "
                    "candidates, user_confirmed",
                    profile_id,
                    skill.raw_name,
                    skill.evidence_phrase,
                    skill.skill_id,
                    skill.confidence,
                    skill.needs_disambiguation,
                    _candidates_json(skill),
                    skill.user_confirmed,
                )
                rows.append(row)
        out = [_skill_from_row(r) for r in rows]
        for stored, source in zip(out, skills):
            stored.embedding = source.embedding
        return out

    if session_id is None:
        raise ValueError("session_id is required for the in-memory backend")
    entry = _memory.get(session_id)
    if entry is None:
        raise ValueError(f"Unknown session {session_id}")
    entry.skills = [
        SkillRow(
            id=uuid4(),
            profile_id=profile_id,
            raw_name=s.raw_name,
            evidence_phrase=s.evidence_phrase,
            normalized_skill_id=s.skill_id,
            match_confidence=s.confidence,
            needs_disambiguation=s.needs_disambiguation,
            candidates=_candidates_json(s),
            user_confirmed=s.user_confirmed,
            embedding=s.embedding,
        )
        for s in skills
    ]
    return entry.skills


def _candidates_json(skill: NormalizedSkill) -> list[dict[str, Any]]:
    return [
        {
            "id": c.skill.id,
            "code": c.skill.code,
            "name": c.skill.name,
            "category": c.skill.category,
            "hint": c.skill.hint,
            "similarity": round(c.similarity, 4),
        }
        for c in skill.candidates
    ]


def _skill_from_row(row) -> SkillRow:
    return SkillRow(
        id=row["id"],
        profile_id=row["profile_id"],
        raw_name=row["raw_name"],
        evidence_phrase=row["evidence_phrase"],
        normalized_skill_id=row["normalized_skill_id"],
        match_confidence=float(row["match_confidence"])
        if row["match_confidence"] is not None else None,
        needs_disambiguation=row["needs_disambiguation"],
        candidates=list(row["candidates"] or []),
        user_confirmed=row["user_confirmed"],
    )


async def get_skills(session_id: UUID) -> list[SkillRow]:
    if db.is_available():
        rows = await db.fetch(
            "select s.id, s.profile_id, s.raw_name, s.evidence_phrase, "
            "s.normalized_skill_id, s.match_confidence, s.needs_disambiguation, "
            "s.candidates, s.user_confirmed "
            "from extracted_skills s "
            "join extracted_profiles p on p.id = s.profile_id "
            "where p.session_id = $1 "
            "order by s.created_at",
            session_id,
        )
        return [_skill_from_row(r) for r in rows]
    entry = _memory.get(session_id)
    return list(entry.skills) if entry else []


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------


async def replace_matches(
    session_id: UUID,
    matches: list[ScoredMatch],
    explanations: dict[int, Any] | None = None,
) -> list[MatchRow]:
    explanations = explanations or {}

    def _explanation(scheme_id: int) -> tuple[str | None, list[str]]:
        found = explanations.get(scheme_id)
        if found is None:
            return None, []
        return found.summary, list(found.bullets)

    if db.is_available():
        async with db.transaction() as conn:
            await conn.execute("delete from matches where session_id = $1", session_id)
            rows = []
            for match in matches:
                summary, bullets = _explanation(match.scheme.id)
                row = await conn.fetchrow(
                    "insert into matches "
                    "(session_id, scheme_id, skill_similarity_score, "
                    " experience_score, eligibility_score, location_score, "
                    " overall_score, rank, explanation_text, explanation_bullets) "
                    "values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) "
                    "returning id, session_id, scheme_id, skill_similarity_score, "
                    "experience_score, eligibility_score, location_score, "
                    "overall_score, rank, explanation_text, explanation_bullets",
                    session_id, match.scheme.id, match.skill_similarity_score,
                    match.experience_score, match.eligibility_score,
                    match.location_score, match.overall_score, match.rank,
                    summary, bullets,
                )
                rows.append(row)
        return [_match_from_row(r) for r in rows]

    entry = _memory.get(session_id)
    if entry is None:
        raise ValueError(f"Unknown session {session_id}")
    entry.matches = []
    for match in matches:
        summary, bullets = _explanation(match.scheme.id)
        entry.matches.append(
            MatchRow(
                id=uuid4(),
                session_id=session_id,
                scheme_id=match.scheme.id,
                skill_similarity_score=match.skill_similarity_score,
                experience_score=match.experience_score,
                eligibility_score=match.eligibility_score,
                location_score=match.location_score,
                overall_score=match.overall_score,
                rank=match.rank,
                explanation_text=summary,
                explanation_bullets=bullets,
            )
        )
    return entry.matches


def _match_from_row(row) -> MatchRow:
    return MatchRow(
        id=row["id"],
        session_id=row["session_id"],
        scheme_id=row["scheme_id"],
        skill_similarity_score=float(row["skill_similarity_score"]),
        experience_score=float(row["experience_score"]),
        eligibility_score=float(row["eligibility_score"]),
        location_score=float(row["location_score"]),
        overall_score=float(row["overall_score"]),
        rank=row["rank"],
        explanation_text=row["explanation_text"],
        explanation_bullets=list(row["explanation_bullets"] or []),
    )


async def get_matches(session_id: UUID) -> list[MatchRow]:
    if db.is_available():
        rows = await db.fetch(
            "select id, session_id, scheme_id, skill_similarity_score, "
            "experience_score, eligibility_score, location_score, overall_score, "
            "rank, explanation_text, explanation_bullets "
            "from matches where session_id = $1 order by rank",
            session_id,
        )
        return [_match_from_row(r) for r in rows]
    entry = _memory.get(session_id)
    return list(entry.matches) if entry else []


async def get_match(session_id: UUID, scheme_id: int) -> MatchRow | None:
    for match in await get_matches(session_id):
        if match.scheme_id == scheme_id:
            return match
    return None


# ---------------------------------------------------------------------------
# Assistant queries
# ---------------------------------------------------------------------------


async def log_assistant_query(
    session_id: UUID,
    *,
    scheme_id: int | None,
    question_text: str,
    answer_text: str,
    source_note: str | None,
) -> None:
    if db.is_available():
        await db.execute(
            "insert into assistant_queries "
            "(session_id, scheme_id, question_text, answer_text, source_note) "
            "values ($1, $2, $3, $4, $5)",
            session_id, scheme_id, question_text, answer_text, source_note,
        )
        return
    entry = _memory.get(session_id)
    if entry is None:
        return
    entry.questions.append(
        {
            "id": uuid4(),
            "scheme_id": scheme_id,
            "question_text": question_text,
            "answer_text": answer_text,
            "source_note": source_note,
            "created_at": _now(),
        }
    )


async def list_assistant_queries(session_id: UUID, limit: int = 20) -> list[dict[str, Any]]:
    if db.is_available():
        rows = await db.fetch(
            "select id, question_text, answer_text, source_note, scheme_id, "
            "created_at from assistant_queries where session_id = $1 "
            "order by created_at desc limit $2",
            session_id, limit,
        )
        return [dict(r) for r in rows]
    entry = _memory.get(session_id)
    if entry is None:
        return []
    return list(reversed(entry.questions))[:limit]
