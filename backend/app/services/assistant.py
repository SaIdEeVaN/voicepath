"""Follow-up spoken Q&A (PRD section 4.6).

The assistant answers from a context object assembled here from stored rows. It
is not given the catalogue, the taxonomy, or anything about other opportunities
-- only the opportunity in front of the user, their own profile, and the match
that connects them. Narrowing the context is what makes "no invented figures" a
property of the request rather than a hope about the model.

Without an LLM, ``answer_offline`` handles the questions people actually ask on
this screen -- pay, requirements, location, duration, privacy -- by reading the
same fields. Anything outside that set gets an honest "the record does not say".
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.prompts import ASSISTANT_SYSTEM, ASSISTANT_USER_TEMPLATE
from app.services import llm
from app.services.opportunities import Opportunity

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"ta": "Tamil", "hi": "Hindi", "en": "English"}


@dataclass
class Answer:
    answer_text: str
    source_note: str
    provider: str
    answered_from_data: bool = True


@dataclass
class QueryContext:
    opportunity: Opportunity | None = None
    experience_years: float | None = None
    location: str | None = None
    certifications: list[str] | None = None
    skill_names: list[str] | None = None
    audio_retained: bool = False
    overall_score: float | None = None
    matched_skill_names: list[str] | None = None


# ---------------------------------------------------------------------------
# Offline answer copy
# ---------------------------------------------------------------------------

COPY: dict[str, dict[str, str]] = {
    "en": {
        "pay_range": "It pays ₹{low} to ₹{high} a month.",
        "pay_fixed": "It pays ₹{amount} a month.",
        "pay_stipend": "There is a stipend of ₹{amount} a month.",
        "pay_support": "This is support of up to ₹{amount} to start on your own.",
        "pay_unknown": "The record does not give a figure for this one.",
        "certs_none": "No certificate is listed for this one. They ask for experience.",
        "certs_required": "They ask for {certs}.",
        "experience_needed": "They ask for {minimum} years of experience.",
        "experience_none": "No previous experience is asked for.",
        "where": "It is at {organization}, in {location}.",
        "type_training": "This is a training course, not a job.",
        "type_self": "This is support to start your own work, not a job with wages.",
        "type_job": "This is a {type} job.",
        "privacy": "Your voice was not saved. Only the words you said are kept, and no employer has been sent anything.",
        "privacy_retained": "You turned on keeping your voice clips, so they are saved. You can turn that off any time.",
        "why_match": "You match on {skills}.",
        "unknown": "I do not have that in the record for this one. I will not guess at it.",
        "source_listing": "from the listing",
        "source_you": "from what you told me",
        "source_privacy": "from this session's setting",
        "source_none": "not in the record",
    },
    "hi": {
        "pay_range": "महीने के ₹{low} से ₹{high} तक।",
        "pay_fixed": "महीने के ₹{amount}।",
        "pay_stipend": "हर महीने ₹{amount} वजीफ़ा मिलता है।",
        "pay_support": "अपना काम शुरू करने के लिए ₹{amount} तक की सहायता है।",
        "pay_unknown": "इसके लिए रिकॉर्ड में कोई रकम नहीं दी गई है।",
        "certs_none": "इसके लिए कोई सर्टिफिकेट नहीं माँगा गया। वे अनुभव माँगते हैं।",
        "certs_required": "वे {certs} माँगते हैं।",
        "experience_needed": "वे {minimum} साल का अनुभव माँगते हैं।",
        "experience_none": "पहले का कोई अनुभव नहीं माँगा गया।",
        "where": "यह {organization} में है, {location} में।",
        "type_training": "यह प्रशिक्षण है, नौकरी नहीं।",
        "type_self": "यह अपना काम शुरू करने की सहायता है, तनख़्वाह वाली नौकरी नहीं।",
        "type_job": "यह {type} नौकरी है।",
        "privacy": "आपकी आवाज़ सहेजी नहीं गई। सिर्फ़ आपके शब्द रखे हैं, और किसी नियोक्ता को कुछ नहीं भेजा गया।",
        "privacy_retained": "आपने आवाज़ रखने का विकल्प चालू किया है, इसलिए वे सहेजी गई हैं। इसे कभी भी बंद कर सकते हैं।",
        "why_match": "आपका {skills} इससे मेल खाता है।",
        "unknown": "इसके रिकॉर्ड में यह नहीं है। मैं अंदाज़ा नहीं लगाऊँगा।",
        "source_listing": "सूची से",
        "source_you": "आपने जो बताया उससे",
        "source_privacy": "इस सेशन की सेटिंग से",
        "source_none": "रिकॉर्ड में नहीं",
    },
    "ta": {
        "pay_range": "மாதம் ₹{low} முதல் ₹{high} வரை.",
        "pay_fixed": "மாதம் ₹{amount}.",
        "pay_stipend": "மாதம் ₹{amount} உதவித்தொகை உண்டு.",
        "pay_support": "சொந்தமாக தொடங்க ₹{amount} வரை உதவி.",
        "pay_unknown": "இதற்கு பதிவில் தொகை ஏதும் சொல்லப்படவில்லை.",
        "certs_none": "இதற்கு சான்றிதழ் எதுவும் கேட்கவில்லை. அனுபவம் கேட்கிறார்கள்.",
        "certs_required": "அவர்கள் {certs} கேட்கிறார்கள்.",
        "experience_needed": "{minimum} வருட அனுபவம் கேட்கிறார்கள்.",
        "experience_none": "முன் அனுபவம் எதுவும் கேட்கவில்லை.",
        "where": "இது {organization}ல், {location}ல் இருக்கிறது.",
        "type_training": "இது பயிற்சி, வேலை அல்ல.",
        "type_self": "இது சொந்தத் தொழில் தொடங்க உதவி, சம்பள வேலை அல்ல.",
        "type_job": "இது {type} வேலை.",
        "privacy": "உங்கள் குரல் சேமிக்கப்படவில்லை. நீங்கள் சொன்ன வார்த்தைகள் மட்டுமே இருக்கின்றன, யாருக்கும் எதுவும் அனுப்பப்படவில்லை.",
        "privacy_retained": "குரல் பதிவுகளை வைத்திருக்கும் விருப்பத்தை நீங்கள் இயக்கியுள்ளீர்கள். எப்போது வேண்டுமானாலும் நிறுத்தலாம்.",
        "why_match": "உங்கள் {skills} இதற்கு பொருந்துகிறது.",
        "unknown": "இதன் பதிவில் அது இல்லை. நான் ஊகிக்க மாட்டேன்.",
        "source_listing": "வேலை பட்டியலிலிருந்து",
        "source_you": "நீங்கள் சொன்னதிலிருந்து",
        "source_privacy": "இந்த அமர்வின் அமைப்பிலிருந்து",
        "source_none": "பதிவில் இல்லை",
    },
}


def _c(language: str, key: str) -> str:
    table = COPY.get(language, COPY["en"])
    return table.get(key, COPY["en"][key])


# Intent keywords across the three languages. Deliberately shallow -- this is a
# fallback for when there is no model, not an attempt to be one.
INTENTS: dict[str, list[str]] = {
    "pay": ["salary", "pay", "wage", "money", "stipend", "how much", "सैलरी", "तनख्वाह",
            "पैसा", "वजीफ़ा", "कितना", "சம்பளம்", "salary என்ன", "பணம்", "எவ்வளவு"],
    "certificate": ["certificate", "certification", "qualification", "degree", "diploma",
                    "सर्टिफिकेट", "प्रमाणपत्र", "डिग्री", "சான்றிதழ்", "படிப்பு"],
    "experience": ["experience", "years", "how long", "अनुभव", "साल", "தகுதி",
                   "அனுபவம்", "வருடம்"],
    "location": ["where", "location", "place", "far", "distance", "कहाँ", "कहां",
                 "जगह", "दूर", "எங்கே", "இடம்", "தூரம்"],
    "type": ["training", "job", "course", "what is this", "प्रशिक्षण", "नौकरी", "कोर्स",
             "பயிற்சி", "வேலை", "படிப்பு"],
    "privacy": ["voice", "audio", "recording", "privacy", "who hears", "data",
                "आवाज़", "आवाज", "रिकॉर्ड", "निजता", "குரல்", "பதிவு", "தனியுரிமை"],
    "why": ["why", "match", "fit", "suitable", "क्यों", "मेल", "ஏன்", "பொருந்த"],
}


def detect_intent(question: str) -> str | None:
    lowered = re.sub(r"\s+", " ", (question or "").lower()).strip()
    if not lowered:
        return None
    for intent, keywords in INTENTS.items():
        for keyword in keywords:
            if keyword.lower() in lowered:
                return intent
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def answer(
    question: str, context: QueryContext, *, language: str = "en"
) -> Answer:
    if llm.is_available():
        try:
            return await _answer_with_llm(question, context, language=language)
        except (llm.LLMUnavailable, llm.LLMResponseError) as exc:
            logger.warning("Assistant LLM unavailable (%s); using rule answers", exc)
    return answer_offline(question, context, language=language)


async def _answer_with_llm(
    question: str, context: QueryContext, *, language: str
) -> Answer:
    prompt = ASSISTANT_USER_TEMPLATE.format(
        question=question.strip(),
        opportunity=_describe_opportunity(context.opportunity),
        profile=_describe_profile(context),
        match=_describe_match(context),
        audio_retained="on" if context.audio_retained else "off",
    )
    system = ASSISTANT_SYSTEM.format(
        language_name=LANGUAGE_NAMES.get(language, "English")
    )
    payload = await llm.complete_json(system, prompt, temperature=0.2, max_tokens=400)

    if not isinstance(payload, dict):
        raise llm.LLMResponseError("Assistant reply was not a JSON object")

    text = payload.get("answer")
    if not isinstance(text, str) or not text.strip():
        raise llm.LLMResponseError("Assistant returned no answer text")

    note = payload.get("source_note")
    return Answer(
        answer_text=text.strip(),
        source_note=note.strip() if isinstance(note, str) and note.strip()
        else _c(language, "source_listing"),
        provider=llm.provider_name(),
        answered_from_data=bool(payload.get("answered_from_data", True)),
    )


def _describe_opportunity(opportunity: Opportunity | None) -> str:
    if opportunity is None:
        return "No specific opportunity is in view."
    lines = [
        f"- Title: {opportunity.title}",
        f"- Organisation: {opportunity.organization}",
        f"- Place: {opportunity.location}",
        f"- Type: {opportunity.type}",
        f"- Minimum experience: {opportunity.minimum_experience}",
        f"- Certificates required: "
        f"{', '.join(opportunity.certifications_required) or 'none listed'}",
    ]
    if opportunity.salary_min or opportunity.salary_max:
        lines.append(
            f"- Money: min {opportunity.salary_min}, max {opportunity.salary_max} "
            f"(rupees)"
        )
    else:
        lines.append("- Money: not stated in the record")
    if opportunity.nsqf_level:
        lines.append(f"- NSQF level: {opportunity.nsqf_level} (never say this aloud)")
    if opportunity.description:
        lines.append(f"- Listing text: {opportunity.description}")
    return "\n".join(lines)


def _describe_profile(context: QueryContext) -> str:
    return "\n".join(
        [
            f"- Skills they described: "
            f"{', '.join(context.skill_names or []) or 'none recorded'}",
            f"- Years stated: "
            f"{context.experience_years if context.experience_years is not None else 'not stated'}",
            f"- Where they are: {context.location or 'not stated'}",
            f"- Certificates they mentioned: "
            f"{', '.join(context.certifications or []) or 'none mentioned'}",
        ]
    )


def _describe_match(context: QueryContext) -> str:
    if context.overall_score is None:
        return "- Not matched yet."
    return "\n".join(
        [
            f"- Their skills that matched: "
            f"{', '.join(context.matched_skill_names or []) or 'none'}",
            "- Do not state the score as a number.",
        ]
    )


def answer_offline(
    question: str, context: QueryContext, *, language: str = "en"
) -> Answer:
    language = language if language in COPY else "en"
    intent = detect_intent(question)
    opportunity = context.opportunity

    if intent == "privacy":
        key = "privacy_retained" if context.audio_retained else "privacy"
        return Answer(_c(language, key), _c(language, "source_privacy"), "offline")

    if opportunity is None:
        return Answer(
            _c(language, "unknown"), _c(language, "source_none"), "offline",
            answered_from_data=False,
        )

    if intent == "pay":
        return Answer(_pay_answer(opportunity, language),
                      _c(language, "source_listing"), "offline",
                      answered_from_data=bool(opportunity.salary_min or opportunity.salary_max))

    if intent == "certificate":
        required = opportunity.certifications_required or []
        if not required:
            return Answer(_c(language, "certs_none"),
                          _c(language, "source_listing"), "offline")
        return Answer(
            _c(language, "certs_required").format(certs=", ".join(required)),
            _c(language, "source_listing"), "offline",
        )

    if intent == "experience":
        minimum = float(opportunity.minimum_experience or 0)
        if minimum <= 0:
            return Answer(_c(language, "experience_none"),
                          _c(language, "source_listing"), "offline")
        text = _c(language, "experience_needed").format(
            minimum=int(minimum) if minimum.is_integer() else minimum
        )
        return Answer(text, _c(language, "source_listing"), "offline")

    if intent == "location":
        return Answer(
            _c(language, "where").format(
                organization=opportunity.organization, location=opportunity.location
            ),
            _c(language, "source_listing"), "offline",
        )

    if intent == "type":
        if opportunity.type == "Training":
            text = _c(language, "type_training")
        elif opportunity.type == "Self-employment support":
            text = _c(language, "type_self")
        else:
            text = _c(language, "type_job").format(type=opportunity.type)
        return Answer(text, _c(language, "source_listing"), "offline")

    if intent == "why":
        names = context.matched_skill_names or []
        if names:
            return Answer(
                _c(language, "why_match").format(skills=", ".join(names[:3])),
                _c(language, "source_you"), "offline",
            )

    return Answer(
        _c(language, "unknown"), _c(language, "source_none"), "offline",
        answered_from_data=False,
    )


def _pay_answer(opportunity: Opportunity, language: str) -> str:
    if opportunity.type == "Training" and opportunity.salary_min:
        return _c(language, "pay_stipend").format(amount=f"{opportunity.salary_min:,}")
    if opportunity.type == "Self-employment support" and opportunity.salary_max:
        return _c(language, "pay_support").format(amount=f"{opportunity.salary_max:,}")
    if opportunity.salary_min and opportunity.salary_max:
        if opportunity.salary_min == opportunity.salary_max:
            return _c(language, "pay_fixed").format(
                amount=f"{opportunity.salary_min:,}"
            )
        return _c(language, "pay_range").format(
            low=f"{opportunity.salary_min:,}", high=f"{opportunity.salary_max:,}"
        )
    if opportunity.salary_max:
        return _c(language, "pay_support").format(amount=f"{opportunity.salary_max:,}")
    return _c(language, "pay_unknown")


def provider_name() -> str:
    return llm.provider_name()
