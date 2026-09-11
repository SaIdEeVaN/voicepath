"""Answering questions about the scheme, from the scheme's own documents.

The rule this module exists to enforce: **an answer must be traceable to a
passage, or it must not be given.** That is the same principle as
``extraction._validate`` -- there, a skill without a quote from the transcript
is dropped; here, an answer without a retrieved passage is refused.

It matters more here than in most retrieval systems. A wrong answer about
eligibility sends someone on a bus to a district office with the wrong papers.
"The documents do not say" costs them nothing.

What this module may not do:

* It may not influence matching. ``services/matching.py`` imports no LLM and no
  retrieval, so a document cannot move anyone up a ranking.
* It may not answer from the model's own knowledge of Indian welfare schemes.
  The prompt forbids it and the citation requirement makes it visible when it
  happens: an answer with no citation did not come from the corpus.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services import llm, retrieval

logger = logging.getLogger(__name__)

# Below this, a "best match" is not a match. e5 compresses similarity into a
# narrow high band, so a genuinely unrelated passage still scores around 0.7 --
# which is exactly the case where a model, handed it anyway, will write a
# confident answer from a paragraph that does not support it.
MIN_USABLE_SIMILARITY = 0.74

# Enough passages to cover a question asked across two sections, few enough that
# the relevant one is not buried among near-misses.
TOP_K = 5


@dataclass
class SchemeAnswer:
    answer: str
    # Which passages produced it. Empty means the answer was refused, and the
    # UI should say so rather than presenting prose with nothing behind it.
    citations: list[dict] = field(default_factory=list)
    grounded: bool = False
    provider: str = "offline"


_SYSTEM = """\
You answer questions about Indian government welfare schemes using ONLY the \
passages provided.

Absolute rules:

1. USE ONLY THE PASSAGES. You may not use anything you know about these schemes \
from elsewhere. If the passages do not contain the answer, say exactly that. \
A person may travel to a district office on the strength of your answer.

2. CITE. Every claim must be attributable to one of the numbered passages. \
Refer to them as [1], [2] and so on.

3. DO NOT PROMISE ELIGIBILITY. The passages describe rules in general. They \
cannot tell you whether this particular person qualifies. Say what the rule is \
and who decides, never "you are eligible".

4. ANSWER IN THE LANGUAGE OF THE QUESTION. If the question is in Tamil, answer \
in Tamil; Hindi, answer in Hindi. The passages are usually in English -- \
translate what they say, do not switch the person to English.

5. BE SHORT. Three sentences at most. The person is listening to this, not \
reading it.

