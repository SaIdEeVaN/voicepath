"""Postgres access.

One asyncpg pool for the process. pgvector values are passed as the literal
text form (``'[0.1,0.2,...]'``) and cast in SQL, which avoids requiring the
pgvector codec registration on every fresh connection in the pool.

When ``DATABASE_URL`` is unset the API still serves every route -- an in-memory
store stands in, so the pipeline can be exercised without Supabase. Nothing
survives a restart in that mode, and ``/health`` reports it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Sequence

import asyncpg

from app.config import get_settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

# Set when DATABASE_URL is configured but the database could not be reached at
# startup: the kind of error, never its message. None when connected, and
# None when no database was configured at all -- those are different states,
# and /health and the admin gate both need to tell them apart.
_unreachable: str | None = None

# How long startup waits for the first connection. A free host gives the
# process a short window to open its port; a database that is paused or gone
# should cost seconds of that window, not all of it.
CONNECT_TIMEOUT_SECONDS = 15.0

# After an outage at startup: how long to wait before each try, the last
# repeating. A restored Supabase project takes a minute or two to answer.
RECONNECT_DELAYS_SECONDS: tuple[float, ...] = (15.0, 30.0, 60.0, 120.0, 300.0)
# Once the database answers, how often to check whether the sessions started
# in memory during the outage have finished.
QUIET_CHECK_SECONDS = 60.0

# What the background reconnect is doing, for /health. None when not running.
_reconnect_state: str | None = None


def vector_literal(values: Sequence[float]) -> str:
    """pgvector's text input format."""
    return "[" + ",".join(f"{float(v):.6f}" for v in values) + "]"


def is_configured() -> bool:
    """A database was asked for, whether or not it answered."""
    return bool(get_settings().database_url)


# ---------------------------------------------------------------------------
# The schema the code needs
# ---------------------------------------------------------------------------
#
# On 2026-09-12 code that wrote matches.explanation_language reached production
# before db/007 added the column. Every route touching a match failed, and
# /health stayed green: the database was connected, and connected was all it
# checked. Now it also checks that every table and column a migration added is
# there, and says which migration to apply. tests/test_schema_check.py reads
# every file in db/ and fails if a migration adds one that is not listed here.

REQUIRED_SCHEMA: tuple[tuple[str, str | None, str], ...] = (
    # (table, column or None for the table itself, migration that adds it)
    ("scheme_documents", None, "005_documents.sql"),
    ("document_chunks", None, "005_documents.sql"),
    ("schemes", "official_url", "006_schemes_rename.sql"),
    ("matches", "scheme_id", "006_schemes_rename.sql"),
    ("matches", "explanation_language", "007_match_language.sql"),
    ("scheme_documents", "source_url", "009_document_source_url.sql"),
    ("schemes", "skill_match", "010_national_schemes.sql"),
    ("sessions", "key_hash", "013_session_keys.sql"),
)
# How long a schema check is trusted. /health is called often (the site asks
# every minute while open); the schema changes only when someone migrates.
SCHEMA_CHECK_SECONDS = 300.0

_schema_gaps: list[str] = []
_schema_checked_at = 0.0


async def check_schema(*, force: bool = False) -> list[str]:
    """Missing tables and columns, as "table.column (apply 0NN_file.sql)"."""
    global _schema_gaps, _schema_checked_at
    if _pool is None:
        return []
    now = asyncio.get_running_loop().time()
    if not force and _schema_checked_at and now - _schema_checked_at < SCHEMA_CHECK_SECONDS:
        return list(_schema_gaps)
    rows = await fetch(
        "select table_name, column_name from information_schema.columns "
        "where table_schema = 'public'"
    )
    present = {(r["table_name"], r["column_name"]) for r in rows}
    tables = {table for table, _ in present}
    gaps = []
    for table, column, migration in REQUIRED_SCHEMA:
        found = table in tables if column is None else (table, column) in present
        if not found:
            name = table if column is None else f"{table}.{column}"
            gaps.append(f"{name} (apply db/{migration})")
    if gaps and gaps != _schema_gaps:
        logger.error("The database is missing what the code needs: %s", "; ".join(gaps))
    _schema_gaps = gaps
    _schema_checked_at = now
    return list(gaps)


def schema_gaps() -> list[str]:
    """What the last schema check found missing; [] when complete or unchecked."""
    return list(_schema_gaps)


def unreachable() -> str | None:
    """Why a configured database is not in use, or None if it is (or none is)."""
    return _unreachable


async def init_pool() -> asyncpg.Pool | None:
    """Connect, or fall back to the in-memory store and say so.

    A database that cannot be reached used to stop the API from starting at
    all. On 2026-11-03 the Supabase project was paused for inactivity, every
    boot died on its first connection, and the whole product -- the catalogue,
    matching and the map included, none of which need the database -- was
    down with it.

    Now the API starts on the in-memory store instead. Nothing is hidden:
    the error is logged in full, ``/health`` lists ``database`` as degraded
    and says it is configured but unreachable, the interface shows a notice,
    and the admin gate stops honouring the bootstrap token (it cannot see
    whether real admins exist). ``reconnect_in_background`` then keeps
    trying, and switches over once nobody is mid-flow on the in-memory store
    (2026-11-05); before that, only a restart picked the database back up.
    """
    global _pool, _unreachable
    settings = get_settings()
    if not settings.database_url:
        logger.warning(
            "DATABASE_URL is not set. Running with the in-memory store; "
            "sessions, profiles and matches will not survive a restart."
        )
        return None
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=10,
                # Supabase's pooler does not support server-side prepared
                # statements in transaction mode; disabling the cache keeps the
                # same code working against both the pooler and a direct
                # connection.
                statement_cache_size=0,
                command_timeout=30,
                timeout=CONNECT_TIMEOUT_SECONDS,
                init=_init_connection,
            )
        except Exception as exc:  # noqa: BLE001 - any failure here means "no database"
            _unreachable = type(exc).__name__
            logger.error(
                "DATABASE_URL is set but the database could not be reached "
                "(%s: %s). Starting with the in-memory store: nothing is saved "
                "until the database is back and the API restarts.",
                type(exc).__name__, exc,
            )
            return None
        _unreachable = None
        logger.info("Postgres pool ready")
    return _pool


