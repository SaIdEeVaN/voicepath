"""Skill labels in the reader's language.

A Tamil sentence with an English noun dropped into it -- "நீங்கள் Welding
செய்கிறீர்கள்" -- is what you get when the taxonomy only knows English names.
These tests hold the whole path: catalogue, taxonomy lookup, grounding, and the
sentence the person finally reads.
"""

from __future__ import annotations

import re

import pytest

from app.data.catalogue import DISPLAY_NAMES, TAXONOMY, display_names_for
from app.services import taxonomy
from app.services.explanation import explain_offline
from app.services.matching import ProfileInput, score_one
from app.services.normalization import NormalizedSkill, normalize_many
from app.services.schemes import Scheme, RequiredSkill

LATIN = re.compile(r"[A-Za-z]{3,}")


class TestCatalogueLabels:
    def test_every_skill_has_a_tamil_and_hindi_name(self):
        missing = [
            entry["code"]
            for entry in TAXONOMY
            if not DISPLAY_NAMES.get(entry["code"], {}).get("ta")
            or not DISPLAY_NAMES.get(entry["code"], {}).get("hi")
        ]
        assert not missing, f"No Tamil/Hindi label for: {missing}"

    def test_no_label_is_left_in_english(self):
        for code, names in DISPLAY_NAMES.items():
            assert not LATIN.search(names["ta"]), f"{code} Tamil label is Latin"
            assert not LATIN.search(names["hi"]), f"{code} Hindi label is Latin"

    def test_english_is_always_present_as_the_fallback(self):
        names = display_names_for("SK022", "Welding")
        assert names["en"] == "Welding"
        assert names["ta"]

    def test_an_unknown_code_still_gets_english(self):
        names = display_names_for("SK999", "Something New")
        assert names == {"en": "Something New"}


class TestTaxonomyLocalization:
    @pytest.mark.asyncio
    async def test_localized_picks_the_readers_language(self):
        welding = await taxonomy.get_by_code("SK022")
        assert welding is not None
        assert welding.localized("ta") == "வெல்டிங்"
        assert welding.localized("hi") == "वेल्डिंग"
        assert welding.localized("en") == "Welding"

    @pytest.mark.asyncio
    async def test_unknown_language_falls_back_to_english(self):
        welding = await taxonomy.get_by_code("SK022")
        assert welding is not None
        assert welding.localized("fr") == "Welding"
        assert welding.localized(None) == "Welding"

    @pytest.mark.asyncio
    async def test_a_regional_tag_still_resolves(self):
        welding = await taxonomy.get_by_code("SK022")
        assert welding is not None
        assert welding.localized("ta-IN") == "வெல்டிங்"

    @pytest.mark.asyncio
    async def test_normalization_carries_the_labels_through(self):
        result = await normalize_many([("welding", "I know a little welding")])
        assert result[0].display_names.get("ta") == "வெல்டிங்"


class TestExplanationLanguage:
    def _match(self):
        scheme = Scheme(
            id=1, title="Welder", organization="Annai Steel", location="Salem",
            district="Salem", type="Full-time", minimum_experience=1,
            certifications_required=[], salary_min=16000, salary_max=21000,
            nsqf_level="4", source_reference="OGD/TEST", description="Welding.",
            required_skills=[RequiredSkill(6, "SK022", "Welding", 1.0, True)],
        )
        profile = ProfileInput(
            experience_years=6.0, location="Salem", district="Salem",
            certifications=[],
            skills=[
                NormalizedSkill(
                    raw_name="welding", evidence_phrase="I know welding",
                    skill_id=6, code="SK022", name="Welding",
                    display_names={"en": "Welding", "ta": "வெல்டிங்",
                                   "hi": "वेल्डिंग"},
                )
            ],
        )
        return score_one(profile, scheme)

    def test_the_tamil_sentence_names_the_skill_in_tamil(self):
        bullets = explain_offline(self._match(), language="ta").bullets
        joined = " ".join(bullets)
        assert "வெல்டிங்" in joined
        assert "Welding" not in joined

    def test_the_hindi_sentence_names_the_skill_in_hindi(self):
        joined = " ".join(explain_offline(self._match(), language="hi").bullets)
        assert "वेल्डिंग" in joined
        assert "Welding" not in joined

    def test_english_is_unaffected(self):
        joined = " ".join(explain_offline(self._match(), language="en").bullets)
        assert "Welding" in joined

    def test_a_skill_without_labels_still_produces_a_sentence(self):
        """An unlocalized skill must not blank the card."""
        scheme = Scheme(
            id=1, title="X", organization="Y", location="Salem", district="Salem",
            type="Full-time", minimum_experience=0, certifications_required=[],
            salary_min=None, salary_max=None, nsqf_level=None,
            source_reference=None, description=None,
            required_skills=[RequiredSkill(99, "SK999", "New Trade", 1.0, True)],
        )
        profile = ProfileInput(
            skills=[
                NormalizedSkill(
                    raw_name="new trade", evidence_phrase="I do the new trade",
                    skill_id=99, code="SK999", name="New Trade",
                )
            ]
        )
        result = explain_offline(score_one(profile, scheme), language="ta")
        assert result.bullets