Reply as JSON: {"answer": "...", "used": [1, 2]}
`used` lists only the passages you actually relied on.\
"""


def _refusal(language: str) -> str:
    """Said when the corpus does not cover the question."""
    return {
        "ta": "இந்தக் கேள்விக்கான பதில் ஆவணங்களில் இல்லை. "
              "மாவட்ட சமூக நலத் துறை அலுவலகத்தில் கேளுங்கள்.",
        "hi": "इस सवाल का जवाब इन दस्तावेज़ों में नहीं है। "
              "ज़िला समाज कल्याण कार्यालय में पूछिए।",
    }.get(language, "The documents do not answer this. Ask at the district "
                    "Social Welfare Office.")


async def ask(question: str, *, language: str = "en") -> SchemeAnswer:
    """Answer from the corpus; widen it once if the corpus falls short.

    The trigger is the model reporting it could not answer, not an empty
    retrieval. Retrieval is never empty: e5 scores every passage in a narrow
    high band, so a question about a scheme we hold nothing on still comes back
    with five confident-looking neighbours about a different one. The only
    reliable signal that the corpus does not cover a question is the step that
    read the passages saying so.

    Widening happens once. A second miss is an answer we do not have.
    """
    clean = (question or "").strip()
    if not clean:
        raise ValueError("Nothing was asked")

    answer = await _answer_from_corpus(clean, language=language)
    if answer.grounded:
        return answer

    from app.services import websearch

    if not websearch.is_available():
        return answer
    if not await _widen_corpus(clean):
        return answer

    return await _answer_from_corpus(clean, language=language)


async def _answer_from_corpus(clean: str, *, language: str) -> SchemeAnswer:
    passages = await retrieval.search(clean, limit=TOP_K)
    usable = [p for p in passages if p.similarity >= MIN_USABLE_SIMILARITY]

    # Keyword-only hits carry no similarity score, so keep them when dense
    # search found nothing: an exact-string match on "NSQF Level 4" is evidence
    # even though the vector path did not surface it.
    if not usable:
        usable = [p for p in passages if p.similarity == 0.0][:2]

    if not usable:
        logger.info("No usable passage for: %s", clean[:80])
        return SchemeAnswer(answer=_refusal(language), citations=[], grounded=False)

    if not llm.is_available():
        # Without a model there is no honest way to summarise a passage, so
        # hand back the passage itself rather than nothing. The citation is the
        # answer, which is the shape the whole module is built around anyway.
        best = usable[0]
        return SchemeAnswer(
            answer=best.content.strip()[:600],
            citations=[_cite(best)],
            grounded=True,
            provider="offline",
        )

    numbered = "\n\n".join(
        f"[{i + 1}] ({p.source}"
        + (f", {p.heading}" if p.heading else "")
        + f")\n{p.content.strip()}"
        for i, p in enumerate(usable)
    )
    prompt = (
        f"Question ({language}): {clean}\n\n"
        f"Passages:\n\n{numbered}\n\n"
        "Answer using only these passages."
    )

    try:
        payload = await llm.complete_json(_SYSTEM, prompt, temperature=0.2, max_tokens=600)
    except (llm.LLMUnavailable, llm.LLMResponseError) as exc:
        logger.warning("Scheme answer unavailable (%s); returning the passage", exc)
        best = usable[0]
        return SchemeAnswer(
            answer=best.content.strip()[:600],
            citations=[_cite(best)],
            grounded=True,
            provider="offline",
        )

    answer = str((payload or {}).get("answer") or "").strip()
    if not answer:
        return SchemeAnswer(answer=_refusal(language), citations=[], grounded=False)

    # Cite only what the model said it used. An index it invented is dropped
    # rather than followed, so a citation always points at a real passage.
    used = [
        usable[i - 1]
        for i in (payload.get("used") or [])
        if isinstance(i, int) and 1 <= i <= len(usable)
    ]

    # No passage used means the model answered from nothing -- usually because
    # it is telling the person the documents do not cover this. Attaching a
    # citation anyway would be the exact failure this module exists to prevent:
    # a source shown beside an answer that did not come from it.
    if not used:
        return SchemeAnswer(
            answer=answer, citations=[], grounded=False,
            provider=llm.provider_name(),
        )

    return SchemeAnswer(
        answer=answer,
        citations=[_cite(p) for p in used],
        grounded=True,
        provider=llm.provider_name(),
    )


async def _widen_corpus(question: str) -> bool:
    """Fetch official pages for a question the corpus cannot answer.

    True when something new became answerable. False for every other outcome --
    no provider, nothing found, pages that would not load -- and the caller
    then refuses, which is the honest end of this path.

    Only Tier 1 pages become answerable. Anything else is stored waiting for
    review, so a search cannot quietly widen what the system will assert.
    """
    from app.services import websearch

    if not websearch.is_available():
        return False
    try:
        outcomes = await websearch.search_and_ingest(question, limit=3)
    except websearch.SearchUnavailable as exc:
        # Section 20: an unreachable search falls back to what is already
        # stored, which is exactly what the caller does next.
        logger.info("Search unavailable (%s); answering from the corpus alone", exc)
        return False

    added = [o for o in outcomes if o.get("status") == "active" and o.get("chunks")]
    if added:
        logger.info(
            "Widened the corpus for %r: %s",
            question[:60], ", ".join(o["domain"] for o in added),
        )
    return bool(added)


def _cite(passage: retrieval.Retrieved) -> dict:
    """A citation a person could actually follow back to the document."""
    # A source that is a URL is shown as one. It came from the search API and
    # is passed through unchanged -- never assembled, never repaired.
    source = passage.source
    return {
        "source": source,
        "source_url": source if source.startswith(("http://", "https://")) else None,
        "document_title": passage.document_title,
        "heading": passage.heading,
        # Enough to recognise the passage, not so much that the answer is buried.
        "excerpt": " ".join(passage.content.split())[:280],
        "similarity": round(passage.similarity, 3),
    }
