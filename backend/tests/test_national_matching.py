"""Scoring national schemes: one trade is enough, and they are open everywhere.

Two rules added with the national schemes on 2026-11-04, and the reason for
each:

* **skill_match "any".** PM Vishwakarma covers eighteen trades. Scored as
  coverage of all of them, a tailor earned 1/18 of the skill term, fell under
  the evidence threshold and never saw the scheme made for her trade.
* **Nationwide location.** "All India" is not a town; scored as one, every
  national scheme was "elsewhere" for everyone.

And one guard against what the first version did: generic schemes -- "open to
any trade" -- tied with one another for everyone and pushed a welder's own
local job off the first page. They now score below a trade-specific match and
at most three of them make the list.
"""

from __future__ import annotations

from app.services.explanation import explain_offline
from app.services.matching import (
    LOCATION_ELSEWHERE,
    LOCATION_NATIONWIDE,
    MAX_OPEN_TO_ANY_TRADE,
    ProfileInput,
    location_score,
    rank,
    score_one,
)
from app.services.normalization import NormalizedSkill
from app.services.schemes import RequiredSkill, Scheme

TAILORING = RequiredSkill(51, "SK051", "Tailoring", 1.0, False)
CARPENTRY = RequiredSkill(42, "SK042", "Carpentry", 1.0, False)
WELDING = RequiredSkill(22, "SK022", "Welding", 1.0, True)


def scheme(id: int, **overrides) -> Scheme:
    values = {
        "id": id, "title": f"Scheme {id}", "organization": "Ministry",
        "location": "All India", "district": "All India", "type": "Training",
        "minimum_experience": 0.0, "certifications_required": [], "salary_min": None,
        "salary_max": None, "nsqf_level": None, "source_reference": f"GOI/TEST/{id}",
        "description": "Official text.", "required_skills": [], "skill_match": "any",
    }
    values.update(overrides)
    return Scheme(**values)


def person(code: str, skill_id: int, name: str, *, location: str | None = "Madurai"):
    return ProfileInput(
        experience_years=4.0, location=location, district=location,
        skills=[NormalizedSkill(raw_name=name.lower(), evidence_phrase=f"I do {name}",
                                skill_id=skill_id, code=code, name=name)],
    )


def vishwakarma() -> Scheme:
    trades = [TAILORING, CARPENTRY] + [
        RequiredSkill(200 + i, f"SK2{i:02d}", f"Trade {i}", 1.0, False) for i in range(16)
    ]
    return scheme(1, title="PM Vishwakarma", type="Self-employment support",
                  required_skills=trades)


def generic(id: int, *codes: tuple[int, str, str]) -> Scheme:
    return scheme(id, required_skills=[
        RequiredSkill(skill_id, code, name, 0.4, False) for skill_id, code, name in codes
    ])


class TestOneTradeIsEnough:
    def test_a_tailor_fits_a_scheme_that_names_tailoring_fully(self):
        match = score_one(person("SK051", 51, "Tailoring"), vishwakarma())
        assert match.skill_similarity_score == 1.0
        assert match.skill_evidence
        assert match.matched_skill_codes == ["SK051"]

    def test_under_coverage_she_would_have_been_filtered_out(self):
        all_mode = vishwakarma()
        all_mode.skill_match = "all"
        match = score_one(person("SK051", 51, "Tailoring"), all_mode)
        assert match.skill_similarity_score < 0.1

    def test_a_trade_it_does_not_name_earns_nothing(self):
        match = score_one(person("SK022", 22, "Welding"), vishwakarma())
        assert match.skill_similarity_score == 0.0
        assert not match.skill_evidence

    def test_open_to_any_trade_earns_less_and_claims_nothing(self):
        match = score_one(person("SK022", 22, "Welding"),
                          generic(2, (22, "SK022", "Welding"), (51, "SK051", "Tailoring")))
        assert match.skill_similarity_score == 0.4
        assert match.skill_evidence
        # Not "this was made for welders" -- it was made for everyone.
        assert match.matched_skill_codes == []
        assert match.grounding["open_to_any_trade"] is True


class TestOpenEverywhere:
    def test_a_national_scheme_is_as_near_as_the_persons_district(self):
        assert location_score(person("SK051", 51, "Tailoring"), vishwakarma()) == (
            LOCATION_NATIONWIDE
        )

    def test_whether_or_not_they_said_where_they_are(self):
        nowhere = person("SK051", 51, "Tailoring", location=None)
        assert location_score(nowhere, vishwakarma()) == LOCATION_NATIONWIDE

    def test_a_local_opening_elsewhere_is_still_elsewhere(self):
        local = scheme(3, location="Salem", district="Salem", skill_match="all")
        assert location_score(person("SK051", 51, "Tailoring"), local) == LOCATION_ELSEWHERE


class TestTheFirstPageStaysUseful:
    def welder_job(self) -> Scheme:
        return scheme(10, title="Welder", location="Madurai", district="Madurai",
                      type="Full-time", skill_match="all",
                      required_skills=[WELDING, RequiredSkill(25, "SK025", "Sheet Metal", 0.7, True)])

    def test_a_partial_match_in_their_own_trade_outranks_any_generic_scheme(self):
        welder = person("SK022", 22, "Welding")
        generics = [generic(20 + i, (22, "SK022", "Welding")) for i in range(6)]
        ranked = rank(welder, [*generics, self.welder_job()])
        assert ranked[0].scheme.title == "Welder"

    def test_at_most_a_few_generic_schemes_are_listed(self):
        welder = person("SK022", 22, "Welding")
        generics = [generic(20 + i, (22, "SK022", "Welding")) for i in range(8)]
        ranked = rank(welder, [*generics, self.welder_job()], limit=8)
        open_to_any = [m for m in ranked if m.grounding["open_to_any_trade"]]
        assert len(open_to_any) == MAX_OPEN_TO_ANY_TRADE
        # Stable: the first ones by id, every time.
        assert [m.scheme.id for m in open_to_any] == [20, 21, 22]

    def test_a_scheme_that_names_their_trade_is_not_capped(self):
        tailor = person("SK051", 51, "Tailoring")
        named = [scheme(30 + i, required_skills=[TAILORING]) for i in range(5)]
        ranked = rank(tailor, named, limit=8)
        assert len(ranked) == 5


class TestWhatTheExplanationSays:
    def test_a_national_scheme_says_so_instead_of_a_distance(self):
        match = score_one(person("SK051", 51, "Tailoring"), vishwakarma())
        bullets = explain_offline(match, language="en").bullets
        assert "It is a national scheme, open across India." in bullets
        assert not any("away from where you are" in b for b in bullets)

    def test_a_generic_scheme_never_claims_to_be_for_their_trade(self):
        match = score_one(person("SK022", 22, "Welding"), generic(2, (22, "SK022", "Welding")))
        bullets = explain_offline(match, language="en").bullets
        assert "It is open to many trades, not one in particular." in bullets
        assert not any("that is what this work is" in b for b in bullets)

    def test_both_sentences_exist_in_tamil_and_hindi(self):
        match = score_one(person("SK022", 22, "Welding"), generic(2, (22, "SK022", "Welding")))
        for language in ("ta", "hi"):
            bullets = explain_offline(match, language=language).bullets
            assert len(bullets) >= 2
            assert not any("open" in b for b in bullets)  # translated, not English
