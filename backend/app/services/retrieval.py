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
    # True when full-text search matched, i.e. the words are literally in the
    # document. Dense similarity cannot carry this: e5 packs everything into a
    # narrow band, so "asdfghjkl" scores 0.79 against a corpus it shares no
    # word with. Whether a term actually appears is the honest signal.
    matched_keyword: bool = False
    # The government's own page for this document, when one has been recorded
    # in `data/scheme_docs/sources.json`. Defaulted rather than required: most
    # documents have no URL, that is the honest state, and nothing is ever
    # constructed to fill the gap.
    source_url: str | None = None


# Roughly 500 tokens. Measured in characters because the tokenizer lives behind
# the embedding API now, and a 4:1 character-to-token ratio is close enough for
# deciding where to cut a paragraph.
_TARGET_CHARS = 2000
# Carried from the end of one chunk into the start of the next, so an answer
# that straddles a boundary is not cut in half.
_OVERLAP_CHARS = 200

# Two independent signs that a block is prose. A block needs only one.
#
# Words per line catches ordinary wrapped prose, and is the original test --
# calibrated against portal pages, where menus run two to four words a line and
# the prose beside them fifteen and up.
_MIN_WORDS_PER_LINE = 6
# Sentence endings per 100 characters catches prose that wraps short because a
# PDF's layout made it, which the line test reads as a menu. Measured across a
# scheme playbook and the PM-AJAY guidelines: prose 0.61-0.75, contents pages
# and score tables 0.20-0.29.
_MIN_SENTENCE_DENSITY = 0.45

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


# A sentence ending, not a decimal point or a section number. "1.2 % of
# households" must not read as two sentences -- that is exactly the shape of
# the scoring tables this filter exists to reject.
_SENTENCE_END = re.compile(r"(?<!\d)[.!?।](?=\s|$)")


