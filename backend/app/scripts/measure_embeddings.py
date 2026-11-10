"""Measure what the configured embedder does on this project's own data.

    cd backend
    python -m app.scripts.measure_embeddings > measured.json

Four thresholds describe how one embedding model behaves on this vocabulary.
They are not constants, and they have to be measured again whenever the model
changes:

* ``matching.SKILL_SIMILARITY_FLOOR``: two different skills more alike than
  this are related, not merely embedded by the same model.
* ``normalization_accept_threshold`` and ``normalization_candidate_threshold``:
  how close a spoken phrase must be to a skill to be accepted outright, or
  offered as a choice.
* ``scheme_qa.MIN_USABLE_SIMILARITY``: below this, a document passage is not
  an answer to the question.

This prints, as JSON, the similarities each one is set from: every pair of
skills in the taxonomy, the best skill for each phrase below (with the skill
it should be, or none), and the best passage for each question below (on or
off topic) over the documents in ``data/scheme_docs``. Run it once with the
old model and once with the new, and carry each threshold across so that it
makes the same decisions. That is how the 2026-11-10 values were set, when
e5-base gave way to e5-small; STATUS.md records the numbers.

No database is needed: everything embedded comes from the repository.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import get_settings
from app.data.catalogue import TAXONOMY, embedding_text
from app.services import embeddings
from app.services.retrieval import chunk_text

DOCS = Path(__file__).resolve().parents[2] / "data" / "scheme_docs"

# How people describe their work, and the skill each phrase should reach.
# None: no skill in the taxonomy is meant, and the phrase should match none.
PHRASES: list[tuple[str, str | None]] = [
    ("I fix bikes and scooters", "SK001"),
    ("I repair cars at a garage", "SK002"),
    ("I service lorries and buses", "SK003"),
    ("I can tell what is wrong with an engine from its sound", "SK014"),
    ("I do the wiring in vehicles", "SK015"),
    ("I weld gates and grills", "SK022"),
    ("I work a lathe in a machine shop", "SK026"),
    ("I do house wiring", "SK031"),
    ("I repair fans, mixies and fridges", "SK032"),
    ("I install and service AC units", "SK033"),
    ("I build walls with bricks", "SK041"),
    ("I make doors and furniture from wood", "SK042"),
    ("I paint houses", "SK043"),
    ("I fit pipes and taps", "SK044"),
    ("I stitch blouses and churidars", "SK051"),
    ("I do embroidery work on sarees", "SK052"),
    ("I run power looms", "SK053"),
    ("I cook for weddings and functions", "SK061"),
    ("I bake bread and cakes", "SK062"),
    ("I grow paddy and sugarcane", "SK071"),
    ("I keep cows and sell milk", "SK072"),
    ("I raise chickens", "SK073"),
    ("I drive a tractor", "SK074"),
    ("I drive an auto and a car", "SK081"),
    ("I drive a lorry", "SK082"),
    ("I load and unload goods", "SK083"),
    ("I sell things in a shop", "SK091"),
    ("I keep the accounts for my shop", "SK092"),
    ("I repair mobile phones", "SK101"),
    ("I work as a security guard", "SK110"),
    ("I do bridal makeup and threading", "SK111"),
    ("I fit solar panels on roofs", "SK034"),
    ("I weave on a handloom", "SK055"),
    ("I go fishing in a boat", "SK075"),
    ("I sell vegetables from a cart", "SK095"),
    ("I cut hair", "SK113"),
    ("I make pots from clay", "SK127"),
    ("I make and mend sandals", "SK130"),
    ("I make jewellery from gold", "SK126"),
    ("நான் பைக் ரிப்பேர் செய்கிறேன்", "SK001"),
    ("நான் வெல்டிங் வேலை செய்கிறேன்", "SK022"),
    ("நான் தையல் வேலை செய்கிறேன்", "SK051"),
    ("நான் வீட்டு வயரிங் செய்கிறேன்", "SK031"),
    ("நான் மாடு வளர்க்கிறேன்", "SK072"),
    ("நான் மீன் பிடிக்கிறேன்", "SK075"),
    ("नाई का काम करता हूँ", "SK113"),
    ("मैं सिलाई करती हूँ", "SK051"),
    ("मैं बाइक ठीक करता हूँ", "SK001"),
    ("मैं प्लंबर का काम करता हूँ", "SK044"),
    ("मैं ट्रक चलाता हूँ", "SK082"),
    # Nothing in the taxonomy.
    ("I like watching cricket", None),
    ("My village is near Salem", None),
    ("I have two children in school", None),
    ("I studied up to tenth standard", None),
    ("I want a government job", None),
    ("My husband passed away last year", None),
    ("I am looking for a loan", None),
    ("I have a ration card", None),
    ("I sing in the temple choir", None),
    ("I teach mathematics to children", None),
    ("எனக்கு கிரிக்கெட் பிடிக்கும்", None),
    ("मुझे पैसे चाहिए", None),
]

# Questions about the schemes this project holds documents for, and questions
# none of them answer.
QUESTIONS: list[tuple[str, bool]] = [
    ("What training does PM Vishwakarma give?", True),
    ("How much is the stipend during PM Vishwakarma training?", True),
    ("What is the loan amount under PM Vishwakarma?", True),
    ("Who is eligible for PMEGP?", True),
    ("How much subsidy does PMEGP give in rural areas?", True),
    ("What is the maximum Mudra loan?", True),
    ("What are the Shishu, Kishore and Tarun categories?", True),
    ("How much loan can a street vendor get under PM SVANidhi?", True),
    ("What is the stipend for apprentices under NAPS?", True),
    ("What does Jan Shikshan Sansthan teach?", True),
    ("What support does SFURTI give to artisan clusters?", True),
    ("What help does NAMASTE give sanitation workers?", True),
    ("What does PMMSY do for fishermen?", True),
    ("How does SMAM help farmers buy machines?", True),
    ("What does DDU-GKY offer rural youth?", True),
    ("What is RSETI?", True),
    ("What loans does NMDFC give to minorities?", True),
    ("What does the National SC-ST Hub do?", True),
    ("What is the Fund of Funds for Startups?", True),
    ("What is PM-DAKSH?", True),
    ("What do KVIC and Khadi schemes offer?", True),
    ("Who won the cricket world cup?", False),
    ("What is the recipe for sambar?", False),
    ("What will the weather be tomorrow in Chennai?", False),
    ("How do I reset my phone password?", False),
    ("Who is the prime minister of Japan?", False),
    ("What is the capital of France?", False),
    ("How do I learn to play guitar?", False),
    ("What time does the train to Madurai leave?", False),
]


def _documents() -> list[str]:
    """Every passage, embedded as retrieval.ingest embeds it."""
    passages = []
    for path in sorted(DOCS.iterdir()):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        first = text.splitlines()[0] if text else ""
        title = first.lstrip("# ").strip() or path.stem
        for chunk in chunk_text(text):
            passages.append(" | ".join(p for p in (title, chunk.heading, chunk.content) if p))
    return passages


def main() -> int:
    settings = get_settings()
    if settings.embedding_provider == "offline":
        print("The offline embedder has nothing to measure; configure a model.", file=sys.stderr)
        return 1

    codes = [e["code"] for e in TAXONOMY]
    skills = embeddings.embed_documents([embedding_text(e) for e in TAXONOMY])
    pairs = {
        f"{codes[i]}~{codes[j]}": embeddings.cosine_similarity(skills[i], skills[j])
        for i in range(len(codes))
        for j in range(i + 1, len(codes))
    }

    phrases = []
    for text, expected in PHRASES:
        vector = embeddings.embed_query(text)
        ranked = sorted(
            ((embeddings.cosine_similarity(vector, s), c) for s, c in zip(skills, codes)),
            reverse=True,
        )
        phrases.append({
            "text": text, "expected": expected,
            "best": ranked[0][1], "best_similarity": ranked[0][0],
            "second_similarity": ranked[1][0],
            "expected_similarity": next((s for s, c in ranked if c == expected), None),
        })

    passages = _documents()
    vectors = embeddings.embed_documents(passages)
    questions = []
    for text, on_topic in QUESTIONS:
        vector = embeddings.embed_query(text)
        best = max(embeddings.cosine_similarity(vector, p) for p in vectors)
        questions.append({"text": text, "on_topic": on_topic, "best_similarity": best})

    json.dump({
        "model": settings.embedding_model,
        "provider": settings.embedding_provider,
        "dimension": settings.embedding_dimension,
        "skill_pairs": pairs,
        "phrases": phrases,
        "passages": len(passages),
        "questions": questions,
    }, sys.stdout, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
