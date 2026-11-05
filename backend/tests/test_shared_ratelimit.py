"""Rate limits hold across instances, through a shared store.

Until 2026-11-05 every counter lived in the process, so behind more than one
instance each limit multiplied by the instance count. These run against a
real Redis server -- started here from the ``redis-server`` binary, or the one
``REDIS_TEST_URL`` names -- and skip when neither is available.

"Another instance" is simulated with ``ratelimit.reset()``, which wipes every
in-process counter and the client: whatever still limits after it is held by
the store.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import reload_settings
from app.main import app
from app.services import ratelimit

BOOTSTRAP = "test-bootstrap-token-not-a-real-one"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def redis_url():
    if os.environ.get("REDIS_TEST_URL"):
        yield os.environ["REDIS_TEST_URL"]
        return
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("no redis-server binary and no REDIS_TEST_URL")
    port = _free_port()
    proc = subprocess.Popen(
        [binary, "--port", str(port), "--bind", "127.0.0.1", "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        proc.kill()
        pytest.skip("redis-server did not start")
    yield f"redis://127.0.0.1:{port}/0"
    proc.terminate()
    proc.wait(timeout=5)


def _flush(url: str) -> None:
    import redis

    redis.Redis.from_url(url).flushdb()


def _keys(url: str) -> list[str]:
    import redis

    return [k.decode() for k in redis.Redis.from_url(url).keys("*")]


@pytest.fixture
def shared(monkeypatch, redis_url):
    _flush(redis_url)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_ASSISTANT_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", redis_url)
    reload_settings()
    ratelimit.reset()
    yield redis_url
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL")
    reload_settings()
    ratelimit.reset()


@pytest.fixture
def store_down(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_ASSISTANT_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", f"redis://127.0.0.1:{_free_port()}/0")
    reload_settings()
    ratelimit.reset()
    yield
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL")
    reload_settings()
    ratelimit.reset()


def ask(client, session: str):
    return client.post(
        "/api/assistant/query",
        json={"question_text": "how much does it pay?"},
        headers={"X-VoicePath-Session": session},
    )


class TestShared:
    def test_a_limit_outlives_the_instance_that_counted_it(self, shared):
        session = str(uuid.uuid4())
        with TestClient(app) as client:
            codes = [ask(client, session).status_code for _ in range(3)]
            assert codes == [200, 200, 200]
        ratelimit.reset()  # a different instance: nothing in memory
        with TestClient(app) as client:
            response = ask(client, session)
        assert response.status_code == 429
        assert 0 < int(response.headers["Retry-After"]) <= ratelimit.WINDOW_SECONDS + 1

    def test_the_admin_lockout_is_shared_too(self, shared):
        wrong = {"Authorization": "Bearer wrong-token"}
        with TestClient(app) as client:
            for _ in range(ratelimit.ADMIN_FAILURES_PER_ADDRESS):
                assert client.get("/api/admin/schemes", headers=wrong).status_code == 403
        ratelimit.reset()
        right = {"Authorization": f"Bearer {BOOTSTRAP}"}
        with TestClient(app) as client:
            assert client.get("/api/admin/schemes", headers=right).status_code == 429

    def test_nothing_personal_is_stored_in_the_clear(self, shared):
        session = str(uuid.uuid4())
        with TestClient(app) as client:
            ask(client, session)
        keys = _keys(shared)
        assert keys and all(k.startswith(ratelimit.KEY_PREFIX) for k in keys)
        joined = " ".join(keys)
        assert session not in joined
        assert "testclient" not in joined and "127.0.0.1" not in joined

    def test_counters_expire_on_their_own(self, shared):
        import redis

        with TestClient(app) as client:
            ask(client, str(uuid.uuid4()))
        r = redis.Redis.from_url(shared)
        ttls = [r.ttl(k) for k in r.keys("*")]
        assert ttls and all(0 < t <= 2 * ratelimit.WINDOW_SECONDS for t in ttls)

    def test_health_says_the_counters_are_shared(self, shared):
        with TestClient(app) as client:
            ask(client, str(uuid.uuid4()))
            assert client.get("/health").json()["rate_limits"] == {"store": "shared"}


class TestStoreDown:
    def test_requests_are_still_served_and_still_limited(self, store_down):
        session = str(uuid.uuid4())
        with TestClient(app) as client:
            codes = [ask(client, session).status_code for _ in range(5)]
        assert codes == [200, 200, 200, 429, 429]

    def test_it_stops_asking_a_store_that_is_down(self, store_down, monkeypatch):
        with TestClient(app) as client:
            ask(client, str(uuid.uuid4()))
            assert ratelimit._store_down_until > time.monotonic()
            started = time.monotonic()
            for _ in range(5):
                ask(client, str(uuid.uuid4()))
            # Five requests inside the rest period pay no connection timeout.
            assert time.monotonic() - started < ratelimit.STORE_TIMEOUT_SECONDS * 3

    def test_health_says_why_it_counts_locally(self, store_down):
        with TestClient(app) as client:
            ask(client, str(uuid.uuid4()))
            report = client.get("/health").json()["rate_limits"]
        assert report["store"] == "process"
        assert "unreachable" in report["reason"]
        assert "127.0.0.1" not in report["reason"]


def test_without_a_store_it_says_so():
    ratelimit.reset()
    assert ratelimit.status_report() == {"store": "process"}
