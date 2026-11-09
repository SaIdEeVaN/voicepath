"""Jobs, training and schemes: three kinds, their details, their weights.

Decided 2026-11-09: one table with a kind that follows from the type, details
of that kind taken only from what a listing states, and the four scoring
terms weighed per kind.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.data.catalogue import DETAILS, SCHEMES
from app.main import app
from app.routes.admin import SchemeWrite, _kind_and_details
from app.services import kinds
from app.services.matching import ProfileInput, score_one
from app.services.normalization import NormalizedSkill
from app.services.schemes import RequiredSkill, Scheme

MIGRATION = Path(__file__).resolve().parents[2] / "db" / "014_scheme_kinds.sql"


class TestTheKind:
    @pytest.mark.parametrize("scheme_type, kind", [
        ("Full-time", "job"), ("Part-time", "job"),
        ("Training", "training"), ("Apprenticeship", "training"),
        ("Self-employment support", "scheme"), ("Something new", "scheme"),
    ])
    def test_it_follows_from_the_type(self, scheme_type, kind):
        assert kinds.kind_for_type(scheme_type) == kind

    def test_a_scheme_built_anywhere_gets_its_kind(self):
        built = Scheme(id=1, title="t", organization="o", location="Salem", district="Salem",
                       type="Training", minimum_experience=0, certifications_required=[],
                       salary_min=None, salary_max=None, nsqf_level=None,
                       source_reference=None, description=None)
        assert built.kind == "training"

    def test_the_catalogue_has_all_three(self):
        found = {kinds.kind_for_type(s["type"]) for s in SCHEMES}
        assert found == {"job", "training", "scheme"}


class TestTheWeights:
    @pytest.mark.parametrize("kind", kinds.KINDS)
    def test_each_set_sums_to_one(self, kind):
        assert abs(sum(kinds.WEIGHTS[kind].values()) - 1.0) < 1e-9

    def test_training_weighs_distance_most_after_skill(self):
        w = kinds.WEIGHTS["training"]
        assert w["location"] > w["eligibility"] > w["experience"]

    def test_a_job_weighs_experience_more_than_a_course(self):
        assert kinds.WEIGHTS["job"]["experience"] > kinds.WEIGHTS["training"]["experience"]

    def test_a_scheme_weighs_eligibility_most_after_skill(self):
        w = kinds.WEIGHTS["scheme"]
        assert w["eligibility"] > w["experience"] and w["eligibility"] > w["location"]

    def test_the_same_person_scores_differently_by_kind(self):
        def scheme(scheme_type):
            return Scheme(id=1, title="t", organization="o", location="Erode", district="Erode",
                          type=scheme_type, minimum_experience=5, certifications_required=[],
                          salary_min=None, salary_max=None, nsqf_level=None,
                          source_reference=None, description=None,
                          required_skills=[RequiredSkill(1, "SK022", "Welding", 1.0, True)])
        person = ProfileInput(
            experience_years=0, location="Chennai", district="Chennai", certifications=[],
            skills=[NormalizedSkill(raw_name="welding", evidence_phrase="I weld",
                                    skill_id=1, code="SK022", name="Welding")],
        )
        job, course = score_one(person, scheme("Full-time")), score_one(person, scheme("Training"))
        assert job.weights == kinds.WEIGHTS["job"]
        assert course.weights == kinds.WEIGHTS["training"]
        assert job.overall_score != course.overall_score


class TestTheDetails:
    def test_valid_details_pass_through(self):
        assert kinds.clean_details("training", {
            "duration_months": 4, "stipend_monthly": 3000, "course_fee": 0,
            "next_batch": "2026-12-01", "mode": "in_person",
        }) == {"duration_months": 4, "stipend_monthly": 3000, "course_fee": 0,
               "next_batch": "2026-12-01", "mode": "in_person"}

    def test_empty_values_are_dropped(self):
        assert kinds.clean_details("job", {"openings": None, "apply_by": ""}) == {}

    @pytest.mark.parametrize("kind, details, says", [
        ("job", {"stipend_monthly": 3000}, "not a detail a job has"),
        ("job", {"openings": -1}, "whole number"),
        ("job", {"openings": 2.5}, "whole number"),
        ("job", {"openings": True}, "whole number"),
        ("job", {"apply_by": "next week"}, "YYYY-MM-DD"),
        ("job", {"shift_work": "yes"}, "true or false"),
        ("training", {"mode": "by post"}, "in_person, online"),
        ("training", {"duration_months": 0}, "above 0"),
        ("scheme", {"how_to_apply": "x" * 601}, "600"),
    ])
    def test_wrong_details_say_what_is_wrong(self, kind, details, says):
        with pytest.raises(ValueError, match=says):
            kinds.clean_details(kind, details)

    def test_an_impossible_date_is_refused(self):
        with pytest.raises(ValueError):
            kinds.clean_details("job", {"apply_by": "2026-02-31"})

    @pytest.mark.parametrize("reference", sorted(DETAILS))
    def test_every_stated_detail_is_well_formed_for_its_kind(self, reference):
        entry = next(s for s in SCHEMES if s["source_reference"] == reference)
        kind = kinds.kind_for_type(entry["type"])
        assert kinds.clean_details(kind, DETAILS[reference]) == DETAILS[reference]

    def test_the_migration_writes_exactly_the_catalogues_details(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        written = {
            ref: json.loads(value.replace("''", "'"))
            for ref, value in re.findall(r"\(\s*'([^']+)',\s*'(\{.*?\})'\)", sql)
        }
        assert written == DETAILS

    def test_a_how_to_apply_is_quoted_from_the_description(self):
        for reference, details in DETAILS.items():
            if "how_to_apply" in details:
                entry = next(s for s in SCHEMES if s["source_reference"] == reference)
                assert details["how_to_apply"] in entry["description"]


class TestTheAdminForm:
    def test_the_kind_comes_from_the_type(self):
        kind, details = _kind_and_details(SchemeWrite(
            title="t", organization="o", location="Salem", type="Training",
            details={"stipend_monthly": 1500},
        ))
        assert (kind, details) == ("training", {"stipend_monthly": 1500})

    def test_a_detail_of_another_kind_is_refused_with_its_name(self):
        with pytest.raises(HTTPException) as refused:
            _kind_and_details(SchemeWrite(
                title="t", organization="o", location="Salem", type="Full-time",
                details={"stipend_monthly": 1500},
            ))
        assert refused.value.status_code == 422
        assert "stipend_monthly" in refused.value.detail


class TestTheApi:
    def test_listings_carry_their_kind_and_details(self):
        with TestClient(app) as client:
            rows = client.get("/api/schemes").json()
        by_ref = {r["source_reference"]: r for r in rows}
        course = by_ref["PMAJAY/SKILL/TN/SLM/ITI/2024/0042"]
        assert course["kind"] == "training"
        assert course["details"] == {"duration_months": 4, "stipend_monthly": 3000}
        assert {r["kind"] for r in rows} == {"job", "training", "scheme"}

    def test_each_result_shows_the_weights_its_kind_used(self):
        with TestClient(app) as client:
            session_id = client.post(
                "/api/speech/client-transcript",
                json={"transcript": "I do welding and tailoring in Salem for six years.",
                      "language_detected": "en"},
            ).json()["session_id"]
            client.post("/api/profile/extract", json={"session_id": session_id})
            matches = client.post(
                "/api/schemes/match", json={"session_id": session_id, "limit": 30}
            ).json()["matches"]
        assert matches
        for match in matches:
            assert match["breakdown"]["weights"] == kinds.WEIGHTS[match["scheme"]["kind"]]
