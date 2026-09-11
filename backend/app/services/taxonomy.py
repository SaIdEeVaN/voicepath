"""Skill taxonomy access.

Reads from Postgres when it is configured, and from the in-process catalogue
otherwise. Both paths return the same shape, so ``normalization.py`` and
``matching.py`` never branch on which one is live.

The in-memory path embeds the catalogue once, on first use. With the offline
embedding provider that is instant; with a real model it is a few seconds at
first request, and then cached for the life of the process.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app.data.catalogue import TAXONOMY, display_names_for, embedding_text
from app.services import db, embeddings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaxonomySkill:
    id: int
    code: str
    name: str
    category: str
    hint: str | None
    embedding: list[float] | None = None
    # {"en": ..., "ta": ..., "hi": ...}. English is always present.
    display_names: dict[str, str] = field(default_factory=dict)

    def localized(self, language: str | None) -> str:
        """The label to show a speaker of `language`, falling back to English."""
        names = self.display_names or {}
        code = (language or "en").split("-")[0].lower()
        return names.get(code) or names.get("en") or self.name


@dataclass(frozen=True)
class ScoredSkill:
    skill: TaxonomySkill
    similarity: float


_memory_cache: list[TaxonomySkill] | None = None
_memory_lock = asyncio.Lock()


async def _memory_taxonomy() -> list[TaxonomySkill]:
    global _memory_cache
    if _memory_cache is not None:
        return _memory_cache
    async with _memory_lock:
        if _memory_cache is not None:
            return _memory_cache
        logger.info("Embedding %d taxonomy entries in memory", len(TAXONOMY))
        texts = [embedding_text(e) for e in TAXONOMY]
        # Blocking model work; keep the event loop free.
        vectors = await asyncio.to_thread(embeddings.embed_documents, texts)
        _memory_cache = [
            TaxonomySkill(
                id=index + 1,
                code=entry["code"],
                name=entry["name"],
                category=entry["category"],
                hint=entry["hint"],
                embedding=vector,
                display_names=display_names_for(entry["code"], entry["name"]),
            )
            for index, (entry, vector) in enumerate(zip(TAXONOMY, vectors))
        ]
        return _memory_cache


def reset_memory_cache() -> None:
    """Used by tests that switch embedding providers mid-run."""
    global _memory_cache, _alias_index
    _memory_cache = None
    _alias_index = None


# ---------------------------------------------------------------------------
# Lexical alias index
# ---------------------------------------------------------------------------
#
# When someone says a phrase that IS one of a skill's aliases -- "welding",
# "बाइक रिपेयर", "மோட்டார் சைக்கிள் ரிப்பேர்" -- that is stronger evidence than
# any similarity score, and it should not depend on an embedding model agreeing.
#
# It also fixes a real dilution effect: a taxonomy node's embedding blends a
# dozen aliases into one vector, so an exact hit on any single alias scores
# well below what its exactness deserves.

_alias_index: dict[str, int] | None = None
_alias_lock = asyncio.Lock()

_WS = re.compile(r"\s+")


def _fold(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFKC", text or "")).strip().casefold()


async def _get_alias_index() -> dict[str, int]:
    """Map folded alias -> taxonomy id.

    First writer wins on collision: two skills sharing an alias is a taxonomy
    problem, and silently preferring the later one would hide it.
    """
    global _alias_index
    if _alias_index is not None:
        return _alias_index
    async with _alias_lock:
        if _alias_index is not None:
            return _alias_index

        index: dict[str, int] = {}

        def add(key: str, skill_id: int) -> None:
            folded = _fold(key)
            if len(folded) >= 3:
                index.setdefault(folded, skill_id)

        if db.is_available():
            rows = await db.fetch("select id, name, aliases from skill_taxonomy")
            for row in rows:
                add(row["name"], row["id"])
                for alias in row["aliases"] or []:
                    if isinstance(alias, str):
                        add(alias, row["id"])
        else:
            for skill, entry in zip(await _memory_taxonomy(), TAXONOMY):
                add(entry["name"], skill.id)
                for alias in entry["aliases"]:
                    add(alias, skill.id)

        _alias_index = index
        return _alias_index


async def lexical_match(phrase: str) -> TaxonomySkill | None:
    """Exact alias or name hit for a spoken phrase, if there is one.

    Deliberately exact rather than fuzzy. A substring rule would map "welding
    certificate" onto Welding, which is precisely the kind of upgrade the PRD
    forbids -- so a near miss falls through to embedding search, where it can be
    flagged for the user instead.
    """
    folded = _fold(phrase)
    if len(folded) < 3:
        return None
    index = await _get_alias_index()
    skill_id = index.get(folded)
    if skill_id is None:
        return None
    found = await get_by_ids([skill_id])
    return found.get(skill_id)


async def list_all() -> list[TaxonomySkill]:
    if db.is_available():
        rows = await db.fetch(
            "select id, code, name, category, hint, display_names "
            "from skill_taxonomy order by code"
        )
        return [
            TaxonomySkill(
                id=r["id"], code=r["code"], name=r["name"],
                category=r["category"], hint=r["hint"],
                display_names=dict(r["display_names"] or {}),
            )
            for r in rows
        ]
    return [
        TaxonomySkill(s.id, s.code, s.name, s.category, s.hint,
                      display_names=s.display_names)
        for s in await _memory_taxonomy()
    ]


async def get_by_ids(ids: list[int]) -> dict[int, TaxonomySkill]:
    if not ids:
        return {}
    if db.is_available():
        rows = await db.fetch(
            "select id, code, name, category, hint, display_names "
            "from skill_taxonomy where id = any($1::bigint[])",
            ids,
        )
        return {
            r["id"]: TaxonomySkill(
                id=r["id"], code=r["code"], name=r["name"],
                category=r["category"], hint=r["hint"],
                display_names=dict(r["display_names"] or {}),
            )
            for r in rows
        }
    wanted = set(ids)
    return {
        s.id: TaxonomySkill(s.id, s.code, s.name, s.category, s.hint,
                            display_names=s.display_names)
        for s in await _memory_taxonomy()
        if s.id in wanted
    }


async def get_by_code(code: str) -> TaxonomySkill | None:
    if db.is_available():
        row = await db.fetchrow(
            "select id, code, name, category, hint, display_names "
            "from skill_taxonomy where code = $1",
            code,
        )
        if row is None:
            return None
        return TaxonomySkill(
            id=row["id"], code=row["code"], name=row["name"],
            category=row["category"], hint=row["hint"],
            display_names=dict(row["display_names"] or {}),
        )
    for skill in await _memory_taxonomy():
        if skill.code == code:
            return TaxonomySkill(skill.id, skill.code, skill.name, skill.category,
                                 skill.hint, display_names=skill.display_names)
    return None


async def search(query: str, *, limit: int = 5) -> list[ScoredSkill]:
    """Nearest taxonomy entries for a spoken phrase, best first."""
    text = (query or "").strip()
    if not text:
        return []
    vector = await asyncio.to_thread(embeddings.embed_query, text)
    return await search_by_vector(vector, limit=limit)


async def search_by_vector(
    vector: list[float], *, limit: int = 5
) -> list[ScoredSkill]:
    if db.is_available():
        rows = await db.fetch(
            "select id, code, name, category, hint, display_names, similarity "
            "from match_skill_taxonomy($1::vector, $2, 0.0)",
            db.vector_literal(vector),
            limit,
        )
        return [
            ScoredSkill(
                skill=TaxonomySkill(
                    id=r["id"], code=r["code"], name=r["name"],
                    category=r["category"], hint=r["hint"],
                    display_names=dict(r["display_names"] or {}),
                ),
                similarity=float(r["similarity"]),
            )
            for r in rows
        ]

    scored = [
        ScoredSkill(
            skill=TaxonomySkill(s.id, s.code, s.name, s.category, s.hint,
                                display_names=s.display_names),
            similarity=embeddings.cosine_similarity(vector, s.embedding or []),
        )
        for s in await _memory_taxonomy()
    ]
    scored.sort(key=lambda s: s.similarity, reverse=True)
    return scored[:limit]


async def embedding_for_skill_ids(ids: list[int]) -> dict[int, list[float]]:
    """Embeddings for taxonomy entries, used to score scheme requirements."""
    if not ids:
        return {}
    if db.is_available():
        rows = await db.fetch(
            "select id, embedding::text as embedding from skill_taxonomy "
            "where id = any($1::bigint[]) and embedding is not null",
            ids,
        )
        out: dict[int, list[float]] = {}
        for row in rows:
            raw = row["embedding"]
            if not raw:
                continue
            out[row["id"]] = [float(x) for x in raw.strip("[]").split(",") if x]
        return out
    wanted = set(ids)
    return {
        s.id: list(s.embedding or [])
        for s in await _memory_taxonomy()
        if s.id in wanted and s.embedding
    }
