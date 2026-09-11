"""Where a question goes, and what retrieval is still not allowed to touch.

Two things are being protected here.

A question about the listing must be answered from the listing. Pay, distance
and certificates are facts about one row, and sending them through a document
search would trade an exact answer for a paraphrase of a policy document.

And retrieval must stay out of the ranking. The reason a match is defensible is
that `matching.py` is arithmetic over stored numbers -- the same profile against
the same catalogue produces the same order every time. A retrieved document that
could nudge a score would end that, quietly.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from app.services import assistant, matching
from app.services.assistant import QueryContext, detect_intent
from app.services.schemes import Scheme


@pytest.fixture
def scheme() -> Scheme:
    return Scheme(
        id=1,
        title="Two-Wheeler Service Technician",
        organization="Ratnam Auto Works",
        location="Salem",
        district="Salem",
        type="Full-time",
        minimum_experience=2,
        certifications_required=[],
        salary_min=14000,
        salary_max=18000,
        nsqf_level="4",
        source_reference="OGD/TN/SLM/AUTO/2024/0117",
        description="Servicing and repair of motorcycles at a workshop in Salem.",
        official_url=None,
    )


class TestRouting:
    @pytest.mark.parametrize(
        "question",
        [
            "how much does it pay?",
            "do I need a certificate?",
            "how far is it?",
            "how many years of experience?",
        ],
    )
    def test_listing_questions_are_recognised(self, question):
        """These resolve to a row field, so they never reach retrieval."""
        assert detect_intent(question) is not None

    @pytest.mark.parametrize(
        "question",
        [
            "who is eligible for this scheme?",
            "what documents do I need to apply?",
            "क्या मेरी आय सीमा से ज़्यादा है तो भी मिलेगा?",
        ],
    )
    def test_scheme_questions_are_not_claimed_by_a_listing_intent(self, question):
        """An unmatched intent is the signal to consult the guidelines.

        If a keyword were ever added that swallowed one of these, the question
        would be answered from a single row instead of the policy text, which
        is how a confident wrong answer about eligibility gets made.
        """
        assert detect_intent(question) is None

    def test_the_assistant_survives_retrieval_being_unavailable(self, scheme, monkeypatch):
        """A corpus that cannot be reached is a missing enhancement, not an outage."""

        async def explode() -> bool:
            raise RuntimeError("corpus unreachable")

        monkeypatch.setattr(assistant.retrieval, "is_ready", explode)

        answer = asyncio.run(
            assistant.answer("who is eligible?", QueryContext(scheme=scheme))
        )
        assert answer.answer_text
        assert answer.citations == []


class TestRankingIsolation:
    def test_matching_imports_neither_retrieval_nor_an_llm(self):
        """The property that makes a ranking auditable, asserted structurally.

        Reading the module source rather than its imports: a lazy import inside
        a function would pass an attribute check and still put a model in the
        ranking path.
        """
        source = inspect.getsource(matching)
        for forbidden in ("retrieval", "scheme_qa", "llm"):
            assert forbidden not in source, (
                f"matching.py references {forbidden!r}; ranking must stay "
                "reproducible from stored numbers alone"
            )

    def test_an_answer_carries_no_route_back_to_a_score(self):
        """Citations travel outward only.

        The Answer type is what retrieval returns through. If it ever gained a
        field a score could be read from, an explanation could start
        influencing the order it was meant to describe.
        """
        fields = set(assistant.Answer.__dataclass_fields__)
        assert fields == {
            "answer_text",
            "source_note",
            "provider",
            "answered_from_data",
            "citations",
        }
