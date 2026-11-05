"""Persistence for sessions, profiles, skills, matches and questions.

Two backends behind one interface: Postgres when ``DATABASE_URL`` is set, and a
process-local dict when it is not. The in-memory backend exists so the pipeline
is runnable and testable without Supabase; it is bounded and evicts oldest-first
so a long-running dev server cannot grow without limit.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterator
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
    # The session's secret, in the clear, on the row create_session returns
    # and nowhere else: it is handed to the person once and never stored.
    issued_key: str | None = None
    # Its SHA-256, for the in-memory store (the database keeps its own).
    key_hash: str | None = None


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
    # Which language the prose above is in. None means unknown -- a row
    # written before the column existed -- and reads as "rewrite it".
    explanation_language: str | None = None


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
    _touch_memory()
    _memory[entry.session.id] = entry
    _memory.move_to_end(entry.session.id)
    while len(_memory) > MEMORY_SESSION_LIMIT:
        _memory.popitem(last=False)


def _memory_get(session_id: UUID) -> _MemorySession | None:
    _touch_memory()
    return _memory.get(session_id)


def reset_memory() -> None:
    global _last_memory_activity
    _memory.clear()
    _retired.clear()
    _last_memory_activity = None


# ---------------------------------------------------------------------------
# Handing over to the database after an outage
# ---------------------------------------------------------------------------
#
# When the database comes back (db.reconnect_in_background), the API switches
# to it -- but only once nobody is mid-flow on the in-memory store. A session
# started during the outage cannot be carried across: its skill and scheme ids
# are the in-memory catalogue's, which are not the database's, so continuing
# it against the database would match the wrong rows. It is retired instead,
# and a request for it is told plainly that it was not saved.

# Monotonic time of the last read or write of an in-memory session.
_last_memory_activity: float | None = None
# Sessions that lived in memory until the switch.
_retired: set[UUID] = set()

RETIRED_SESSION_MESSAGE = (
    "This session was started while VoicePath's database was down, so it was not "
    "saved. Please start again from the beginning."
)


def _touch_memory() -> None:
    global _last_memory_activity
    _last_memory_activity = time.monotonic()


def memory_quiet(idle_seconds: float) -> bool:
    """True when no in-memory session has been used for ``idle_seconds``."""
    if not _memory or _last_memory_activity is None:
        return True
    return time.monotonic() - _last_memory_activity >= idle_seconds


def retire_memory_sessions() -> int:
    """Forget the in-memory sessions, remembering only that they existed."""
    _retired.update(_memory.keys())
    count = len(_memory)
    _memory.clear()
    return count


def missing_session(session_id: UUID | str | None) -> tuple[int, str]:
    """Status and message for a session id that was not found."""
    try:
        key = session_id if isinstance(session_id, UUID) else UUID(str(session_id))
    except (TypeError, ValueError):
        key = None
    if key is not None and key in _retired:
        return 410, RETIRED_SESSION_MESSAGE
    return 404, "That session was not found."


# ---------------------------------------------------------------------------
# Session keys
# ---------------------------------------------------------------------------
#
# Until 2026-11-05 a session's id was all it took to read or change it, and
# the id is in request paths (/api/sessions/{id}) -- so in access logs, and in
# anything else that records a URL. Now each session also has a secret key:
# 256 random bits, handed to the person once when the session is created, sent
# back only in the X-VoicePath-Session-Key header, and stored only as its
# SHA-256. Every function below that reads or writes one session's data checks
# it first, so no route can forget to. A missing or wrong key is
# indistinguishable from a session that does not exist; a session from before
# keys existed (no hash) is refused with a plain "start again" -- decided
# 2026-11-05.
#
# The key a request presents is put in a context variable by
# security.SessionKeyMiddleware, with a per-request cache so a route that
# touches a session five times checks it once.

SESSION_KEY_HEADER = "x-voicepath-session-key"

_presented_key: ContextVar[str | None] = ContextVar("vp_session_key", default=None)
_verified: ContextVar[set[UUID] | None] = ContextVar("vp_session_verified", default=None)

UNKEYED_SESSION_MESSAGE = (
    "This session was started before a security update, so it can no longer be "
    "opened. Please start again from the beginning."
)


class SessionAccessDenied(Exception):
    """Raised by the per-session functions; main.py turns it into a response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def new_session_key() -> tuple[str, str]:
    """A fresh key and the hash to store for it."""
    key = secrets.token_urlsafe(32)
    return key, _key_hash(key)


