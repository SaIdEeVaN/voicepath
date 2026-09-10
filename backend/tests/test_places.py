"""Place names, across scripts and grammatical cases.

Extraction returns the person's own words, so a Tamil speaker's location
arrives as "சேலத்துல" while the catalogue says "Salem". Before these were
reconciled, a person standing in Salem scored as far from a Salem opening as
someone in another state, and the explanation layer told them so.
"""

from __future__ import annotations

import pytest

from app.services import matching
from app.services.matching import ProfileInput, canonical_place, score_one
from app.services.normalization import NormalizedSkill
from app.services.opportunities import Opportunity, RequiredSkill


class TestCanonicalPlace:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("Salem", "salem"),
            ("salem", "salem"),
            ("  SALEM  ", "salem"),
            ("சேலம்", "salem"),
            ("சேலத்துல", "salem"),      # Tamil locative: "in Salem"
            ("சேலத்தில", "salem"),
            ("सेलम", "salem"),
            ("Erode", "erode"),
            ("ஈரோடு", "erode"),
            ("Attur", "attur"),
            ("ஆத்தூர்", "attur"),
            ("Salem, Tamil Nadu", "salem"),
            ("Salem (Tamil Nadu)", "salem"),
        ],
    )
    def test_every_form_reaches_one_key(self, value, expected):
        assert canonical_place(value) == expected

    def test_unknown_place_is_returned_folded(self):
        assert canonical_place("Kolkata") == "kolkata"

    def test_empty_input_is_empty(self):
        assert canonical_place(None) == ""
        assert canonical_place("   ") == ""

    def test_short_coincidental_prefixes_do_not_collide(self):
        """"Sal" is too short to mean Salem."""
        assert canonical_place("Sal") != "salem"

    def test_two_different_towns_stay_different(self):
        assert canonical_place("Salem") != canonical_place("Erode")


def _opportunity(**overrides) -> Opportunity:
    defaults = dict(
        id=1, title="Welder", organization="Annai Steel", location="Salem",
        district="Salem", type="Full-time", minimum_experience=1,
        certifications_required=[], salary_min=16000, salary_max=21000,
        nsqf_level="4", source_reference="OGD/TEST", description="Welding.",
        required_skills=[RequiredSkill(6, "SK022", "Welding", 1.0, True)],
    )
    defaults.update(overrides)
    return Opportunity(**defaults)


def _profile(location: str | None) -> ProfileInput:
    return ProfileInput(
        experience_years=6.0,
        location=location,
        district=location,
        certifications=[],
        skills=[
            NormalizedSkill(
                raw_name="welding", evidence_phrase="வெல்டிங் கொஞ்சம் தெரியும்",
                skill_id=6, code="SK022", name="Welding",
            )
        ],
    )


class TestLocationScoringAcrossScripts:
    @pytest.mark.parametrize("said", ["Salem", "சேலம்", "சேலத்துல", "सेलम"])
    def test_saying_where_you_are_in_any_script_scores_as_here(self, said):
        result = score_one(_profile(said), _opportunity())
        assert result.location_score == matching.LOCATION_SAME_PLACE

    def test_a_town_in_the_district_is_near_not_far(self):
        result = score_one(_profile("ஆத்தூர்"), _opportunity())
        assert result.location_score == matching.LOCATION_SAME_DISTRICT

    def test_a_neighbouring_district_scores_between(self):
        result = score_one(_profile("ஈரோடு"), _opportunity())
        assert result.location_score == matching.LOCATION_ADJACENT_DISTRICT

    def test_somewhere_genuinely_far_still_scores_low(self):
        result = score_one(_profile("Kolkata"), _opportunity())
        assert result.location_score == matching.LOCATION_ELSEWHERE

    def test_the_explanation_does_not_call_home_far_away(self):
        """The bug this guards: telling someone in Salem that a Salem job is
        away from where they are."""
        from app.services.explanation import explain_offline

        match = score_one(_profile("சேலத்துல"), _opportunity())
        bullets = " ".join(explain_offline(match, language="ta").bullets)
        assert "தூரம்" not in bullets, "called a local opening distant"
