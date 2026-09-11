"""Request and response models.

These are the contract the frontend types mirror in ``frontend/lib/types.ts``.
Field names are snake_case on the wire.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["ta", "hi", "en", "auto"]


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Speech
# ---------------------------------------------------------------------------


class TranscribeResponse(Base):
    session_id: UUID
    transcript: str
    language_detected: str
    provider: str
    # PRD section 7: state plainly whether the recording was kept.
    audio_retained: bool = False


class ClientTranscriptRequest(Base):
    """A transcript the browser produced on-device.

    Used when server-side STT is unavailable. The audio never leaves the
    device in this path, which is stricter than the default, not looser.
    """

    transcript: str = Field(min_length=1, max_length=20000)
    language_detected: str = "auto"
    session_id: UUID | None = None


class SynthesizeRequest(Base):
    text: str = Field(min_length=1, max_length=2000)
    language: Language = "en"


class SynthesizeResponse(Base):
    provider: str
    audio_base64: str | None
    speech_locale: str
    use_browser_tts: bool


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class ExtractRequest(Base):
    session_id: UUID | None = None
    # Optional: lets a caller extract from a transcript it already holds.
    transcript: str | None = None
    language: Language = "auto"


class ExtractedSkill(Base):
    id: UUID | None = None
    raw_name: str
    evidence_phrase: str
    normalized_skill_id: int | None = None
    normalized_code: str | None = None
    normalized_name: str | None = None
    display_names: dict[str, str] = Field(default_factory=dict)
    category: str | None = None
    match_confidence: float | None = None
    needs_disambiguation: bool = False
    candidates: list["SkillCandidate"] = Field(default_factory=list)
    user_confirmed: bool = False


class SkillCandidate(Base):
    id: int
    code: str
    name: str
    category: str
    hint: str | None = None
    similarity: float
    # {"en": ..., "ta": ..., "hi": ...}. The interface shows the reader's
    # language; `name` stays English so logs and admin views are stable.
    display_names: dict[str, str] = Field(default_factory=dict)


class ExtractedProfile(Base):
    id: UUID | None = None
    session_id: UUID | None = None
    experience_years: float | None = None
    experience_context: str | None = None
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    location: str | None = None
    work_preferences: list[str] = Field(default_factory=list)
    uncertainty_flags: list[str] = Field(default_factory=list)


class ExtractResponse(Base):
    session_id: UUID | None
    profile: ExtractedProfile
    skills: list[ExtractedSkill]
    provider: str
    # True when extraction ran without an LLM. The UI says so out loud.
    degraded: bool = False


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class SkillEdit(Base):
    """One user correction from the /understanding screen."""

    id: UUID | None = None
    raw_name: str
    evidence_phrase: str
    removed: bool = False
    # Set when the user picked an answer on the disambiguation screen.
    chosen_skill_id: int | None = None


class NormalizeRequest(Base):
    session_id: UUID | None = None
    skills: list[SkillEdit] | None = None


class NormalizeResponse(Base):
    session_id: UUID | None
    skills: list[ExtractedSkill]
    provider: str
    degraded: bool = False


# ---------------------------------------------------------------------------
# Schemes and matching
# ---------------------------------------------------------------------------


class SchemeSummary(Base):
    id: int
    title: str
    organization: str
    location: str
    district: str | None = None
    type: str
    minimum_experience: float
    certifications_required: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    nsqf_level: str | None = None
    source_reference: str | None = None
    # Where the government describes this scheme. A page a person can open,
    # as opposed to source_reference, which is a code to quote at an office.
    official_url: str | None = None


class SchemeDetail(SchemeSummary):
    description: str | None = None
    required_skills: list[SkillCandidate] = Field(default_factory=list)
    # Admin views only. Public listings filter on it, so a beneficiary
    # never sees a row where this is false.
    is_active: bool = True


class ScoreBreakdown(Base):
    skill_similarity_score: float
    experience_score: float
    eligibility_score: float
    location_score: float


class MatchResult(Base):
    scheme: SchemeSummary
    rank: int
    overall_score: float
    breakdown: ScoreBreakdown
    explanation_text: str | None = None
    explanation_bullets: list[str] = Field(default_factory=list)
    # Which of the user's skills carried the match, for the trust layer.
    matched_skill_codes: list[str] = Field(default_factory=list)


class MatchRequest(Base):
    session_id: UUID | None = None
    # Lets a caller match without a stored session (tests, admin previews).
    profile: ExtractedProfile | None = None
    skills: list[ExtractedSkill] | None = None
    limit: int | None = None
    explain: bool = True
    # The language to explain in. Absent, the session's detected language is
    # used -- but that is the language of the recording, not necessarily the
    # one the person is reading the page in.
    language: str | None = None


class MatchResponse(Base):
    session_id: UUID | None
    matches: list[MatchResult]
    explanation_provider: str
    degraded: bool = False


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------


class AssistantQueryRequest(Base):
    session_id: UUID | None = None
    scheme_id: int | None = None
    question_text: str = Field(min_length=1, max_length=1000)
    language: Language = "en"


class AssistantQueryResponse(Base):
    question_text: str
    answer_text: str
    source_note: str
    provider: str
    # True when the answer had to be "the data does not say".
    answered_from_data: bool = True


class AssistantQueryLog(Base):
    id: UUID
    question_text: str
    answer_text: str
    source_note: str | None
    scheme_id: int | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Session / passport
# ---------------------------------------------------------------------------


class AudioRetentionRequest(Base):
    audio_retained: bool


class SessionSummary(Base):
    id: UUID
    created_at: datetime
    language_detected: str | None
    transcript: str | None
    audio_retained: bool
    audio_url: str | None


class PassportResponse(Base):
    session: SessionSummary
    profile: ExtractedProfile | None
    skills: list[ExtractedSkill]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(Base):
    status: Literal["ok", "degraded"]
    providers: dict[str, str]
    degraded: list[str]
    database: dict[str, object]


ExtractedSkill.model_rebuild()
