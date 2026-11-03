"""Postgres access.

One asyncpg pool for the process. pgvector values are passed as the literal
text form (``'[0.1,0.2,...]'``) and cast in SQL, which avoids requiring the
pgvector codec registration on every fresh connection in the pool.

When ``DATABASE_URL`` is unset the API still serves every route -- an in-memory
store stands in, so the pipeline can be exercised without Supabase. Nothing
survives a restart in that mode, and ``/health`` reports it.
"""

from __future__ import annotations

import json
import logging
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


def vector_literal(values: Sequence[float]) -> str:
    """pgvector's text input format."""
    return "[" + ",".join(f"{float(v):.6f}" for v in values) + "]"


def is_configured() -> bool:
    """A database was asked for, whether or not it answered."""
    return bool(get_settings().database_url)


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
    whether real admins exist). It does not reconnect on its own -- sessions
    started in memory would vanish mid-flow if it did -- so the next restart
    picks the database back up.
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
    global _pool, _unreachable
    _unreachable = None
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Postgres pool closed")


def pool() -> asyncpg.Pool | None:
    return _pool


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
            return {
                "connected": False,
                "configured": True,
                "reason": "unreachable at startup; running on the in-memory store",
                "error": _unreachable,
            }
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
        return {
            "connected": True,
            "configured": True,
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
