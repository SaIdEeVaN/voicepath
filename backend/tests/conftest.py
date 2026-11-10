"""Test configuration.

The whole suite runs against offline providers and the in-memory store, so it
needs no keys, no network and no database. That is deliberate: the guarantees
being tested (never invent, deterministic ranking, no re-ranking) are properties
of this code, not of any vendor, and a test that needed a vendor to demonstrate
them would be testing the wrong thing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.update(
    {
        "APP_ENV": "test",
        "LLM_PROVIDER": "offline",
        "STT_PROVIDER": "offline",
        "TTS_PROVIDER": "offline",
        "EMBEDDING_PROVIDER": "offline",
        # Needs no key, so nothing downgrades it automatically -- without this
        # the map tests would query a volunteer server on every run.
        "PLACES_PROVIDER": "offline",
        "RATE_LIMIT_ENABLED": "false",
        "LOG_LEVEL": "WARNING",
    }
)
# Emptied rather than popped. Settings reads `.env` as well as the environment,
# and a *missing* variable lets the file's value through -- so a developer with a
# real DATABASE_URL in .env would silently run the suite against their database.
# An empty value is present, so it shadows the file, and every consumer treats it
# as unset.
os.environ["DATABASE_URL"] = ""
os.environ["LLM_API_KEY"] = ""
# Same reasoning, and the same trap: Settings reads `.env`, so without pinning
# this the admin tests run against whatever bootstrap token the developer has
# configured -- a real production credential on a machine that has one, and
# nothing at all on CI. The gate would then be tested differently in the two
# places. A fixed, obviously-fake value makes "wrong token" and "no token
# configured" two distinct, reproducible states.
os.environ["ADMIN_BOOTSTRAP_TOKEN"] = "test-bootstrap-token-not-a-real-one"

from app.config import reload_settings  # noqa: E402
from app.services import embeddings, llm, schemes, ratelimit, repository, taxonomy  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_state():
    reload_settings()
    repository.reset_memory()
    ratelimit.reset()
    llm.reset_status()
    embeddings.reset_status()
    embeddings.unblock()
    yield
    repository.reset_memory()
    llm.reset_status()
    embeddings.reset_status()
    embeddings.unblock()


@pytest.fixture(scope="session", autouse=True)
def _reset_catalogue_caches():
    taxonomy.reset_memory_cache()
    schemes.reset_memory_cache()
    yield


# ---------------------------------------------------------------------------
# Session keys, the way the frontend sends them
# ---------------------------------------------------------------------------
#
# Since 2026-11-05 a session opens only with its secret key, sent in the
# X-VoicePath-Session-Key header (repository._require_key). The frontend keeps
# the key it is handed when a session is created and sends it with every
# request about that session; the test client does the same, so the hundreds
# of tests about everything else need not each carry keys by hand.
#
# A test about the keys themselves turns this off for its client with
# ``client.vp_send_keys = False`` -- tests/test_session_keys.py does.

import json as _json  # noqa: E402
import re as _re  # noqa: E402

from starlette.testclient import TestClient as _TestClient  # noqa: E402

_UUID = _re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", _re.I)
_original_request = _TestClient.request


def _request_with_session_keys(self, method, url, *args, **kwargs):
    keys: dict[str, str] = self.__dict__.setdefault("_vp_keys", {})
    if getattr(self, "vp_send_keys", True) and keys:
        mentioned = set(_UUID.findall(str(url)))
        body = kwargs.get("json")
        if body is not None:
            mentioned |= set(_UUID.findall(_json.dumps(body, default=str)))
        headers = dict(kwargs.get("headers") or {})
        for value in headers.values():
            mentioned |= set(_UUID.findall(str(value)))
        held = [keys[m.lower()] for m in mentioned if m.lower() in keys]
        if held and not any(k.lower() == "x-voicepath-session-key" for k in headers):
            headers["X-VoicePath-Session-Key"] = held[0]
            kwargs["headers"] = headers
    response = _original_request(self, method, url, *args, **kwargs)
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and payload.get("session_key") and payload.get("session_id"):
        keys[str(payload["session_id"]).lower()] = payload["session_key"]
    return response


_TestClient.request = _request_with_session_keys
