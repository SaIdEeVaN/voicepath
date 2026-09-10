"""The matching engine is the part of the system that must never surprise
anyone: the same person against the same catalogue has to produce the same
ranking, and the weights have to be the weights the PRD states."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.services import matching
from app.services.matching import ProfileInput, rank, score_one
from app.services.normalization import NormalizedSkill
from app.services.opportunities import Opportunity, RequiredSkill


def make_opportunity(**overrides) -> Opportunity:
    defaults = dict(
        id=1,
        title="Two-Wheeler Service Technician",
        organization="Ratnam Auto Works",
        location="Salem",
        district="Salem",
        type="Full-time",
        minimum_experience=2.0,
        certifications_required=[],
        salary_min=14000,
        salary_max=18000,
        nsqf_level="4",
        source_reference="OGD/TEST/1",
        description="Bike repair.",
        required_skills=[
            RequiredSkill(skill_id=1, code="SK001", name="Two-Wheeler Repair",
                          weight=1.0, is_essential=True),
        ],
    )
    defaults.update(overrides)
    return Opportunity(**defaults)


def make_profile(**overrides) -> ProfileInput:
    defaults = dict(
        experience_years=6.0,
        location="Salem",
        district="Salem",
        certifications=[],
        skills=[
            NormalizedSkill(
                raw_name="bike repair",
                evidence_phrase="I have been repairing bikes for six years",
                skill_id=1,
                code="SK001",
                name="Two-Wheeler Repair",
            )
        ],
    )
    defaults.update(overrides)
    return ProfileInput(**defaults)


class TestWeights:
    def test_weights_are_the_prd_weights(self):
        settings = get_settings()
        assert settings.weight_skill == 0.50
        assert settings.weight_experience == 0.25
        assert settings.weight_eligibility == 0.15
        assert settings.weight_location == 0.10

    def test_perfect_profile_scores_one(self):
        result = score_one(make_profile(), make_opportunity())
        assert result.overall_score == pytest.approx(1.0)

    def test_overall_is_the_weighted_sum(self):
        """Each component contributes exactly its stated share, nothing else."""
        result = score_one(
            make_profile(experience_years=1.0, location="Chennai", district="Chennai"),
            make_opportunity(certifications_required=["Trade Certificate"]),
        )
        expected = (
            result.skill_similarity_score * 0.50
            + result.experience_score * 0.25
            + result.eligibility_score * 0.15
            + result.location_score * 0.10
        )
        assert result.overall_score == pytest.approx(round(expected, 4), abs=1e-4)


class TestExperience:
    def test_meeting_the_minimum_is_full_marks(self):
        result = score_one(make_profile(experience_years=2.0), make_opportunity())
        assert result.experience_score == 1.0

    def test_exceeding_the_minimum_is_not_extra_credit(self):
        two = score_one(make_profile(experience_years=2.0), make_opportunity())
        twenty = score_one(make_profile(experience_years=20.0), make_opportunity())
        assert two.experience_score == twenty.experience_score == 1.0

    def test_falling_short_scales_rather_than_disqualifies(self):
        result = score_one(make_profile(experience_years=1.0), make_opportunity())
        assert result.experience_score == pytest.approx(0.5)

    def test_no_minimum_means_no_barrier(self):
        result = score_one(
            make_profile(experience_years=None), make_opportunity(minimum_experience=0)
        )
        assert result.experience_score == 1.0

    def test_unstated_experience_is_neither_credited_nor_punished(self):
        """Not mentioning years must not bury someone who has them."""
        result = score_one(make_profile(experience_years=None), make_opportunity())
        assert result.experience_score == matching.EXPERIENCE_UNKNOWN


class TestEligibility:
    def test_nothing_required_is_fully_met(self):
        result = score_one(make_profile(), make_opportunity(certifications_required=[]))
        assert result.eligibility_score == 1.0

    def test_unstated_certificate_is_not_assumed(self):
        """The section 7 rule, applied to scoring: silence is not a yes."""
        result = score_one(
            make_profile(certifications=[]),
            make_opportunity(certifications_required=["LMV Driving Licence"]),
        )
        assert result.eligibility_score == 0.0

    def test_held_certificate_counts(self):
        result = score_one(
            make_profile(certifications=["LMV Driving Licence"]),
            make_opportunity(certifications_required=["LMV Driving Licence"]),
        )
        assert result.eligibility_score == 1.0

    def test_partial_credit_for_some_of_several(self):
        result = score_one(
            make_profile(certifications=["LMV Driving Licence"]),
            make_opportunity(
                certifications_required=["LMV Driving Licence", "Trade Certificate"]
            ),
        )
        assert result.eligibility_score == pytest.approx(0.5)


class TestLocation:
    def test_same_place_is_best(self):
        result = score_one(make_profile(location="Salem"), make_opportunity())
        assert result.location_score == matching.LOCATION_SAME_PLACE

    def test_town_inside_the_district_counts_as_district(self):
        result = score_one(
            make_profile(location="Attur", district="Attur"),
            make_opportunity(location="Salem", district="Salem"),
        )
        assert result.location_score == matching.LOCATION_SAME_DISTRICT

    def test_adjacent_district_scores_between(self):
        result = score_one(
            make_profile(location="Salem", district="Salem"),
            make_opportunity(location="Erode", district="Erode"),
        )
        assert result.location_score == matching.LOCATION_ADJACENT_DISTRICT

    def test_unknown_location_sits_in_the_middle(self):
        result = score_one(
            make_profile(location=None, district=None), make_opportunity()
        )
        assert result.location_score == matching.LOCATION_UNKNOWN

    def test_far_away_scores_lowest(self):
        result = score_one(
            make_profile(location="Kolkata", district="Kolkata"), make_opportunity()
        )
        assert result.location_score == matching.LOCATION_ELSEWHERE


class TestSkillSimilarity:
    def test_exact_taxonomy_match_is_full_credit(self):
        result = score_one(make_profile(), make_opportunity())
        assert result.skill_similarity_score == 1.0
        assert "SK001" in result.matched_skill_codes

    def test_unrelated_skills_earn_nothing(self):
        profile = make_profile(
            skills=[
                NormalizedSkill(
                    raw_name="tailoring", evidence_phrase="I stitch clothes",
                    skill_id=99, code="SK051", name="Tailoring",
                )
            ]
        )
        result = score_one(profile, make_opportunity())
        assert result.skill_similarity_score == 0.0

    def test_coverage_is_of_the_requirement_not_the_person(self):
        """Twenty irrelevant skills must not beat one relevant skill."""
        focused = make_profile()
        scattered = make_profile(
            skills=[
                focused.skills[0],
                *[
                    NormalizedSkill(
                        raw_name=f"other {i}", evidence_phrase="said it",
                        skill_id=500 + i, code=f"SK5{i:02d}", name=f"Other {i}",
                    )
                    for i in range(20)
                ],
            ]
        )
        assert (
            score_one(focused, make_opportunity()).skill_similarity_score
            == score_one(scattered, make_opportunity()).skill_similarity_score
        )

    def test_essential_skill_carries_more_weight(self):
        opportunity = make_opportunity(
            required_skills=[
                RequiredSkill(1, "SK001", "Two-Wheeler Repair", 1.0, True),
                RequiredSkill(2, "SK108", "Customer Handling", 0.4, False),
            ]
        )
        result = score_one(make_profile(), opportunity)
        # 1.0 of 1.4 available weight.
        assert result.skill_similarity_score == pytest.approx(1.0 / 1.4, abs=1e-3)

    def test_no_requirements_cannot_be_unmet(self):
        result = score_one(make_profile(), make_opportunity(required_skills=[]))
        assert result.skill_similarity_score == 1.0


class TestRanking:
    def _catalogue(self) -> list[Opportunity]:
        return [
            make_opportunity(id=1),
            make_opportunity(id=2, minimum_experience=10.0),
            make_opportunity(id=3, location="Erode", district="Erode"),
            make_opportunity(
                id=4,
                required_skills=[
                    RequiredSkill(99, "SK051", "Tailoring", 1.0, True)
                ],
            ),
        ]

    def test_ranking_is_descending_and_numbered_from_one(self):
        ranked = rank(make_profile(), self._catalogue())
        assert [m.rank for m in ranked] == [1, 2, 3, 4]
        scores = [m.overall_score for m in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_ranking_is_deterministic(self):
        """Run it ten times, get the same answer ten times.

        This is what lets the explanation layer be constrained to describing a
        result: if the ranking could drift, the constraint would be untestable.
        """
        profile = make_profile()
        catalogue = self._catalogue()
        first = [(m.opportunity.id, m.overall_score) for m in rank(profile, catalogue)]
        for _ in range(9):
            assert [
                (m.opportunity.id, m.overall_score) for m in rank(profile, catalogue)
            ] == first

    def test_ties_break_on_id_so_order_is_stable(self):
        catalogue = [make_opportunity(id=7), make_opportunity(id=3)]
        ranked = rank(make_profile(), catalogue)
        assert ranked[0].overall_score == ranked[1].overall_score
        assert [m.opportunity.id for m in ranked] == [3, 7]

    def test_limit_truncates_after_ranking_not_before(self):
        ranked = rank(make_profile(), self._catalogue(), limit=2)
        assert len(ranked) == 2
        assert [m.rank for m in ranked] == [1, 2]

    def test_no_llm_is_involved(self, monkeypatch):
        """Ranking must work with the LLM module made unusable."""
        import app.services.llm as llm_module

        def explode(*args, **kwargs):
            raise AssertionError("matching must not call the LLM")

        monkeypatch.setattr(llm_module, "complete_json", explode)
        monkeypatch.setattr(llm_module, "complete_text", explode)
        ranked = rank(make_profile(), self._catalogue())
        assert ranked[0].rank == 1


class TestGrounding:
    def test_grounding_names_only_stored_facts(self):
        result = score_one(make_profile(), make_opportunity())
        grounding = result.grounding
        assert grounding["experience_years"] == 6.0
        assert grounding["user_location"] == "Salem"
        assert "Two-Wheeler Repair" in grounding["matched_skill_names"]
        assert grounding["missing_certifications"] == []

    def test_missing_certificate_is_recorded_for_the_explanation(self):
        result = score_one(
            make_profile(),
            make_opportunity(certifications_required=["LMV Driving Licence"]),
        )
        assert result.grounding["missing_certifications"] == ["LMV Driving Licence"]