@contextmanager
def presenting(key: str | None) -> Iterator[None]:
    """Act as the holder of ``key`` for the duration (middleware, and tests)."""
    key_token = _presented_key.set(key)
    cache_token = _verified.set(set())
    try:
        yield
    finally:
        _presented_key.reset(key_token)
        _verified.reset(cache_token)


def _mark_verified(session_id: UUID) -> None:
    cache = _verified.get()
    if cache is None:
        cache = set()
        _verified.set(cache)
    cache.add(session_id)


async def _stored_key_hash(session_id: UUID) -> tuple[bool, str | None]:
    """(exists, key_hash) without touching anything else of the session."""
    if db.is_available():
        row = await db.fetchrow("select key_hash from sessions where id = $1", session_id)
        return (row is not None, row["key_hash"] if row else None)
    entry = _memory.get(session_id)
    return (entry is not None, entry.session.key_hash if entry else None)


async def _require_key(session_id: UUID | None) -> None:
    """Refuse unless the request holds this session's key.

    A session that does not exist passes through, so the caller's own
    "not found" (or "retired after an outage") answer stands.
    """
    if session_id is None:
        return
    cache = _verified.get()
    if cache is not None and session_id in cache:
        return
    exists, stored = await _stored_key_hash(session_id)
    if not exists:
        return
    if stored is None:
        raise SessionAccessDenied(410, UNKEYED_SESSION_MESSAGE)
    presented = _presented_key.get()
    if not presented or not hmac.compare_digest(_key_hash(presented), stored):
        raise SessionAccessDenied(404, "That session was not found.")
    _mark_verified(session_id)


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

    key, key_hash = new_session_key()
    if db.is_available():
        row = await db.fetchrow(
            "insert into sessions "
            "(transcript, language_detected, stt_provider, audio_retained, audio_url, key_hash) "
            "values ($1, $2, $3, $4, $5, $6) "
            "returning id, created_at, language_detected, transcript, "
            "audio_retained, audio_url, stt_provider",
            transcript, language_detected, stt_provider, audio_retained, audio_url, key_hash,
        )
        session = _session_from_row(row)
    else:
        session = SessionRow(
            id=uuid4(),
            created_at=_now(),
            language_detected=language_detected,
            transcript=transcript,
            audio_retained=audio_retained,
            audio_url=audio_url,
            stt_provider=stt_provider,
            key_hash=key_hash,
        )
        _remember(_MemorySession(session=session))
    # The request that made it may go on using it before the person has
    # the key to send back (extract creates and then fills a session).
    _mark_verified(session.id)
    # A copy: the stored row (in memory, the very object kept) holds the hash
    # only, never the key.
    return replace(session, issued_key=key)


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
    await _require_key(session_id)
    if db.is_available():
        row = await db.fetchrow(
            "select id, created_at, language_detected, transcript, audio_retained, "
            "audio_url, stt_provider from sessions where id = $1",
            session_id,
        )
        return _session_from_row(row) if row else None
    entry = _memory_get(session_id)
    return entry.session if entry else None


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
    await _require_key(session_id)
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

    entry = _memory_get(session_id)
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
    await _require_key(session_id)
    if db.is_available():
        row = await db.fetchrow(
            "select id, session_id, experience_years, experience_context, education, "
            "certifications, location, work_preferences, uncertainty_flags "
            "from extracted_profiles where session_id = $1",
            session_id,
        )
        return _profile_from_row(row) if row else None
    entry = _memory_get(session_id)
    return entry.profile if entry else None


async def replace_skills(
    profile_id: UUID, skills: list[NormalizedSkill], *, session_id: UUID | None = None
) -> list[SkillRow]:
    """Write the skill set for a profile, replacing whatever was there.

    Replacement rather than merge: the /understanding screen sends the full
    corrected list, and a merge would resurrect skills the user deleted.
    """
    await _require_key(session_id)
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
    entry = _memory_get(session_id)
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
    await _require_key(session_id)
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
    entry = _memory_get(session_id)
    return list(entry.skills) if entry else []


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------


