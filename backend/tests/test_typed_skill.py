"""`/api/profile/normalize` tolerates a skill it has never stored.

Written on 2026-09-12 for the understanding screen's typed box, which sent new
skills through this route carrying no id. That box was moved to
`/api/profile/skills` hours later, because going through normalization skipped
extraction -- the only step that asks whether the words describe work at all --
and so turned "desire doue or ousmane dembele ?" into an uncertain skill card.
See `test_typed_input_validation.py` for that.

These tests are kept because the property is still real and still worth
guarding: the route takes the full corrected list and replaces what is stored,
so an entry without an id has to be accepted rather than dropped, and the
entries already there must survive. Nothing in the interface relies on it
today.

The last test matters most, and is the one the move was made for: typing
"asdfghjkl" resolves to no taxonomy skill. Normalization will always name a
nearest node -- e5 has no concept of "unrelated" -- so what it must never do is
claim one.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

TRANSCRIPT = "I have been repairing two-wheelers for six years in Salem."


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _session_with_skills(client) -> tuple[str, list[dict]]:
    session_id = client.post(
        "/api/speech/client-transcript",
        json={"transcript": TRANSCRIPT, "language_detected": "en"},
    ).json()["session_id"]
    extracted = client.post(
        "/api/profile/extract", json={"session_id": session_id}
    ).json()
    return session_id, extracted["skills"]


def _as_edits(skills: list[dict]) -> list[dict]:
    return [
        {
            "id": s.get("id"),
            "raw_name": s["raw_name"],
            "evidence_phrase": s["evidence_phrase"],
        }
        for s in skills
    ]


class TestATypedSkillIsAccepted:
    def test_a_skill_with_no_id_is_added(self, client):
        """The interface sends no id for something never stored."""
        session_id, skills = _session_with_skills(client)

        response = client.post(
            "/api/profile/normalize",
            json={
                "session_id": session_id,
                "skills": _as_edits(skills)
                + [{"raw_name": "carpentry", "evidence_phrase": "carpentry"}],
            },
        )

        assert response.status_code == 200
        names = [s["raw_name"] for s in response.json()["skills"]]
        assert "carpentry" in names

    def test_it_keeps_the_skills_that_were_already_there(self, client):
        """Adding one must not drop the rest: the route replaces the stored
        list wholesale, so the interface has to send everything back."""
        session_id, skills = _session_with_skills(client)
        before = {s["raw_name"] for s in skills}

        after = client.post(
            "/api/profile/normalize",
            json={
                "session_id": session_id,
                "skills": _as_edits(skills)
                + [{"raw_name": "carpentry", "evidence_phrase": "carpentry"}],
            },
        ).json()["skills"]

        assert before <= {s["raw_name"] for s in after}
        assert len(after) == len(skills) + 1

    def test_the_typed_words_are_its_evidence(self, client):
        """A card shows the words that produced it. For a typed skill those are
        the words they typed -- not a quote lifted from the spoken transcript,
        which would attribute the wrong thing to them."""
        session_id, skills = _session_with_skills(client)

        after = client.post(
            "/api/profile/normalize",
            json={
                "session_id": session_id,
                "skills": _as_edits(skills)
                + [{"raw_name": "carpentry", "evidence_phrase": "carpentry"}],
            },
        ).json()["skills"]

        typed = next(s for s in after if s["raw_name"] == "carpentry")
        assert typed["evidence_phrase"] == "carpentry"
        assert TRANSCRIPT not in typed["evidence_phrase"]


class TestTypingIsNotAWayAround:
    def test_it_is_still_normalized_against_the_taxonomy(self, client):
        """Typed or spoken, a skill only counts for matching once it resolves
        to a taxonomy node. It is not accepted merely because it was typed."""
        session_id, skills = _session_with_skills(client)

        after = client.post(
            "/api/profile/normalize",
            json={
                "session_id": session_id,
                "skills": _as_edits(skills)
                + [{"raw_name": "carpentry", "evidence_phrase": "carpentry"}],
            },
        ).json()["skills"]

        typed = next(s for s in after if s["raw_name"] == "carpentry")
        # Either it resolved, or it is flagged for the person to settle --
        # never silently accepted as a match it did not earn.
        assert (
            typed["normalized_skill_id"] is not None
            or typed["needs_disambiguation"]
            or typed["match_confidence"] is None
        )

    def test_nonsense_does_not_become_a_skill(self, client):
        """Typing is a way in, not a way past normalization."""
        session_id, skills = _session_with_skills(client)

        after = client.post(
            "/api/profile/normalize",
            json={
                "session_id": session_id,
                "skills": _as_edits(skills)
                + [{"raw_name": "asdfghjkl", "evidence_phrase": "asdfghjkl"}],
            },
        ).json()["skills"]

        junk = next(s for s in after if s["raw_name"] == "asdfghjkl")
        assert junk["normalized_skill_id"] is None, (
            "gibberish must not resolve to a taxonomy skill"
        )
