"""Retrieval over scheme documents (PRD section 9, local only).

Why this exists, and where it is deliberately not used.

The scheme catalogue is small enough to reason over directly -- the whole
of it is roughly 700 tokens, and the model's context window holds 131,000. There
is nothing to retrieve *from*. Policy documents are the opposite: scheme
guidelines run to hundreds of pages, and a person's question ("am I eligible if
my income is above the limit?") cannot be answered from a scheme row at
any length.

So retrieval answers questions about the scheme. It never touches matching.
``services/matching.py`` imports no LLM and no retrieval, and that is the
property that makes a ranking defensible: the same profile against the same
catalogue produces the same order every time. A retrieved document must never
be able to move someone up a list.

Two retrieval paths, combined:

``dense``    embeddings, via the same multilingual-e5-base the taxonomy uses.
             Finds meaning across languages -- a Tamil question can match an
             English paragraph.
``keyword``  Postgres full-text. Finds exact strings that embeddings blur:
             "NSQF Level 4", a section number, a scheme code.

Neither alone is enough, which is why both are here.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from app.config import get_settings
from app.services import db, embeddings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Chunk:
    """A retrievable passage, with enough context to be cited."""

    content: str
    heading: str | None
    ordinal: int


@dataclass(frozen=True)
class Retrieved:
    """A chunk found for a question, with where it came from."""

    chunk_id: int
    document_title: str
    source: str
    heading: str | None
    content: str
    similarity: float


# Roughly 500 tokens. Measured in characters because the tokenizer lives behind
# the embedding API now, and a 4:1 character-to-token ratio is close enough for
# deciding where to cut a paragraph.
_TARGET_CHARS = 2000
# Carried from the end of one chunk into the start of the next, so an answer
# that straddles a boundary is not cut in half.
_OVERLAP_CHARS = 200

# A heading is a short line that is not a sentence: numbered clauses, ALL CAPS
# titles, or a bare title case line. Crude, and deliberately so -- the cost of a
# missed heading is a chunk with no label, not a wrong answer.
_HEADING = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+\S.{0,80}|[A-Z][A-Z\s\d.,'&()-]{4,80})\s*$"
)


def chunk_text(text: str) -> list[Chunk]:
    """Split a document into retrievable passages.

    Structure first, size second. Splitting purely by character count severs
    eligibility clauses and tables mid-thought, and a fragment that means
    nothing on its own cannot be rescued by any amount of prompting later.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]

    chunks: list[Chunk] = []
    buffer: list[str] = []
    heading: str | None = None
    size = 0

    def flush(carry_overlap: bool = True) -> None:
        """Emit the buffered text as a chunk.

        ``carry_overlap`` is False at a section boundary. Overlap exists so an
        answer spanning a split is not severed -- but carried across a heading
        it files one section's text under another's label, which misleads
        retrieval and makes the citation point at the wrong clause.
        """
        nonlocal buffer, size
        if not buffer:
            return
        body = "\n\n".join(buffer).strip()
        if body:
            chunks.append(Chunk(content=body, heading=heading, ordinal=len(chunks)))
        tail = ""
        if carry_overlap and len(body) > _OVERLAP_CHARS:
            tail = _clean_overlap(body[-_OVERLAP_CHARS:])
        buffer = [tail] if tail else []
        size = len(tail)

    for block in blocks:
        if _HEADING.match(block) and len(block) < 100:
            # A heading starts a new passage: the text under it is about
            # something new, and mixing the two blurs both.
            flush(carry_overlap=False)
            heading = block.strip()
            continue

        # A single block larger than the target is split on sentence ends, so
        # the cut lands between thoughts rather than inside one.
        if len(block) > _TARGET_CHARS:
            flush()
            for piece in _split_long(block):
                chunks.append(
                    Chunk(content=piece, heading=heading, ordinal=len(chunks))
                )
            continue

        if size + len(block) > _TARGET_CHARS:
            flush()
        buffer.append(block)
        size += len(block)

    flush()
    return [c for c in chunks if _is_prose(c.content)]


def _is_prose(text: str) -> bool:
    """Reject chunks that are flattened tables rather than sentences.

    A statistics table extracted from a PDF becomes "Literacy Rate (Census,
    2001) 54.7 64.8" -- meaningless as prose, but it still embeds to somewhere
    and competes for rank against passages that would actually answer the
    question. Retrieval has no way to tell it is noise; the cheapest place to
    exclude it is here.

    The test is the share of characters that are letters. Real sentences run
    well above 70% in every script we handle; a table of figures falls far
    below it.
    """
    stripped = text.strip()
    if len(stripped) < 80:
        return False
    letters = sum(1 for ch in stripped if ch.isalpha())
    return letters / len(stripped) >= 0.65


