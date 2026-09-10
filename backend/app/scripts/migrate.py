"""Apply the SQL files in db/ against DATABASE_URL, in order.

    cd backend
    python -m app.scripts.migrate            # apply everything
    python -m app.scripts.migrate --check    # connect and report, change nothing
    python -m app.scripts.migrate --only 001 # one file

Exists because psql is not always installed on Windows, and asyncpg already is.
Statements go through the simple query protocol, so multi-statement files and
dollar-quoted function bodies run exactly as written.

Every file in db/ is idempotent (`create ... if not exists`, `on conflict`), so
re-running is safe and is the normal way to pick up a schema change.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

import asyncpg

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("migrate")

DB_DIR = Path(__file__).resolve().parents[3] / "db"


def _mask(dsn: str) -> str:
    """Hide the password before anything is logged."""
    return re.sub(r"(://[^:/@]+:)[^@]*@", r"\1****@", dsn)


def _files(only: str | None) -> list[Path]:
    found = sorted(p for p in DB_DIR.glob("*.sql"))
    if only:
        found = [p for p in found if p.name.startswith(only)]
    return found


async def _report(conn: asyncpg.Connection) -> None:
    version = await conn.fetchval("select version()")
    logger.info("Connected: %s", version.split(",")[0])

    has_vector = await conn.fetchval(
        "select exists (select 1 from pg_extension where extname = 'vector')"
    )
    logger.info("pgvector installed: %s", has_vector)

    tables = await conn.fetch(
        "select tablename from pg_tables where schemaname = 'public' order by tablename"
    )
    names = [t["tablename"] for t in tables]
    logger.info("Public tables (%d): %s", len(names), ", ".join(names) or "none")

    if "skill_taxonomy" in names:
        total = await conn.fetchval("select count(*) from skill_taxonomy")
        embedded = await conn.fetchval(
            "select count(*) from skill_taxonomy where embedding is not null"
        )
        logger.info("Taxonomy: %d rows, %d embedded", total, embedded)
        if total and not embedded:
            logger.warning(
                "No embeddings yet. Semantic normalization stays inert until you "
                "run: python -m app.scripts.embed_taxonomy"
            )
    if "opportunities" in names:
        count = await conn.fetchval("select count(*) from opportunities where is_active")
        logger.info("Active opportunities: %d", count)


async def main(only: str | None, check_only: bool) -> int:
    settings = get_settings()
    if not settings.database_url:
        logger.error(
            "DATABASE_URL is not set. Add it to backend/.env:\n"
            "  DATABASE_URL=postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres"
        )
        return 1

    files = _files(only)
    if not files:
        logger.error("No .sql files found in %s", DB_DIR)
        return 1

    logger.info("Target: %s", _mask(settings.database_url))

    try:
        conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    except Exception as exc:
        logger.error("Could not connect: %s", exc)
        logger.error(
            "If this is a direct connection (db.PROJECT.supabase.co:5432) and your "
            "network is IPv4-only, use the transaction pooler string instead "
            "(...pooler.supabase.com:6543)."
        )
        return 1

    try:
        if check_only:
            await _report(conn)
            return 0

        for path in files:
            sql = path.read_text(encoding="utf-8")
            logger.info("Applying %s (%d bytes)", path.name, len(sql))
            try:
                # Each file in one transaction: a file either lands whole or
                # not at all, so a failure never leaves a half-built schema.
                async with conn.transaction():
                    await conn.execute(sql)
            except Exception as exc:
                logger.error("%s failed: %s", path.name, exc)
                logger.error("Nothing from that file was applied. Earlier files stand.")
                return 1
            logger.info("  ok")

        logger.info("")
        await _report(conn)
        logger.info("")
        logger.info("Next: python -m app.scripts.embed_taxonomy")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Connect and report only")
    parser.add_argument("--only", help="Apply just the file(s) with this prefix, e.g. 003")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.only, args.check)))