async def _init_connection(conn: asyncpg.Connection) -> None:
    # jsonb in and out as Python objects rather than strings.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def close_pool() -> None:
    global _pool, _unreachable, _reconnect_state
    _unreachable = None
    _reconnect_state = None
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Postgres pool closed")


def pool() -> asyncpg.Pool | None:
    return _pool


async def _reachable() -> bool:
    """One throwaway connection: does the database answer at all?"""
    try:
        conn = await asyncpg.connect(
            dsn=get_settings().database_url,
            timeout=CONNECT_TIMEOUT_SECONDS,
            statement_cache_size=0,
        )
    except Exception as exc:  # noqa: BLE001 - any failure means "not yet"
        logger.info("Database still unreachable (%s)", type(exc).__name__)
        return False
    try:
        await conn.close()
    except Exception:  # noqa: BLE001 - it answered; closing is not the question
        pass
    return True


async def reconnect_in_background(
    *,
    is_quiet: Callable[[], bool],
    on_connected: Callable[[], Awaitable[None]],
    delays: Sequence[float] = RECONNECT_DELAYS_SECONDS,
    quiet_check: float = QUIET_CHECK_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> bool:
    """Keep trying a database that did not answer at startup; switch when safe.

    Before 2026-11-05 the API stayed on the in-memory store until someone
    restarted it, however soon the database came back. Now it retries -- 15s,
    30s, 1m, 2m, then every 5 minutes -- and once the database answers, waits
    for ``is_quiet()``: nobody mid-flow on the in-memory store. Switching under
    someone would continue their session against a different catalogue (the
    in-memory skill and scheme ids are not the database's). Then the pool is
    opened and ``on_connected`` runs. Returns True once switched.
    """
    global _reconnect_state
    if not is_configured():
        return False
    attempt = 0
    while _pool is None:
        _reconnect_state = "retrying"
        await sleep(delays[min(attempt, len(delays) - 1)])
        attempt += 1
        if not await _reachable():
            continue
        while not is_quiet():
            _reconnect_state = "waiting for sessions started during the outage to finish"
            logger.info("Database answers again; waiting for in-memory sessions to finish")
            await sleep(quiet_check)
        if await init_pool() is None:
            continue
        _reconnect_state = None
        logger.warning("Reconnected to the database after %d attempt(s)", attempt)
        try:
            await on_connected()
        except Exception:  # noqa: BLE001 - connected either way; say what failed
            logger.exception("Reconnected, but the follow-up work failed")
        return True
    _reconnect_state = None
    return True


def reconnect_state() -> str | None:
    return _reconnect_state


def is_available() -> bool:
    return _pool is not None


@asynccontextmanager
async def connection() -> AsyncIterator[asyncpg.Connection]:
    if _pool is None:
        raise RuntimeError("Database is not configured (DATABASE_URL unset)")
    async with _pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def transaction() -> AsyncIterator[asyncpg.Connection]:
    """Short transaction. Do no network I/O inside it -- an LLM call held open
    across a transaction pins a pool connection for the length of the call."""
    async with connection() as conn:
        async with conn.transaction():
            yield conn


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    async with connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> asyncpg.Record | None:
    async with connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    async with connection() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args: Any) -> str:
    async with connection() as conn:
        return await conn.execute(query, *args)


async def healthcheck() -> dict[str, Any]:
    if _pool is None:
        if _unreachable is not None:
            # The kind of error only. /health is public, and a driver's
            # message can name the host, the project or the user.
            answer = {
                "connected": False,
                "configured": True,
                "reason": "unreachable at startup; running on the in-memory store",
                "error": _unreachable,
            }
            if _reconnect_state is not None:
                answer["reconnect"] = _reconnect_state
            return answer
        return {"connected": False, "configured": False, "reason": "DATABASE_URL not set"}
    try:
        async with connection() as conn:
            await conn.fetchval("select 1")
            has_vector = await conn.fetchval(
                "select exists (select 1 from pg_extension where extname = 'vector')"
            )
            taxonomy = await conn.fetchval("select count(*) from skill_taxonomy")
            embedded = await conn.fetchval(
                "select count(*) from skill_taxonomy where embedding is not null"
            )
            schemes = await conn.fetchval(
                "select count(*) from schemes where is_active"
            )
        gaps = await check_schema()
        return {
            "connected": True,
            "configured": True,
            # Connected is not the same as usable: a migration the code
            # depends on may not have been applied.
            "schema": {"ok": not gaps, "missing": gaps},
            "pgvector": bool(has_vector),
            "taxonomy_rows": taxonomy,
            "taxonomy_embedded": embedded,
            "active_schemes": schemes,
        }
    except Exception as exc:  # pragma: no cover - depends on live database
        logger.exception("Database healthcheck failed")
        # Full detail is in the log line above; the public answer names the
        # kind of failure only.
        return {
            "connected": False,
            "configured": True,
            "reason": "query failed",
            "error": type(exc).__name__,
        }
