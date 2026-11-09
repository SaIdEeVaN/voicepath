"""Bring the database up to what the deployed code ships with.

Three things a new release can add that the database does not have yet, each
of which used to need someone to run a script by hand against production
with its password -- which nobody remembered, and which the build session
could not do at all:

* **Skills with no embedding.** Added by a seed file; until a vector is
  computed normalization cannot reach them, so the skill silently never
  appears. (``scripts/embed_taxonomy.py`` does the same by hand.)
* **Bundled documents not in the corpus.** A new file in
  ``data/scheme_docs`` is official text the assistant should be able to cite.
  (``scripts/ingest_documents.py`` does the same by hand.)
* **Documents with no URL**, when ``sources.json`` now records one. Filled in,
  never overwritten: a URL already there was put there on purpose.

Run at startup, in the background, so the API answers while it works -- and
again every half hour while anything is still missing (since 2026-11-09).
Before that it ran once: on 2026-11-05 the embedder was out of credits at
startup, and even after credits were added nothing loaded until someone
restarted the API by hand.
Idempotent: everything it does is "only what is missing", so a restart or a
second worker repeats nothing. It never re-opens a document an admin
rejected, and it does nothing at all when the embedding provider is offline,
because hash vectors written into the corpus would be wrong forever after.

Text files only (.md, .txt). The deployed image has no PDF reader, and the
PDFs already in the corpus were ingested by hand with one.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.config import get_settings
from app.data.catalogue import embedding_text, taxonomy_by_code
from app.services import db, embeddings, retrieval

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "scheme_docs"
SOURCES_FILE = "sources.json"
TEXT_SUFFIXES = {".md", ".txt"}
# Shorter than this is a stub or a failed extraction, not a document.
MIN_DOCUMENT_CHARS = 200


def _skill_text(code: str, name: str, category: str, aliases: list[str]) -> str:
    """The same text scripts/embed_taxonomy.py embeds, so vectors agree."""
    known = taxonomy_by_code().get(code)
    if known:
        return embedding_text(known)
    return " | ".join(p for p in (name, category, *aliases) if p)


def source_urls(directory: Path = DOCS_DIR) -> dict[str, str]:
    path = directory / SOURCES_FILE
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v.strip() for k, v in data.items()
            if not k.startswith("_") and isinstance(v, str) and v.strip()}


def _title(path: Path, text: str) -> str:
    """The document's own heading, or its file name made readable."""
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    if first.startswith("# "):
        return first[2:].strip()
    return path.stem.replace("_", " ").replace("-", " ").strip()


async def embed_missing_skills() -> int:
    rows = await db.fetch(
        "select id, code, name, category, aliases from skill_taxonomy "
        "where embedding is null order by code"
    )
    if not rows:
        return 0
    texts = [
        _skill_text(r["code"], r["name"], r["category"], list(r["aliases"] or []))
        for r in rows
    ]
    vectors = await asyncio.to_thread(embeddings.embed_documents, texts)
    dimension = get_settings().embedding_dimension
    written = 0
    async with db.transaction() as conn:
        for row, vector in zip(rows, vectors):
            if len(vector) != dimension:
                logger.error(
                    "Skill %s embedded to %d dims, column expects %d; stopping",
                    row["code"], len(vector), dimension,
                )
                break
            await conn.execute(
                "update skill_taxonomy set embedding = $2::vector "
                "where id = $1 and embedding is null",
                row["id"], db.vector_literal(vector),
            )
            written += 1
    return written