def _clean_overlap(tail: str) -> str:
    """Trim a carried tail to start at a real boundary.

    Slicing the last N characters lands mid-word about as often as not, and a
    chunk opening with "lage during the last one year" embeds badly and reads as
    nonsense when it is quoted back as a citation. Prefer the start of the last
    sentence; fall back to the next word boundary.
    """
    sentences = re.split(r"(?<=[.!?।])\s+", tail)
    if len(sentences) > 1 and len(sentences[-1]) > 40:
        return sentences[-1].strip()
    space = tail.find(" ")
    return tail[space + 1:].strip() if space != -1 else tail.strip()


def _split_long(block: str) -> list[str]:
    """Cut an oversized block at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?।])\s+", block)
    out: list[str] = []
    current: list[str] = []
    size = 0
    for sentence in sentences:
        if size + len(sentence) > _TARGET_CHARS and current:
            out.append(" ".join(current))
            current, size = [], 0
        current.append(sentence)
        size += len(sentence)
    if current:
        out.append(" ".join(current))
    return [piece for piece in out if piece.strip()]


async def ingest(
    *, title: str, source: str, text: str, language: str = "en"
) -> tuple[int, int]:
    """Chunk, embed and store one document. Returns (document_id, chunk_count).

    Re-ingesting the same source replaces its chunks. Documents get revised and
    extraction gets better; leaving the old passages behind would mean retrieval
    quietly citing a version nobody can find any more.
    """
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError(f"{source}: nothing to ingest after chunking")

    # Documents are embedded as passages, questions as queries. e5 is trained
    # with both prefixes and loses accuracy without them; embed_documents
    # applies the passage prefix for us.
    vectors = await asyncio.to_thread(
        embeddings.embed_documents, [c.content for c in chunks]
    )

    settings = get_settings()
    for vector in vectors:
        if len(vector) != settings.embedding_dimension:
            raise ValueError(
                f"{source}: embedder produced {len(vector)} dims, "
                f"the column expects {settings.embedding_dimension}"
            )

    async with db.transaction() as conn:
        document_id = await conn.fetchval(
            """
            insert into scheme_documents (title, source, language)
            values ($1, $2, $3)
            on conflict (source) do update
              set title = excluded.title, language = excluded.language
            returning id
            """,
            title, source, language,
        )
        await conn.execute(
            "delete from document_chunks where document_id = $1", document_id
        )
        for chunk, vector in zip(chunks, vectors):
            await conn.execute(
                """
                insert into document_chunks
                  (document_id, ordinal, heading, content, embedding)
                values ($1, $2, $3, $4, $5::vector)
                """,
                document_id, chunk.ordinal, chunk.heading, chunk.content,
                db.vector_literal(vector),
            )

    logger.info("Ingested %s: %d chunks", source, len(chunks))
    return document_id, len(chunks)


async def search(question: str, *, limit: int = 5) -> list[Retrieved]:
    """Hybrid retrieval: dense and keyword, merged.

    Dense search finds meaning and crosses languages. Keyword search finds exact
    strings -- "NSQF Level 4", a section number -- that a 768-dimensional
    average blurs away. Running both and merging costs one extra query and
    covers the failure mode of each.
    """
    clean = (question or "").strip()
    if not clean:
        return []

    vector = await asyncio.to_thread(embeddings.embed_query, clean)

    dense, keyword = await asyncio.gather(
        db.fetch(
            "select * from match_document_chunks($1::vector, $2, 0.0)",
            db.vector_literal(vector), limit,
        ),
        db.fetch(
            """
            select c.id as chunk_id, d.title as document_title, d.source,
                   c.heading, c.content,
                   ts_rank(c.tsv, plainto_tsquery('simple', $1)) as rank
            from document_chunks c
            join scheme_documents d on d.id = c.document_id
            where c.tsv @@ plainto_tsquery('simple', $1)
            order by rank desc
            limit $2
            """,
            clean, limit,
        ),
    )

    # Reciprocal rank fusion: score by position in each list rather than by raw
    # score. Cosine similarity and ts_rank are not on the same scale and cannot
    # be added; their rankings can be. A chunk found by both paths rises.
    scores: dict[int, float] = {}
    rows: dict[int, dict] = {}
    for ranking in (dense, keyword):
        for position, row in enumerate(ranking):
            chunk_id = row["chunk_id"]
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (60 + position)
            rows.setdefault(chunk_id, dict(row))

    best = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:limit]
    return [
        Retrieved(
            chunk_id=cid,
            document_title=rows[cid]["document_title"],
            source=rows[cid]["source"],
            heading=rows[cid].get("heading"),
            content=rows[cid]["content"],
            # Present only on the dense path; keyword-only hits report 0.0
            # rather than a number from a different scale.
            similarity=float(rows[cid].get("similarity") or 0.0),
        )
        for cid in best
    ]


async def is_ready() -> bool:
    """True when there is a corpus to retrieve from."""
    if not db.is_available():
        return False
    count = await db.fetchval(
        "select count(*) from document_chunks where embedding is not null"
    )
    return bool(count)
