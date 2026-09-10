"""Transcript to structured profile (PRD section 4.2).

Two things happen here, and the second matters as much as the first.

1. The transcript is sent to the LLM with the extraction prompt, in its source
   language, with no translation step.

2. Everything that comes back is checked against the transcript before it is
   accepted. The prompt says "never invent"; this module makes that a property
   of the system rather than a request. A skill whose ``evidence_phrase`` is not
   actually in the transcript is dropped -- not corrected, not kept with a
   warning. Dropped.

When no LLM is configured, ``extract_offline`` does a lexical pass over the
taxonomy aliases. It cannot infer, so it finds less. What it does find is
anchored to real words in the transcript by construction, which keeps the
guarantee intact at a lower recall.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.data.catalogue import TAXONOMY
from app.prompts import EXTRACTION_SYSTEM, EXTRACTION_USER_TEMPLATE
from app.services import llm

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "ta": "Tamil",
    "hi": "Hindi",
    "en": "English",
    "auto": "Tamil, Hindi or English, possibly mixed",
}


@dataclass
class RawSkill:
    raw_name: str
    evidence_phrase: str


@dataclass
class ExtractionResult:
    experience_years: float | None = None
    experience_context: str | None = None
    education: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    location: str | None = None
    work_preferences: list[str] = field(default_factory=list)
    uncertainty_flags: list[str] = field(default_factory=list)
    skills: list[RawSkill] = field(default_factory=list)
    provider: str = "offline"
    degraded: bool = True


# ---------------------------------------------------------------------------
# Evidence verification
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")
_WORD = re.compile(r"\w+", re.UNICODE)


def _normalise(text: str) -> str:
    """Fold to a form where "the same words" compare equal.

    NFKC because Indic text arrives in several normalisation forms depending on
    the keyboard and the STT provider, and two visually identical strings can
    differ byte for byte.
    """
    folded = unicodedata.normalize("NFKC", text or "")
    return _WS.sub(" ", folded).strip().casefold()


def evidence_is_grounded(evidence: str, transcript: str) -> bool:
    """Is this phrase really in the transcript?

    Exact match after normalisation is the common case. The token fallback
    exists because models routinely drop a comma or a trailing particle when
    quoting; requiring every word of the phrase to appear in the transcript,
    in order, still makes fabrication impossible while tolerating that.
    """
    ev = _normalise(evidence)
    tr = _normalise(transcript)
    if not ev or not tr:
        return False
    if ev in tr:
        return True

    ev_tokens = _WORD.findall(ev)
    if len(ev_tokens) < 2:
        # A single word that is not a substring is not evidence.
        return False

    cursor = 0
    tr_tokens = _WORD.findall(tr)
    for token in ev_tokens:
        try:
            cursor = tr_tokens.index(token, cursor) + 1
        except ValueError:
            return False
    return True


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------


async def extract(transcript: str, *, language: str = "auto") -> ExtractionResult:
    transcript = (transcript or "").strip()
    if not transcript:
        raise ValueError("Cannot extract from an empty transcript")

    if not llm.is_available():
        return extract_offline(transcript, language=language)

    prompt = EXTRACTION_USER_TEMPLATE.format(
        language=LANGUAGE_NAMES.get(language, LANGUAGE_NAMES["auto"]),
        transcript=transcript,
    )

    try:
        payload = await llm.complete_json(EXTRACTION_SYSTEM, prompt, temperature=0.1)
    except (llm.LLMUnavailable, llm.LLMResponseError) as exc:
        logger.warning("LLM extraction failed (%s); falling back to lexical pass", exc)
        result = extract_offline(transcript, language=language)
        result.uncertainty_flags.append(
            "The language model was unavailable, so only clearly named skills "
            "were picked up."
        )
        return result

    return _validate(payload, transcript, provider=llm.provider_name())


def _validate(payload: Any, transcript: str, *, provider: str) -> ExtractionResult:
    """Accept only what the transcript supports."""
    if not isinstance(payload, dict):
        raise llm.LLMResponseError("Extraction did not return a JSON object")

    result = ExtractionResult(provider=provider, degraded=False)

    # The model's own flags land first, so that everything appended below adds
    # to them rather than being overwritten by them.
    result.uncertainty_flags = _clean_list(payload.get("uncertainty_flags"))
    result.experience_context = _clean_str(payload.get("experience_context"))
    result.location = _clean_str(payload.get("location"))
    result.education = _clean_list(payload.get("education"))
    result.certifications = _clean_list(payload.get("certifications"))
    result.work_preferences = _clean_list(payload.get("work_preferences"))

    years = payload.get("experience_years")
    if isinstance(years, (int, float)) and not isinstance(years, bool):
        # Guard against a model turning "a few years" into a decade.
        if 0 <= float(years) <= 70:
            result.experience_years = float(years)
        else:
            result.uncertainty_flags.append(
                "The number of years was not clear enough to record."
            )

    dropped = 0
    seen: set[str] = set()
    for item in payload.get("skills") or []:
        if not isinstance(item, dict):
            continue
        raw_name = _clean_str(item.get("raw_name"))
        evidence = _clean_str(item.get("evidence_phrase"))
        if not raw_name or not evidence:
            dropped += 1
            continue
        if not evidence_is_grounded(evidence, transcript):
            # The model quoted something that was never said.
            logger.warning("Dropping ungrounded skill %r (evidence: %r)", raw_name, evidence)
            dropped += 1
            continue
        key = _normalise(raw_name)
        if key in seen:
            continue
        seen.add(key)
        result.skills.append(RawSkill(raw_name=raw_name, evidence_phrase=evidence))

    if dropped:
        result.uncertainty_flags.append(
            "Some things could not be traced back to your words, so they were "
            "left out."
        )

    return result


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in {"null", "none", "n/a", "unknown"}:
        return None
    return stripped[:500]


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        cleaned = _clean_str(item if isinstance(item, str) else str(item))
        if cleaned:
            out.append(cleaned)
    return out[:20]


# ---------------------------------------------------------------------------
# Offline extraction
# ---------------------------------------------------------------------------

# "six years", "6 saal", "ஆறு வருஷம்" -- the digit form covers most STT output,
# which tends to render spoken numerals as digits.
_YEAR_PATTERNS = [
    re.compile(r"(\d{1,2})\s*(?:\+)?\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"(\d{1,2})\s*(?:साल|वर्ष|बरस)"),
    re.compile(r"(\d{1,2})\s*(?:வருஷ|வருட|ஆண்டு)"),
]

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6,
    "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ஒரு": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5, "ஆறு": 6,
    "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10,
}

_YEAR_WORDS = ["years", "year", "yrs", "साल", "वर्ष", "बरस", "வருஷ", "வருட", "ஆண்டு"]

# Sentence-ish split that works across Latin, Devanagari and Tamil punctuation.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")


def extract_offline(transcript: str, *, language: str = "auto") -> ExtractionResult:
    """Lexical extraction: find taxonomy aliases that literally occur.

    Recall is much lower than the LLM path -- this finds named skills, not
    described ones. Precision is what it protects: every skill it returns is
    backed by a clause from the transcript that contains the matched words.
    """
    result = ExtractionResult(provider="offline", degraded=True)
    normalised = _normalise(transcript)
    clauses = [c.strip() for c in _SENTENCE_SPLIT.split(transcript) if c.strip()]

    result.experience_years = _find_years(transcript, normalised)

    seen: set[str] = set()
    for entry in TAXONOMY:
        for alias in [entry["name"], *entry["aliases"]]:
            needle = _normalise(alias)
            if len(needle) < 3 or needle not in normalised:
                continue
            clause = _clause_containing(clauses, needle) or transcript.strip()
            key = entry["code"]
            if key in seen:
                break
            seen.add(key)
            result.skills.append(
                RawSkill(raw_name=alias, evidence_phrase=clause[:400])
            )
            break

    result.uncertainty_flags.append(
        "This was read without a language model, so only skills you named "
        "directly were picked up."
    )
    return result


def _clause_containing(clauses: list[str], needle: str) -> str | None:
    for clause in clauses:
        if needle in _normalise(clause):
            return clause
    return None


def _find_years(transcript: str, normalised: str) -> float | None:
    for pattern in _YEAR_PATTERNS:
        match = pattern.search(transcript)
        if match:
            value = float(match.group(1))
            if 0 < value <= 70:
                return value

    # Spelled-out numbers, only when a year word follows closely. Requiring the
    # pairing avoids reading "two bikes" as two years.
    for word, value in _WORD_NUMBERS.items():
        idx = normalised.find(_normalise(word))
        if idx == -1:
            continue
        window = normalised[idx : idx + len(word) + 22]
        if any(_normalise(y) in window for y in _YEAR_WORDS):
            return float(value)
    return None
