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

from app.config import reload_settings  # noqa: E402
from app.services import schemes, ratelimit, repository, taxonomy  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_state():
    reload_settings()
    repository.reset_memory()
    ratelimit.reset()
    yield
    repository.reset_memory()


@pytest.fixture(scope="session", autouse=True)
def _reset_catalogue_caches():
    taxonomy.reset_memory_cache()
    schemes.reset_memory_cache()
    yield
