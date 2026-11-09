"""Every error the API sends carries a code the screen can translate.

The messages are English; the frontend says each code in English, Tamil and
Hindi (frontend/lib/i18n.ts, ``errorCodes``). These fail if a message the
table maps disappears from the code, if a response loses its code, or if the
frontend has no translation for one.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import errors
from app.config import reload_settings
from app.main import app
from app.services import ratelimit

APP = Path(__file__).resolve().parents[1] / "app"
I18N = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "i18n.ts"


def all_codes() -> set[str]:
    return set(errors.BY_MESSAGE.values()) | set(errors.BY_STATUS.values())


def test_every_mapped_message_is_still_raised_somewhere():
    source = "\n".join(
        p.read_text(encoding="utf-8") for p in APP.rglob("*.py") if p.name != "errors.py"
    )
    for message in errors.BY_MESSAGE:
        # Long messages are built from adjacent string literals; the first
        # few words are enough to find them.
        head = message[:40]
        assert head in source or head in source.replace('"\n    "', ""), message


def test_the_frontend_says_every_code_in_three_languages():
    text = I18N.read_text(encoding="utf-8")
    blocks = re.findall(r"errorCodes: \{(.*?)\n  \}", text, re.DOTALL)
    assert len(blocks) == 3, "expected an errorCodes block for en, ta and hi"
    for block in blocks:
        for code in all_codes():
            assert re.search(rf"\b{code}:", block), f"{code} missing from a language"


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.vp_send_keys = False
        yield c


def test_a_session_opened_without_its_key(client):
    session_id = client.post(
        "/api/speech/client-transcript",
        json={"transcript": "I weld.", "language_detected": "en"},
    ).json()["session_id"]
    body = client.get(f"/api/sessions/{session_id}").json()
    assert body["code"] == "session_not_found"


def test_an_unknown_session(client):
    body = client.get(f"/api/sessions/{uuid.uuid4()}").json()
    assert body == {"detail": "That session was not found.", "code": "session_not_found"}


def test_an_empty_transcript(client):
    response = client.post(
        "/api/speech/client-transcript",
        json={"transcript": "   ", "language_detected": "en"},
    )
    assert response.json()["code"] in ("empty_transcript", "invalid_input")


def test_input_that_fails_validation(client):
    response = client.post("/api/query/understand", json={"text": "a" * 20001})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_input"
    assert isinstance(body["detail"], list)  # FastAPI's own detail is kept


def test_a_body_that_is_too_large(client):
    response = client.post(
        "/api/profile/extract",
        content=b"{" + b" " * (300 * 1024) + b"}",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "too_large"


def test_too_many_requests(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_ASSISTANT_PER_MINUTE", "1")
    reload_settings()
    ratelimit.reset()
    session = str(uuid.uuid4())
    codes = []
    for _ in range(3):
        r = client.post("/api/assistant/query", json={"question_text": "pay?"},
                        headers={"X-VoicePath-Session": session})
        codes.append(r.json().get("code"))
    assert "too_many_requests" in codes
    reload_settings()
    ratelimit.reset()


def test_an_unmapped_message_still_arrives_whole(client):
    # A 404 for a route that does not exist: no code, the detail as before.
    body = client.get("/api/no-such-route").json()
    assert body["detail"] == "Not Found"
    assert "code" not in body
