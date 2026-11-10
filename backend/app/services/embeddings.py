"""Multilingual embeddings for skill normalization (PRD section 4.3).

Providers:

``onnx`` (the default since 2026-11-10)
    ``multilingual-e5-small`` running inside the API: an int8 ONNX export
    read by onnxruntime, tokenised by sentencepiece. No key and nothing to run
    out of. Hugging Face's own ``tokenizers`` package would have been the
    obvious tokenizer, but loading this model's 250,000-word vocabulary
    through it took 282 MB on its own -- more than the model. sentencepiece
    reads the same vocabulary in about 55 MB and yields the same ids
    (checked on 4,682 texts from this project; see ``_token_ids``).

``local``
    ``sentence-transformers`` running ``EMBEDDING_MODEL``. For development;
    torch does not fit the deployed container.

``hf_api``
    The Hugging Face Inference API. What production used until 2026-11-04,
    when the account's credits ran out and every call came back 402.

``offline``
    A deterministic character-n-gram hashing embedding. It has no semantic
    knowledge: it will match "bike repair" to the alias "bike repair" and score
    "பைக் ரிப்பேர்" against the Tamil alias, because those strings are in the
    taxonomy's alias list, but it will not connect "I fix two-wheelers" to
    "Two-Wheeler Repair" the way a real model does. It exists so the pipeline
    runs and is testable without a model download, and every response it
    influences is labelled ``provider: "offline"``.

All produce L2-normalized vectors of ``EMBEDDING_DIMENSION`` floats, so a dot
product is a cosine similarity. The pgvector columns must have that many
dimensions; ``db.check_schema`` compares, and ``block`` stops every embedding
while they differ (see *Vectors the database cannot hold*).
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from app.config import get_settings

logger = logging.getLogger(__name__)

class EmbeddingUnavailable(RuntimeError):
    """The hosted embedder could not be reached.

    Deliberately not caught and downgraded to the hash provider: those vectors
    are not comparable with the ones already stored, so falling back would not
    degrade the match, it would silently corrupt it. Failing loudly is the
    honest option.
    """


_model: Any = None
_model_lock = threading.Lock()

# e5 models are trained with these prefixes and lose accuracy without them.
_E5_QUERY_PREFIX = "query: "
_E5_PASSAGE_PREFIX = "passage: "


def _is_e5(model_name: str) -> bool:
    return "e5" in model_name.lower()


def _load_local_model() -> Any:
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        settings = get_settings()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise RuntimeError(
                "EMBEDDING_PROVIDER=local needs sentence-transformers. "
                "Install it with `pip install -r requirements-ml.txt`, or set "
                "EMBEDDING_PROVIDER=offline."
            ) from exc
        logger.info("Loading embedding model %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        dim = _model.get_sentence_embedding_dimension()
        if dim != settings.embedding_dimension:
            raise RuntimeError(
                f"{settings.embedding_model} produces {dim}-dim vectors but "
                f"EMBEDDING_DIMENSION is {settings.embedding_dimension}. The "
                "pgvector column must match -- update both, then re-embed the "
                "taxonomy."
            )
        return _model


# ---------------------------------------------------------------------------
# On-server provider: multilingual-e5-small as int8 ONNX (2026-11-10)
# ---------------------------------------------------------------------------

ONNX_FILE = "model_quantized.onnx"
SENTENCEPIECE_FILE = "sentencepiece.bpe.model"

# XLM-RoBERTa's special ids. sentencepiece numbers its pieces from <unk>=0,
# <s>=1, </s>=2; the model was trained with fairseq's numbering, which puts
# <s>=0, <pad>=1, </s>=2, <unk>=3 first and shifts every other piece up by
# one. transformers' XLMRobertaTokenizer does exactly this mapping.
_BOS, _EOS, _UNK = 0, 2, 3
MAX_TOKENS = 512

# One text per forward pass, never a batch. The int8 model quantizes its
# activations with one scale per call, computed over everything in it, so a
# text batched with others came out up to 0.0075 cosine away from the same
# text alone (measured 2026-11-10) -- a skill's similarity would have depended
# on what else the person said. Alone, a text always gets the same vector. It
# is also faster here: a batch pads every text to its longest (108 ms per
# passage alone against 427 ms in batches of eight), and it keeps memory flat.

_onnx: tuple[Any, Any, frozenset[str]] | None = None


def _load_onnx() -> tuple[Any, Any, frozenset[str]]:
    global _onnx
    if _onnx is not None:
        return _onnx
    with _model_lock:
        if _onnx is not None:
            return _onnx
        import onnxruntime
        import sentencepiece

        settings = get_settings()
        folder = Path(settings.embedding_model_dir)
        options = onnxruntime.SessionOptions()
        # One thread: the container has a fraction of one CPU, and more
        # threads only contend for it with the requests being served.
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        # The arena keeps the largest batch's buffers forever; without it the
        # memory goes back after each call.
        options.enable_cpu_mem_arena = False
        logger.info("Loading embedding model from %s", folder)
        session = onnxruntime.InferenceSession(
            str(folder / ONNX_FILE), options, providers=["CPUExecutionProvider"]
        )
        pieces = sentencepiece.SentencePieceProcessor(
            model_file=str(folder / SENTENCEPIECE_FILE)
        )
        names = frozenset(i.name for i in session.get_inputs())
        loaded = (session, pieces, names)
        dim = len(_run_onnx(loaded, ["passage: x"])[0])
        if dim != settings.embedding_dimension:
            raise RuntimeError(
                f"{folder / ONNX_FILE} produces {dim}-dim vectors but "
                f"EMBEDDING_DIMENSION is {settings.embedding_dimension}. The "
                "pgvector columns must match -- see db/015."
            )
        _onnx = loaded
        return _onnx


def _token_ids(pieces: Any, text: str) -> list[int]:
    """XLM-RoBERTa ids for ``text``, as transformers would make them.

    Whitespace is collapsed first. Hugging Face's tokenizer turns a trailing
    space or newline into a token of its own and sentencepiece drops it; with
    whitespace collapsed the two agreed on 4,677 of 4,682 texts from this
    project's taxonomy, catalogue, documents and questions -- the five others
    were box-drawing art and one tie in how a long run of repeated characters
    is split.
    """
    ids = [piece + 1 if piece else _UNK for piece in pieces.encode(" ".join(text.split()))]
    return [_BOS, *ids[: MAX_TOKENS - 2], _EOS]


def _run_onnx(loaded: tuple[Any, Any, frozenset[str]], prepared: list[str]) -> list[list[float]]:
    """Mean-pooled, L2-normalized vectors -- what sentence-transformers does for e5."""
    import numpy as np

    session, pieces, names = loaded
    out: list[list[float]] = []
    for text in prepared:
        ids = np.array([_token_ids(pieces, text)], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": np.ones_like(ids)}
        if "token_type_ids" in names:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = session.run(None, feed)[0][0]
        pooled = hidden.mean(axis=0)
        norm = float(np.linalg.norm(pooled))
        out.append([float(x) / norm for x in pooled] if norm else [0.0] * len(pooled))
    return out


def _embed_onnx(prepared: list[str]) -> list[list[float]]:
    return _run_onnx(_load_onnx(), prepared)


# ---------------------------------------------------------------------------
# Offline provider
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    padded = f" {text} "
    if len(padded) <= n:
        return [padded]
    return [padded[i : i + n] for i in range(len(padded) - n + 1)]


def _hash_embed(text: str, dimension: int) -> list[float]:
    """Hash tokens and character trigrams into a fixed-width vector.

    Trigrams carry most of the weight: they survive the spelling drift that
    speech-to-text produces, and they work in scripts where whitespace
    tokenisation is a poor guide to word boundaries.
    """
    vec = [0.0] * dimension
    lowered = text.lower().strip()
    if not lowered:
        return vec

    features: list[tuple[str, float]] = []
    for token in _TOKEN_RE.findall(lowered):
        features.append((f"w:{token}", 1.0))
    for gram in _char_ngrams(lowered):
        features.append((f"g:{gram}", 0.6))

    for feature, weight in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "big") % dimension
        # Sign from an independent byte keeps unrelated features from piling
        # up in the same direction.
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def provider_name() -> str:
    return get_settings().embedding_provider


def embed_documents(texts: Sequence[str]) -> list[list[float]]:
    """Embed taxonomy entries (the "passage" side)."""
    return _embed(list(texts), is_query=False)


def embed_query(text: str) -> list[float]:
    """Embed one spoken skill phrase (the "query" side)."""
    return _embed([text], is_query=True)[0]


def embed_queries(texts: Sequence[str]) -> list[list[float]]:
    return _embed(list(texts), is_query=True)


# ---------------------------------------------------------------------------
# Whether the hosted embedder is answering
# ---------------------------------------------------------------------------
#
# On 2026-11-04 the Hugging Face Inference API began answering 402 Payment
# Required -- the account's free credits were spent -- and every skill a
# person described turned into a 500 at /api/profile/extract, because
# normalization could not embed it. /health still said "embeddings: hf_api".
#
# Remembered like llm.py remembers Groq refusing: reported in /health and
# cleared by the next answer. Callers now catch EmbeddingUnavailable and fall
# back -- normalization to exact names and aliases, retrieval to keyword
# search -- so the outage costs recall rather than the whole request.

_HOLD_SECONDS = 600.0
_clock = time.time
_failure: tuple[str, float, float] | None = None  # (reason, since, until)


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=UTC).isoformat(timespec="seconds")


def recent_failure() -> dict[str, str] | None:
    failure = _failure
    if failure is None or _clock() >= failure[2]:
        return None
    reason, since, until = failure
    return {"reason": reason, "since": _iso(since), "until": _iso(until)}


# ---------------------------------------------------------------------------
# Vectors the database cannot hold
# ---------------------------------------------------------------------------
#
# Switching from e5-base to e5-small changed every vector from 768 numbers to
# 384. Postgres refuses to compare or store vectors of different sizes, so
# code that ran before db/015 widened -- narrowed -- the columns would fail
# every search and every write with a database error. db.check_schema compares
# the columns with EMBEDDING_DIMENSION and blocks embedding until they agree;
# the callers' existing fallbacks (names and aliases, keyword search) carry the
# service meanwhile, /health names the migration, and the block lifts by
# itself at the next check after the migration is applied.

_blocked: str | None = None


def block(reason: str) -> None:
    global _blocked
    if _blocked != reason:
        logger.error("Embeddings blocked: %s", reason)
    _blocked = reason


def unblock() -> None:
    global _blocked
    if _blocked is not None:
        logger.info("Embeddings unblocked: the database's vectors fit again")
    _blocked = None


def blocked() -> str | None:
    return _blocked


def status() -> dict[str, str]:
    """What /health reports about embeddings: configured, and answering?"""
    if _blocked is not None:
        return {"status": "dimension_mismatch", "detail": _blocked}
    if get_settings().embedding_provider == "offline":
        return {"status": "offline"}
    failure = recent_failure()
    if failure is None:
        return {"status": "ok"}
    return {"status": failure["reason"], "since": failure["since"], "until": failure["until"]}


def reset_status() -> None:
    global _failure
    _failure = None


def _note_failure(reason: str) -> None:
    global _failure
    now = _clock()
    since = _failure[1] if _failure is not None and now < _failure[2] else now
    _failure = (reason, since, now + _HOLD_SECONDS)
    logger.warning("Embeddings marked unavailable: %s", reason)


def _note_success() -> None:
    global _failure
    _failure = None


def _outage_reason(status_code: int) -> str:
    if status_code == 402:
        return "payment_required"
    if status_code == 429:
        return "rate_limited"
    if status_code in (401, 403):
        return "rejected"
    if status_code == 404:
        return "model_missing"
    if status_code >= 500:
        return "server_error"
    return "refused"


def _embed_hf_api(prepared: list[str]) -> list[list[float]]:
    """Embed through the Hugging Face Inference API.

    The point of this provider is that it runs the SAME model as ``local``, so
    vectors already stored in Postgres stay valid and no re-embedding is needed
    when a deployment switches to it. It exists because torch is ~530MB, which
    is the difference between fitting a free container tier and not.

    The API returns raw vectors; sentence-transformers returns normalized ones,
    and ``cosine_similarity`` is a dot product that assumes unit length. So the
    normalization the local path gets for free has to happen here explicitly.
    """
    import httpx

    settings = get_settings()
    url = (
        "https://router.huggingface.co/hf-inference/models/"
        f"{settings.embedding_model}/pipeline/feature-extraction"
    )
    try:
        with httpx.Client(timeout=settings.embedding_api_timeout) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.hf_token or ''}"},
                json={"inputs": prepared, "options": {"wait_for_model": True}},
            )
    except httpx.HTTPError as exc:
        _note_failure("unreachable")
        raise EmbeddingUnavailable(f"Embedding request failed: {exc}") from exc

    if response.status_code >= 400:
        _note_failure(_outage_reason(response.status_code))
        raise EmbeddingUnavailable(
            f"Embedding API returned {response.status_code}: {response.text[:200]}"
        )
    _note_success()

    payload = response.json()
    if not isinstance(payload, list) or len(payload) != len(prepared):
        raise EmbeddingUnavailable("Embedding API returned an unexpected shape")

    out: list[list[float]] = []
    for row in payload:
        vector = _mean_pool(row)
        out.append(_l2_normalize(vector))
    return out


def _mean_pool(row: Any) -> list[float]:
    """Collapse token vectors to one sentence vector.

    The endpoint returns a flat vector for some models and a token matrix for
    others. Averaging the tokens is what sentence-transformers does for e5, so
    handling both here keeps the two providers interchangeable.
    """
    if row and isinstance(row[0], (int, float)):
        return [float(x) for x in row]
    if not row:
        raise EmbeddingUnavailable("Embedding API returned an empty vector")
    width = len(row[0])
    totals = [0.0] * width
    for token in row:
        for i, value in enumerate(token):
            totals[i] += float(value)
    return [total / len(row) for total in totals]


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


def _embed(texts: list[str], *, is_query: bool) -> list[list[float]]:
    settings = get_settings()
    if not texts:
        return []
    if _blocked is not None:
        # Callers already fall back on this: normalization to names and
        # aliases, retrieval to keyword search, the catch-up to waiting.
        raise EmbeddingUnavailable(_blocked)

    if settings.embedding_provider == "offline":
        return [_hash_embed(t, settings.embedding_dimension) for t in texts]

    prepared = texts
    if _is_e5(settings.embedding_model):
        prefix = _E5_QUERY_PREFIX if is_query else _E5_PASSAGE_PREFIX
        prepared = [prefix + t for t in texts]

    if settings.embedding_provider == "onnx":
        return _embed_onnx(prepared)
    if settings.embedding_provider == "hf_api":
        return _embed_hf_api(prepared)

    model = _load_local_model()
    vectors = model.encode(
        prepared,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [[float(x) for x in row] for row in vectors]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity clamped to [0, 1].

    Both providers emit normalized vectors, so this is a dot product. Negative
    similarities are clamped rather than rescaled: downstream every score is a
    fraction in [0, 1], and a negative cosine means "unrelated", not
    "anti-related", for this use.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, min(1.0, dot))
