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
from app.services.schemes import NATIONWIDE, Scheme

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
    # Whether the skill term was *earned* rather than defaulted.
    #
    # True only when the scheme declares requirements and this person earned
    # something against them. It separates "this fits the work you described"
    # from "this does not exclude you" -- a scheme declaring no skills cannot
    # be ruled out, which is not the same as fitting, and a carpenter was
    # shown one at the top of their results because of it.
    #
    # The flag does not change any score. What to do with a result that lacks
    # it is the interface's decision, not this module's.
    skill_evidence: bool = False
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
    # Headquarters whose district has another name.
    "nagercoil": "kanniyakumari",
    "udhagamandalam": "nilgiris",
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

# A national scheme -- PMKVY, PM Vishwakarma, Mudra -- is open wherever the
# person is: it is delivered through district offices, training centres, banks
# and Common Service Centres everywhere. Scored as their own district rather
# than their own town, because "available in your district" is what the record
# supports; "in your town" it does not say. Applied whether or not the person
# said where they are, since the answer is the same either way.
LOCATION_NATIONWIDE = LOCATION_SAME_DISTRICT

# What to score when the person never said how long they have worked. Neither
# credited nor penalised: the profile carries an uncertainty flag and the
# interface asks. Scoring 0 would bury people who simply did not mention it.
EXPERIENCE_UNKNOWN = 0.5

# A scheme that lists no required skills tells us nothing about whether this
# person fits it. That is the absence of evidence, not evidence of a perfect
# fit, so it takes the same neutral value as an unknown location or unknown
# experience rather than full marks.
#
# It used to return 1.0, on the reasoning that "nothing asked for cannot be
# unmet". True while every scheme was seeded with its skills; false the moment
# the admin form -- which has no field for skills -- created one. Such a scheme
# then scored 0.50 + 0.25 + 0.15 + 0.05 = 0.95 for everybody and sat at the top
# of every result page.
SKILL_UNKNOWN = 0.5

# Below this cosine, two different taxonomy skills are not related -- they are
# merely both embedded by the same model.
#
# Measured, not guessed. With multilingual-e5-base over this taxonomy, cosine
# from Carpentry to all twenty-two required skills in the catalogue runs 0.853
# (Engine Diagnostics) to 0.921 (Welding), with Retail Sales at 0.918 -- a
# spread of 0.068 containing no usable signal. A genuine relationship separates
# cleanly above it: Two-Wheeler Repair scores 1.000 against itself and 0.947
# against Four-Wheeler Repair.
#
# The old floor was 0.55, which admitted the entire noise band and paid it
# `weight * similarity`, so an unrelated trade collected 85-92% of the weight.
#
# Re-measure this if the taxonomy or the embedding model changes; it describes
# the model's behaviour over this vocabulary, not a universal constant.
SKILL_SIMILARITY_FLOOR = 0.92

# How close a requirement must be, after rescaling, before an explanation may
# name it as a skill the person has. Partial credit still counts toward the
# score below this -- it is simply not something to claim out loud.
SKILL_MATCHED_AT = 0.5

# How much of the required weight must be earned before a result counts as
# fitting the work someone described, rather than merely not excluding them.
#
# Not simply "more than zero". The floor above is a measurement, and a value a
# hair over it is slop rather than overlap: the closest unrelated pair measured
# (Carpentry to Welding, 0.9207) sits 0.0007 above the 0.92 floor and rescales
# to 0.009. This clears that comfortably while admitting a genuine neighbour --
# Two-Wheeler to Four-Wheeler Repair rescales to 0.34.
SKILL_EVIDENCE_AT = 0.05

# How many "open to any trade" schemes a result list may hold. See rank().
MAX_OPEN_TO_ANY_TRADE = 3

