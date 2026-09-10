"""The extraction guardrail.

PRD section 4.2 says the extraction layer must never invent. The prompt asks for
that; ``_validate`` enforces it. These tests exercise the enforcement, because a
prompt that is merely asked nicely is not a guarantee.
"""

from __future__ import annotations

import pytest

from app.services import extraction
from app.services.extraction import evidence_is_grounded, extract_offline

TRANSCRIPT_EN = (
    "I have been repairing bikes for six years. I worked at a shop in Salem, "
    "I can tell the problem just by the engine sound. I know a little welding. "
    "I talk to the customers who come to the shop myself."
)

TRANSCRIPT_TA = (
    "எனக்கு ஆறு வருஷமா பைக் ரிப்பேர் தெரியும். சேலத்துல ஒரு கடையில வேலை பாத்தேன், "
    "எஞ்சின் சத்தம் கேட்டாலே என்ன பிரச்சனை தெரியும். வெல்டிங் கொஞ்சம் தெரியும்."
)

TRANSCRIPT_HI = (
    "मुझे छह साल से बाइक रिपेयर आता है। सेलम में एक दुकान पर काम किया। "
    "वेल्डिंग थोड़ी आती है।"
)


class TestEvidenceGrounding:
    def test_exact_quote_is_grounded(self):
        assert evidence_is_grounded("repairing bikes for six years", TRANSCRIPT_EN)

    def test_invented_quote_is_not(self):
        assert not evidence_is_grounded(
            "I have a diploma in automobile engineering", TRANSCRIPT_EN
        )

    def test_case_and_spacing_differences_are_tolerated(self):
        assert evidence_is_grounded("REPAIRING   BIKES", TRANSCRIPT_EN)

    def test_dropped_punctuation_is_tolerated(self):
        assert evidence_is_grounded("I worked at a shop in Salem", TRANSCRIPT_EN)

    def test_reordered_words_are_not_grounded(self):
        """Word order matters -- otherwise a bag of real words could be
        rearranged into a claim that was never made."""
        assert not evidence_is_grounded("bikes repairing six for years", TRANSCRIPT_EN)

    def test_single_unmatched_word_is_not_evidence(self):
        assert not evidence_is_grounded("welding", "I fix bikes and scooters")

    def test_tamil_quote_is_grounded(self):
        assert evidence_is_grounded("பைக் ரிப்பேர் தெரியும்", TRANSCRIPT_TA)

    def test_hindi_quote_is_grounded(self):
        assert evidence_is_grounded("बाइक रिपेयर आता है", TRANSCRIPT_HI)

    def test_tamil_invention_is_rejected(self):
        assert not evidence_is_grounded("எனக்கு ஐடிஐ சான்றிதழ் இருக்கு", TRANSCRIPT_TA)

    def test_empty_inputs_are_not_grounded(self):
        assert not evidence_is_grounded("", TRANSCRIPT_EN)
        assert not evidence_is_grounded("something", "")


class TestValidation:
    """``_validate`` is the gate every LLM extraction passes through."""

    def test_ungrounded_skills_are_dropped(self):
        payload = {
            "experience_years": 6,
            "skills": [
                {"raw_name": "bike repair",
                 "evidence_phrase": "repairing bikes for six years"},
                {"raw_name": "ITI certificate",
                 "evidence_phrase": "I completed my ITI in 2019"},
            ],
        }
        result = extraction._validate(payload, TRANSCRIPT_EN, provider="test")
        names = [s.raw_name for s in result.skills]
        assert "bike repair" in names
        assert "ITI certificate" not in names

    def test_dropping_something_is_surfaced_not_hidden(self):
        payload = {
            "skills": [
                {"raw_name": "welding certificate",
                 "evidence_phrase": "I am a certified welder"}
            ]
        }
        result = extraction._validate(payload, TRANSCRIPT_EN, provider="test")
        assert result.skills == []
        assert result.uncertainty_flags, "the user must be told something was dropped"

    def test_absurd_experience_is_refused_and_flagged(self):
        payload = {"experience_years": 900, "skills": []}
        result = extraction._validate(payload, TRANSCRIPT_EN, provider="test")
        assert result.experience_years is None
        assert result.uncertainty_flags

    def test_null_experience_stays_null(self):
        """"A few years" must not become a number."""
        payload = {"experience_years": None, "skills": []}
        result = extraction._validate(payload, TRANSCRIPT_EN, provider="test")
        assert result.experience_years is None

    def test_placeholder_strings_are_treated_as_absent(self):
        payload = {"location": "unknown", "experience_context": "N/A", "skills": []}
        result = extraction._validate(payload, TRANSCRIPT_EN, provider="test")
        assert result.location is None
        assert result.experience_context is None

    def test_duplicate_skills_collapse(self):
        payload = {
            "skills": [
                {"raw_name": "bike repair", "evidence_phrase": "repairing bikes"},
                {"raw_name": "Bike Repair", "evidence_phrase": "repairing bikes"},
            ]
        }
        result = extraction._validate(payload, TRANSCRIPT_EN, provider="test")
        assert len(result.skills) == 1

    def test_evidence_is_preserved_verbatim(self):
        payload = {
            "skills": [
                {"raw_name": "engine diagnostics",
                 "evidence_phrase": "I can tell the problem just by the engine sound"}
            ]
        }
        result = extraction._validate(payload, TRANSCRIPT_EN, provider="test")
        assert (
            result.skills[0].evidence_phrase
            == "I can tell the problem just by the engine sound"
        )

    def test_non_object_payload_is_rejected(self):
        from app.services.llm import LLMResponseError

        with pytest.raises(LLMResponseError):
            extraction._validate(["not", "an", "object"], TRANSCRIPT_EN, provider="test")


class TestOfflineExtraction:
    def test_finds_named_skills_in_english(self):
        result = extract_offline(TRANSCRIPT_EN, language="en")
        assert result.skills
        assert result.degraded is True
        assert result.provider == "offline"

    def test_every_evidence_phrase_is_real(self):
        """The offline path cannot invent by construction -- prove it."""
        for transcript, language in (
            (TRANSCRIPT_EN, "en"), (TRANSCRIPT_TA, "ta"), (TRANSCRIPT_HI, "hi")
        ):
            result = extract_offline(transcript, language=language)
            for skill in result.skills:
                assert evidence_is_grounded(skill.evidence_phrase, transcript), (
                    f"{skill.raw_name!r} quoted something not in the transcript"
                )

    def test_reads_years_from_digits(self):
        result = extract_offline("I have 6 years of bike repair experience", language="en")
        assert result.experience_years == 6.0

    def test_reads_spelled_out_years(self):
        result = extract_offline(TRANSCRIPT_EN, language="en")
        assert result.experience_years == 6.0

    def test_does_not_read_a_count_as_a_duration(self):
        """"two bikes" is not two years."""
        result = extract_offline("I fix two bikes every day", language="en")
        assert result.experience_years is None

    def test_says_out_loud_that_it_is_degraded(self):
        result = extract_offline(TRANSCRIPT_EN, language="en")
        assert result.uncertainty_flags


class TestExtractEntryPoint:
    @pytest.mark.asyncio
    async def test_empty_transcript_is_refused(self):
        with pytest.raises(ValueError):
            await extraction.extract("   ")

    @pytest.mark.asyncio
    async def test_falls_back_when_no_llm_is_configured(self):
        result = await extraction.extract(TRANSCRIPT_EN, language="en")
        assert result.provider == "offline"
        assert result.degraded is True
