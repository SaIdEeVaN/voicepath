"""Multilingual embeddings for skill normalization (PRD section 4.3).

Two providers:

``local``
    ``sentence-transformers`` running ``EMBEDDING_MODEL`` (default
    ``intfloat/multilingual-e5-base``). This is the real one. The model is
    loaded lazily on first use -- importing this module must stay cheap,
    because the FastAPI app imports it at startup.

``offline``
    A deterministic character-n-gram hashing embedding. It has no semantic
    knowledge: it will match "bike repair" to the alias "bike repair" and score
    "பைக் ரிப்பேர்" against the Tamil alias, because those strings are in the
    taxonomy's alias list, but it will not connect "I fix two-wheelers" to
    "Two-Wheeler Repair" the way a real model does. It exists so the pipeline
    runs and is testable without a 1GB model download, and every response it
    influences is labelled ``provider: "offline"``.

Both produce L2-normalized vectors of ``EMBEDDING_DIMENSION`` floats, so a dot
product is a cosine similarity and the pgvector column dimension holds either way.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
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
        raise EmbeddingUnavailable(f"Embedding request failed: {exc}") from exc

    if response.status_code >= 400:
        raise EmbeddingUnavailable(
            f"Embedding API returned {response.status_code}: {response.text[:200]}"
        )

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

    if settings.embedding_provider == "offline":
        return [_hash_embed(t, settings.embedding_dimension) for t in texts]

    prepared = texts
    if _is_e5(settings.embedding_model):
        prefix = _E5_QUERY_PREFIX if is_query else _E5_PASSAGE_PREFIX
        prepared = [prefix + t for t in texts]

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
