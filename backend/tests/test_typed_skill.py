"""A skill someone typed instead of said (spec sections 4.3 and 5).

Every route into this product used to end at the microphone. The understanding
screen offered "say something more" beside the cards and "say it again" when
nothing was found, and both went back to `/speak`. That leaves someone in a
noisy room, on a shared phone, or whose trade was misheard -- which is exactly
where Tamil speech recognition is weakest -- with nothing else to try.

The screen takes typed skills now, and they enter through `/api/profile/normalize`
carrying no id, because they have never been stored. These tests pin that
contract, since the interface depends on it.

What must stay true: **typing is a way in, not a way around.** A typed skill is
normalized like any other -- exact alias, then embedding, then the
disambiguation screen if it is not clear enough -- and it carries evidence like
any other. The evidence is what the person typed, which is the same rule the
landing page follows when someone types a sentence instead of speaking it.
Nothing is attributed to anyone that they did not say, in either medium.
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
