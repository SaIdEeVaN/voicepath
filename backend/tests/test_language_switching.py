"""The reader's language, not the recording's (spec sections 4.5 and 5).

A person can change language on any screen. Static interface copy follows
immediately because it is rendered from a table. Server-written prose --
explanations and answers -- does not: it was written once, in whatever language
was current at the time, and stored.

The bug these tests pin down is that a stored explanation could never change
language at all. ``GET /api/schemes/{id}/match/{session}`` returned the
persisted text with no way to ask for another language, so a person who
switched to Tamil on the detail screen kept reading English reasons underneath
a Tamil interface.

What must stay true while fixing it: the *numbers* are audited and must not
move. Re-explaining rewrites the sentences from the stored scores; it does not
re-score anything.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

TRANSCRIPT = (
    "I have six years of experience repairing two-wheelers. I worked at a shop "
    "in Salem. I also know a little welding."
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _matched_session(client) -> tuple[str, int]:
    """A session carrying stored matches, explained in English."""
    session_id = client.post(
        "/api/speech/client-transcript",
        json={"transcript": TRANSCRIPT, "language_detected": "en"},
    ).json()["session_id"]

    client.post("/api/profile/extract", json={"session_id": session_id})

    matched = client.post(
        "/api/schemes/match",
        json={"session_id": session_id, "language": "en"},
    ).json()
    assert matched["matches"], "fixture needs at least one match to read back"
    return session_id, matched["matches"][0]["scheme"]["id"]


class TestStoredMatchFollowsTheReader:
    def test_re_explains_in_the_requested_language(self, client):
        """The detail screen in Tamil must not show the English explanation."""
        session_id, scheme_id = _matched_session(client)

        english = client.get(
            f"/api/schemes/{scheme_id}/match/{session_id}",
            params={"language": "en"},
        ).json()
        tamil = client.get(
            f"/api/schemes/{scheme_id}/match/{session_id}",
            params={"language": "ta"},
        ).json()

        assert english["explanation_bullets"], "the fixture stored no bullets"
        assert tamil["explanation_bullets"], "Tamil came back with nothing to read"
        assert tamil["explanation_bullets"] != english["explanation_bullets"]

        # Not merely different -- actually Tamil. Devanagari and Latin both
        # fail this, so it cannot pass by returning Hindi or the original.
        joined = " ".join(tamil["explanation_bullets"])
        assert any("஀" <= ch <= "௿" for ch in joined), (
            f"expected Tamil script in the bullets, got: {joined!r}"
        )

    def test_re_explaining_does_not_move_the_audited_scores(self, client):
        """Only the sentences are rewritten. The numbers were audited."""
        session_id, scheme_id = _matched_session(client)

        english = client.get(
            f"/api/schemes/{scheme_id}/match/{session_id}",
            params={"language": "en"},
        ).json()
        tamil = client.get(
            f"/api/schemes/{scheme_id}/match/{session_id}",
            params={"language": "ta"},
        ).json()

        assert tamil["overall_score"] == english["overall_score"]
        assert tamil["breakdown"] == english["breakdown"]
        assert tamil["rank"] == english["rank"]

    def test_hindi_is_reachable_too(self, client):
        session_id, scheme_id = _matched_session(client)

        hindi = client.get(
            f"/api/schemes/{scheme_id}/match/{session_id}",
            params={"language": "hi"},
        ).json()

        joined = " ".join(hindi["explanation_bullets"])
        assert any("ऀ" <= ch <= "ॿ" for ch in joined), (
            f"expected Devanagari in the bullets, got: {joined!r}"
        )

    def test_asking_for_nothing_returns_what_was_stored(self, client):
        """No language asked for is not a reason to regenerate anything."""
        session_id, scheme_id = _matched_session(client)

        stored = client.get(f"/api/schemes/{scheme_id}/match/{session_id}")

        assert stored.status_code == 200
        assert stored.json()["explanation_bullets"]

    def test_an_unmatched_scheme_still_404s(self, client):
        """Re-explaining must not invent a match that was never stored."""
        session_id, _ = _matched_session(client)

        response = client.get(
            f"/api/schemes/999999/match/{session_id}", params={"language": "ta"}
        )

        assert response.status_code == 404

    def test_a_bad_session_id_is_still_refused(self, client):
        response = client.get(
            "/api/schemes/1/match/not-a-uuid", params={"language": "ta"}
        )

        assert response.status_code == 400
