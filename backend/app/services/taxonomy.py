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
import math
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
        try:
            vectors: list[list[float] | None] = list(
                await asyncio.to_thread(embeddings.embed_documents, texts)
            )
        except embeddings.EmbeddingUnavailable as exc:
            # Names and aliases need no vector, so the skill list still
            # answers; it is not cached, and the next request tries again.
            logger.warning("Taxonomy not embedded (%s); names and aliases only", exc)
            return [
                TaxonomySkill(
                    id=index + 1,
                    code=entry["code"],
                    name=entry["name"],
                    category=entry["category"],
                    hint=entry["hint"],
                    embedding=None,
                    display_names=display_names_for(entry["code"], entry["name"]),
                )
                for index, entry in enumerate(TAXONOMY)
            ]
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
    global _memory_cache, _alias_index, _keyword_index
    _memory_cache = None
    _alias_index = None
    _keyword_index = None


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


# ---------------------------------------------------------------------------
# Keyword shortlist
# ---------------------------------------------------------------------------
#
# Between "said a skill's exact name" and "the embedding model placed it" there
# was nothing, so a skill described in a person's own words -- "identifying
# engine problems by sound", "pharmacist" -- landed nowhere whenever the model
# was down (Hugging Face out of credits, 2026-11) or simply missed it.
#
# This shortlists skills that share distinctive words with what was said. It
# only ever *offers*: normalization hands the shortlist to the model to choose
# from, or to the person, exactly as it does the embedding search's middle
# band. A shared word is never enough to accept a skill on its own -- that is
# the upgrade lexical_match's docstring forbids.

_SPLIT = re.compile(r"[\s\-_/\\.,;:!?()\[\]{}\"'“”‘’…|+&*#@0-9]+")
_ENGLISH_SUFFIXES = ("ings", "ing", "ers", "er", "ed", "es", "s")
# Long enough that "diagnose", "diagnosing" and "diagnostics" meet, short enough
# that "pharmacist", "pharmacy" and "pharmaceutical" do. Tamil and Hindi words
# are cut the same way, which also strips Tamil case endings ("இன்ஜினோட" is
# "இன்ஜின்" with a genitive on it).
_STEM_LENGTH = 6

# Words that say nothing about which skill: function words, and the words for
# work, years, knowing and problems that every description of work contains.
_STOPWORDS_RAW = """
a an the and or of in on at by for with to from as is was are were be been am
i me my mine we our you your he she they them it its this that these those
who what when where how which why do did does done doing can could will would
get got make made have has had know knew known knowing understand
work works worked working job jobs velai seyden paarthen panninen years year
experience problem problems issue issues thing things stuff good well very
also all everything lot some any other more much like just only really
நான் எனக்கு என் என்ன அது இது அந்த இந்த ஒரு நல்லா நல்ல தெரியும் வேலை
பார்த்தேன் செய்தேன் செய்வேன் வருடம் வருஷம் ஆண்டு கேட்டா பிரச்சனை எல்லாம்
मैं मेरा मेरी मुझे है था थी हूँ हूं का की के में से और को काम साल करता
करती किया आता आती जानता जानती समस्या दिक्कत सब
drug dealer dealing
"""
# "drug" and "dealer" above: "pharmaceutical drug dealer" is an alias of
# Medicine Sales and Distribution -- the licensed trade -- but the words alone
# are not, and a bare "drug dealer" should shortlist nothing.


def _stem(token: str) -> str:
    if token.isascii():
        for suffix in _ENGLISH_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                token = token[: -len(suffix)]
                break
    return token[:_STEM_LENGTH]


# -- Sounds-alike keys (2026-11-09) ------------------------------------------
#
# A trade word spoken in Tamil or Hindi is usually an English one, and it can
# arrive in any spelling: "மெக்கானிக்கு" for "மெக்கானிக்", "எலக்ட்ரீசியன்"
# for "எலெக்ட்ரீஷியன்", or the English itself. Each word is reduced to the
# consonants it is said with, in classes the three scripts share -- Tamil
# writes k and g, t and d, p and b with one letter each -- so வெல்டிங்,
# वेल्डिंग and "welding" all become "vltn". The keys join the vocabulary
# above as "~key", so they can only shortlist a skill, like any word.
#
# Deliberately not meaning: "வெள்ளி" (silver) is a real word, silver work is a
# real trade, and it keys apart from welding. Whisper's mishearing of
# welding as silver is the speech prompt's job (stt_vocabulary.py).

_TAMIL_SOUNDS = {
    "க": "k", "ங": "n", "ச": "s", "ஞ": "n", "ட": "t", "ண": "n", "த": "t", "ந": "n",
    "ப": "p", "ம": "m", "ய": "", "ர": "r", "ல": "l", "வ": "v", "ழ": "l", "ள": "l",
    "ற": "r", "ன": "n", "ஜ": "j", "ஷ": "s", "ஸ": "s", "ஹ": "",
}
_DEVANAGARI_SOUNDS = {
    "क": "k", "ख": "k", "ग": "k", "घ": "k", "ङ": "n", "च": "s", "छ": "s", "ज": "j",
    "झ": "j", "ञ": "n", "ट": "t", "ठ": "t", "ड": "t", "ढ": "t", "ण": "n", "त": "t",
    "थ": "t", "द": "t", "ध": "t", "न": "n", "प": "p", "फ": "p", "ब": "p", "भ": "p",
    "म": "m", "य": "", "र": "r", "ल": "l", "व": "v", "श": "s", "ष": "s", "स": "s",
    "ह": "", "ं": "n", "ँ": "n",
}
_MIN_KEY = 3
_CROSS_SCRIPT_KEY = 4


