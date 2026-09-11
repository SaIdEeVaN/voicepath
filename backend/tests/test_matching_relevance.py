"""A score has to mean something (spec sections 4.4 and 8).

Reported from the deployed app: *"I was a carpenter for 3 years"* returned
Pharma Business at 95, Plumbing Works at 95, and a welding course at 91 — while
the explanations underneath correctly said there was no connection between
carpentry and any of them. The reasoning knew; the number did not.

Reproduced against the live catalogue, and it was two separate defects.

**A scheme that asks for nothing scored full marks.** `skill_similarity`
returned 1.0 when `required_skills` was empty, on the reasoning that "nothing
asked for cannot be unmet". That was fair when every scheme was seeded with its
skills, and false the moment the admin form — which has no field for skills —
created one. Both 95s were admin-created schemes with zero requirements, and
they will always outrank a real match: 0.50 + 0.25 + 0.15 + 0.05 = 0.95.

Asking for nothing is not evidence of fit. It is the absence of evidence, and
this file pins it to the neutral value the other unknowns already use.

**The similarity floor was far below the model's noise floor.** Measured over
this catalogue with `multilingual-e5-base`, cosine from Carpentry to every
required skill runs 0.853 (Engine Diagnostics) to 0.921 (Welding) — a spread of
0.068 across twenty-two unrelated trades, with Retail Sales at 0.918 essentially
tied with Welding. There is no signal in that band. A genuine match separates
cleanly: Two-Wheeler Repair scores 1.000 against itself, 0.947 against
Four-Wheeler Repair, then falls to 0.84-0.89 for everything else.

The code admitted anything above **0.55** and paid it `weight * similarity`, so
an unrelated trade collected 85-92% of the weight. Similarity is rescaled
against the measured floor now, so the noise band pays nothing and only real
proximity survives.
"""

from __future__ import annotations

import math

import pytest

from app.services.matching import ProfileInput, score_one, skill_similarity
from app.services.normalization import NormalizedSkill
from app.services.schemes import RequiredSkill, Scheme


def _unit(angle_degrees: float) -> list[float]:
    """A 2-D unit vector. Cosine between two of these is cos(difference)."""
    radians = math.radians(angle_degrees)
    return [math.cos(radians), math.sin(radians)]


def _scheme(required: list[RequiredSkill], **overrides) -> Scheme:
    defaults = dict(
        id=1,
        title="Test scheme",
        organization="Test org",
        location="Salem",
        district="Salem",
        type="Full-time",
        minimum_experience=0.0,
        certifications_required=[],
        salary_min=None,
        salary_max=None,
        nsqf_level=None,
        source_reference=None,
        description="",
        required_skills=required,
    )
    defaults.update(overrides)
    return Scheme(**defaults)


def _profile(skills: list[NormalizedSkill], **overrides) -> ProfileInput:
    defaults = dict(
        experience_years=3.0,
        location="Salem",
        district="Salem",
        certifications=[],
        skills=skills,
    )
    defaults.update(overrides)
    return ProfileInput(**defaults)


def _owned(skill_id: int, code: str, embedding: list[float]) -> NormalizedSkill:
    return NormalizedSkill(
        raw_name=code.lower(),
        evidence_phrase="said so",
        skill_id=skill_id,
        code=code,
        name=code,
        confidence=1.0,
        embedding=embedding,
    )


class TestAskingForNothingIsNotAPerfectMatch:
    def test_a_scheme_with_no_requirements_does_not_score_full_marks(self):
        empty = _scheme([])
        result = score_one(_profile([_owned(1, "SK001", _unit(0))]), empty)

        assert result.skill_similarity_score < 1.0, (
            "a scheme that asks for nothing gives no evidence of fit"
        )

    def test_it_cannot_outrank_a_scheme_the_person_actually_matches(self):
        """The reported bug, at its smallest."""
        carpenter = _owned(42, "SK042", _unit(0))

        exact = _scheme(
            [RequiredSkill(skill_id=42, code="SK042", name="Carpentry",
                           weight=1.0, is_essential=True, embedding=_unit(0))]
        )
        asks_nothing = _scheme([], id=2)

        matched = score_one(_profile([carpenter]), exact)
        empty = score_one(_profile([carpenter]), asks_nothing)

        assert matched.overall_score > empty.overall_score, (
            "a scheme requiring the person's own trade must beat one that "
            "lists no skills at all"
        )


