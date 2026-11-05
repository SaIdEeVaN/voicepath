"""A session opens only with its secret key.

Until 2026-11-05 a session's id was all it took to read or change it, and the
id travels in request paths -- /api/sessions/{id} -- so in access logs. Now
each session has a 256-bit key, given once at creation, sent back only in the
X-VoicePath-Session-Key header and stored only as its SHA-256. A missing or
wrong key reads exactly like a session that does not exist; a session from
before keys existed is refused with a plain "start again".

These clients send keys only by hand (``vp_send_keys = False``), so every
request here says exactly what it presents.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import repository

TRANSCRIPT = "I have repaired two-wheelers in Salem for six years. I also do welding."
HEADER = "X-VoicePath-Session-Key"


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.vp_send_keys = False
        yield c


def start(client) -> tuple[str, str]:
    body = client.post(
        "/api/speech/client-transcript",
        json={"transcript": TRANSCRIPT, "language_detected": "en"},
    ).json()
    return body["session_id"], body["session_key"]


def routes(session_id: str) -> list[tuple[str, str, dict | None]]:
    return [
        ("get", f"/api/sessions/{session_id}", None),
        ("get", f"/api/sessions/{session_id}/questions", None),
        ("post", "/api/profile/extract", {"session_id": session_id}),
        ("post", "/api/schemes/match", {"session_id": session_id}),
        ("put", "/api/profile/experience", {"session_id": session_id, "experience_years": 4}),
        ("post", "/api/profile/skills", {"session_id": session_id, "text": "I weld", "language": "en"}),
        ("post", "/api/assistant/query",
         {"session_id": session_id, "question_text": "how much does it pay?"}),
    ]


def call(client, method, path, body, key=None):
    headers = {HEADER: key} if key else {}
    if body is None:
        return getattr(client, method)(path, headers=headers)
    return getattr(client, method)(path, json=body, headers=headers)


class TestTheKey:
    def test_every_new_session_gets_its_own(self, client):
        (a, key_a), (b, key_b) = start(client), start(client)
        assert len(key_a) >= 43 and len(key_b) >= 43
        assert key_a != key_b and a != b

    def test_it_is_stored_only_as_a_hash(self, client):
        session_id, key = start(client)
        stored = repository._memory[uuid.UUID(session_id)].session
        assert stored.key_hash == hashlib.sha256(key.encode()).hexdigest()
        assert stored.issued_key is None
        assert key not in repr(stored)

    def test_extract_without_a_session_hands_one_out(self, client):
        body = client.post("/api/profile/extract", json={"transcript": TRANSCRIPT}).json()
        assert body["session_id"] and body["session_key"]
        passport = client.get(
            f"/api/sessions/{body['session_id']}", headers={HEADER: body["session_key"]}
        )
        assert passport.status_code == 200


class TestWithoutIt:
    def test_the_id_alone_opens_nothing(self, client):
        session_id, _key = start(client)
        for method, path, body in routes(session_id):
            response = call(client, method, path, body)
            assert response.status_code == 404, (path, response.text)
            assert response.json()["detail"] == "That session was not found."

    def test_a_wrong_key_is_the_same_as_none(self, client):
        session_id, _key = start(client)
        response = call(client, "get", f"/api/sessions/{session_id}", None, key="x" * 43)
        assert response.status_code == 404

    def test_one_sessions_key_does_not_open_another(self, client):
        (a, _), (_b, key_b) = start(client), start(client)
        assert call(client, "get", f"/api/sessions/{a}", None, key=key_b).status_code == 404

    def test_a_missing_session_and_a_locked_one_look_alike(self, client):
        session_id, _key = start(client)
        locked = call(client, "get", f"/api/sessions/{session_id}", None)
        missing = call(client, "get", f"/api/sessions/{uuid.uuid4()}", None)
        assert (locked.status_code, locked.json()) == (missing.status_code, missing.json())


class TestWithIt:
    def test_the_whole_flow_works(self, client):
        session_id, key = start(client)
        for method, path, body in routes(session_id):
            response = call(client, method, path, body, key=key)
            assert response.status_code == 200, (path, response.text)

    def test_a_stored_match_needs_it_too(self, client):
        session_id, key = start(client)
        call(client, "post", "/api/profile/extract", {"session_id": session_id}, key=key)
        matches = call(client, "post", "/api/schemes/match", {"session_id": session_id},
                       key=key).json()["matches"]
        assert matches
        path = f"/api/schemes/{matches[0]['scheme']['id']}/match/{session_id}"
        assert call(client, "get", path, None).status_code == 404
        assert call(client, "get", path, None, key=key).status_code == 200


class TestSessionsFromBefore:
    def test_a_session_without_a_key_is_asked_to_start_again(self, client):
        session_id, key = start(client)
        repository._memory[uuid.UUID(session_id)].session.key_hash = None
        response = call(client, "get", f"/api/sessions/{session_id}", None, key=key)
        assert response.status_code == 410
        assert "start again" in response.json()["detail"]


class TestTheBrowserMayAskForIt:
    def test_cors_admits_the_header(self, client):
        response = client.options(
            "/api/sessions/x",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-voicepath-session-key",
            },
        )
        assert response.status_code == 200
        assert "x-voicepath-session-key" in response.headers["access-control-allow-headers"].lower()
