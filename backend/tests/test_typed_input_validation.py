"""What happens to typed text that is not work (spec sections 4.2 and 6).

Reported from the deployed app: typing *"desire doue or ousmane dembele ?"*
into the understanding screen produced a skill card titled with those words,
flagged "I am not fully sure about this one", and let the person carry on to
their matches.

The spoken path never had this problem. Extraction reads a transcript and
returns nothing for football players, so an off-topic recording lands on the
empty state. The typed box added on 2026-09-12 skipped that step and went
straight to normalization, which is a different question entirely: *which
taxonomy node is this nearest?* -- and e5 answers that for anything. Measured,
those five words scored 0.7528 against the taxonomy, "who is the prime
minister" 0.7568 and "asdfghjkl" 0.7795, all comfortably over the 0.60
candidate threshold. So each became an uncertain skill rather than nothing.

This is the third place the same property has had to be handled: e5 has no
concept of "unrelated", only of "nearest".

The landing page already states the rule the typed box broke -- typing "joins
the pipeline at exactly the point speech does: the transcript". It now does:
text is classified, and work is extracted from it exactly as from speech.

Three outcomes, and the middle one is why classification is the right step
rather than extraction alone:

* **work** -- skills are extracted and appended, each carrying evidence quoted
  from what was typed.
* **a question** -- "who is eligible for PM-AJAY" is not work, but it is not
  nonsense either, and refusing it would be wrong. It is handed back for the
  assistant to answer.
* **neither** -- refused, with nothing added.
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


def _session(client) -> str:
    session_id = client.post(
        "/api/speech/client-transcript",
        json={"transcript": TRANSCRIPT, "language_detected": "en"},
    ).json()["session_id"]
    client.post("/api/profile/extract", json={"session_id": session_id})
    return session_id


def _add(client, session_id: str, text: str):
    return client.post(
        "/api/profile/skills",
        json={"session_id": session_id, "text": text, "language": "en"},
    )


class TestWorkIsAccepted:
    def test_a_trade_typed_on_its_own_is_added(self, client):
        session_id = _session(client)

        response = _add(client, session_id, "carpentry")

        assert response.status_code == 200
        body = response.json()
        assert body["kind"] == "work"
        assert body["accepted"] is True
        assert any("carpent" in s["raw_name"].lower() for s in body["skills"])

    def test_it_keeps_what_was_already_understood(self, client):
        session_id = _session(client)
        before = len(client.post(
            "/api/profile/normalize", json={"session_id": session_id}
        ).json()["skills"])

        body = _add(client, session_id, "carpentry").json()

        assert len(body["skills"]) > before, "adding one must not drop the rest"

    def test_the_evidence_comes_from_what_was_typed(self, client):
        """A card shows back the words that produced it. For typed work those
        are the typed words -- never a quote from the spoken transcript, which
        would attribute the wrong thing to the person."""
        session_id = _session(client)

        body = _add(client, session_id, "carpentry").json()

        typed = [s for s in body["skills"] if "carpent" in s["raw_name"].lower()]
        assert typed, "the typed skill is missing"
        assert TRANSCRIPT not in typed[0]["evidence_phrase"]


class TestNothingOffTopicBecomesASkill:
    """The invariant the reported bug violated.

    Whether a given off-topic string reads as a question or as noise is a
    detail -- "desire doue or ousmane dembele ?" carries a question mark and so
    classifies as a question, which is right, and the assistant will then say
    the documents do not cover it. What must never happen, for any of them, is
    a skill card titled with those words.
    """

    OFF_TOPIC = [
        "desire doue or ousmane dembele ?",  # the reported case
        "asdfghjkl",
        "hello",
        "who is the prime minister",
    ]

    @pytest.mark.parametrize("text", OFF_TOPIC)
    def test_no_skill_is_accepted(self, client, text):
        session_id = _session(client)

        body = _add(client, session_id, text).json()

        assert body["accepted"] is False
        assert body["kind"] != "work"
        assert body["skills"] == []

    @pytest.mark.parametrize("text", OFF_TOPIC)
    def test_nothing_is_stored_for_it(self, client, text):
        session_id = _session(client)
        before = client.post(
            "/api/profile/normalize", json={"session_id": session_id}
        ).json()["skills"]

        _add(client, session_id, text)

        after = client.post(
            "/api/profile/normalize", json={"session_id": session_id}
        ).json()["skills"]
        assert len(after) == len(before)


class TestPlainNoiseIsNotEvenAQuestion:
    @pytest.mark.parametrize("text", ["asdfghjkl", "hello"])
    def test_it_is_refused_outright(self, client, text):
        """Nothing to extract and nothing being asked."""
        session_id = _session(client)

        body = _add(client, session_id, text).json()

        assert body["kind"] == "neither"


class TestAQuestionIsNotNonsense:
    def test_it_is_handed_back_to_be_answered(self, client):
        """Refusing a real question because it is not work would be wrong."""
        session_id = _session(client)

        body = _add(client, session_id, "who is eligible for PM-AJAY?").json()

        assert body["kind"] == "question"
        assert body["accepted"] is False, "a question adds no skill"
        assert body["question"]

    def test_it_adds_no_skill(self, client):
        session_id = _session(client)
        before = client.post(
            "/api/profile/normalize", json={"session_id": session_id}
        ).json()["skills"]

        _add(client, session_id, "who is eligible for PM-AJAY?")

        after = client.post(
            "/api/profile/normalize", json={"session_id": session_id}
        ).json()["skills"]
        assert len(after) == len(before)


class TestTheEdges:
    def test_blank_text_is_refused(self, client):
        session_id = _session(client)
        assert _add(client, session_id, "   ").status_code == 422

    def test_an_unknown_session_is_not_found(self, client):
        response = _add(
            client, "00000000-0000-0000-0000-000000000001", "carpentry"
        )
        assert response.status_code == 404
