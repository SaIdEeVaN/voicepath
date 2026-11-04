"""Experience can be corrected without recording again.

It is a quarter of every match score, and a misheard number -- "six" heard as
"two" -- used to be fixable only by recording everything again. These tests
hold the three things the correction must do: change that one field, leave
every other part of the profile and the skills as extracted, and not let a
score computed on the old number survive it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Names welding, which the offline extractor finds, so the suite needs no LLM.
TRANSCRIPT = (
    "I have been repairing bikes for six years. I worked at a shop in Salem. "
    "I know a little welding."
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _extracted(client) -> tuple[str, dict]:
    session_id = client.post(
        "/api/speech/client-transcript",
        json={"transcript": TRANSCRIPT, "language_detected": "en"},
    ).json()["session_id"]
    body = client.post("/api/profile/extract", json={"session_id": session_id}).json()
    return session_id, body


def _correct(client, session_id, years):
    return client.put(
        "/api/profile/experience",
        json={"session_id": session_id, "experience_years": years},
    )


def _match(client, session_id) -> list[dict]:
    # The whole ranking, not the first page: the point is how each scheme's
    # experience score moves, wherever it lands.
    return client.post(
        "/api/schemes/match",
        json={"session_id": session_id, "explain": False, "limit": 100},
    ).json()["matches"]


class TestTheCorrection:
    def test_it_changes_the_stored_number(self, client):
        session_id, _ = _extracted(client)

        response = _correct(client, session_id, 4)
        assert response.status_code == 200
        assert response.json()["experience_years"] == 4

        passport = client.get(f"/api/sessions/{session_id}").json()
        assert passport["profile"]["experience_years"] == 4

    def test_it_changes_nothing_else(self, client):
        session_id, _ = _extracted(client)
        before = client.get(f"/api/sessions/{session_id}").json()

        _correct(client, session_id, 9)
        after = client.get(f"/api/sessions/{session_id}").json()

        assert after["skills"] == before["skills"]
        for key in (
            "experience_context",
            "education",
            "certifications",
            "location",
            "work_preferences",
            "uncertainty_flags",
        ):
            assert after["profile"][key] == before["profile"][key], key

    def test_null_clears_it(self, client):
        session_id, _ = _extracted(client)
        assert _correct(client, session_id, None).json()["experience_years"] is None

    def test_it_is_kept_to_one_decimal_place_like_the_column(self, client):
        session_id, _ = _extracted(client)
        assert _correct(client, session_id, 2.26).json()["experience_years"] == 2.3


class TestScoresOnTheOldNumberDoNotSurvive:
    def test_stored_matches_are_cleared_when_it_changes(self, client):
        session_id, _ = _extracted(client)
        first = _match(client, session_id)
        assert first, "the transcript should match something"
        scheme_id = first[0]["scheme"]["id"]
        assert client.get(f"/api/schemes/{scheme_id}/match/{session_id}").status_code == 200

        _correct(client, session_id, 0.5)

        assert client.get(f"/api/schemes/{scheme_id}/match/{session_id}").status_code == 404

    def test_matching_again_uses_the_corrected_number(self, client):
        session_id, _ = _extracted(client)
        before = {m["scheme"]["id"]: m for m in _match(client, session_id)}

        _correct(client, session_id, 0.5)
        after = {m["scheme"]["id"]: m for m in _match(client, session_id)}

        # Somewhere asking for more than half a year must now score lower on
        # experience than it did on the transcript's six.
        asks_for_more = [
            sid for sid, m in before.items()
            if (m["scheme"].get("minimum_experience") or 0) > 0.5 and sid in after
        ]
        assert asks_for_more, "the catalogue should have a scheme asking for experience"
        for sid in asks_for_more:
            assert (
                after[sid]["breakdown"]["experience_score"]
                < before[sid]["breakdown"]["experience_score"]
            ), sid

    def test_saving_the_same_number_keeps_the_matches(self, client):
        session_id, extracted = _extracted(client)
        first = _match(client, session_id)
        scheme_id = first[0]["scheme"]["id"]

        _correct(client, session_id, extracted["profile"]["experience_years"])

        assert client.get(f"/api/schemes/{scheme_id}/match/{session_id}").status_code == 200


class TestRefusals:
    @pytest.mark.parametrize("years", [-1, 71, 1000])
    def test_an_impossible_number_is_refused(self, client, years):
        session_id, _ = _extracted(client)
        assert _correct(client, session_id, years).status_code == 422

    def test_an_unknown_session_is_refused(self, client):
        response = _correct(client, "00000000-0000-0000-0000-000000000000", 3)
        assert response.status_code == 404

    def test_a_session_with_nothing_understood_yet_is_refused(self, client):
        session_id = client.post(
            "/api/speech/client-transcript",
            json={"transcript": TRANSCRIPT, "language_detected": "en"},
        ).json()["session_id"]
        response = _correct(client, session_id, 3)
        assert response.status_code == 404
        assert "Nothing has been understood" in response.json()["detail"]
