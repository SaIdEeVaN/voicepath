"""A failed model is not a licence to assert (spec sections 7 and 9).

`scheme_qa` exists to enforce one rule: **an answer must be traceable to a
passage, or it must not be given.** The module's own docstring says the only
reliable signal that the corpus does not cover a question is "the step that
read the passages saying so" -- because e5 scores every passage in a narrow
high band, so a question about something the corpus has never heard of still
returns five confident-looking neighbours.

Found while ingesting the full scheme corpus. Asking *"What is the capital of
France?"* against 1096 chunks of Indian government scheme documents returned
`grounded=True` and a passage about the Ambedkar International Centre.

The cause was not retrieval. It was Groq answering **429 Rate limit reached**,
and the handler for that falling back to "return the best passage, grounded".
That fallback was written for deliberate offline operation, where there is no
model by design and handing back the passage is a considered trade -- the
citation is the answer. Reused for a *transient* failure it does something
different: it removes the only judge the system has and then asserts anyway.

A deployment configured with a model is expected to use it. When the call
fails, the honest answer is that nothing could be answered right now, not an
unrelated paragraph presented as grounded.
"""

from __future__ import annotations

import pytest

from app.services import llm, retrieval, scheme_qa
from app.services.retrieval import Retrieved


def _passage(content: str, similarity: float = 0.80) -> Retrieved:
    return Retrieved(
        chunk_id=1,
        document_title="Annual Report",
        source="annual_report.pdf",
        heading=None,
        content=content,
        similarity=similarity,
    )


UNRELATED = _passage(
    "The Ambedkar International Centre is a premier centre of excellence under "
    "the Ministry of Social Justice and Empowerment, Government of India."
)


@pytest.fixture
def one_passage(monkeypatch):
    async def _search(question, *, limit=5):
        return [UNRELATED]

    monkeypatch.setattr(retrieval, "search", _search)


@pytest.fixture
def llm_configured_but_failing(monkeypatch):
    """A model is configured; the call fails. A 429 is the real case."""
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(llm, "provider_name", lambda: "groq")

    async def _explode(*args, **kwargs):
        raise llm.LLMUnavailable("groq returned 429: Rate limit reached")

    monkeypatch.setattr(llm, "complete_json", _explode)


class TestATransientFailureRefuses:
    @pytest.mark.asyncio
    async def test_it_does_not_assert_an_unrelated_passage(
        self, one_passage, llm_configured_but_failing
    ):
        """The reported case, at its smallest."""
        answer = await scheme_qa.ask("What is the capital of France?", language="en")

        assert answer.grounded is False, (
            "a passage nothing verified must not be returned as grounded"
        )

    @pytest.mark.asyncio
    async def test_it_carries_no_citation(
        self, one_passage, llm_configured_but_failing
    ):
        """A citation beside an unverified answer is the exact failure this
        module exists to prevent: a source shown beside text that did not come
        from it."""
        answer = await scheme_qa.ask("What is the capital of France?", language="en")

        assert answer.citations == []

    @pytest.mark.asyncio
    async def test_it_does_not_quote_the_passage_as_the_answer(
        self, one_passage, llm_configured_but_failing
    ):
        answer = await scheme_qa.ask("What is the capital of France?", language="en")

        assert "Ambedkar International Centre" not in answer.answer


class TestDeliberateOfflineIsUnchanged:
    """Running with no model at all is a different situation and a documented
    trade: there is no judge by design, and the passage with its citation is
    the honest shape. That behaviour is not what broke, and is left alone."""

    @pytest.fixture
    def no_llm(self, monkeypatch):
        monkeypatch.setattr(llm, "is_available", lambda: False)

    @pytest.mark.asyncio
    async def test_the_passage_is_still_returned(self, one_passage, no_llm):
        answer = await scheme_qa.ask("Tell me about the centre", language="en")

        assert answer.grounded is True
        assert answer.citations
        assert answer.provider == "offline"
