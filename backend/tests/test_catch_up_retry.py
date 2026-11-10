"""The catch-up keeps trying until nothing is missing -- no restart needed.

On 2026-11-05 the embedder was out of credits at startup; the catch-up ran
once, was refused, and even after credits were added nothing loaded until the
API was restarted by hand. Since 2026-11-09 it tries again every half hour
while anything is still missing, and /health shows what is left.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import reload_settings
from app.main import app
from app.services import corpus_sync


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hf_api")
    monkeypatch.setenv("HF_TOKEN", "test-token-not-real")
    reload_settings()
    monkeypatch.setattr(corpus_sync.db, "is_available", lambda: True)
    corpus_sync._status.clear()
    yield
    corpus_sync._status.clear()
    reload_settings()


class Recorder:
    def __init__(self, backlog):
        self.backlog = list(backlog)
        self.tries = 0
        self.waits: list[float] = []
        self.status_while_waiting: list[dict] = []

    async def catch_up(self):
        self.tries += 1

    async def missing(self):
        return self.backlog.pop(0)

    async def sleep(self, seconds):
        self.waits.append(seconds)
        self.status_while_waiting.append(corpus_sync.status())


def run_with(monkeypatch, recorder):
    monkeypatch.setattr(corpus_sync, "catch_up_safely", recorder.catch_up)
    monkeypatch.setattr(corpus_sync, "missing", recorder.missing)
    return corpus_sync.keep_catching_up(sleep=recorder.sleep)


async def test_it_tries_again_until_nothing_is_missing(hosted, monkeypatch):
    rec = Recorder([
        {"skills": 28, "documents": 24},   # embedder still refusing
        {"skills": 28, "documents": 24},
        {"skills": 0, "documents": 0},     # credits arrived
    ])
    await run_with(monkeypatch, rec)
    assert rec.tries == 3
    assert rec.waits == [corpus_sync.RETRY_SECONDS] * 2


async def test_health_can_show_what_is_left(hosted, monkeypatch):
    rec = Recorder([{"skills": 28, "documents": 24}, {"skills": 0, "documents": 0}])
    await run_with(monkeypatch, rec)
    waiting = rec.status_while_waiting[0]
    assert waiting["missing"] == {"skills": 28, "documents": 24}
    assert "next_try" in waiting
    assert corpus_sync.status() == {"missing": {"skills": 0, "documents": 0, "chunks": 0}}


async def test_a_failed_count_means_try_again_later(hosted, monkeypatch):
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("database blinked")
        return {"skills": 0, "documents": 0}

    rec = Recorder([])
    monkeypatch.setattr(corpus_sync, "catch_up_safely", rec.catch_up)
    monkeypatch.setattr(corpus_sync, "missing", flaky)
    await corpus_sync.keep_catching_up(sleep=rec.sleep)
    assert rec.tries == 2 and len(rec.waits) == 1


async def test_without_a_database_it_tries_once_and_stops(monkeypatch):
    rec = Recorder([{"skills": 5, "documents": 0}])
    monkeypatch.setattr(corpus_sync.db, "is_available", lambda: False)
    await run_with(monkeypatch, rec)
    assert rec.tries == 1 and rec.waits == []


async def test_with_the_offline_embedder_it_does_not_loop(monkeypatch):
    rec = Recorder([{"skills": 5, "documents": 0}])
    monkeypatch.setattr(corpus_sync.db, "is_available", lambda: True)
    await run_with(monkeypatch, rec)  # tests run with EMBEDDING_PROVIDER=offline
    assert rec.tries == 1 and rec.waits == []


async def test_missing_counts_skills_unloaded_documents_and_passages(hosted, monkeypatch, tmp_path):
    (tmp_path / "LOADED.md").write_text("x" * 300, encoding="utf-8")
    (tmp_path / "NEW.md").write_text("y" * 300, encoding="utf-8")
    (tmp_path / "STUB.md").write_text("too short", encoding="utf-8")
    (tmp_path / "scan.pdf").write_bytes(b"%PDF")

    async def fetchval(query, *args):
        assert "embedding is null" in query
        if "document_chunks" in query:
            # Only passages of sources still searched; a rejected one's are not.
            assert "status <> 'rejected'" in query
            return 1150
        return 28

    async def fetch(query, *args):
        return [{"source": "LOADED.md"}]

    monkeypatch.setattr(corpus_sync.db, "fetchval", fetchval)
    monkeypatch.setattr(corpus_sync.db, "fetch", fetch)
    assert await corpus_sync.missing(tmp_path) == {"skills": 28, "documents": 1, "chunks": 1150}


def test_health_reports_the_backlog(hosted):
    corpus_sync._status.update(missing={"skills": 28, "documents": 24}, next_try="2026-11-09T15:00:00+00:00")
    original = corpus_sync._status.copy()
    with TestClient(app) as client:
        corpus_sync._status.clear()
        corpus_sync._status.update(original)
        body = client.get("/health").json()
    assert body["catch_up"]["missing"] == {"skills": 28, "documents": 24}
