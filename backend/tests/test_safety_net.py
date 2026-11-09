"""The second safety net, and the phrasings added on 2026-11-09.

The fixed list (services/safety.py) works with Groq down but only knows the
phrasings someone wrote down. Since 2026-11-09 the model calls that already
happen -- the intent classifier on every transcript and typed line, and the
assistant on every question -- also say whether someone is in danger, at no
extra request. Either one saying so gets the helplines.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import assistant, intent, llm, safety
from app.services.assistant import QueryContext

# Each added phrasing, and the everyday sentence nearest to it that must not
# trigger it.
ADDED = [
    "He threatened to kill me",
    "my husband is attacking me",
    "someone is stalking my daughter",
    "I don't feel safe",
    "I am not safe at home",
    "there is domestic violence in our house",
    "I have been self harming",
    "I want to hang myself",
    "I keep thinking of taking my own life",
    "there is no reason to live",
    "they won't let me leave the factory",
    "we are bonded labour at the brick kiln",
    "அவன் கொலை மிரட்டல் விடுகிறான்",
    "என்னை கொன்னுடுவேன் என்கிறான்",
    "அவன் என்னை தாக்கினான்",
    "வீட்டில் எனக்கு பாதுகாப்பு இல்லை",
    "தூக்கு போட்டுக்கலாம்னு தோணுது",
    "என்னை வெளியே விடமாட்டாங்க",
    "நாங்க கொத்தடிமையா வேலை செய்றோம்",
    "वह मुझे मार डालेगा",
    "मुझे जान से मारने की धमकी मिली",
    "घरेलू हिंसा हो रही है",
    "मैं फाँसी लगाने की सोच रहा हूँ",
    "ज़हर खा लूँगा",
    "मालिक घर से बाहर नहीं जाने देता",
    "हम बंधुआ मजदूर हैं",
    "मैं सुरक्षित नहीं हूँ",
]

NEAREST_ORDINARY = [
    "I need work to save my family",     # was a false alarm until 2026-11-09
    "I want to save my money",
    "my job is in danger",
    "the machine can hurt your hand if you are careless",
    "I fight for my rights at work",
    "I cut cloth for tailoring",
    "I hang wallpaper and paint houses",
    "I chase payments from customers",
    "safety shoes are needed for welding",
    "I work with poison for pest control",
    "I will not let my skills go to waste",
    "வீட்டில் தையல் வேலை செய்கிறேன்",
    "குடும்பத்தை காப்பாற்ற வேலை வேண்டும்",
    "मजदूर हूँ, ईंट भट्ठे पर काम किया है",
    "क्या यह योजना सुरक्षित है?",
]


@pytest.mark.parametrize("text", ADDED)
def test_an_added_phrasing_is_recognised(text):
    assert safety.detect_distress(text)


@pytest.mark.parametrize("text", NEAREST_ORDINARY)
def test_the_nearest_ordinary_sentence_is_not(text):
    assert not safety.detect_distress(text)


# A plea no list could hold: no fixed phrase, only meaning.
UNLISTED = "every night he comes home drunk and I am scared of what he will do to the children"


@pytest.fixture
def model_says(monkeypatch):
    """The model answers with ``someone_in_danger`` as given."""
    def set_reading(in_danger: bool, **extra):
        async def complete_json(system, prompt, **kwargs):
            if "someone_in_danger" not in system:
                raise AssertionError("asked a model call that does not carry the danger field")
            return {"describes_work": False, "asks_question": True, "question": None,
                    "answer": "An ordinary answer.", "source_note": "listing",
                    "answered_from_data": True, "someone_in_danger": in_danger, **extra}

        monkeypatch.setattr(llm, "is_available", lambda: True)
        monkeypatch.setattr(llm, "complete_json", complete_json)
    return set_reading


def test_the_unlisted_plea_really_is_unlisted():
    assert not safety.detect_distress(UNLISTED)


async def test_the_classifier_reads_danger_the_list_misses(model_says):
    model_says(True)
    assert (await intent.classify(UNLISTED)).in_danger


async def test_the_classifier_does_not_invent_it(model_says):
    model_says(False)
    assert not (await intent.classify("I repair bikes")).in_danger


async def test_offline_the_list_still_stands_alone(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: False)
    assert not (await intent.classify(UNLISTED)).in_danger


async def test_the_assistant_answers_it_with_the_helplines(model_says):
    model_says(True)
    result = await assistant._answer_with_llm(UNLISTED, QueryContext(), language="hi")
    assert result.urgent
    assert result.answer_text == safety.HELPLINES["hi"]


async def test_the_assistant_answers_ordinary_questions_as_before(model_says):
    model_says(False)
    result = await assistant._answer_with_llm("how much does it pay?", QueryContext(), language="en")
    assert not result.urgent
    assert result.answer_text == "An ordinary answer."


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_understanding_shows_the_helplines_on_the_models_reading(client, model_says):
    model_says(True)
    body = client.post("/api/query/understand", json={"text": UNLISTED, "language": "en"}).json()
    assert body["urgent"] is True


def test_a_typed_unlisted_plea_is_not_stored_as_a_skill(client, model_says, monkeypatch):
    session_id = client.post(
        "/api/speech/client-transcript",
        json={"transcript": "I have repaired two-wheelers for six years.", "language_detected": "en"},
    ).json()["session_id"]
    monkeypatch.setattr(llm, "is_available", lambda: False)
    client.post("/api/profile/extract", json={"session_id": session_id})

    model_says(True)
    body = client.post(
        "/api/profile/skills",
        json={"session_id": session_id, "text": UNLISTED, "language": "en"},
    ).json()
    assert body["urgent"] is True
    assert body["kind"] == "question"
    assert body["accepted"] is False
