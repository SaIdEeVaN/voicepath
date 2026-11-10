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

import asyncio
import logging
from dataclasses import dataclass, field

from app.services import llm, retrieval

logger = logging.getLogger(__name__)

# Below this, a "best match" is not a match. e5 compresses similarity into a
# narrow high band, so a genuinely unrelated passage still scores around 0.7 --
# which is exactly the case where a model, handed it anyway, will write a
# confident answer from a paragraph that does not support it.
#
# Model-specific. Re-measured 2026-11-10 for e5-small
# (app/scripts/measure_embeddings.py, 21 questions the documents answer and 8
# they do not): the weakest answerable question scores 0.837, so 0.77 keeps
# the margin e5-base had at 0.74 below its weakest (0.816), and sharing out
# the same proportion of questions gives 0.767. Off-topic questions reach
# 0.82 ("recipe for sambar") under either model; the passage filter is one
# guard of several, not the one that stops those.
MIN_USABLE_SIMILARITY = 0.77

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
    # The model's judgement of whether the question is about schemes at all.
    # None when no model read it. Only a definite True may send the question
    # to web search: "who is better, Mbappe or Yamal" searched gov.in, found
    # sports news on a public broadcaster's .gov.in site, and stored it as
    # scheme guidance.
    about_schemes: bool | None = None


