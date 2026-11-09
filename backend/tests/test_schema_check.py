"""/health notices a database that lacks what the code needs.

On 2026-09-12 code reached production before the migration that added its
column, every route touching a match failed, and /health stayed green because
the database was connected. These hold the check that replaced that, and the
list it checks against: a migration that adds a table or column the list
does not name fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import get_settings
from app.main import _degraded
from app.services import db

DB_DIR = Path(__file__).resolve().parents[2] / "db"
# 001-004 are the baseline the code was first written against.
BASELINE = {"001_schema.sql", "002_functions.sql", "003_seed.sql", "004_policies.sql"}

ADD_COLUMN = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?(\w+)\s+add\s+column\s+if\s+not\s+exists\s+(\w+)",
    re.IGNORECASE,
)
CREATE_TABLE = re.compile(r"create\s+table\s+if\s+not\s+exists\s+(\w+)", re.IGNORECASE)
RENAME_COLUMN = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?(\w+)\s+rename\s+column\s+\w+\s+to\s+(\w+)",
    re.IGNORECASE,
)


def migrations():
    for path in sorted(DB_DIR.glob("*.sql")):
        if path.name not in BASELINE:
            yield path, path.read_text(encoding="utf-8")


def test_every_column_and_table_a_migration_adds_is_checked():
    listed = {(table, column) for table, column, _ in db.REQUIRED_SCHEMA}
    missing = []
    for path, sql in migrations():
        for table, column in ADD_COLUMN.findall(sql):
            if (table.lower(), column.lower()) not in listed:
                missing.append(f"{path.name}: {table}.{column}")
        for table in CREATE_TABLE.findall(sql):
            if (table.lower(), None) not in listed:
                missing.append(f"{path.name}: table {table}")
    assert not missing, f"Add these to db.REQUIRED_SCHEMA: {missing}"


def test_renamed_columns_the_code_reads_are_checked():
    listed = {(table, column) for table, column, _ in db.REQUIRED_SCHEMA}
    for _path, sql in migrations():
        for table, column in RENAME_COLUMN.findall(sql):
            if table.lower() == "matches":
                assert (table.lower(), column.lower()) in listed


def test_each_entry_names_a_migration_that_exists():
    for _table, _column, migration in db.REQUIRED_SCHEMA:
        assert (DB_DIR / migration).exists(), migration


@pytest.fixture
def fake_database(monkeypatch):
    """A connected pool whose information_schema we control."""
    state = {"queries": 0, "columns": set()}

    async def fetch(query, *args):
        state["queries"] += 1
        return [{"table_name": t, "column_name": c} for t, c in state["columns"]]

    monkeypatch.setattr(db, "_pool", object())
    monkeypatch.setattr(db, "fetch", fetch)
    monkeypatch.setattr(db, "_schema_gaps", [])
    monkeypatch.setattr(db, "_schema_checked_at", 0.0)
    everything = {(t, c or "id") for t, c, _ in db.REQUIRED_SCHEMA}
    state["columns"] = set(everything)
    yield state
    db._pool = None


async def test_a_complete_schema_has_no_gaps(fake_database):
    assert await db.check_schema(force=True) == []


async def test_a_missing_column_names_the_migration_to_apply(fake_database):
    fake_database["columns"].discard(("sessions", "key_hash"))
    gaps = await db.check_schema(force=True)
    assert gaps == ["sessions.key_hash (apply db/013_session_keys.sql)"]


async def test_a_missing_table_is_reported_too(fake_database):
    fake_database["columns"] = {
        (t, c) for t, c in fake_database["columns"] if t != "document_chunks"
    }
    gaps = await db.check_schema(force=True)
    assert "document_chunks (apply db/005_documents.sql)" in gaps


async def test_it_is_cached_between_health_calls(fake_database):
    await db.check_schema(force=True)
    await db.check_schema()
    await db.check_schema()
    assert fake_database["queries"] == 1
    await db.check_schema(force=True)
    assert fake_database["queries"] == 2


async def test_a_gap_marks_the_database_degraded(fake_database):
    fake_database["columns"].discard(("matches", "explanation_language"))
    await db.check_schema(force=True)
    assert "database" in _degraded(get_settings())


async def test_without_a_database_there_is_nothing_to_check(monkeypatch):
    monkeypatch.setattr(db, "_pool", None)
    assert await db.check_schema(force=True) == []