# Under skill_match "any", a requirement at full weight is a trade the scheme's
# own text names -- PM Vishwakarma's eighteen. Lower weights mean "open to any
# trade" (catalogue.ANY_TRADE). Only a named trade may be claimed out loud as
# the reason a scheme fits; the rest is said as "not limited to one trade".
SKILL_NAMED_WEIGHT = 1.0


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
    # District headquarters added 2026-11-05 (app/data/places.py has the sources).
    "ariyalur": ("ariyalur", "அரியலூர்", "அரியலூர", "अरियालुर"),
    "chengalpattu": ("chengalpattu", "chengalpet", "chingleput", "செங்கல்பட்டு", "செங்கல்பட்ட", "चेंगलपट्टू"),
    "cuddalore": ("cuddalore", "கடலூர்", "கடலூர", "कडलूर"),
    "dindigul": ("dindigul", "திண்டுக்கல்", "திண்டுக்கல", "डिंडिगुल"),
    "kallakurichi": ("kallakurichi", "கள்ளக்குறிச்சி", "कल्लाकुरिची"),
    "kanchipuram": ("kanchipuram", "kancheepuram", "காஞ்சிபுரம்", "காஞ்சிபுரம", "காஞ்சிபுர", "कांचीपुरम"),
    "nagercoil": ("nagercoil", "nagarcoil", "kanyakumari", "kanniyakumari", "நாகர்கோவில்", "நாகர்கோவில", "கன்னியாகுமரி", "नागरकोइल", "कन्याकुमारी"),
    "mayiladuthurai": ("mayiladuthurai", "mayavaram", "மயிலாடுதுறை", "मयीलाडूतुरै"),
    "nagapattinam": ("nagapattinam", "நாகப்பட்டினம்", "நாகப்பட்டினம", "நாகப்பட்டின", "नागपट्टनम"),
    "udhagamandalam": ("udhagamandalam", "ooty", "nilgiris", "உதகமண்டலம்", "உதகமண்டலம", "உதகமண்டல", "ஊட்டி", "நீலகிரி", "उदगमंदलम", "ऊटी", "नीलगिरि"),
    "perambalur": ("perambalur", "பெரம்பலூர்", "பெரம்பலூர", "पेरम्बलूर"),
    "pudukkottai": ("pudukkottai", "pudukottai", "புதுக்கோட்டை", "पुदुकोट्टई", "पुदुक्कोट्टई"),
    "ramanathapuram": ("ramanathapuram", "ramnad", "ramnathapuram", "இராமநாதபுரம்", "இராமநாதபுரம", "இராமநாதபுர", "ராமநாதபுரம்", "ராமநாதபுரம", "ராமநாதபுர", "रामानाथपुरम"),
    "ranipet": ("ranipet", "இராணிப்பேட்டை", "ராணிப்பேட்டை", "रानीपेट"),
    "sivaganga": ("sivaganga", "sivagangai", "சிவகங்கை", "शिवगंगा"),
    "tenkasi": ("tenkasi", "தென்காசி", "तेंकाशी"),
    "thanjavur": ("thanjavur", "tanjore", "தஞ்சாவூர்", "தஞ்சாவூர", "तंजावुर"),
    "theni": ("theni", "தேனி", "तेनी"),
    "thoothukudi": ("thoothukudi", "tuticorin", "thoothukkudi", "தூத்துக்குடி", "तूतुकुडी"),
    "tirunelveli": ("tirunelveli", "nellai", "திருநெல்வேலி", "நெல்லை", "तिरूनेलवेली"),
    "tirupathur": ("tirupathur", "tirupattur", "tiruppattur", "திருப்பத்தூர்", "திருப்பத்தூர", "तिरुपत्तुर"),
    "tiruvallur": ("tiruvallur", "thiruvallur", "திருவள்ளூர்", "திருவள்ளூர", "तिरुवल्लुर"),
    "tiruvannamalai": ("tiruvannamalai", "thiruvannamalai", "திருவண்ணாமலை", "तिरुवन्नमलई"),
    "tiruvarur": ("tiruvarur", "thiruvarur", "திருவாரூர்", "திருவாரூர", "तिरुवारूर"),
    "vellore": ("vellore", "வேலூர்", "வேலூர", "वेल्लोर"),
    "viluppuram": ("viluppuram", "villupuram", "விழுப்புரம்", "விழுப்புரம", "விழுப்புர", "विलुप्पुरम"),
    "virudhunagar": ("virudhunagar", "virudunagar", "விருதுநகர்", "விருதுநகர", "विरुधुनगर"),
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