def _is_prose(text: str) -> bool:
    """Reject chunks that are flattened tables rather than sentences.

    A statistics table extracted from a PDF becomes "Literacy Rate (Census,
    2001) 54.7 64.8" -- meaningless as prose, but it still embeds to somewhere
    and competes for rank against passages that would actually answer the
    question. Retrieval has no way to tell it is noise; the cheapest place to
    exclude it is here.

    Two tests, because they catch different things.

    The share of characters that are letters rejects a table of figures: real
    sentences run well above 70% in every script we handle.

    Sentence-ending density rejects the rest -- a contents page, an annexure
    list, a navigation menu. None of them are sentences, and none of them carry
    full stops at anything like the rate prose does.

    Either sign of prose is enough, and that is the fix rather than the
    thresholds. Words per line alone was the original test, and it does not
    survive a designed PDF: ingesting a 107-page scheme playbook it rejected 88
    of 106 blocks and threw away 150,000 of 188,000 characters, including the
    scheme descriptions themselves, which the card layout wraps at four to five
    words a line. Sentence density alone is no better -- government prose runs
    to very long sentences, and a department's vision statement measured 0.29,
    indistinguishable from a contents page.

    A block that wraps long is prose. A block that wraps short but ends
    sentences at a normal rate is also prose. Only a block that does neither is
    furniture.
    """
    stripped = text.strip()
    if len(stripped) < 80:
        return False

    letters = sum(1 for ch in stripped if ch.isalpha())
    if letters / len(stripped) < 0.65:
        return False

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return False

    # Two independent signs of prose, and either is enough. Requiring both is
    # what broke card layouts: they wrap short, so they fail the line test
    # while reading as perfectly good sentences.
    words_per_line = sum(len(line.split()) for line in lines) / len(lines)
    if words_per_line >= _MIN_WORDS_PER_LINE:
        return True

    # Flattened, so a wrapped sentence counts once rather than once per line.
    flat = " ".join(lines)
    endings = len(_SENTENCE_END.findall(flat))
    return 100.0 * endings / len(flat) >= _MIN_SENTENCE_DENSITY


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
    *,
    title: str,
    source: str,
    text: str,
    language: str = "en",
    source_url: str | None = None,
    source_domain: str | None = None,
    trust_tier: int = 2,
    status: str = "active",
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
    #
    # What is embedded carries the document's title and the chunk's heading;
    # what is stored and quoted does not. A passage reading "Skill Verification
    # followed by 5-7 days Basic Training. Stipend Rs 500 per day" is exactly
    # the answer to "what training does PM Vishwakarma give" and contains none
    # of those words, because the scheme is named in the page's opening rather
    # than in every paragraph. Embedded bare it is unreachable by its own name.
    vectors = await asyncio.to_thread(
        embeddings.embed_documents,
        [
            " | ".join(part for part in (title, chunk.heading, chunk.content) if part)
            for chunk in chunks
        ],
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
            insert into scheme_documents
              (title, source, language, source_url, source_domain,
               trust_tier, status, retrieved_at)
            values ($1, $2, $3, $4, $5, $6, $7, now())
            on conflict (source) do update
              set title = excluded.title,
                  language = excluded.language,
                  source_url = excluded.source_url,
                  source_domain = excluded.source_domain,
                  trust_tier = excluded.trust_tier,
                  -- A re-fetch does not re-open a rejected source. An admin
                  -- decided that, and fetching the page again is not new
                  -- information about whether it should be trusted.
                  status = case
                    when scheme_documents.status = 'rejected' then 'rejected'
                    else excluded.status
                  end,
                  retrieved_at = now()
            returning id
            """,
            title, source, language, source_url, source_domain, trust_tier, status,
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


# Words that say what kind of question it is, not what it is about. The chunks
# are indexed with the `simple` config, which keeps every word, so a query
# that ANDed "who is eligible for" alongside the scheme's name needed all of
# them in one passage -- and natural questions matched nothing at all: measured
# against the live corpus, "Who is eligible for Sigaram Thodu?" found 0 chunks
# by keyword. Dropped before the query is built. "scheme" is here too: nearly
# every passage says it, so it ranks nothing.
_QUESTION_WORDS = frozenset(
    """
    a an the this that these those there here it its is are was were be been am
    to of in on at by for with from and or but if then than so as not no yes
    i you he she we they me my your our their his her us them
    what who whom whose which when where why how does do did done can could
    would should will shall may might must have has had get gets got give gives
    given tell explain about more details detail information info any some all
    also need needed want wants please know much many under scheme schemes
    hi hey hello thanks thank ok okay test
    क्या कौन किस कैसे कब कहाँ कहां है हैं था थी का की के में से को और या इस यह वह
    मुझे मेरा मेरी मेरे लिए पर भी तो कितना कितनी कितने बताइए बताओ बताएं योजना
    என்ன யார் எப்படி எங்கே எப்போது இது அது ஒரு மற்றும் பற்றி சொல்லுங்கள்
    சொல்லுங்க எனக்கு என் இந்த அந்த திட்டம் திட்டத்தின்
    """.split()
)

# Characters that carry no topic. Stripped from each word's edges only, so a
# hyphenated name like "pm-ajay" survives intact for the query.
_EDGE_PUNCTUATION = ".,!?;:\"'()[]{}<>“”‘’`|/\\।"


def content_terms(question: str) -> list[str]:
    """The words of a question that could be in a passage, in order, once each."""
    seen: list[str] = []
    for raw in (question or "").split():
        word = raw.strip(_EDGE_PUNCTUATION).lower()
        if len(word) < 2 or word in _QUESTION_WORDS or word in seen:
            continue
        seen.append(word)
    return seen


def _is_latin(text: str) -> bool:
    return all(ord(ch) < 0x250 for ch in text)


def _normalise(text: str) -> str:
    """Lower-cased, punctuation read as spaces, so "PM-AJAY?" meets "pm ajay"."""
    return " " + re.sub(
        r"[\s\-–—_.,!?;:\"'()\[\]{}<>/\\|।“”‘’`]+", " ", (text or "").lower()
    ).strip() + " "


def named_schemes(question: str) -> list[str]:
    """Keys of the schemes in data/scheme_names.py that a question names."""
    from app.data.scheme_names import SCHEME_NAMES

    haystack = _normalise(question)
    found: list[str] = []
    for key, entry in SCHEME_NAMES.items():
        for name in entry["names"]:
            needle = _normalise(name)
            if _is_latin(name):
                # Whole words: " ajay " inside " pm ajay scheme ", never inside
                # " vijayan ". The padding in _normalise makes that a plain
                # substring test.
                hit = needle in haystack
            else:
                # Tamil and Devanagari attach case endings to the name itself,
                # so the bare stem is matched wherever it occurs.
                hit = needle.strip() in haystack
            if hit:
                found.append(key)
                break
    return found


def named_sources(question: str) -> list[str]:
    """``scheme_documents.source`` values for every scheme the question names."""
    from app.data.scheme_names import SCHEME_NAMES

    sources: list[str] = []
    for key in named_schemes(question):
        for source in SCHEME_NAMES[key]["sources"]:
            if source not in sources:
                sources.append(source)
    return sources


async def search(
    question: str, *, limit: int = 5, sources: list[str] | None = None
) -> list[Retrieved]:
    """Hybrid retrieval: dense and keyword, merged.

    Dense search finds meaning and crosses languages. Keyword search finds exact
    strings -- "NSQF Level 4", a section number -- that a 768-dimensional
    average blurs away. Running both and merging costs one extra query and
    covers the failure mode of each.

    ``sources`` restricts both paths to those documents. It is set when the
    question names a scheme: a passage from another scheme's guidelines can
    read as a confident answer and be wrong in every particular.
    """
    clean = (question or "").strip()
    if not clean:
        return []

    vector = await asyncio.to_thread(embeddings.embed_query, clean)
    restrict = list(sources) if sources else None

    # Content words, ORed. ts_rank still puts passages holding more of them
    # first, and the fusion below does the rest.
    terms = content_terms(clean)
    keyword_query = " OR ".join(terms)

    dense_rows = db.fetch(
        """
        select c.id as chunk_id, d.title as document_title, d.source,
               d.source_url, c.heading, c.content,
               1 - (c.embedding <=> $1::vector) as similarity
        from document_chunks c
        join scheme_documents d on d.id = c.document_id
        -- A source awaiting verification, or rejected outright, must not be
        -- reachable by either route.
        where d.status = 'active'
          and c.embedding is not null
          and ($3::text[] is null or d.source = any($3::text[]))
        order by c.embedding <=> $1::vector
        limit $2
        """,
        db.vector_literal(vector), limit, restrict,
    )

    async def keyword_rows() -> list:
        if not terms:
            return []
        return await db.fetch(
            """
            select c.id as chunk_id, d.title as document_title, d.source,
                   d.source_url, c.heading, c.content,
                   ts_rank(c.tsv, websearch_to_tsquery('simple', $1)) as rank
            from document_chunks c
            join scheme_documents d on d.id = c.document_id
            where d.status = 'active'
              and c.tsv @@ websearch_to_tsquery('simple', $1)
              and ($3::text[] is null or d.source = any($3::text[]))
            order by rank desc
            limit $2
            """,
            keyword_query, limit, restrict,
        )

    dense, keyword = await asyncio.gather(dense_rows, keyword_rows())

    # Reciprocal rank fusion: score by position in each list rather than by raw
    # score. Cosine similarity and ts_rank are not on the same scale and cannot
    # be added; their rankings can be. A chunk found by both paths rises.
    scores: dict[int, float] = {}
    rows: dict[int, dict] = {}
    literal: set[int] = {row["chunk_id"] for row in keyword}
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
            source_url=rows[cid].get("source_url"),
            heading=rows[cid].get("heading"),
            content=rows[cid]["content"],
            # Present only on the dense path; keyword-only hits report 0.0
            # rather than a number from a different scale.
            similarity=float(rows[cid].get("similarity") or 0.0),
            matched_keyword=cid in literal,
        )
        for cid in best
    ]


# The chunks are indexed with the `simple` config, which keeps stop words --
# so "there" in "hi there" matches a corpus that says "there" constantly. These
# carry no topic and must not make a greeting look like a search. Only English
# function words: a Tamil or Hindi term is content by the time it reaches here.
_NOT_A_TOPIC = frozenset(
    """
    a an the this that these those there here it its is are was were be been am
    to of in on at by for with from and or but if then than so as
    i you he she we they me my your our their his her
    hi hey hello thanks thank ok okay yes no please test
    """.split()
)


async def mentions(text: str) -> bool:
    """Does the corpus contain any of these words?

    Separate from ``search`` on purpose. Search ANDs its terms, which is right
    for finding a passage -- "pm ajay skill development" should not match a
    chunk that merely says "development". This asks a weaker question for a
    different job: is any of this a word the documents actually use, or is it
    noise? "PM-AJAY" is; "asdfghjkl" is not.
    """
    clean = (text or "").strip()
    if not clean or not db.is_available():
        return False
    # OR across terms. websearch_to_tsquery is forgiving about punctuation --
    # "PM-AJAY" survives as a query rather than becoming a phrase operator.
    terms = [
        word
        for word in (w.strip(".,!?;:\"'()").lower() for w in clean.split())
        # Two characters or fewer is an initialism at best, and on its own it
        # matches too much. "PM" alone proves nothing; "AJAY" does.
        if len(word) > 2 and word not in _NOT_A_TOPIC
    ]
    if not terms:
        return False

    return bool(
        await db.fetchval(
            """
            select exists (
              select 1 from document_chunks
              where tsv @@ websearch_to_tsquery('simple', $1)
            )
            """,
            " OR ".join(terms),
        )
    )


async def is_ready() -> bool:
    """True when there is a corpus to retrieve from.

    `exists` rather than `count`: this is checked on every question that might
    be about the scheme, and it only ever needs to know whether the corpus is
    empty, not how large it is.
    """
    if not db.is_available():
        return False
    return bool(
        await db.fetchval(
            "select exists (select 1 from document_chunks where embedding is not null)"
        )
    )