def _latin_sounds(word: str) -> str:
    w = word.lower()
    w = w.replace("ph", "f").replace("ck", "k").replace("sh", "s").replace("ch", "s")
    w = re.sub(r"c(?=[eiy])", "s", w)
    w = re.sub(r"g(?=[eiy])", "j", w)
    table = str.maketrans({"c": "k", "q": "k", "x": "k", "z": "s", "w": "v", "y": "",
                           "b": "p", "d": "t", "g": "k", "f": "p", "h": ""})
    return re.sub(r"[aeiou]", "", w.translate(table))


def _sound_key(token: str) -> str | None:
    if token.isascii():
        if not token.isalpha():
            return None
        consonants = _latin_sounds(token)
    else:
        consonants = "".join(
            _TAMIL_SOUNDS.get(c, _DEVANAGARI_SOUNDS.get(c, "")) for c in token
        )
    key = re.sub(r"(.)\1+", r"\1", consonants)  # doubled letters said once
    key = re.sub(r"nk$", "n", key)              # -ing, -ங், -ंग alike
    key = key.replace("np", "mp")               # a nasal before p is m: प्लंबर
    if len(key) < _MIN_KEY:
        return None
    # Three consonants say too little to cross languages: English "sound" and
    # Tamil "சொந்த" (own) both key "snt". Short keys match spelling variants
    # within one script; only longer ones ("vltn", "lktrsn") cross scripts.
    if len(key) < _CROSS_SCRIPT_KEY:
        script = "la" if token.isascii() else ("ta" if any(c in _TAMIL_SOUNDS for c in token) else "hi")
        return f"{script}:{key}"
    return key


def _words(text: str) -> set[str]:
    out: set[str] = set()
    for token in _SPLIT.split(_fold(text)):
        if not token:
            continue
        stem = _stem(token)
        if stem in _STOPWORDS or len(stem) < (3 if stem.isascii() else 2):
            continue
        out.add(stem)
        if key := _sound_key(token):
            out.add("~" + key)
    return out


_STOPWORDS: set[str] = set()
_STOPWORDS = _words(_STOPWORDS_RAW)

# A word this many skills share or fewer can pick a skill out; "repair" or
# "machine" cannot, so a phrase needs at least one word this rare to be
# shortlisted at all.
_DISTINCTIVE_DF = 3
# Share of a phrase's known words (weighted by rarity) a skill must cover.
_MIN_KEYWORD_SCORE = 0.34
# Words from the evidence count less than words from the skill's own name.
_EVIDENCE_WEIGHT = 0.5

_keyword_index: tuple[dict[int, set[str]], dict[str, int]] | None = None
_keyword_lock = asyncio.Lock()


async def _get_keyword_index() -> tuple[dict[int, set[str]], dict[str, int]]:
    """Each skill's vocabulary, and how many skills each word appears in."""
    global _keyword_index
    if _keyword_index is not None:
        return _keyword_index
    async with _keyword_lock:
        if _keyword_index is not None:
            return _keyword_index

        vocab: dict[int, set[str]] = {}

        def add(skill_id: int, *texts: str | None) -> None:
            words = vocab.setdefault(skill_id, set())
            for text in texts:
                if isinstance(text, str):
                    words |= _words(text)

        if db.is_available():
            rows = await db.fetch(
                "select id, name, hint, aliases, display_names from skill_taxonomy"
            )
            for row in rows:
                names = dict(row["display_names"] or {})
                add(row["id"], row["name"], row["hint"], *(row["aliases"] or []),
                    *names.values())
        else:
            for skill, entry in zip(await _memory_taxonomy(), TAXONOMY):
                add(skill.id, entry["name"], entry["hint"], *entry["aliases"],
                    *skill.display_names.values())

        df: dict[str, int] = {}
        for words in vocab.values():
            for word in words:
                df[word] = df.get(word, 0) + 1
        _keyword_index = (vocab, df)
        return _keyword_index


async def keyword_candidates(
    phrase: str, evidence: str = "", *, limit: int = 3
) -> list[ScoredSkill]:
    """Skills sharing rare words with a phrase -- to offer, never to accept.

    ``similarity`` on the result is the share of the phrase's known words the
    skill covers, weighted by how rare each word is: 1.0 means every word the
    taxonomy knows points at this skill. It is not an embedding similarity and
    is never compared against the accept threshold.
    """
    said = _words(phrase)
    heard = _words(evidence) - said
    if not said and not heard:
        return []
    vocab, df = await _get_keyword_index()
    total_skills = max(len(vocab), 1)

    def weight(word: str) -> float:
        rarity = math.log(1 + total_skills / df[word])
        return rarity * (1.0 if word in said else _EVIDENCE_WEIGHT)

    known = [w for w in said | heard if w in df]
    if not known:
        return []
    possible = sum(weight(w) for w in known)

    scored: list[tuple[float, int]] = []
    for skill_id, words in vocab.items():
        shared = [w for w in known if w in words]
        if not any(df[w] <= _DISTINCTIVE_DF for w in shared):
            continue
        score = sum(weight(w) for w in shared) / possible
        if score >= _MIN_KEYWORD_SCORE:
            scored.append((score, skill_id))
    if not scored:
        return []

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    top = scored[:limit]
    found = await get_by_ids([skill_id for _, skill_id in top])
    return [
        ScoredSkill(skill=found[skill_id], similarity=round(score, 3))
        for score, skill_id in top
        if skill_id in found
    ]


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