def transferable(similarity: float) -> float:
    """Raw cosine to usable credit, against the model's measured noise floor.

    Linear from the floor to 1.0, so a similarity at the floor is worth
    nothing and only the distance above it counts. Without this the score is
    dominated by the fact that e5 rates every pair of trades around 0.9.
    """
    if similarity <= SKILL_SIMILARITY_FLOOR:
        return 0.0
    return (similarity - SKILL_SIMILARITY_FLOOR) / (1.0 - SKILL_SIMILARITY_FLOOR)


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
        # Not "everyone fits" -- "we cannot tell". See SKILL_UNKNOWN.
        return SKILL_UNKNOWN, []

    owned_ids = {s.skill_id for s in profile.skills if s.skill_id is not None}
    owned_vectors = [
        (s.code, s.embedding)
        for s in profile.skills
        if s.embedding
    ]

    if getattr(scheme, "skill_match", "all") == "any":
        return _any_trade_similarity(required, owned_ids, owned_vectors)

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

        # Below the floor the resemblance is noise rather than transferable
        # skill, and `transferable` returns nothing for it.
        credit = transferable(best)
        if credit > 0.0:
            earned += weight * credit
            # Naming a skill in an explanation is a claim about the person.
            # Partial credit can move a score without being worth saying.
            if best_code and credit >= SKILL_MATCHED_AT:
                matched.append(requirement.code)

    if total_weight == 0.0:
        return 0.0, []
    return round(min(1.0, earned / total_weight), 4), matched


def _requirement_credit(
    requirement, owned_ids: set[int], owned_vectors: list[tuple[str, list[float]]]
) -> float:
    """How much of one required skill the person has: 1.0 exact, else transferable."""
    if requirement.skill_id in owned_ids:
        return 1.0
    if not requirement.embedding:
        return 0.0
    best = max(
        (cosine_similarity(requirement.embedding, vector) for _, vector in owned_vectors),
        default=0.0,
    )
    return transferable(best)


def _any_trade_similarity(
    required, owned_ids: set[int], owned_vectors: list[tuple[str, list[float]]]
) -> tuple[float, list[str]]:
    """One trade is enough: the best single requirement carries the score.

    For a scheme that serves many trades -- PM Vishwakarma's eighteen, PMKVY's
    every sector -- coverage of all of them is the wrong question. A tailor is
    not a twentieth of a fit for PM Vishwakarma; tailoring is one of its
    trades, so a tailor fits it fully. Weighted coverage would have scored her
    0.05 and filtered the scheme out.

    The weight still counts, as how squarely the scheme names the trade: a
    named trade (1.0) earns full marks, "open to any trade" (0.6) earns less,
    so PM Vishwakarma ranks above PMKVY for a carpenter. Only named trades are
    returned as matched, because an explanation may claim them.
    """
    best = 0.0
    named: list[str] = []
    for requirement in required:
        weight = min(max(requirement.weight, 0.0), 1.0)
        if weight == 0.0:
            continue
        credit = _requirement_credit(requirement, owned_ids, owned_vectors)
        best = max(best, credit * weight)
        if credit >= SKILL_MATCHED_AT and weight >= SKILL_NAMED_WEIGHT:
            named.append(requirement.code)
    return round(min(1.0, best), 4), named


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


def is_nationwide(scheme: Scheme) -> bool:
    """True for a scheme open across India rather than in one place."""
    return _norm(scheme.location) == _norm(NATIONWIDE)


def location_score(profile: ProfileInput, scheme: Scheme) -> float:
    """Distance, in the only terms the data supports: place and district.

    Both sides go through `canonical_place` first, so the person's own words --
    in whatever script and case they said them -- reach the same key as the
    catalogue's English spelling. Then through the town/district table, so
    someone in Attur is understood to be in Salem district.
    """
    if is_nationwide(scheme):
        return LOCATION_NATIONWIDE

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
    # Declared requirements, and enough earned against them to mean something.
    # A scheme with no requirements returns SKILL_UNKNOWN, which is not
    # evidence however large it looks.
    skill_evidence = bool(scheme.required_skills) and skill >= SKILL_EVIDENCE_AT
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
        skill_evidence=skill_evidence,
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
        # Open across India; said instead of a distance.
        "nationwide": is_nationwide(scheme),
        # Fits because the scheme takes any trade, not because it names this
        # one. Said as such, never as "made for your work".
        "open_to_any_trade": getattr(scheme, "skill_match", "all") == "any"
        and not matched,
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

    cap = limit or settings.match_result_limit
    kept: list[ScoredMatch] = []
    open_to_any = 0
    for match in scored:
        if len(kept) >= cap:
            break
        # Schemes that take any trade tie with one another for everyone --
        # eight of them at one score, ordered by id. Past a few they say
        # nothing new and push out the openings in the person's own trade, so
        # only the first few are kept here. The rest are still listed on
        # /nearby under "anywhere in India". Deterministic: same input, same
        # cut.
        if match.grounding.get("open_to_any_trade") and match.skill_evidence:
            if open_to_any >= MAX_OPEN_TO_ANY_TRADE:
                continue
            open_to_any += 1
        kept.append(match)

    for index, match in enumerate(kept, start=1):
        match.rank = index
    return kept
