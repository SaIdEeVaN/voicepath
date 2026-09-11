"""The admin overview figures (spec section 18).

`/admin` was three navigation cards and no numbers. Every figure the spec asks
for was already in the database; nothing was counting them.

Two properties matter more than the arithmetic:

* **It is gated like every other admin route.** An overview is still a view of
  what people have been doing.
* **It reports no transcripts and no question text.** `/admin/sessions` already
  refuses to show what people said about their lives, and an aggregate is not a
  loophole for that -- popular *skills* and *locations* are catalogue values,
  where a popular *question* would be someone's own words.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

GOOD_TOKEN = "test-bootstrap-token-not-a-real-one"
AUTH = {"Authorization": f"Bearer {GOOD_TOKEN}"}

TRANSCRIPT = (
    "I have six years of experience repairing two-wheelers. "
    "I worked at a shop in Salem."
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _a_session(client) -> str:
    sid = client.post(
        "/api/speech/client-transcript",
        json={"transcript": TRANSCRIPT, "language_detected": "en"},
    ).json()["session_id"]
    client.post("/api/profile/extract", json={"session_id": sid})
    return sid


class TestTheGate:
    def test_no_token_is_rejected(self, client):
        assert client.get("/api/admin/overview").status_code == 401

    def test_wrong_token_is_rejected(self, client):
        response = client.get(
            "/api/admin/overview", headers={"Authorization": "Bearer wrong"}
        )
        assert response.status_code == 403


class TestTheFigures:
    def test_it_reports_the_shape_the_dashboard_needs(self, client):
        body = client.get("/api/admin/overview", headers=AUTH).json()

        assert set(body) >= {"schemes", "sessions", "corpus", "popular"}

        assert set(body["schemes"]) >= {"total", "active", "inactive", "by_type"}
        assert set(body["sessions"]) >= {"total", "today", "questions"}
        assert set(body["popular"]) >= {"skills", "locations"}

    def test_active_and_inactive_sum_to_the_total(self, client):
        schemes = client.get("/api/admin/overview", headers=AUTH).json()["schemes"]

        assert schemes["active"] + schemes["inactive"] == schemes["total"]
        assert schemes["total"] > 0, "the seeded catalogue should not be empty"

    def test_by_type_covers_every_scheme(self, client):
        schemes = client.get("/api/admin/overview", headers=AUTH).json()["schemes"]

        counted = sum(entry["count"] for entry in schemes["by_type"])
        assert counted == schemes["active"], (
            "by_type is the active catalogue, so it must account for all of it"
        )

    def test_a_session_moves_the_numbers(self, client):
        before = client.get("/api/admin/overview", headers=AUTH).json()
        _a_session(client)
        after = client.get("/api/admin/overview", headers=AUTH).json()

        assert after["sessions"]["total"] == before["sessions"]["total"] + 1
        assert after["sessions"]["today"] >= 1

    def test_popular_skills_come_back_named(self, client):
        _a_session(client)
        popular = client.get("/api/admin/overview", headers=AUTH).json()["popular"]

        for entry in popular["skills"]:
            assert entry["name"], "a skill with no name is not a usable row"
            assert entry["count"] >= 1


class TestItStaysWithinWhatAdminMaySee:
    def test_it_carries_no_transcript_and_no_question_text(self, client):
        _a_session(client)
        client.post(
            "/api/assistant/query",
            json={"question": "how much does it pay?", "scheme_id": 1},
        )

        raw = client.get("/api/admin/overview", headers=AUTH).text.lower()

        # The fixture transcript's own words must not appear in an aggregate.
        for phrase in ("two-wheelers", "i worked at a shop", "how much does it pay"):
            assert phrase not in raw, f"the overview leaked {phrase!r}"

    def test_popular_lists_are_bounded(self, client):
        popular = client.get("/api/admin/overview", headers=AUTH).json()["popular"]

        # An unbounded "popular" list is a dump of the table wearing a summary's
        # name, and on a busy deployment it is also a slow query.
        assert len(popular["skills"]) <= 10
        assert len(popular["locations"]) <= 10