async def replace_matches(
    session_id: UUID,
    matches: list[ScoredMatch],
    explanations: dict[int, Any] | None = None,
    language: str | None = None,
) -> list[MatchRow]:
    """Persist a ranking, recording which language it was explained in.

    ``language`` is stored so a later read can tell whether the prose is
    the one the reader wants, instead of serving whatever was written
    first and hoping.
    """
    await _require_key(session_id)
    explanations = explanations or {}
    stored_language = (language or "").split("-")[0] or None

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
                    " overall_score, rank, explanation_text, explanation_bullets, "
                    " explanation_language) "
                    "values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) "
                    "returning id, session_id, scheme_id, skill_similarity_score, "
                    "experience_score, eligibility_score, location_score, "
                    "overall_score, rank, explanation_text, explanation_bullets, "
                    "explanation_language",
                    session_id, match.scheme.id, match.skill_similarity_score,
                    match.experience_score, match.eligibility_score,
                    match.location_score, match.overall_score, match.rank,
                    summary, bullets, stored_language,
                )
                rows.append(row)
        return [_match_from_row(r) for r in rows]

    entry = _memory_get(session_id)
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
                explanation_language=stored_language,
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
        explanation_language=row["explanation_language"],
    )


# ---------------------------------------------------------------------------
# Admin overview (spec section 18)
# ---------------------------------------------------------------------------

_POPULAR_LIMIT = 10


async def overview() -> dict[str, Any]:
    """Aggregate counts for the admin dashboard.

    Two rules shape what is counted, both inherited from `/admin/sessions`,
    which shows activity without showing what anyone said:

    * **Skills are counted by their taxonomy name, never by `raw_name`.** A
      raw name is the person's own words. An aggregate is not a loophole for
      the transcript rule, so a skill that never normalized is left out rather
      than reported in the phrasing someone used about their own life.
    * **Question text is never touched.** Questions are counted, not sampled.

    Works from either store, because the admin surface is reachable in offline
    mode and a dashboard that 503s there would be worse than one showing zeros.
    """
    if db.is_available():
        return await _overview_sql()
    return await _overview_memory()


async def _overview_sql() -> dict[str, Any]:
    schemes = await db.fetchrow(
        "select count(*) as total, "
        "       count(*) filter (where is_active) as active "
        "from schemes"
    )
    by_type = await db.fetch(
        "select type, count(*) as count from schemes "
        "where is_active group by type order by count desc, type"
    )
    sessions = await db.fetchrow(
        "select count(*) as total, "
        "       count(*) filter (where created_at >= date_trunc('day', now())) as today "
        "from sessions"
    )
    by_language = await db.fetch(
        "select coalesce(language_detected, 'unknown') as language, count(*) as count "
        "from sessions group by 1 order by count desc, language"
    )
    questions = await db.fetchrow(
        "select count(*) as total, "
        "       count(*) filter (where created_at >= date_trunc('day', now())) as today "
        "from assistant_queries"
    )
    corpus = await db.fetchrow(
        "select (select count(*) from scheme_documents) as documents, "
        "       (select count(*) from document_chunks) as chunks"
    )
    skills = await db.fetch(
        "select t.name, t.code, count(*) as count "
        "from extracted_skills e join skill_taxonomy t on t.id = e.normalized_skill_id "
        "where e.normalized_skill_id is not null "
        "group by t.name, t.code order by count desc, t.name limit $1",
        _POPULAR_LIMIT,
    )
    locations = await db.fetch(
        "select location as name, count(*) as count from extracted_profiles "
        "where location is not null and btrim(location) <> '' "
        "group by location order by count desc, location limit $1",
        _POPULAR_LIMIT,
    )

    total = int(schemes["total"])
    active = int(schemes["active"])
    return {
        "schemes": {
            "total": total,
            "active": active,
            "inactive": total - active,
            "by_type": [
                {"type": r["type"], "count": int(r["count"])} for r in by_type
            ],
        },
        "sessions": {
            "total": int(sessions["total"]),
            "today": int(sessions["today"]),
            "questions": int(questions["total"]),
            "questions_today": int(questions["today"]),
            "by_language": [
                {"language": r["language"], "count": int(r["count"])}
                for r in by_language
            ],
        },
        "corpus": {
            "documents": int(corpus["documents"]),
            "chunks": int(corpus["chunks"]),
        },
        "popular": {
            "skills": [
                {"name": r["name"], "code": r["code"], "count": int(r["count"])}
                for r in skills
            ],
            "locations": [
                {"name": r["name"], "count": int(r["count"])} for r in locations
            ],
        },
    }


