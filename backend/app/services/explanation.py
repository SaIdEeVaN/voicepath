"""Grounded explanations for an already-decided ranking (PRD section 4.5).

The contract, in one line: this module receives a ``ScoredMatch`` and returns
text. It never returns a score, never reorders, and the caller does not read a
ranking back out of it. The separation the PRD asks for is structural -- there
is no return path through which an explanation could change a result.

The offline path builds the same bullets from templates over the same
``grounding`` dict. Because the grounding dict is a closed set of stored facts,
the templated bullets are grounded by construction, which makes this the one
place where losing the LLM costs fluency rather than trustworthiness.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.prompts import EXPLANATION_SYSTEM, EXPLANATION_USER_TEMPLATE
from app.services import llm
from app.services.matching import ScoredMatch

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"ta": "Tamil", "hi": "Hindi", "en": "English"}


@dataclass
class Explanation:
    bullets: list[str]
    summary: str
    provider: str


# ---------------------------------------------------------------------------
# Templated fallback copy
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "skills_match": "You do {skills} — that is what this work is.",
        "skills_partial": "Your {skills} is close to what they need here.",
        "experience_meets": "You said {years} years; they ask for {minimum}.",
        "experience_short": "They ask for {minimum} years. You said {years}.",
        "experience_none_needed": "No previous experience is asked for.",
        "same_place": "It is in {place}, where you are.",
        "different_place": "This is in {place}, away from where you are.",
        "cert_missing": "They ask for {certs}. You did not mention having it.",
        "training": "This is training, not a job — it gives a certificate for work you already do.",
        "stipend": "It comes with a stipend of ₹{amount} a month.",
        "support": "This is money to start on your own, up to ₹{amount}.",
        "pay": "The pay is ₹{low} to ₹{high} a month.",
        "summary_strong": "This is close to the work you described.",
        "summary_partial": "Some of your work fits here, not all of it.",
        "summary_weak": "This is further from what you described.",
    },
    "hi": {
        "skills_match": "आप {skills} करते हैं — यह काम वही है।",
        "skills_partial": "आपका {skills} यहाँ की ज़रूरत के करीब है।",
        "experience_meets": "आपने {years} साल बताए; वे {minimum} माँगते हैं।",
        "experience_short": "वे {minimum} साल माँगते हैं। आपने {years} बताए।",
        "experience_none_needed": "पहले का कोई अनुभव नहीं माँगा गया है।",
        "same_place": "यह {place} में ही है, जहाँ आप हैं।",
        "different_place": "यह {place} में है, आपकी जगह से दूर।",
        "cert_missing": "वे {certs} माँगते हैं। आपने बताया नहीं कि आपके पास है।",
        "training": "यह नौकरी नहीं, प्रशिक्षण है — जो काम आप करते हैं उसी का प्रमाणपत्र मिलता है।",
        "stipend": "इसमें हर महीने ₹{amount} वजीफ़ा मिलता है।",
        "support": "यह अपना काम शुरू करने के लिए पैसा है, ₹{amount} तक।",
        "pay": "महीने के ₹{low} से ₹{high} तक।",
        "summary_strong": "यह उसी काम के करीब है जो आपने बताया।",
        "summary_partial": "आपका कुछ काम यहाँ फिट होता है, पूरा नहीं।",
        "summary_weak": "यह आपके बताए काम से कुछ दूर है।",
    },
    "ta": {
        "skills_match": "நீங்கள் {skills} செய்கிறீர்கள் — இந்த வேலை அதுவே.",
        "skills_partial": "உங்கள் {skills} இங்கு தேவைப்படுவதற்கு நெருக்கமானது.",
        "experience_meets": "நீங்கள் {years} வருடம் சொன்னீர்கள்; அவர்கள் {minimum} கேட்கிறார்கள்.",
        "experience_short": "அவர்கள் {minimum} வருடம் கேட்கிறார்கள். நீங்கள் {years} சொன்னீர்கள்.",
        "experience_none_needed": "முன் அனுபவம் எதுவும் கேட்கவில்லை.",
        "same_place": "இது {place}லேயே இருக்கிறது, நீங்கள் இருக்கும் இடத்தில்.",
        "different_place": "இது {place}ல் இருக்கிறது, உங்கள் ஊரிலிருந்து தூரம்.",
        "cert_missing": "அவர்கள் {certs} கேட்கிறார்கள். உங்களிடம் இருப்பதாக நீங்கள் சொல்லவில்லை.",
        "training": "இது வேலை அல்ல, பயிற்சி — நீங்கள் ஏற்கனவே செய்யும் வேலைக்கு சான்றிதழ் தருகிறது.",
        "stipend": "மாதம் ₹{amount} உதவித்தொகை உண்டு.",
        "support": "இது சொந்தமாக தொடங்க தரும் பணம், ₹{amount} வரை.",
        "pay": "மாதம் ₹{low} முதல் ₹{high} வரை.",
        "summary_strong": "நீங்கள் சொன்ன வேலைக்கு இது மிக நெருக்கம்.",
        "summary_partial": "உங்கள் வேலையில் சில இங்கு பொருந்துகிறது, எல்லாம் இல்லை.",
        "summary_weak": "இது நீங்கள் சொன்ன வேலையிலிருந்து சற்று தூரம்.",
    },
}


def _t(language: str, key: str) -> str:
    table = TEMPLATES.get(language, TEMPLATES["en"])
    return table.get(key, TEMPLATES["en"][key])


def _number(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _join(items: list[str], language: str) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    separator = ", "
    tail = {"en": " and ", "hi": " और ", "ta": " மற்றும் "}.get(language, " and ")
    return separator.join(items[:-1]) + tail + items[-1]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def explain(match: ScoredMatch, *, language: str = "en") -> Explanation:
    if llm.is_available():
        try:
            return await _explain_with_llm(match, language=language)
        except (llm.LLMUnavailable, llm.LLMResponseError) as exc:
            logger.warning("Explanation LLM unavailable (%s); using templates", exc)
    return explain_offline(match, language=language)


async def explain_many(
    matches: list[ScoredMatch], *, language: str = "en"
) -> dict[int, Explanation]:
    """Explain a ranked list. Order in, order out -- unchanged."""
    out: dict[int, Explanation] = {}
    for match in matches:
        out[match.opportunity.id] = await explain(match, language=language)
    return out


async def _explain_with_llm(match: ScoredMatch, *, language: str) -> Explanation:
    grounding = match.grounding
    opportunity = match.opportunity

    prompt = EXPLANATION_USER_TEMPLATE.format(
        skills=_join(list(grounding.get("user_skill_names") or []), "en") or "not stated",
        experience=_number(grounding.get("experience_years")) or "not stated",
        location=grounding.get("user_location") or "not stated",
        certifications=_join(
            [c for c in (grounding.get("missing_certifications") or [])], "en"
        )
        or "none stated",
        title=opportunity.title,
        organization=opportunity.organization,
        location_opportunity=opportunity.location,
        type=opportunity.type,
        minimum_experience=_number(opportunity.minimum_experience) or "0",
        certifications_required=_join(opportunity.certifications_required, "en")
        or "none listed",
        pay=_pay_phrase(opportunity),
        description=opportunity.description or "no further detail in the record",
        skill_score=f"{match.skill_similarity_score:.2f}",
        experience_score=f"{match.experience_score:.2f}",
        eligibility_score=f"{match.eligibility_score:.2f}",
        location_score=f"{match.location_score:.2f}",
        matched_skills=_join(list(grounding.get("matched_skill_names") or []), "en")
        or "none",
    )

    system = EXPLANATION_SYSTEM.format(
        language_name=LANGUAGE_NAMES.get(language, "English")
    )
    payload = await llm.complete_json(system, prompt, temperature=0.3, max_tokens=500)

    if not isinstance(payload, dict):
        raise llm.LLMResponseError("Explanation was not a JSON object")

    bullets = [
        b.strip()
        for b in (payload.get("bullets") or [])
        if isinstance(b, str) and b.strip()
    ][:3]
    summary = payload.get("summary")
    summary = summary.strip() if isinstance(summary, str) else ""

    if not bullets:
        # A model that returned nothing usable must not leave the card blank.
        return explain_offline(match, language=language)

    return Explanation(
        bullets=bullets,
        summary=summary or bullets[0],
        provider=llm.provider_name(),
    )


def _pay_phrase(opportunity) -> str:
    if opportunity.salary_min and opportunity.salary_max:
        if opportunity.salary_min == opportunity.salary_max:
            return f"Rs {opportunity.salary_min} a month"
        return f"Rs {opportunity.salary_min} to {opportunity.salary_max} a month"
    if opportunity.salary_max:
        return f"up to Rs {opportunity.salary_max}"
    if opportunity.salary_min:
        return f"from Rs {opportunity.salary_min}"
    return "not stated in the record"


def explain_offline(match: ScoredMatch, *, language: str = "en") -> Explanation:
    """Template explanation from the grounding facts.

    Reads a little flatter than the model's. Says nothing that is not in the
    record, which is the part that matters.
    """
    language = language if language in TEMPLATES else "en"
    grounding = match.grounding
    opportunity = match.opportunity
    bullets: list[str] = []

    # Prefer the label map so the sentence stays in one language throughout.
    labels = grounding.get("matched_skill_labels") or []
    matched_names = [
        (m.get(language) or m.get("en") or "")
        for m in labels
        if isinstance(m, dict)
    ]
    matched_names = [n for n in matched_names if n]
    if not matched_names:
        matched_names = [str(n) for n in (grounding.get("matched_skill_names") or [])]
    if matched_names:
        key = "skills_match" if match.skill_similarity_score >= 0.8 else "skills_partial"
        bullets.append(
            _t(language, key).format(skills=_join(matched_names[:2], language))
        )

    minimum = float(opportunity.minimum_experience or 0)
    years = grounding.get("experience_years")
    if minimum <= 0:
        bullets.append(_t(language, "experience_none_needed"))
    elif isinstance(years, (int, float)):
        key = "experience_meets" if float(years) >= minimum else "experience_short"
        bullets.append(
            _t(language, key).format(
                years=_number(float(years)), minimum=_number(minimum)
            )
        )

    # Say the uncomfortable thing, and say it early. A requirement the person
    # does not meet is the single most useful sentence on the card, so it goes
    # above the pay and the distance -- never last, where the cap could cut it.
    missing = [str(c) for c in (grounding.get("missing_certifications") or [])]
    if missing:
        bullets.append(
            _t(language, "cert_missing").format(certs=_join(missing, language))
        )

    if opportunity.type == "Training":
        bullets.append(_t(language, "training"))
        if opportunity.salary_min:
            bullets.append(
                _t(language, "stipend").format(amount=f"{opportunity.salary_min:,}")
            )
    elif opportunity.type == "Self-employment support":
        if opportunity.salary_max:
            bullets.append(
                _t(language, "support").format(amount=f"{opportunity.salary_max:,}")
            )
    elif opportunity.salary_min and opportunity.salary_max:
        bullets.append(
            _t(language, "pay").format(
                low=f"{opportunity.salary_min:,}", high=f"{opportunity.salary_max:,}"
            )
        )

    if grounding.get("same_place"):
        bullets.append(_t(language, "same_place").format(place=opportunity.location))
    elif match.location_score <= 0.5:
        bullets.append(
            _t(language, "different_place").format(place=opportunity.location)
        )

    if match.overall_score >= 0.8:
        summary_key = "summary_strong"
    elif match.overall_score >= 0.6:
        summary_key = "summary_partial"
    else:
        summary_key = "summary_weak"

    return Explanation(
        bullets=bullets[:4],
        summary=_t(language, summary_key),
        provider="offline",
    )


def provider_name() -> str:
    return llm.provider_name()
