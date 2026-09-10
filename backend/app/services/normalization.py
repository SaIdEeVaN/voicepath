"""Raw skill mention to taxonomy entry (PRD section 4.3).

The mechanism is embedding similarity: "bike repair", "बाइक रिपेयर",
"மோட்டார் சைக்கிள் ரிப்பேர்" and "I fix bikes" all sit near the same point in a
multilingual space, and the taxonomy node for SK001 sits there too because its
embedding text includes those aliases.

Three outcomes per skill, and the middle one is the point of the design:

* similarity >= accept threshold -> normalized outright.
* between the candidate and accept thresholds -> the LLM is asked to choose
  among the top candidates. If it declines, or picks with low confidence, the
  skill is flagged ``needs_disambiguation`` and the user is asked. That is the
  low-confidence screen in the design.
* below the candidate threshold -> left unnormalized, with candidates attached
  so the interface can still offer them.

A skill is never silently mapped to something the evidence does not support.
Unnormalized skills stay in the profile with their evidence intact; they simply
do not contribute to the skill-similarity term in matching.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.config import get_settings
from app.prompts import DISAMBIGUATION_SYSTEM, DISAMBIGUATION_USER_TEMPLATE
from app.services import embeddings, llm, taxonomy
from app.services.taxonomy import ScoredSkill

logger = logging.getLogger(__name__)


@dataclass
class NormalizedSkill:
    raw_name: str
    evidence_phrase: str
    skill_id: int | None = None
    code: str | None = None
    name: str | None = None
    category: str | None = None
    confidence: float | None = None
    needs_disambiguation: bool = False
    candidates: list[ScoredSkill] = field(default_factory=list)
    user_confirmed: bool = False
    # Set to the raw phrase's embedding so matching does not recompute it.
    embedding: list[float] | None = None
    # {"en": ..., "ta": ..., "hi": ...} for whatever this normalized to.
    display_names: dict[str, str] = field(default_factory=dict)


async def normalize_many(
    skills: list[tuple[str, str]],
    *,
    use_llm_assist: bool = True,
) -> list[NormalizedSkill]:
    """Normalize ``[(raw_name, evidence_phrase), ...]``.

    Embedding is batched -- one model call for the whole set rather than one
    per skill, which is the difference between ~40ms and ~400ms on the local
    provider and matters more on a hosted one.
    """
    if not skills:
        return []

    settings = get_settings()
    texts = [raw for raw, _ in skills]
    vectors = await asyncio.to_thread(embeddings.embed_queries, texts)

    results: list[NormalizedSkill] = []
    needs_assist: list[NormalizedSkill] = []

    for (raw_name, evidence), vector in zip(skills, vectors):
        candidates = await taxonomy.search_by_vector(
            vector, limit=max(settings.normalization_candidate_count, 3)
        )
        entry = NormalizedSkill(
            raw_name=raw_name,
            evidence_phrase=evidence,
            candidates=[
                c for c in candidates
                if c.similarity >= settings.normalization_candidate_threshold
            ],
            embedding=vector,
        )

        # Saying a skill's own name or alias settles it. Checked before the
        # similarity thresholds because it is better evidence than either.
        exact = await taxonomy.lexical_match(raw_name)
        if exact is not None:
            _accept(entry, exact, 1.0)
            results.append(entry)
            continue

        best = candidates[0] if candidates else None
        if best and best.similarity >= settings.normalization_accept_threshold:
            _accept(entry, best.skill, best.similarity)
        elif best and best.similarity >= settings.normalization_candidate_threshold:
            entry.needs_disambiguation = True
            entry.confidence = best.similarity
            needs_assist.append(entry)
        else:
            entry.needs_disambiguation = bool(entry.candidates)
            entry.confidence = best.similarity if best else 0.0

        results.append(entry)

    if use_llm_assist and needs_assist and llm.is_available():
        await _llm_assist(needs_assist)

    return results


def _accept(entry: NormalizedSkill, skill: taxonomy.TaxonomySkill, confidence: float) -> None:
    entry.skill_id = skill.id
    entry.code = skill.code
    entry.name = skill.name
    entry.category = skill.category
    entry.confidence = round(confidence, 3)
    entry.needs_disambiguation = False
    entry.display_names = dict(skill.display_names or {})


async def _llm_assist(entries: list[NormalizedSkill]) -> None:
    """Let the model choose among candidates the embedding search shortlisted.

    It cannot introduce a skill: the prompt constrains it to the candidate
    list, and the code below re-checks the returned code against that list
    before accepting it. A prompt is a request; this is the enforcement.
    """
    for entry in entries:
        if not entry.candidates:
            continue
        allowed = {c.skill.code: c for c in entry.candidates}
        rendered = "\n".join(
            f"- {c.skill.code}: {c.skill.name} ({c.skill.category})"
            f"{' -- ' + c.skill.hint if c.skill.hint else ''}"
            for c in entry.candidates
        )
        prompt = DISAMBIGUATION_USER_TEMPLATE.format(
            raw_name=entry.raw_name,
            evidence_phrase=entry.evidence_phrase,
            candidates=rendered,
        )
        try:
            payload = await llm.complete_json(
                DISAMBIGUATION_SYSTEM, prompt, temperature=0.0, max_tokens=300
            )
        except (llm.LLMUnavailable, llm.LLMResponseError) as exc:
            logger.warning("Disambiguation assist unavailable: %s", exc)
            return

        if not isinstance(payload, dict):
            continue
        code = payload.get("skill_code")
        confidence = payload.get("confidence")
        if not isinstance(code, str) or code not in allowed:
            # Declined, or hallucinated a code. Either way the user decides.
            continue
        if not isinstance(confidence, (int, float)) or confidence < 0.6:
            continue

        chosen = allowed[code]
        _accept(entry, chosen.skill, float(confidence))


async def apply_user_choice(
    entry: NormalizedSkill, skill_id: int
) -> NormalizedSkill:
    """Apply a pick from the disambiguation screen.

    A user's answer beats the model's and beats the threshold -- they are the
    one who did the work.
    """
    found = await taxonomy.get_by_ids([skill_id])
    skill = found.get(skill_id)
    if skill is None:
        return entry
    _accept(entry, skill, 1.0)
    entry.user_confirmed = True
    entry.needs_disambiguation = False
    return entry


def provider_name() -> str:
    return embeddings.provider_name()
