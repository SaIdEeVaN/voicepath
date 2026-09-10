"""Compute and store embeddings for every taxonomy entry.

    cd backend
    python -m app.scripts.embed_taxonomy            # only missing ones
    python -m app.scripts.embed_taxonomy --all      # recompute everything

Run this after seeding, after adding taxonomy entries through the admin API,
and after changing EMBEDDING_MODEL. Until an entry has an embedding it is
invisible to normalization -- it cannot be matched at all, which is the safe
failure mode, but it does mean the skill silently never appears.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from app.config import get_settings
from app.data.catalogue import embedding_text, taxonomy_by_code
from app.services import db, embeddings

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("embed_taxonomy")


def _text_for(code: str, name: str, category: str, aliases: list[str]) -> str:
    """Prefer the catalogue's alias list; fall back to what the row holds."""
    known = taxonomy_by_code().get(code)
    if known:
        return embedding_text(known)
    parts = [name, category, *aliases]
    return " | ".join(p for p in parts if p)


async def main(recompute_all: bool) -> int:
    settings = get_settings()
    if not settings.database_url:
        logger.error("DATABASE_URL is not set. Nothing to write to.")
        return 1

    await db.init_pool()
    try:
        where = "" if recompute_all else "where embedding is null"
        rows = await db.fetch(
            f"select id, code, name, category, aliases from skill_taxonomy {where} "
            "order by code"
        )
        if not rows:
            logger.info("Nothing to embed. All entries already have vectors.")
            return 0

        logger.info(
            "Embedding %d entries with %s (%s)",
            len(rows), settings.embedding_model, settings.embedding_provider,
        )
        texts = [
            _text_for(r["code"], r["name"], r["category"], list(r["aliases"] or []))
            for r in rows
        ]
        vectors = await asyncio.to_thread(embeddings.embed_documents, texts)

        written = 0
        async with db.transaction() as conn:
            for row, vector in zip(rows, vectors):
                if len(vector) != settings.embedding_dimension:
                    logger.error(
                        "%s produced %d dims, column expects %d. Stopping.",
                        row["code"], len(vector), settings.embedding_dimension,
                    )
                    return 1
                await conn.execute(
                    "update skill_taxonomy set embedding = $2::vector where id = $1",
                    row["id"], db.vector_literal(vector),
                )
                written += 1

        logger.info("Wrote %d embeddings.", written)

        remaining = await db.fetchval(
            "select count(*) from skill_taxonomy where embedding is null"
        )
        if remaining:
            logger.warning("%d entries still have no embedding.", remaining)
        return 0
    finally:
        await db.close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", help="Recompute every entry, not just missing ones"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.all)))
