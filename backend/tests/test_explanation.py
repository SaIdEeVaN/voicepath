"""PRD section 4.5: the explanation layer explains a ranking that already
exists. It must never alter the ranking, and never imply eligibility the data
does not support."""

from __future__ import annotations

import pytest

from app.services import explanation
from app.services.explanation import explain_offline
from app.services.matching import ProfileInput, rank, score_one
from app.services.normalization import NormalizedSkill
from app.services.schemes import Scheme, RequiredSkill


def scheme(**overrides) -> Scheme:
    defaults = dict(
        id=1, title="Two-Wheeler Service Technician", organization="Ratnam Auto Works",
        location="Salem", district="Salem", type="Full-time", minimum_experience=2.0,
        certifications_required=[], salary_min=14000, salary_max=18000,
        nsqf_level="4", source_reference="OGD/TEST/1", description="Bike repair.",
        required_skills=[
            RequiredSkill(1, "SK001", "Two-Wheeler Repair", 1.0, True)
        ],
    )
    defaults.update(overrides)
    return Scheme(**defaults)


def profile(**overrides) -> ProfileInput:
    defaults = dict(
        experience_years=6.0, location="Salem", district="Salem", certifications=[],
        skills=[
            NormalizedSkill(
                raw_name="bike repair",
                evidence_phrase="I have been repairing bikes for six years",
                skill_id=1, code="SK001", name="Two-Wheeler Repair",
            )
        ],
    )
    defaults.update(overrides)
    return ProfileInput(**defaults)


class TestCannotReRank:
    @pytest.mark.asyncio
    async def test_explaining_does_not_change_scores_or_order(self):
        catalogue = [
            scheme(id=1),
            scheme(id=2, minimum_experience=10.0),
            scheme(id=3, location="Erode", district="Erode"),
        ]
        ranked = rank(profile(), catalogue)
        before = [(m.scheme.id, m.rank, m.overall_score) for m in ranked]

        await explanation.explain_many(ranked, language="en")

        after = [(m.scheme.id, m.rank, m.overall_score) for m in ranked]
        assert before == after

    @pytest.mark.asyncio
    async def test_explanation_returns_text_only(self):
        """There is no field an explanation could put a score into."""
        result = await explanation.explain(score_one(profile(), scheme()))
        assert set(vars(result)) == {"bullets", "summary", "provider"}
        assert all(isinstance(b, str) for b in result.bullets)
        assert isinstance(result.summary, str)


class TestGroundedCopy:
    def test_names_a_skill_the_person_actually_has(self):
        result = explain_offline(score_one(profile(), scheme()), language="en")
        joined = " ".join(result.bullets)
        assert "Two-Wheeler Repair" in joined

    def test_states_the_missing_certificate_rather_than_glossing_it(self):
        """The uncomfortable fact is the most useful sentence on the card."""
        match = score_one(
            profile(), scheme(certifications_required=["LMV Driving Licence"])
        )
        result = explain_offline(match, language="en")
        assert any("LMV Driving Licence" in b for b in result.bullets)

    def test_says_when_the_place_is_far(self):
        match = score_one(
            profile(location="Salem", district="Salem"),
            scheme(location="Erode", district="Erode"),
        )
        result = explain_offline(match, language="en")
        assert any("Erode" in b for b in result.bullets)

    def test_never_promises_selection_or_eligibility(self):
        forbidden = [
            "you are eligible", "you qualify", "you will be selected",
            "guaranteed", "you will get", "certain to",
        ]
        for opp in (
            scheme(),
            scheme(certifications_required=["Trade Certificate"]),
            scheme(minimum_experience=20.0),
            scheme(type="Training", salary_min=3000, salary_max=3000),
        ):
            result = explain_offline(score_one(profile(), opp), language="en")
            text = " ".join([*result.bullets, result.summary]).lower()
            for phrase in forbidden:
                assert phrase not in text, f"{phrase!r} appeared in: {text}"

    def test_no_jargon_reaches_the_user(self):
        """Section 2: no NSQF levels, no raw scores in user-facing copy."""
        for language in ("en", "hi", "ta"):
            result = explain_offline(score_one(profile(), scheme()), language=language)
            text = " ".join([*result.bullets, result.summary]).lower()
            for term in ("nsqf", "vector", "embedding", "cosine", "score", "sk001"):
                assert term not in text

    def test_weak_match_summary_is_honest(self):
        match = score_one(
            profile(experience_years=0.0, location="Kolkata", district="Kolkata"),
            scheme(
                minimum_experience=10.0,
                certifications_required=["Trade Certificate"],
                required_skills=[RequiredSkill(99, "SK051", "Tailoring", 1.0, True)],
            ),
        )
        result = explain_offline(match, language="en")
        assert match.overall_score < 0.6
        assert "further" in result.summary.lower()


class TestLanguages:
    @pytest.mark.parametrize("language", ["en", "hi", "ta"])
    def test_every_language_produces_copy(self, language):
        result = explain_offline(score_one(profile(), scheme()), language=language)
        assert result.bullets
        assert result.summary

    def test_unknown_language_falls_back_to_english(self):
        result = explain_offline(score_one(profile(), scheme()), language="fr")
        assert result.bullets

    def test_tamil_copy_is_actually_tamil(self):
        result = explain_offline(score_one(profile(), scheme()), language="ta")
        joined = "".join(result.bullets)
        assert any("஀" <= ch <= "௿" for ch in joined)

    def test_hindi_copy_is_actually_hindi(self):
        result = explain_offline(score_one(profile(), scheme()), language="hi")
        joined = "".join(result.bullets)
        assert any("ऀ" <= ch <= "ॿ" for ch in joined)
