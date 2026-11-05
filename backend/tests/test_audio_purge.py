"""Recordings are never kept, and the daily safety net holds that line.

Decided 2026-11-05: the passport's "keep my voice clips" toggle flipped a flag
and saved nothing, so it is gone (tests/test_api.py holds that). What stays is
db/002's purge_expired_audio, which the API now runs daily -- before, nothing
ever called it.
"""

from __future__ import annotations

import asyncio

import pytest

from app import main
from app.services import db


async def test_without_a_database_there_is_nothing_to_purge():
    assert await main.purge_audio_once() is None


async def test_it_calls_the_purge_with_the_retention_window(monkeypatch):
    calls = []

    async def fetchval(query, *args):
        calls.append((query, args))
        return 2

    monkeypatch.setattr(db, "is_available", lambda: True)
    monkeypatch.setattr(db, "fetchval", fetchval)
    assert await main.purge_audio_once() == 2
    assert calls == [("select purge_expired_audio($1)", (90,))]


async def test_a_failed_night_does_not_stop_the_api(monkeypatch):
    async def fetchval(query, *args):
        raise ConnectionError("database went away")

    monkeypatch.setattr(db, "is_available", lambda: True)
    monkeypatch.setattr(db, "fetchval", fetchval)
    assert await main.purge_audio_once() is None


async def test_it_runs_once_a_day(monkeypatch):
    runs = []
    waits = []

    async def once():
        runs.append(True)

    async def sleep(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(main, "purge_audio_once", once)
    with pytest.raises(asyncio.CancelledError):
        await main.purge_audio_daily(sleep=sleep)
    assert runs == [True, True]
    assert waits == [86400, 86400]