_SYSTEM = """\
You answer questions about Indian government welfare schemes using ONLY the \
passages provided.

Absolute rules:

1. USE ONLY THE PASSAGES. You may not use anything you know about these schemes \
from elsewhere. If the passages do not contain the answer, say exactly that. \
A person may travel to a district office on the strength of your answer.

2. THE RIGHT SCHEME. If the question names a scheme and the passages are about \
a different one, the passages do not answer it -- even if they look similar. \
Never describe one scheme's rules as another's.

3. CITE. Every claim must be attributable to one of the numbered passages. \
Refer to them as [1], [2] and so on.

4. DO NOT PROMISE ELIGIBILITY. The passages describe rules in general. They \
cannot tell you whether this particular person qualifies. Say what the rule is \
and who decides, never "you are eligible".

5. ANSWER IN THE LANGUAGE OF THE QUESTION. If the question is in Tamil, answer \
in Tamil; Hindi, answer in Hindi. The passages are usually in English -- \
translate what they say, do not switch the person to English.

6. BE SHORT. Three sentences at most. The person is listening to this, not \
reading it.

Reply as JSON:
{"answer": "...", "used": [1, 2], "answerable": true, "about_schemes": true}

- `answerable`: true only if the passages actually answer this question, about \
the scheme it asks about. If you are explaining that they do not, it is false.
- `used`: only the passages you actually relied on. Empty when not answerable.
- `about_schemes`: true if the question is about government schemes, welfare, \
benefits, loans, subsidies, training, jobs or how to apply for them; false for \
anything else (sport, trivia, small talk), whatever the passages say.\
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


async def ask(
    question: str, *, language: str = "en", in_view: str | None = None
) -> SchemeAnswer:
    """Answer from the corpus, or refuse -- and queue a search if it is worth one.

    The trigger for looking further is the model reporting it could not answer,
    not an empty retrieval. Retrieval is never empty: e5 scores every passage in
    a narrow high band, so a question about a scheme we hold nothing on still
    comes back with five confident-looking neighbours about a different one.
    The only reliable signal that the corpus does not cover a question is the
    step that read the passages saying so.

    A web search no longer answers the question that triggered it. Fetched
    pages wait for an admin before anything can be said from them, so there is
    nothing to gain by keeping the person waiting through a search, a fetch and
    an embedding: the refusal is returned at once, and the search runs in the
    background to put candidate pages in front of a reviewer -- and only when
    the model judged the question to be about schemes at all.
    """
    clean = (question or "").strip()
    if not clean:
        raise ValueError("Nothing was asked")

    answer = await _answer_from_corpus(clean, language=language, in_view=in_view)
    if not answer.grounded and answer.about_schemes is True:
        _queue_search(clean)
    return answer


async def _answer_from_corpus(
    clean: str, *, language: str, in_view: str | None = None
) -> SchemeAnswer:
    # A named scheme narrows the search to its own documents. If those do not
    # hold the answer, no other scheme's passage is allowed to stand in for it:
    # a question about PM-AJAY was answered from an e-Shram help page that way.
    sources = retrieval.named_sources(clean)
    if sources:
        passages = await retrieval.search(clean, limit=TOP_K, sources=sources)
    else:
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
    # The listing on screen, when there is one. It is a local opening, not a
    # scheme these passages describe, so "who can apply for this?" asked on its
    # page must not be answered from some central scheme's rules.
    viewing = (
        f"The person is looking at a local listing: {in_view}. The passages do "
        "not describe that listing. A question about it -- \"this\", \"it\", "
        "\"this job\" -- is not answerable from them.\n\n"
        if in_view else ""
    )
    prompt = (
        f"{viewing}"
        f"Question ({language}): {clean}\n\n"
        f"Passages:\n\n{numbered}\n\n"
        "Answer using only these passages."
    )

    try:
        payload = await llm.complete_json(_SYSTEM, prompt, temperature=0.2, max_tokens=600)
    except (llm.LLMUnavailable, llm.LLMResponseError) as exc:
        # Refuse, rather than fall back to the offline shape above.
        #
        # That shape -- hand back the best passage, grounded, with its citation
        # -- is a considered trade when there is no model *by design*: nothing
        # can summarise, so the citation is the answer. Reused for a transient
        # failure it does something else entirely. It removes the only judge
        # this module has and then asserts anyway.
        #
        # Retrieval cannot supply that judgement. e5 scores every passage in a
        # narrow high band, so a question the corpus has never heard of still
        # returns five confident-looking neighbours: asking about the capital
        # of France returned a passage on the Ambedkar International Centre,
        # marked grounded, because Groq had answered 429 a moment earlier.
        #
        # A deployment configured with a model is expected to use it. When the
        # call fails, the honest answer is that nothing could be answered right
        # now -- and a retry will usually succeed, which a false assertion
        # forecloses.
        #
        # One exception, and it is not a judgement retrieval makes: the person
        # named the scheme, and the passage comes from that scheme's own
        # document because the search was restricted to it. "sigaram thodu
        # scheme" was refused outright while Groq was rate-limited, although
        # thirteen passages of its own EOI were sitting in the corpus. Quoting
        # the best of them, with its citation, says nothing the document does
        # not say.
        if sources:
            logger.warning(
                "Scheme answer unavailable (%s); quoting the named scheme's document",
                exc,
            )
            return _quote(usable[0])
        logger.warning("Scheme answer unavailable (%s); refusing", exc)
        return SchemeAnswer(answer=_refusal(language), citations=[], grounded=False)

    payload = payload if isinstance(payload, dict) else {}
    about = payload.get("about_schemes")
    about_schemes = about if isinstance(about, bool) else None

    answer = str(payload.get("answer") or "").strip()
    if not answer:
        return SchemeAnswer(
            answer=_refusal(language), citations=[], grounded=False,
            about_schemes=about_schemes,
        )

    # Cite only what the model said it used. An index it invented is dropped
    # rather than followed, so a citation always points at a real passage.
    used = [
        usable[i - 1]
        for i in (payload.get("used") or [])
        if isinstance(i, int) and 1 <= i <= len(usable)
    ]

    # Grounded needs both: the model says the passages answer the question,
    # and it names the passages it used. Either alone is not enough.
    #
    # `used` alone was the old test, and it let through answers that cite a
    # passage in order to say it does not help: "the passages do not mention
    # PM-KISAN; they describe e-Shram [1]" was shown as an answer "from the
    # scheme guidelines". So was "the passages do not compare Mbappe and
    # Yamal". Missing or not a boolean counts as no.
    if payload.get("answerable") is not True or not used:
        return SchemeAnswer(
            answer=_refusal(language), citations=[], grounded=False,
            provider=llm.provider_name(), about_schemes=about_schemes,
        )

    return SchemeAnswer(
        answer=answer,
        citations=[_cite(p) for p in used],
        grounded=True,
        provider=llm.provider_name(),
        about_schemes=about_schemes,
    )


def _quote(passage: retrieval.Retrieved) -> SchemeAnswer:
    """The passage itself as the answer, with its citation."""
    return SchemeAnswer(
        answer=passage.content.strip()[:600],
        citations=[_cite(passage)],
        grounded=True,
        provider="offline",
    )


# Background searches, held so asyncio does not collect them mid-flight (it
# keeps only a weak reference to a task nobody awaits).
_pending_searches: set[asyncio.Task] = set()


def _queue_search(question: str) -> None:
    """Look for official pages for an unanswered scheme question, later.

    Whatever is found is stored for review, never made answerable directly
    (websearch.search_and_ingest), so this cannot change what the person is
    told -- now or next time -- until an admin has looked.
    """
    from app.services import websearch

    if not websearch.is_available():
        return
    task = asyncio.create_task(_search_for_review(question))
    _pending_searches.add(task)
    task.add_done_callback(_pending_searches.discard)


async def _search_for_review(question: str) -> None:
    from app.services import websearch

    try:
        outcomes = await websearch.search_and_ingest(question, limit=3)
    except websearch.SearchUnavailable as exc:
        logger.info("Search unavailable (%s); nothing queued for review", exc)
        return
    except Exception as exc:  # noqa: BLE001 - a background search must not crash anything
        logger.warning("Background search failed for %r: %s", question[:60], exc)
        return
    queued = [o for o in outcomes if o.get("chunks")]
    if queued:
        logger.info(
            "Queued %d page(s) for review after %r: %s",
            len(queued), question[:60], ", ".join(o["domain"] for o in queued),
        )


def _cite(passage: retrieval.Retrieved) -> dict:
    """A citation a person could actually follow back to the document."""
    # A source that is a URL is shown as one. It came from the search API and
    # is passed through unchanged -- never assembled, never repaired.
    source = passage.source
    # A recorded URL first; otherwise a source that is itself a URL, which is
    # how a web-fetched page arrives. Never anything assembled from the two.
    url = passage.source_url
    if not url and source.startswith(("http://", "https://")):
        url = source
    return {
        "source": source,
        "source_url": url,
        "document_title": passage.document_title,
        "heading": passage.heading,
        # Enough to recognise the passage, not so much that the answer is buried.
        "excerpt": " ".join(passage.content.split())[:280],
        "similarity": round(passage.similarity, 3),
    }