async def _overview_memory() -> dict[str, Any]:
    # Imported here: schemes imports this module for its own catalogue work,
    # and at module scope the two would not finish importing each other.
    from app.services import schemes as schemes_service, taxonomy

    catalogue = await schemes_service.list_active()
    by_type: dict[str, int] = {}
    for scheme in catalogue:
        by_type[scheme.type] = by_type.get(scheme.type, 0) + 1

    start_of_day = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    entries = list(_memory.values())

    languages: dict[str, int] = {}
    locations: dict[str, int] = {}
    skill_ids: dict[int, int] = {}
    questions = 0
    questions_today = 0

    for entry in entries:
        language = entry.session.language_detected or "unknown"
        languages[language] = languages.get(language, 0) + 1

        place = (entry.profile.location or "").strip() if entry.profile else ""
        if place:
            locations[place] = locations.get(place, 0) + 1

        for skill in entry.skills:
            if skill.normalized_skill_id is not None:
                skill_ids[skill.normalized_skill_id] = (
                    skill_ids.get(skill.normalized_skill_id, 0) + 1
                )

        for question in entry.questions:
            questions += 1
            asked = question.get("created_at")
            if isinstance(asked, datetime) and asked >= start_of_day:
                questions_today += 1

    named = await taxonomy.get_by_ids(list(skill_ids))
    skills = [
        {
            "name": named[skill_id].name,
            "code": named[skill_id].code,
            "count": count,
        }
        for skill_id, count in skill_ids.items()
        if skill_id in named
    ]
    skills.sort(key=lambda s: (-s["count"], s["name"]))

    ranked_locations = sorted(
        ({"name": name, "count": count} for name, count in locations.items()),
        key=lambda entry: (-entry["count"], entry["name"]),
    )

    return {
        "schemes": {
            "total": len(catalogue),
            "active": len(catalogue),
            # The in-memory catalogue holds no deactivated rows to count.
            "inactive": 0,
            "by_type": sorted(
                ({"type": name, "count": count} for name, count in by_type.items()),
                key=lambda entry: (-entry["count"], entry["type"]),
            ),
        },
        "sessions": {
            "total": len(entries),
            "today": sum(1 for e in entries if e.session.created_at >= start_of_day),
            "questions": questions,
            "questions_today": questions_today,
            "by_language": sorted(
                ({"language": name, "count": count} for name, count in languages.items()),
                key=lambda entry: (-entry["count"], entry["language"]),
            ),
        },
        "corpus": {"documents": 0, "chunks": 0},
        "popular": {
            "skills": skills[:_POPULAR_LIMIT],
            "locations": ranked_locations[:_POPULAR_LIMIT],
        },
    }


async def get_matches(session_id: UUID) -> list[MatchRow]:
    await _require_key(session_id)
    if db.is_available():
        rows = await db.fetch(
            "select id, session_id, scheme_id, skill_similarity_score, "
            "experience_score, eligibility_score, location_score, overall_score, "
            "rank, explanation_text, explanation_bullets, explanation_language "
            "from matches where session_id = $1 order by rank",
            session_id,
        )
        return [_match_from_row(r) for r in rows]
    entry = _memory_get(session_id)
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
    await _require_key(session_id)
    if db.is_available():
        await db.execute(
            "insert into assistant_queries "
            "(session_id, scheme_id, question_text, answer_text, source_note) "
            "values ($1, $2, $3, $4, $5)",
            session_id, scheme_id, question_text, answer_text, source_note,
        )
        return
    entry = _memory_get(session_id)
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
    await _require_key(session_id)
    if db.is_available():
        rows = await db.fetch(
            "select id, question_text, answer_text, source_note, scheme_id, "
            "created_at from assistant_queries where session_id = $1 "
            "order by created_at desc limit $2",
            session_id, limit,
        )
        return [dict(r) for r in rows]
    entry = _memory_get(session_id)
    if entry is None:
        return []
    return list(reversed(entry.questions))[:limit]
