"""Request and response models.

These are the contract the frontend types mirror in ``frontend/lib/types.ts``.
Field names are snake_case on the wire.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    """A transcript that did not come from server-side speech recognition.

    Two ways in: the browser recognised the speech on-device when server-side
    STT was unavailable, or the person typed it. Either way no audio exists to
    send, which is stricter than the default path rather than looser.

    Typed text joins the pipeline here deliberately. Extraction, the evidence
    check, normalisation and matching then run identically, so a typed sentence
    is held to the same rule as a spoken one: nothing may be attributed to
    someone that they did not say.
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
    # Whether this fits the work the person described, as opposed to merely
    # not excluding them. A scheme declaring no skills cannot be ruled out,
    # which is not the same as fitting. Defaults false so a stored match read
    # back from before this existed is not claimed as a fit.
    skill_evidence: bool = False


class ExperienceUpdateRequest(Base):
    """Years of work, as the person corrects them on /understanding."""

    session_id: UUID
    # Null clears it -- "I did not say" is a correction too. The same bound
    # extraction applies to a number the model reads from speech.
    experience_years: float | None = Field(default=None, ge=0, le=70)


class AddSkillRequest(Base):
    """Text someone typed on the understanding screen."""

    session_id: UUID
    text: str = Field(min_length=1, max_length=300)
    language: str = "auto"


class AddSkillResponse(Base):
    """What that text turned out to be.

    Three outcomes rather than two, because a question is neither work nor
    nonsense. Refusing "who is eligible for PM-AJAY" for not being a trade
    would be wrong, so it is handed back for the assistant to answer.
    """

    accepted: bool
    kind: Literal["work", "question", "neither"]
    # The full stored list when work was found, so the screen can replace what
    # it holds rather than merge and risk duplicating.
    skills: list[ExtractedSkill] = Field(default_factory=list)
    # Present when the text was a question, in the person's own words.
    question: str | None = None
    provider: str = "offline"
    # The text said someone is in danger. kind is "question" and question is
    # the text, so the screen asks the assistant, which answers with 112.
    urgent: bool = False


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


class QueryUnderstandRequest(Base):
    text: str
    language: str = "en"


class QueryUnderstandResponse(Base):
    """What the person was doing, so the caller knows which step to run.

    Both flags can be true. "I do welding, is there a scheme for that?" needs
    skills extracted and the question answered, and treating it as one or the
    other drops half of what they said.
    """

    describes_work: bool
    asks_question: bool
    # Their words, never a rephrasing. Null when they asked nothing.
    question: str | None = None
    provider: str
    # Someone is in danger, said in so many words. Decided by fixed patterns
    # (app/services/safety.py), not the classifier, so it holds when the LLM
    # is down. The caller then asks the assistant, which answers with 112.
    urgent: bool = False


class AssistantQueryResponse(Base):
    question_text: str
    answer_text: str
    source_note: str
    provider: str
    # True when the answer had to be "the data does not say".
    answered_from_data: bool = True
    # Present only when the answer came from a scheme document. Each entry
    # names the document and the passage, so the claim can be checked against
    # the government's own text rather than taken on the system's word.
    citations: list[dict] = Field(default_factory=list)
    # The question said someone is in danger. answer_text is then the
    # emergency numbers (112, 181, 1098, 14416) and nothing else, and the
    # screen shows it first, with numbers that can be tapped to call.
    urgent: bool = False


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
    # {"status": "ok" | "offline" | why it is not answering, "since", "until"}.
    # "llm" is in `degraded` both when it is offline by configuration and
    # while it is not answering; this says which, and until when.
    llm: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Nearby (the map)
# ---------------------------------------------------------------------------

NearbyCategory = Literal["training", "employment", "government", "bank"]
NEARBY_CATEGORIES: tuple[str, ...] = ("training", "employment", "government", "bank")


class NearbyRequest(Base):
    """Where to look, and for what.

    A device location wins over a spoken place when both are sent. It is
    rounded to about a kilometre before it is used for anything, and it is
    never stored: this request writes nothing.
    """

    place: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _both_coordinates_or_neither(self) -> "NearbyRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Send both latitude and longitude, or neither.")
        return self


class NearbyCentre(Base):
    latitude: float
    longitude: float
    # gps: the device said; place: a town we recognised; default: we do not
    # know where the person is, so this is where the openings are.
    source: Literal["gps", "place", "default"]
    key: str | None = None
    names: dict[str, str] = Field(default_factory=dict)


class NearbySchemeRef(Base):
    id: int
    title: str
    organization: str
    type: str


class NearbySchemePlace(Base):
    """Every opening in one town, pinned at the town centre.

    Grouped because the record knows the town and nothing finer: eleven
    pins stacked on one point would look like eleven addresses.
    """

    key: str
    names: dict[str, str]
    latitude: float
    longitude: float
    distance_km: float
    approximate: bool = True
    schemes: list[NearbySchemeRef]


class SupportPlace(Base):
    """An office from OpenStreetMap. Passed through, never invented."""

    id: str
    category: NearbyCategory
    name: str
    names: dict[str, str] = Field(default_factory=dict)
    latitude: float
    longitude: float
    distance_km: float
    address: str | None = None
    opening_hours: str | None = None
    osm_url: str


class NearbyResponse(Base):
    """The openings half of the map. Answered from the catalogue alone.

    Offices are a separate request (``SupportRequest``) because they come from
    a volunteer server that can take tens of seconds; the openings should not
    wait on it.
    """

    centre: NearbyCentre
    scheme_places: list[NearbySchemePlace]
    # Openings whose town is not on the map yet. Listed, not dropped: a
    # scheme missing from the map is still a scheme.
    unplaced_schemes: list[NearbySchemeRef] = Field(default_factory=list)


class SupportRequest(Base):
    """Offices around a point. Coarsened to about a kilometre before use."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=10, ge=1, le=25)
    categories: list[NearbyCategory] = Field(
        default_factory=lambda: list(NEARBY_CATEGORIES)
    )


class SupportResponse(Base):
    support_places: list[SupportPlace]
    # ok: looked, and this is what is there (possibly nothing).
    # unavailable: could not look just now. offline: live lookups are off
    # here and the bundled snapshot does not cover this search.
    support_status: Literal["ok", "unavailable", "offline"]
    # Where an ok answer came from: the bundled snapshot or a live query.
    source: Literal["snapshot", "live"] | None = None
    # The day the snapshot was fetched (ISO date), when it answered.
    as_of: str | None = None
    radius_km: float
    provider: str
    degraded: bool
    attribution: str


class KnownPlace(Base):
    key: str
    district: str
    names: dict[str, str]
    latitude: float
    longitude: float


ExtractedSkill.model_rebuild()
