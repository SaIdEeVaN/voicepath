"""Entity tagging over the transcript (AI4Bharat IndicNER, MIT).

What this is for, and what it is not for.

IndicNER tags people, organisations and places across the Indic languages. It
does **not** find skills, and no NER model would: "எங்க மாமா கடையில வேலை
செஞ்சேன்" ("I worked at my uncle's shop") contains no entity that maps to
two-wheeler repair. Skill inference stays with the LLM and the embedding
search; this module supplies the structure around it.

Two concrete uses:

* **Location.** A place the person actually named beats one inferred from a
  job listing. ``locations()`` returns them in the order spoken.
* **Evidence spans.** Character offsets let the UI underline the words that
  produced a field, rather than re-searching the transcript for a substring
  that may appear twice.

Entities are supporting evidence, never a source of assertion. Nothing here
adds a claim about the person -- it only points at words they already said.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass

from app.config import get_settings

logger = logging.getLogger(__name__)

# IndicNER emits the standard CoNLL trio. LOC covers towns and districts,
# which is the only one matching consumes directly.
PERSON = "PER"
ORGANISATION = "ORG"
LOCATION = "LOC"


@dataclass(frozen=True)
class Entity:
    label: str
    text: str
    # Offsets into the transcript the tagger was given, so a caller can
    # highlight the exact span rather than searching for the text again.
    start: int
    end: int
    score: float


def is_available() -> bool:
    return get_settings().ner_provider != "offline"


def provider_name() -> str:
    return get_settings().ner_provider


_pipeline = None
_pipeline_lock = threading.Lock()
# Latched after the first failure. Without it every call retries the download,
# and a gated or absent model turns each request into a fresh 20s round trip.
_pipeline_failed: str | None = None


def _load_pipeline():
    global _pipeline, _pipeline_failed
    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline
        if _pipeline_failed is not None:
            raise RuntimeError(_pipeline_failed)
        settings = get_settings()
        try:
            from transformers import pipeline as hf_pipeline
        except ImportError as exc:  # pragma: no cover - depends on install
            raise RuntimeError("transformers is not installed") from exc

        logger.info("Loading NER model %s", settings.ner_model)
        try:
            _pipeline = hf_pipeline(
                "token-classification",
                model=settings.ner_model,
                # Merges B-/I- fragments into one span and gives back offsets.
                aggregation_strategy="simple",
            )
        except Exception as exc:  # noqa: BLE001 - gated repo, no network, bad name
            _pipeline_failed = (
                f"{settings.ner_model} could not be loaded ({type(exc).__name__}). "
                "ai4bharat/IndicNER is a gated repo: accept its terms on "
                "huggingface.co and set HF_TOKEN, or set NER_PROVIDER=offline."
            )
            logger.warning("%s", _pipeline_failed)
            raise RuntimeError(_pipeline_failed) from exc
        return _pipeline


def _tag_sync(text: str) -> list[Entity]:
    tagger = _load_pipeline()
    found: list[Entity] = []
    for raw in tagger(text):
        label = str(raw.get("entity_group") or raw.get("entity") or "").upper()
        # Strip any B-/I- prefix the aggregation did not already remove.
        label = label.split("-")[-1]
        word = (raw.get("word") or "").strip()
        if not word or not label:
            continue
        found.append(
            Entity(
                label=label,
                text=word,
                start=int(raw.get("start", 0)),
                end=int(raw.get("end", 0)),
                score=float(raw.get("score", 0.0)),
            )
        )
    return found


async def tag(text: str) -> list[Entity]:
    """Tag a transcript. Returns [] rather than raising when unavailable.

    A tagger that cannot load is a missing enhancement, not a failed request:
    every caller has something useful to do with an empty list, and the
    pipeline that depends on it is the LLM's, not this one's.
    """
    clean = (text or "").strip()
    if not clean or not is_available():
        return []

    try:
        return await asyncio.to_thread(_tag_sync, clean)
    except Exception as exc:  # noqa: BLE001 - degrade, never fail the request
        logger.warning("NER unavailable (%s); continuing without entities", exc)
        return []


def locations_from(entities: list[Entity]) -> list[str]:
    """Place names in the order they were spoken, de-duplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for entity in entities:
        if entity.label != LOCATION:
            continue
        key = entity.text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(entity.text)
    return out


async def locations(text: str) -> list[str]:
    """Convenience wrapper: tag once, keep the places."""
    return locations_from(await tag(text))
