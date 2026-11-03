"""A configured database that does not answer.

On 2026-11-03 the Supabase project was paused for inactivity and every boot of
the API died on its first connection: the whole product went down, including
the catalogue, matching and the map, none of which need the database. These
hold the line that replaced that: start on memory, say so everywhere, and do
not let "cannot check" reopen the admin bootstrap token.

Simulated with a port nothing listens on, so it fails fast and offline.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import reload_settings
from app.main import app
from app.services import db

UNREACHABLE = "postgresql://postgres.someproject:secret@127.0.0.1:1/postgres"
BOOTSTRAP = "test-bootstrap-token-not-a-real-one"


@pytest.fixture
def unreachable_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE)
    reload_settings()
    yield
    monkeypatch.setenv("DATABASE_URL", "")
    reload_settings()


@pytest.fixture
def client(unreachable_database):
    with TestClient(app) as c:
        yield c


class TestStartup:
    def test_the_api_starts_instead_of_exiting(self, client):
        assert client.get("/health").status_code == 200

    def test_health_names_the_database_as_degraded(self, client):
        body = client.get("/health").json()
        assert body["status"] == "degraded"
        assert "database" in body["degraded"]

    def test_health_separates_unreachable_from_unconfigured(self, client):
        database = client.get("/health").json()["database"]
        assert database["connected"] is False
        assert database["configured"] is True
        assert "unreachable" in database["reason"]
        assert database["error"]

    def test_health_does_not_publish_the_connection_details(self, client):
        """/health is public. The driver's message can name host and user."""
        text = client.get("/health").text
        for secret in ("127.0.0.1", "someproject", "secret", "postgresql://"):
            assert secret not in text

    def test_the_pipeline_still_runs_on_memory(self, client):
        response = client.post(
            "/api/speech/client-transcript",
            json={"transcript": "I repair bikes in Salem.", "language_detected": "en"},
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        assert client.post(
            "/api/profile/extract", json={"session_id": session_id}
        ).status_code == 200

    def test_the_catalogue_and_the_map_still_answer(self, client):
        assert client.get("/api/schemes").json()
        assert client.post("/api/places/nearby", json={"place": "Salem"}).status_code == 200


class TestAdminGateDuringAnOutage:
    def test_the_bootstrap_token_is_not_honoured(self, client):
        """It works only while admin_users is empty, and nobody can see that now.

        Treating "cannot check" as "empty" would reopen the backdoor for
        exactly as long as the database is down.
        """
        response = client.get(
            "/api/admin/overview", headers={"Authorization": f"Bearer {BOOTSTRAP}"}
        )
        assert response.status_code == 503
        assert "database" in response.json()["detail"].lower()

    def test_no_token_is_still_a_401(self, client):
        assert client.get("/api/admin/overview").status_code == 401


class TestUnconfigured:
    def test_no_database_url_is_not_reported_as_an_outage(self):
        with TestClient(app) as c:
            database = c.get("/health").json()["database"]
        assert database["configured"] is False
        assert db.unreachable() is None

    def test_state_does_not_leak_between_runs(self, unreachable_database):
        with TestClient(app):
            assert db.unreachable() is not None
        assert db.unreachable() is None
