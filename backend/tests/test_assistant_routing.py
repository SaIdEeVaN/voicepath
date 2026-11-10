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
    # What ranking must never reach: a model, the document corpus, the web.
    FORBIDDEN = ("llm", "retrieval", "scheme_qa", "websearch", "explanation", "assistant")

    def test_matching_imports_neither_retrieval_nor_an_llm(self):
        """Every import in matching.py, inside functions too, read from its syntax
        tree -- not a substring search, which a comment could trip and a
        renamed import could slip past. Tightened 2026-11-10."""
        import ast

        tree = ast.parse(inspect.getsource(matching))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported |= {f"{module}.{alias.name}" for alias in node.names}
        for name in imported:
            leaf = name.rsplit(".", 1)[-1]
            assert leaf not in self.FORBIDDEN, (
                f"matching.py imports {name}; ranking must stay reproducible "
                "from stored numbers alone"
            )

    def test_ranking_runs_with_every_model_and_search_rigged_to_fail(self, monkeypatch):
        """The import check cannot see through a module matching does import --
        normalization does call the model, for disambiguation. So rank for
        real, with everything that could reach a model, the corpus or the web
        replaced by something that fails the test if it is touched."""
        from app.services import embeddings, llm, retrieval, scheme_qa, websearch
        from app.services.matching import ProfileInput, rank
        from app.services.normalization import NormalizedSkill
        from app.services.schemes import RequiredSkill, Scheme

        def touched(*_args, **_kwargs):
            raise AssertionError("ranking reached a model, the corpus or the web")

        async def touched_async(*_args, **_kwargs):
            touched()

        for module, names in (
            (llm, ("complete_json",)),
            (embeddings, ("embed_queries", "embed_query", "embed_documents")),
            (scheme_qa, ("ask",)),
        ):
            for name in names:
                if hasattr(module, name):
                    original = getattr(module, name)
                    fake = touched_async if inspect.iscoroutinefunction(original) else touched
                    monkeypatch.setattr(module, name, fake)
        for module in (retrieval, websearch):
            for name, value in list(vars(module).items()):
                if inspect.iscoroutinefunction(value) and not name.startswith("_"):
                    monkeypatch.setattr(module, name, touched_async)

        catalogue = [
            Scheme(id=i, title=f"s{i}", organization="o", location=place, district=place,
                   type=kind, minimum_experience=1, certifications_required=[],
                   salary_min=None, salary_max=None, nsqf_level=None,
                   source_reference=None, description=None,
                   required_skills=[RequiredSkill(1, "SK022", "Welding", 1.0, True,
                                                  embedding=[1.0, 0.0])])
            for i, (place, kind) in enumerate(
                [("Salem", "Full-time"), ("Erode", "Training"), ("All India", "Self-employment support")],
                start=1,
            )
        ]
        person = ProfileInput(
            experience_years=3, location="Salem", district="Salem", certifications=[],
            skills=[NormalizedSkill(raw_name="welding", evidence_phrase="I weld",
                                    skill_id=1, code="SK022", name="Welding",
                                    embedding=[1.0, 0.0])],
        )
        first = rank(person, catalogue)
        again = rank(person, catalogue)
        assert first and [m.overall_score for m in first] == [m.overall_score for m in again]

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
            # A yes/no that the answer is the emergency numbers
            # (services/safety.py). It says nothing about any scheme.
            "urgent",
        }
