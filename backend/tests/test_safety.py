"""A plea for help is answered with who can help.

The production question log on 2026-11-04 held "என் பக்கத்தில் ஒரு படிக்கு
தெரியாத பெண்ணு இருக்கு, பிள்ளீஸ் காப்பாற்றுங்கள் என்ன." -- there is an
illiterate woman next to me, please save her -- asked three times, and
answered three times with an explanation that their voice was not recorded.

The other half of these tests matters as much: the people this serves describe
their work in the same words. "I need a job to support my family", "I paint",
"my job is in danger" must still reach the skills and the schemes, not a
helpline.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import assistant, safety
from app.services.assistant import QueryContext

LOGGED = (
    "என் பக்கத்தில் ஒரு படிக்கு தெரியாத பெண்ணு இருக்கு, "
    "பிள்ளீஸ் காப்பாற்றுங்கள் என்ன."
)

DISTRESS = [
    LOGGED,
    "please save me",
    "save her, she is being beaten",
    "my husband beats me every day",
    "I am in danger",
    "my wife is in danger",
    "I want to die",
    "I am going to kill myself",
    "my manager sexually harassed me",
    "they kidnapped my son",
    "என்னை அடிக்கிறார்",
    "காப்பாத்துங்க",
    "மேலாளர் பாலியல் தொல்லை கொடுக்கிறார்",
    "எனக்கு தற்கொலை எண்ணம் வருகிறது",
    "நான் ஆபத்தில் இருக்கிறேன்",
    "मुझे बचाओ",
    "मेरा पति मुझे मारता है",
    "मैं ख़तरे में हूँ",
    "मैं खतरे में हूँ",
    "मैं आत्महत्या करना चाहता हूँ",
]

ORDINARY = [
    "குடும்பத்தை காப்பாற்ற வேலை வேண்டும்",  # I need a job to support my family
    "நான் பெயிண்ட் அடிக்கிறேன்",  # I paint
    "டைப் அடிப்பேன்",  # I type
    "my job is in danger",
    "my house is in danger of flooding",
    "can you help me find a job?",
    "help me with the form",
    "I save money every month",
    "I beat the deadline every time",
    "who is eligible for PM-AJAY?",
    "how much does it pay?",
    "I work in emergency electrical repairs",
    "இந்த திட்டத்தில் என்ன உதவி கிடைக்கும்?",
    "क्या मदद मिलेगी?",
    "मैंने छह साल वेल्डिंग की है",
    "",
    None,
]


class TestDetection:
    @pytest.mark.parametrize("text", DISTRESS)
    def test_a_plea_or_a_report_of_harm_is_recognised(self, text):
        assert safety.detect_distress(text), text

    @pytest.mark.parametrize("text", ORDINARY)
    def test_ordinary_work_and_questions_are_not(self, text):
        assert not safety.detect_distress(text), text

    def test_decomposed_tamil_is_read_the_same_as_composed(self):
        import unicodedata

        assert safety.detect_distress(unicodedata.normalize("NFD", LOGGED))


class TestTheAnswer:
    @pytest.mark.parametrize("language", ["en", "ta", "hi"])
    def test_every_language_gives_112_and_the_other_lines(self, language):
        text = safety.helpline_answer(language)
        for number in ("112", "181", "1098", "14416"):
            assert number in text, (language, number)

    def test_an_unknown_language_falls_back_to_english(self):
        assert safety.helpline_answer("fr") == safety.HELPLINES["en"]
        assert safety.helpline_answer("ta-IN") == safety.HELPLINES["ta"]

    def test_it_does_not_pretend_to_send_help(self):
        assert "cannot send help" in safety.HELPLINES["en"]


class TestTheAssistant:
    async def test_the_logged_question_gets_the_helplines(self):
        result = await assistant.answer(LOGGED, QueryContext(), language="ta")
        assert result.urgent
        assert result.answer_text == safety.HELPLINES["ta"]
        assert result.source_note == safety.SOURCE_NOTE["ta"]

    async def test_it_answers_before_retrieval_or_the_model(self, monkeypatch):
        def refuse(*_args, **_kwargs):
            raise AssertionError("a plea for help must not wait on the network")

        monkeypatch.setattr(assistant.scheme_qa, "ask", refuse)
        monkeypatch.setattr(assistant.llm, "complete_json", refuse)
        monkeypatch.setattr(assistant.llm, "is_available", lambda: True)

        result = await assistant.answer("please save me", QueryContext(), language="en")
        assert result.urgent

    async def test_an_ordinary_question_is_not_urgent(self):
        result = await assistant.answer(
            "what happens to my voice recording?", QueryContext(), language="en"
        )
        assert not result.urgent


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _session(client, transcript="I have repaired two-wheelers for six years."):
    """A session that has been through extraction, as the typed box needs."""
    session_id = client.post(
        "/api/speech/client-transcript",
        json={"transcript": transcript, "language_detected": "en"},
    ).json()["session_id"]
    client.post("/api/profile/extract", json={"session_id": session_id})
    return session_id


class TestTheRoutes:
    def test_the_assistant_route_says_it_is_urgent(self, client):
        body = client.post(
            "/api/assistant/query",
            json={"question_text": LOGGED, "language": "ta"},
        ).json()
        assert body["urgent"] is True
        assert "112" in body["answer_text"]

    def test_an_ordinary_answer_is_not_marked_urgent(self, client):
        body = client.post(
            "/api/assistant/query",
            json={"question_text": "how much does it pay?", "language": "en"},
        ).json()
        assert body["urgent"] is False

    def test_understanding_flags_it_whatever_the_classifier_says(self, client):
        body = client.post(
            "/api/query/understand", json={"text": LOGGED, "language": "ta"}
        ).json()
        assert body["urgent"] is True

        calm = client.post(
            "/api/query/understand",
            json={"text": "நான் பெயிண்ட் அடிக்கிறேன்", "language": "ta"},
        ).json()
        assert calm["urgent"] is False

    def test_typed_distress_goes_to_the_assistant_and_stores_nothing(self, client):
        session_id = _session(client)
        before = client.get(f"/api/sessions/{session_id}").json()["skills"]

        body = client.post(
            "/api/profile/skills",
            json={
                "session_id": session_id,
                "text": "my boss beats me, I am a welder",
                "language": "en",
            },
        ).json()
        assert body["urgent"] is True
        assert body["kind"] == "question"
        assert body["accepted"] is False
        assert body["question"] == "my boss beats me, I am a welder"

        after = client.get(f"/api/sessions/{session_id}").json()["skills"]
        assert after == before

    def test_typed_work_is_unaffected(self, client):
        session_id = _session(client)
        body = client.post(
            "/api/profile/skills",
            json={
                "session_id": session_id,
                "text": "I did welding for three years",
                "language": "en",
            },
        ).json()
        assert body["urgent"] is False
        assert body["kind"] == "work"
