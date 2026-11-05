"""The API picks a database back up without a restart.

Until 2026-11-05 a database that did not answer at startup kept the API on
the in-memory store until someone restarted it, however soon the database
came back. Now it retries in the background and switches once nobody is
mid-flow on the in-memory store: a session started during the outage carries
the in-memory catalogue's skill and scheme ids, which are not the database's,
so it is retired -- and anyone returning to it is told plainly that it was not
saved -- rather than continued against the wrong rows.

No real database: reachability, the pool and the clock are stand-ins.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import reload_settings
from app.main import _after_reconnect, app
from app.services import corpus_sync, db, repository, schemes, taxonomy

UNREACHABLE = "postgresql://postgres.someproject:secret@127.0.0.1:1/postgres"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE)
    reload_settings()
    yield
    # Plain assignment: monkeypatch.setattr here would put the fake pool back
    # when it undoes its changes after this teardown.
    db._pool = None
    db._reconnect_state = None
    monkeypatch.setenv("DATABASE_URL", "")
    reload_settings()


@pytest.fixture(autouse=True)
def fresh_memory():
    repository.reset_memory()
    yield
    repository.reset_memory()


class Clock:
    """Records every wait instead of waiting."""

    def __init__(self):
        self.waits: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)


def answers_after(failures: int):
    calls = {"n": 0}

    async def reachable() -> bool:
        calls["n"] += 1
        return calls["n"] > failures

    return reachable


async def fake_init_pool():
    db._pool = object()  # what is_available() looks at
    return db._pool


class TestTheRetries:
    async def test_it_backs_off_then_switches(self, configured, monkeypatch):
        monkeypatch.setattr(db, "_reachable", answers_after(3))
        monkeypatch.setattr(db, "init_pool", fake_init_pool)
        connected = []

        async def on_connected():
            connected.append(True)

        clock = Clock()
        switched = await db.reconnect_in_background(
            is_quiet=lambda: True, on_connected=on_connected, sleep=clock.sleep
        )
        assert switched is True
        assert clock.waits == [15.0, 30.0, 60.0, 120.0]
        assert connected == [True]
        assert db.is_available()
        assert db.reconnect_state() is None

    async def test_the_last_delay_repeats(self, configured, monkeypatch):
        monkeypatch.setattr(db, "_reachable", answers_after(7))
        monkeypatch.setattr(db, "init_pool", fake_init_pool)
        clock = Clock()

        async def nothing():
            return None

        await db.reconnect_in_background(
            is_quiet=lambda: True, on_connected=nothing, sleep=clock.sleep
        )
        assert clock.waits[-3:] == [300.0, 300.0, 300.0]

    async def test_it_waits_while_anyone_is_mid_flow(self, configured, monkeypatch):
        monkeypatch.setattr(db, "_reachable", answers_after(0))
        monkeypatch.setattr(db, "init_pool", fake_init_pool)
        busy = iter([False, False, True])
        states: list[str | None] = []
        clock = Clock()

        async def sleep(seconds):
            states.append(db.reconnect_state())
            await clock.sleep(seconds)

        async def nothing():
            return None

        await db.reconnect_in_background(
            is_quiet=lambda: next(busy), on_connected=nothing, sleep=sleep
        )
        assert clock.waits == [15.0, 60.0, 60.0]
        assert "outage" in (states[1] or "")

    async def test_nothing_to_do_without_a_database(self, monkeypatch):
        clock = Clock()

        async def nothing():
            return None

        assert await db.reconnect_in_background(
            is_quiet=lambda: True, on_connected=nothing, sleep=clock.sleep
        ) is False
        assert clock.waits == []

    async def test_a_failing_follow_up_still_counts_as_connected(self, configured, monkeypatch):
        monkeypatch.setattr(db, "_reachable", answers_after(0))
        monkeypatch.setattr(db, "init_pool", fake_init_pool)

        async def broken():
            raise RuntimeError("catch-up failed")

        assert await db.reconnect_in_background(
            is_quiet=lambda: True, on_connected=broken, sleep=Clock().sleep
        ) is True


class TestWhoIsMidFlow:
    async def test_an_empty_store_is_quiet(self):
        assert repository.memory_quiet(1800) is True

    async def test_a_session_in_use_is_not(self):
        await repository.create_session(language_detected="en", transcript="I weld.")
        assert repository.memory_quiet(1800) is False
        assert repository.memory_quiet(0) is True


class TestTheHandover:
    async def test_outage_sessions_are_retired_with_a_plain_reason(self):
        session = await repository.create_session(language_detected="en", transcript="I weld.")
        assert repository.retire_memory_sessions() == 1
        assert await repository.get_session(session.id) is None
        code, message = repository.missing_session(session.id)
        assert code == 410
        assert "database was down" in message and "start again" in message

    def test_an_unknown_session_is_still_a_404(self):
        assert repository.missing_session("00000000-0000-4000-8000-000000000000")[0] == 404
        assert repository.missing_session("not-a-uuid")[0] == 404

    async def test_after_reconnect_retires_and_rebuilds(self, monkeypatch):
        calls = []
        monkeypatch.setattr(taxonomy, "reset_memory_cache", lambda: calls.append("taxonomy"))
        monkeypatch.setattr(schemes, "reset_memory_cache", lambda: calls.append("schemes"))

        async def catch_up():
            calls.append("catch_up")

        monkeypatch.setattr(corpus_sync, "catch_up_safely", catch_up)
        session = await repository.create_session(language_detected="en", transcript="I weld.")
        await _after_reconnect()
        assert calls == ["taxonomy", "schemes", "catch_up"]
        assert repository.missing_session(session.id)[0] == 410

    def test_the_api_answers_410_for_a_retired_session(self):
        with TestClient(app) as client:
            session_id = client.post(
                "/api/speech/client-transcript",
                json={"transcript": "I repair bikes in Salem.", "language_detected": "en"},
            ).json()["session_id"]
            repository.retire_memory_sessions()
            for response in (
                client.get(f"/api/sessions/{session_id}"),
                client.post("/api/profile/extract", json={"session_id": session_id}),
                client.post("/api/schemes/match", json={"session_id": session_id}),
            ):
                assert response.status_code == 410, response.text
                assert "start again" in response.json()["detail"]


class TestHealth:
    def test_health_says_it_is_reconnecting(self, configured):
        with TestClient(app) as client:
            database = client.get("/health").json()["database"]
        assert database["connected"] is False
        assert database["reconnect"] == "retrying"
