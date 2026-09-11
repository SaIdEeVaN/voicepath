"""Deterministic matching and ranking (PRD sections 4.4 and 8).

    Skill similarity   50%
    Experience match   25%
    Eligibility        15%
    Location           10%

No language model is involved anywhere in this file. The same profile against
the same catalogue produces the same ranking every time, and the numbers are
reproducible from the stored ``matches`` row. That property is what lets the
explanation layer be constrained to describing a result instead of producing
one -- if ranking could drift, "the LLM must not re-rank" would be unenforceable.

Every component returns a fraction in [0, 1], so ``overall_score`` is directly
the percentage the interface shows.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app.config import get_settings
from app.services.embeddings import cosine_similarity
from app.services.normalization import NormalizedSkill
from app.services.schemes import Scheme

logger = logging.getLogger(__name__)


@dataclass
class ProfileInput:
    """Everything the scorer is allowed to know about the person."""

    experience_years: float | None = None
    location: str | None = None
    district: str | None = None
    certifications: list[str] = field(default_factory=list)
    skills: list[NormalizedSkill] = field(default_factory=list)


@dataclass
class ScoredMatch:
    scheme: Scheme
    skill_similarity_score: float
    experience_score: float
    eligibility_score: float
    location_score: float
    overall_score: float
    rank: int = 0
    matched_skill_codes: list[str] = field(default_factory=list)
    # Facts the explanation layer is permitted to draw on. Nothing else.
    grounding: dict[str, object] = field(default_factory=dict)


# Which district a town sits in. People say the name of their town -- "Attur",
# "Mettur" -- not the district it administers under, and without this a person
# in Attur looks as far from a Salem opening as someone in Kolkata does.
#
# Seeded with the towns the catalogue mentions, then extended at runtime by
# learn_town_districts() from the catalogue itself, so adding a scheme in
# a new town teaches the scorer that town without a code change.
TOWN_DISTRICT: dict[str, str] = {
    "attur": "salem",
    "mettur": "salem",
    "omalur": "salem",
    "sankagiri": "salem",
    "edappadi": "salem",
    "gobichettipalayam": "erode",
    "bhavani": "erode",
    "perundurai": "erode",
    "sathyamangalam": "erode",
    "rasipuram": "namakkal",
    "tiruchengode": "namakkal",
}


def learn_town_districts(catalogue: list[Scheme]) -> None:
    """Teach the scorer the town/district pairs the catalogue already knows.

    Idempotent, and it never overwrites an existing entry -- the static table
    above wins, so a bad row cannot quietly move a town into another district.
    """
    for scheme in catalogue:
        town = canonical_place(scheme.location)
        district = canonical_place(scheme.district)
        if town and district and town != district:
            TOWN_DISTRICT.setdefault(town, district)


# Districts that people commute between in the seeded region. Extend as the
# catalogue grows; an unlisted pair simply scores as "different district",
# which is a conservative answer rather than a wrong one.
ADJACENT_DISTRICTS: dict[str, set[str]] = {
    "salem": {"erode", "namakkal", "dharmapuri", "krishnagiri"},
    "erode": {"salem", "namakkal", "tiruppur", "karur"},
    "namakkal": {"salem", "erode", "karur", "tiruchirappalli"},
    "dharmapuri": {"salem", "krishnagiri"},
    "krishnagiri": {"salem", "dharmapuri"},
    "tiruppur": {"erode", "coimbatore"},
    "coimbatore": {"tiruppur"},
    "karur": {"erode", "namakkal", "tiruchirappalli"},
    "tiruchirappalli": {"karur", "namakkal"},
}

# Scores for the location term. Named so the intent survives tuning.
LOCATION_SAME_PLACE = 1.0
LOCATION_SAME_DISTRICT = 0.85
LOCATION_ADJACENT_DISTRICT = 0.45
LOCATION_UNKNOWN = 0.5
LOCATION_ELSEWHERE = 0.2

# What to score when the person never said how long they have worked. Neither
# credited nor penalised: the profile carries an uncertainty flag and the
# interface asks. Scoring 0 would bury people who simply did not mention it.
EXPERIENCE_UNKNOWN = 0.5


def _norm(value: str | None) -> str:
    return unicodedata.normalize("NFKC", (value or "")).strip().casefold()


# Place names as people actually say them.
#
# Extraction returns the person's own words, so a Tamil speaker's location
# arrives as "சேலத்துல" -- Salem, in the locative case -- while the catalogue
# says "Salem". Comparing those as strings scores a person standing in Salem as
# being nowhere near it, and the explanation layer then tells them so.
#
# Each canonical key lists the forms and inflected stems that mean it. Matching
# is prefix-based in both directions, which absorbs the case endings Tamil and
# Hindi attach to place names without needing a morphological analyser.
PLACE_ALIASES: dict[str, tuple[str, ...]] = {
    "salem": ("salem", "சேலம", "சேலத", "सेलम", "सलेम"),
    "erode": ("erode", "ஈரோடு", "ஈரோட", "इरोड", "इरोडु"),
    "attur": ("attur", "ஆத்தூர", "आत्तूर"),
    "mettur": ("mettur", "மேட்டூர", "मेट्टूर"),
    "omalur": ("omalur", "ஓமலூர", "ओमलूर"),
    "sankagiri": ("sankagiri", "சங்ககிரி", "संकगिरि"),
    "edappadi": ("edappadi", "இடப்பாடி", "एडप्पाडी"),
    "namakkal": ("namakkal", "நாமக்கல", "नामक्कल"),
    "dharmapuri": ("dharmapuri", "தர்மபுரி", "धर्मपुरी"),
    "krishnagiri": ("krishnagiri", "கிருஷ்ணகிரி", "कृष्णगिरि"),
    "tiruppur": ("tiruppur", "tirupur", "திருப்பூர", "तिरुप्पूर"),
    "coimbatore": ("coimbatore", "கோயம்புத்தூர", "கோவை", "कोयंबटूर"),
    "karur": ("karur", "கரூர", "करूर"),
    "tiruchirappalli": ("tiruchirappalli", "trichy", "திருச்சி", "तिरुचि"),
    "chennai": ("chennai", "சென்னை", "चेन्नई"),
    "madurai": ("madurai", "மதுரை", "मदुरै"),
    "bhavani": ("bhavani", "பவானி", "भवानी"),
    "perundurai": ("perundurai", "பெருந்துறை", "पेरुंदुरै"),
    "gobichettipalayam": ("gobichettipalayam", "gobi", "கோபி", "गोबी"),
    "sathyamangalam": ("sathyamangalam", "சத்தியமங்கலம", "सत्यमंगलम"),
    "rasipuram": ("rasipuram", "ராசிபுரம", "रासीपुरम"),
    "tiruchengode": ("tiruchengode", "திருச்செங்கோடு", "तिरुचेंगोड"),
}

# Below this, a shared prefix is coincidence rather than the same place.
_MIN_PLACE_PREFIX = 4


def canonical_place(value: str | None) -> str:
    """Resolve a spoken place name to a canonical key.

    Returns the folded input unchanged when nothing matches, so an unknown
    town still compares equal to itself and simply scores as "somewhere else".
    """
    folded = _norm(value)
    if not folded:
        return ""
    # Strip anything after a separator: "Salem, Tamil Nadu" -> "Salem".
    head = re.split(r"[,;/(]", folded)[0].strip()
    if not head:
        head = folded

    for canonical, aliases in PLACE_ALIASES.items():
        for alias in aliases:
            if head == alias:
                return canonical
            # Prefix in either direction absorbs case endings ("சேலத்துல"
            # begins with "சேலத") and truncations alike.
            shorter = min(len(head), len(alias))
            if shorter >= _MIN_PLACE_PREFIX and (
                head.startswith(alias) or alias.startswith(head)
            ):
                return canonical
    return head


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


def skill_similarity(profile: ProfileInput, scheme: Scheme) -> tuple[float, list[str]]:
    """How well the person's skills cover what this scheme asks for.

    Coverage of the requirement, not of the person: someone with twenty skills
    is not a better fit for a welding job than someone with one, if that one is
    welding. Each required skill contributes its best evidence from the person's
    set, weighted by how central it is to the role.

    An exact taxonomy-id match scores 1.0. Otherwise the cosine similarity
    between the required skill and the person's nearest skill carries it, which
    is what lets "Four-Wheeler Repair" earn partial credit from a two-wheeler
    mechanic without either being hand-coded as related.
    """
    required = scheme.required_skills
    if not required:
        # Nothing asked for cannot be unmet. Rare in practice.
        return 1.0, []

    owned_ids = {s.skill_id for s in profile.skills if s.skill_id is not None}
    owned_vectors = [
        (s.code, s.embedding)
        for s in profile.skills
        if s.embedding
    ]

    total_weight = 0.0
    earned = 0.0
    matched: list[str] = []

    for requirement in required:
        weight = max(requirement.weight, 0.0)
        if weight == 0.0:
            continue
        total_weight += weight

        if requirement.skill_id in owned_ids:
            earned += weight
            matched.append(requirement.code)
            continue

        if not requirement.embedding:
            continue

        best = 0.0
        best_code: str | None = None
        for code, vector in owned_vectors:
            similarity = cosine_similarity(requirement.embedding, vector)
            if similarity > best:
                best = similarity
                best_code = code

        # Below this, the resemblance is noise rather than transferable skill.
        if best >= 0.55:
            earned += weight * best
            if best_code and best >= 0.7:
                matched.append(requirement.code)

    if total_weight == 0.0:
        return 0.0, []
    return round(min(1.0, earned / total_weight), 4), matched


def experience_score(profile: ProfileInput, scheme: Scheme) -> float:
    """Stated experience against the minimum asked for.

    Meeting the minimum is full marks -- exceeding it is not extra credit,
    because the scheme does not ask for more. Falling short scales down
    proportionally rather than disqualifying, so a person one year short still
    sees the opening.
    """
    minimum = float(scheme.minimum_experience or 0)
    if minimum <= 0:
        return 1.0
    if profile.experience_years is None:
        return EXPERIENCE_UNKNOWN
    years = max(0.0, float(profile.experience_years))
    if years >= minimum:
        return 1.0
    return round(years / minimum, 4)


def eligibility_score(profile: ProfileInput, scheme: Scheme) -> float:
    """Fraction of the listed hard requirements the person demonstrably meets.

    Only certificates the person actually stated count. An unstated certificate
    is not assumed present -- that is the section 7 rule applied to scoring.
    """
    required = [c for c in (scheme.certifications_required or []) if c]
    if not required:
        return 1.0

    held = {_norm(c) for c in profile.certifications}
    if not held:
        return 0.0

    met = 0
    for requirement in required:
        needle = _norm(requirement)
        if any(needle in h or h in needle for h in held):
            met += 1
    return round(met / len(required), 4)


def _district_of(place: str) -> str:
    """Resolve a place name to its district, or return it unchanged."""
    return TOWN_DISTRICT.get(place, place)


def location_score(profile: ProfileInput, scheme: Scheme) -> float:
    """Distance, in the only terms the data supports: place and district.

    Both sides go through `canonical_place` first, so the person's own words --
    in whatever script and case they said them -- reach the same key as the
    catalogue's English spelling. Then through the town/district table, so
    someone in Attur is understood to be in Salem district.
    """
    person_place = canonical_place(profile.location)
    if not person_place and not canonical_place(profile.district):
        return LOCATION_UNKNOWN

    person_district = _district_of(canonical_place(profile.district) or person_place)
    opp_place = canonical_place(scheme.location)
    opp_district = _district_of(canonical_place(scheme.district) or opp_place)

    if person_place and opp_place and person_place == opp_place:
        return LOCATION_SAME_PLACE
    if person_district and opp_district and person_district == opp_district:
        return LOCATION_SAME_DISTRICT
    if opp_district in ADJACENT_DISTRICTS.get(person_district, set()):
        return LOCATION_ADJACENT_DISTRICT
    return LOCATION_ELSEWHERE


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def score_one(profile: ProfileInput, scheme: Scheme) -> ScoredMatch:
    settings = get_settings()

    skill, matched = skill_similarity(profile, scheme)
    experience = experience_score(profile, scheme)
    eligibility = eligibility_score(profile, scheme)
    location = location_score(profile, scheme)

    overall = (
        skill * settings.weight_skill
        + experience * settings.weight_experience
        + eligibility * settings.weight_eligibility
        + location * settings.weight_location
    )

    return ScoredMatch(
        scheme=scheme,
        skill_similarity_score=skill,
        experience_score=round(experience, 4),
        eligibility_score=round(eligibility, 4),
        location_score=round(location, 4),
        overall_score=round(min(1.0, max(0.0, overall)), 4),
        matched_skill_codes=matched,
        grounding=_grounding(profile, scheme, matched),
    )


def _grounding(
    profile: ProfileInput, scheme: Scheme, matched: list[str]
) -> dict[str, object]:
    """The closed set of facts the explanation layer may use.

    Assembling it here, rather than handing the explanation layer the whole
    profile, is what makes "grounded" checkable: anything in an explanation
    that is not traceable to this dict came from the model's imagination.
    """
    by_code = {s.code: s for s in profile.skills if s.code}

    # Label maps rather than bare English strings: the explanation layer picks
    # the language at render time, so a Tamil sentence gets a Tamil skill name
    # instead of an English noun dropped into it.
    matched_labels: list[dict[str, str]] = []
    for code in matched:
        skill = by_code.get(code)
        if skill and skill.display_names:
            matched_labels.append(dict(skill.display_names))
        elif skill and skill.name:
            matched_labels.append({"en": skill.name})
    if not matched_labels:
        matched_labels = [
            {"en": r.name} for r in scheme.required_skills if r.code in matched
        ]

    user_labels = [
        dict(s.display_names) if s.display_names
        else {"en": s.name or s.raw_name}
        for s in profile.skills
    ]

    missing_certs = [
        c
        for c in (scheme.certifications_required or [])
        if not any(_norm(c) in _norm(h) or _norm(h) in _norm(c)
                   for h in profile.certifications)
    ]

    return {
        "matched_skill_labels": matched_labels,
        "user_skill_labels": user_labels,
        # English-only views, kept for the LLM prompt and for tests.
        "matched_skill_names": [m.get("en", "") for m in matched_labels if m.get("en")],
        "user_skill_names": [s.name or s.raw_name for s in profile.skills],
        "user_evidence": [s.evidence_phrase for s in profile.skills],
        "experience_years": profile.experience_years,
        "user_location": profile.location,
        "minimum_experience": scheme.minimum_experience,
        "missing_certifications": missing_certs,
        "same_place": _norm(profile.location) == _norm(scheme.location),
    }


def rank(
    profile: ProfileInput,
    catalogue: list[Scheme],
    *,
    limit: int | None = None,
) -> list[ScoredMatch]:
    """Score the catalogue and order it.

    Ties break on scheme id so the order is stable across runs -- an
    unstable ranking would make the persisted ``matches`` rows unreproducible
    and the audit trail worthless.
    """
    settings = get_settings()
    learn_town_districts(catalogue)
    scored = [score_one(profile, o) for o in catalogue]
    scored.sort(key=lambda m: (-m.overall_score, m.scheme.id))

    for index, match in enumerate(scored, start=1):
        match.rank = index

    cap = limit or settings.match_result_limit
    return scored[:cap]