class TestTheNoiseBandPaysNothing:
    def test_an_exact_taxonomy_match_still_scores_full(self):
        owned = _owned(1, "SK001", _unit(0))
        scheme = _scheme(
            [RequiredSkill(skill_id=1, code="SK001", name="Two-Wheeler Repair",
                           weight=1.0, is_essential=True, embedding=_unit(0))]
        )

        score, matched = skill_similarity(_profile([owned]), scheme)

        assert score == 1.0
        assert "SK001" in matched

    def test_an_unrelated_trade_earns_nothing(self):
        """Carpentry against Welding measured 0.9207 -- inside the noise band,
        and indistinguishable from Retail Sales at 0.9183."""
        # ~0.92 cosine: the measured distance between two unrelated trades.
        owned = _owned(42, "SK042", _unit(0))
        unrelated = _scheme(
            [RequiredSkill(skill_id=22, code="SK022", name="Welding",
                           weight=1.0, is_essential=True,
                           embedding=_unit(23.07))]
        )

        score, matched = skill_similarity(_profile([owned]), unrelated)

        assert score < 0.15, f"unrelated trade still collected {score}"
        assert matched == [], "noise must not be reported as a matched skill"

    def test_a_genuinely_related_skill_still_earns_something(self):
        """Two-Wheeler to Four-Wheeler Repair measured 0.947, which is real
        transferable skill and must survive the rescaling."""
        owned = _owned(1, "SK001", _unit(0))
        related = _scheme(
            [RequiredSkill(skill_id=2, code="SK002", name="Four-Wheeler Repair",
                           weight=1.0, is_essential=True,
                           embedding=_unit(18.66))]
        )

        score, _ = skill_similarity(_profile([owned]), related)

        assert score > 0.0, "a real neighbouring trade should not be zeroed"
        assert score < 1.0, "nor should it read as the same trade"

    def test_related_beats_unrelated(self):
        """The property the whole rescaling exists for: the order is right."""
        owned = _owned(1, "SK001", _unit(0))

        related, _ = skill_similarity(
            _profile([owned]),
            _scheme([RequiredSkill(skill_id=2, code="SK002", name="Four-Wheeler",
                                   weight=1.0, is_essential=True,
                                   embedding=_unit(18.66))]),
        )
        unrelated, _ = skill_similarity(
            _profile([owned]),
            _scheme([RequiredSkill(skill_id=9, code="SK009", name="Retail",
                                   weight=1.0, is_essential=True,
                                   embedding=_unit(23.07))]),
        )

        assert related > unrelated


class TestScoresStillSpanTheirRange:
    def test_a_person_who_matches_nothing_does_not_score_high(self):
        """The user's actual complaint: every result sat at 86-95."""
        carpenter = _owned(42, "SK042", _unit(0))
        nothing_in_common = _scheme(
            [RequiredSkill(skill_id=22, code="SK022", name="Welding",
                           weight=1.0, is_essential=True,
                           embedding=_unit(23.07))],
            minimum_experience=0.0,
        )

        result = score_one(_profile([carpenter]), nothing_in_common)

        # Experience, eligibility and location can still contribute; the skill
        # half must not. 0.25 + 0.15 + 0.10 = 0.50 is the ceiling with the
        # skill term at zero.
        assert result.overall_score <= 0.55, (
            f"a total mismatch still scored {result.overall_score}"
        )


class TestWhetherAResultIsWorthShowing:
    """`skill_evidence` separates "this fits your trade" from "this does not
    exclude you".

    A carpenter was shown Pharma Business at the top of the results because it
    declared no skills and so could not be ruled out. The score was honest --
    experience, eligibility and location genuinely did fit -- but the page was
    not, because none of that is why someone comes here. They come to be
    matched on the work they have done.

    The flag is computed where the knowledge is, in matching, and says only
    whether the skill term was *earned* rather than defaulted. What to do with
    a result that lacks it is the interface's decision.
    """

    def test_a_scheme_requiring_the_persons_trade_has_evidence(self):
        owned = _owned(1, "SK001", _unit(0))
        scheme = _scheme(
            [RequiredSkill(skill_id=1, code="SK001", name="Two-Wheeler Repair",
                           weight=1.0, is_essential=True, embedding=_unit(0))]
        )

        assert score_one(_profile([owned]), scheme).skill_evidence is True

    def test_a_scheme_that_declares_nothing_has_none(self):
        """It cannot be ruled out, which is not the same as fitting."""
        owned = _owned(1, "SK001", _unit(0))

        result = score_one(_profile([owned]), _scheme([]))

        assert result.skill_evidence is False
        # The score is still what it is -- the flag does not rewrite it.
        assert result.skill_similarity_score == 0.5

    def test_an_unrelated_trade_has_none(self):
        owned = _owned(42, "SK042", _unit(0))
        unrelated = _scheme(
            [RequiredSkill(skill_id=22, code="SK022", name="Welding",
                           weight=1.0, is_essential=True,
                           embedding=_unit(23.07))]
        )

        assert score_one(_profile([owned]), unrelated).skill_evidence is False

    def test_partial_credit_counts_as_evidence(self):
        """A neighbouring trade is a real reason to show someone a listing,
        even though it is not close enough to name in an explanation."""
        owned = _owned(1, "SK001", _unit(0))
        related = _scheme(
            [RequiredSkill(skill_id=2, code="SK002", name="Four-Wheeler Repair",
                           weight=1.0, is_essential=True,
                           embedding=_unit(18.66))]
        )

        result = score_one(_profile([owned]), related)

        assert result.skill_evidence is True
        assert result.matched_skill_codes == [], (
            "close enough to show, not close enough to claim"
        )