async def ingest_missing_documents(directory: Path = DOCS_DIR) -> int:
    if not directory.is_dir():
        return 0
    # Every source, whatever its status: a rejected one stays rejected.
    known = {r["source"] for r in await db.fetch("select source from scheme_documents")}
    urls = source_urls(directory)
    added = 0
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in TEXT_SUFFIXES or path.name in known:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text.strip()) < MIN_DOCUMENT_CHARS:
            logger.warning("%s: too short to be a document; skipped", path.name)
            continue
        url = urls.get(path.name)
        try:
            _, chunks = await retrieval.ingest(
                title=_title(path, text),
                source=path.name,
                text=text,
                language="en",
                source_url=url,
                source_domain=urlparse(url).hostname if url else None,
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the rest
            logger.warning("Could not ingest %s (%s); will retry next start", path.name, exc)
            continue
        logger.info("Ingested %s: %d chunks", path.name, chunks)
        added += 1
    return added


async def fill_missing_urls(directory: Path = DOCS_DIR) -> int:
    filled = 0
    for source, url in source_urls(directory).items():
        result = await db.execute(
            "update scheme_documents set source_url = $2, source_domain = $3 "
            "where source = $1 and (source_url is null or source_url = '')",
            source, url, urlparse(url).hostname,
        )
        if str(result).endswith(" 1"):
            filled += 1
    return filled


async def catch_up() -> dict[str, int]:
    """Do whatever is missing. Returns how much of each was done."""
    if not db.is_available():
        return {}
    if get_settings().embedding_provider == "offline":
        logger.info(
            "Corpus catch-up skipped: embeddings are offline, and hash vectors "
            "must never be written into the corpus"
        )
        return {}
    # Each step on its own: one failing must not stop the others. URLs first,
    # because they need no embedder -- on 2026-11-04 the embedder was out of
    # credits, and a catch-up that stopped at the first error filled nothing.
    done: dict[str, int] = {}
    for name, step in (
        ("urls_filled", fill_missing_urls),
        ("skills_embedded", embed_missing_skills),
        ("documents_ingested", ingest_missing_documents),
    ):
        if name != "urls_filled" and embeddings.recent_failure() is not None:
            # The embedder just refused; every remaining step would too.
            done[name] = 0
            continue
        try:
            done[name] = await step()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - retried on next start
            logger.warning("Corpus catch-up: %s failed (%s)", name, exc)
            done[name] = 0
    if any(done.values()):
        logger.info("Corpus catch-up: %s", done)
    return done


async def catch_up_safely() -> None:
    """Background entry point: log and carry on, never take the API down."""
    try:
        await catch_up()
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - an enhancement, retried next start
        logger.warning("Corpus catch-up failed (%s); will retry on next start", exc)


# ---------------------------------------------------------------------------
# Trying again until nothing is missing
# ---------------------------------------------------------------------------

RETRY_SECONDS = 30 * 60

# What the last check found still missing, and when the next try is -- for
# /health, so whoever added the credits can see the backlog drain.
_status: dict[str, object] = {}


def status() -> dict[str, object]:
    return dict(_status)


async def missing(directory: Path = DOCS_DIR) -> dict[str, int]:
    """What a catch-up would still do: skills with no vector, documents not in."""
    if not db.is_available():
        return {}
    skills = await db.fetchval("select count(*) from skill_taxonomy where embedding is null")
    known = {r["source"] for r in await db.fetch("select source from scheme_documents")}
    documents = 0
    if directory.is_dir():
        for path in directory.iterdir():
            if path.suffix.lower() not in TEXT_SUFFIXES or path.name in known:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text.strip()) >= MIN_DOCUMENT_CHARS:
                documents += 1
    return {"skills": int(skills or 0), "documents": documents}


async def keep_catching_up(
    *,
    retry_seconds: float = RETRY_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Catch up now, and every ``retry_seconds`` while anything is missing.

    Each try costs one request to a refusing embedder at most (catch_up stops
    at the first refusal). Stops for good once nothing is missing, and does
    nothing at all without a database or with the offline embedder, where no
    amount of trying would help.
    """
    while True:
        await catch_up_safely()
        if not db.is_available() or get_settings().embedding_provider == "offline":
            _status.clear()
            return
        try:
            left = await missing()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - unknown means "try again later"
            logger.warning("Corpus catch-up: could not count what is missing (%s)", exc)
            left = {"unknown": 1}
        if not any(left.values()):
            _status.clear()
            _status["missing"] = {"skills": 0, "documents": 0}
            return
        next_try = datetime.now(timezone.utc) + timedelta(seconds=retry_seconds)
        _status.update(missing=left, next_try=next_try.isoformat(timespec="seconds"))
        logger.info(
            "Corpus catch-up: still missing %s; trying again at %s", left, _status["next_try"]
        )
        await sleep(retry_seconds)
