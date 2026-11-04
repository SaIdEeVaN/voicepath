"""The RAG faults found in the production question log, one test per fault.

Each of these happened to a real question:

* "kylian mbappe or lamine yamal" was answered "from the scheme guidelines",
  citing football news a web search had stored as scheme guidance.
* A question about PM-AJAY (misheard in Tamil) was answered from an e-Shram
  help page, as if it were PM-AJAY's rules.
* "PM-KISAN" got "the passages do not mention PM-KISAN" -- labelled as an
  answer from the guidelines, with a citation.
* "sigaram thodu scheme" was refused while Groq was rate-limited, although its
  own document had thirteen passages in the corpus.
* "What benefits does a farmer get under SMAM?" never reached the guidelines:
  "far" inside "farmer" made it a question about distance.
* Natural questions matched nothing by keyword: the query required every word,
  "who" and "is" and "for" included.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.data.scheme_names import SCHEME_NAMES
from app.services import assistant, llm, retrieval, scheme_qa, websearch
from app.services.assistant import QueryContext, detect_intent
from app.services.retrieval import Retrieved
from app.services.schemes import Scheme

DOCS = Path(__file__).resolve().parents[1] / "data" / "scheme_docs"


def _passage(content="Students in engineering colleges may apply.", *,
             source="EOI_Sigaram_Thodu_2024.pdf", similarity=0.84) -> Retrieved:
    return Retrieved(
        chunk_id=7, document_title="EOI Sigaram Thodu 2024", source=source,
        heading=None, content=content, similarity=similarity,
    )


def _listing() -> Scheme:
    return Scheme(
        id=1, title="Welder (Fabrication Unit)", organization="Annai Steel",
        location="Salem", district="Salem", type="Full-time",
        minimum_experience=1, certifications_required=[], salary_min=16000,
        salary_max=21000, nsqf_level="4", source_reference="OGD/X",
        description="Arc and gas welding.",
    )


@pytest.fixture
def searched(monkeypatch):
    """Record every search, and answer with one Sigaram Thodu passage."""
    calls: list[dict] = []

    async def fake(question, *, limit=5, sources=None):
        calls.append({"question": question, "sources": sources})
        return [_passage()]

    monkeypatch.setattr(retrieval, "search", fake)
    return calls


@pytest.fixture
def model(monkeypatch):
    """A configured model whose reply each test sets."""
    reply: dict = {}
    prompts: list[str] = []
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(llm, "provider_name", lambda: "groq")

    async def complete(system, prompt, **kwargs):
        prompts.append(prompt)
        if isinstance(reply.get("raise"), Exception):
            raise reply["raise"]
        return dict(reply)

    monkeypatch.setattr(llm, "complete_json", complete)
    return reply, prompts


@pytest.fixture
def queued(monkeypatch):
    """Capture background searches instead of running them."""
    questions: list[str] = []
    monkeypatch.setattr(websearch, "is_available", lambda: True)
    monkeypatch.setattr(scheme_qa, "_queue_search", lambda q: questions.append(q))
    return questions


class TestSchemeNames:
    @pytest.mark.parametrize(
        "question,key",
        [
            ("Who is eligible for Sigaram Thodu?", "sigaram-thodu"),
            ("Tell me about PM-AJAY", "pm-ajay"),
            ("pm ajay scheme details", "pm-ajay"),
            ("பி.எம். அஜய் திட்டம் பற்றி சொல்லுங்கள்", "pm-ajay"),
            ("सिगरम थोडु क्या है", "sigaram-thodu"),
            ("विश्वकर्मा योजना में कितना मिलता है", "pm-vishwakarma"),
            ("What is the stipend under PM Vishwakarma?", "pm-vishwakarma"),
            ("subsidy for a tractor under SMAM", "smam"),
            ("கைத்தறி நெசவாளர்களுக்கு என்ன உதவி?", "handloom"),
        ],
    )
    def test_a_named_scheme_is_recognised(self, question, key):
        assert key in retrieval.named_schemes(question)

    @pytest.mark.parametrize(
        "question",
        ["vijayan works in Salem", "I am a farmer", "who is eligible?", "how much does it pay"],
    )
    def test_words_that_only_contain_a_name_do_not_count(self, question):
        assert retrieval.named_schemes(question) == []

    def test_every_source_is_a_real_document(self):
        """A typo here silently narrows a search to nothing."""
        for key, entry in SCHEME_NAMES.items():
            for source in entry["sources"]:
                assert source.startswith("http") or (DOCS / source).exists(), (key, source)


class TestKeywordQuery:
    def test_question_words_are_dropped_and_names_kept(self):
        assert retrieval.content_terms("Who is eligible for PM-AJAY?") == ["eligible", "pm-ajay"]

    def test_tamil_and_hindi_question_words_are_dropped(self):
        assert retrieval.content_terms("சிகரம் தொடு திட்டம் என்ன") == ["சிகரம்", "தொடு"]
        assert retrieval.content_terms("विश्वकर्मा योजना क्या है") == ["विश्वकर्मा"]

    def test_a_greeting_leaves_nothing_to_search_for(self):
        assert retrieval.content_terms("hi, how are you?") == []


class TestIntentWords:
    @pytest.mark.parametrize(
        "question",
        [
            "What benefits does a farmer get under SMAM?",   # far
            "What is the repayment period for an NMDFC loan?",  # pay
            "What data do I need to submit?",                 # data
        ],
    )
    def test_a_keyword_inside_another_word_does_not_claim_the_question(self, question):
        assert detect_intent(question) is None

    @pytest.mark.parametrize(
        "question,intent",
        [("how far is it?", "location"), ("it pays well?", "pay"),
         ("do I need certificates?", "certificate"), ("what happens to my data?", "privacy")],
    )
    def test_whole_words_and_their_endings_still_count(self, question, intent):
        assert detect_intent(question) == intent


class TestRouting:
    @pytest.fixture
    def guidelines(self, monkeypatch):
        """Record whether the guidelines were consulted; always refuse."""
        asked: list[str] = []

        async def ready():
            return True

        async def ask(question, *, language="en", in_view=None):
            asked.append(question)
            return scheme_qa.SchemeAnswer(answer="no", grounded=False)

        monkeypatch.setattr(retrieval, "is_ready", ready)
        monkeypatch.setattr(scheme_qa, "ask", ask)
        return asked

    def test_with_no_listing_a_pay_question_goes_to_the_guidelines(self, guidelines):
        asyncio.run(assistant.answer("How much is the stipend under PM Vishwakarma?", QueryContext()))
        assert guidelines

    def test_a_question_about_the_listing_on_screen_stays_with_it(self, guidelines):
        answer = asyncio.run(
            assistant.answer("how much does it pay?", QueryContext(scheme=_listing()))
        )
        assert guidelines == []
        assert "16,000" in answer.answer_text

    def test_naming_a_covered_scheme_beats_a_listing_keyword(self, guidelines):
        asyncio.run(
            assistant.answer(
                "How many years does PM-AJAY run?", QueryContext(scheme=_listing())
            )
        )
        assert guidelines

    def test_privacy_never_goes_to_the_guidelines(self, guidelines):
        asyncio.run(assistant.answer("is my voice saved?", QueryContext()))
        assert guidelines == []


class TestGrounding:
    def test_a_named_scheme_restricts_the_search_to_its_documents(self, searched, model):
        reply, _ = model
        reply.update(answer="Engineering students [1].", used=[1], answerable=True, about_schemes=True)
        asyncio.run(scheme_qa.ask("Who is eligible for Sigaram Thodu?"))
        assert searched[0]["sources"] == ["EOI_Sigaram_Thodu_2024.pdf"]

    def test_an_unnamed_question_searches_everything(self, searched, model):
        reply, _ = model
        reply.update(answer="x [1]", used=[1], answerable=True, about_schemes=True)
        asyncio.run(scheme_qa.ask("Who can get a subsidy?"))
        assert searched[0]["sources"] is None

    def test_answerable_and_used_together_ground_an_answer(self, searched, model):
        reply, _ = model
        reply.update(answer="Engineering students [1].", used=[1], answerable=True, about_schemes=True)
        result = asyncio.run(scheme_qa.ask("Who is eligible for Sigaram Thodu?"))
        assert result.grounded and result.citations

    def test_citing_a_passage_to_say_it_does_not_help_is_a_refusal(self, searched, model, queued):
        """The PM-KISAN case: used=[1], but the answer is 'the passages do not say'."""
        reply, _ = model
        reply.update(
            answer="The passages do not mention PM-KISAN; they describe e-Shram [1].",
            used=[1], answerable=False, about_schemes=True,
        )
        result = asyncio.run(scheme_qa.ask("Tell me about PM-KISAN"))
        assert result.grounded is False
        assert result.citations == []
        assert "e-Shram" not in result.answer

    def test_a_reply_without_the_answerable_flag_is_not_trusted(self, searched, model):
        reply, _ = model
        reply.update(answer="Engineering students [1].", used=[1])
        result = asyncio.run(scheme_qa.ask("Who is eligible for Sigaram Thodu?"))
        assert result.grounded is False

    def test_the_listing_on_screen_is_described_to_the_model(self, searched, model):
        reply, prompts = model
        reply.update(answer="no", used=[], answerable=False, about_schemes=True)
        asyncio.run(scheme_qa.ask("who can apply for this?", in_view="Welder (Full-time, Annai Steel, Salem)"))
        assert "Welder (Full-time, Annai Steel, Salem)" in prompts[0]


class TestWebSearchGate:
    def test_an_off_topic_question_is_never_searched(self, searched, model, queued):
        """The Mbappe case."""
        reply, _ = model
        reply.update(answer="No.", used=[], answerable=False, about_schemes=False)
        asyncio.run(scheme_qa.ask("kylian mbappe or lamine yamal"))
        assert queued == []

    def test_an_unanswered_scheme_question_is_queued_for_review(self, searched, model, queued):
        reply, _ = model
        reply.update(answer="No.", used=[], answerable=False, about_schemes=True)
        asyncio.run(scheme_qa.ask("Tell me about PM-KISAN"))
        assert queued == ["Tell me about PM-KISAN"]

    def test_without_the_model_s_judgement_nothing_is_searched(self, searched, model, queued):
        reply, _ = model
        reply["raise"] = llm.LLMUnavailable("429")
        asyncio.run(scheme_qa.ask("Who can get a subsidy?"))
        assert queued == []

    def test_an_answered_question_is_not_searched(self, searched, model, queued):
        reply, _ = model
        reply.update(answer="Engineering students [1].", used=[1], answerable=True, about_schemes=True)
        asyncio.run(scheme_qa.ask("Who is eligible for Sigaram Thodu?"))
        assert queued == []


class TestModelDown:
    def test_a_named_scheme_is_quoted_from_its_own_document(self, searched, model):
        """The 'sigaram thodu scheme' case: refused under a 429 with 13 passages on hand."""
        reply, _ = model
        reply["raise"] = llm.LLMUnavailable("groq returned 429")
        result = asyncio.run(scheme_qa.ask("sigaram thodu scheme"))
        assert result.grounded is True
        assert result.citations[0]["source"] == "EOI_Sigaram_Thodu_2024.pdf"
        assert "engineering colleges" in result.answer

    def test_without_a_named_scheme_it_still_refuses(self, searched, model):
        reply, _ = model
        reply["raise"] = llm.LLMUnavailable("groq returned 429")
        result = asyncio.run(scheme_qa.ask("Who can get a subsidy?"))
        assert result.grounded is False
        assert result.citations == []


class TestWebSearchStorage:
    @pytest.mark.parametrize(
        "url",
        [
            "https://ddnews.gov.in/en/soccer-france-battle-past-austria",
            "https://newsonair.gov.in/spanish-super-cup-football",
            "https://www.ddnews.gov.in/en/anything",
        ],
    )
    def test_news_sites_are_never_trusted(self, url):
        assert websearch.is_excluded(url)
        assert websearch.tier_for(url) == 3

    def test_a_scheme_site_is_not_caught_by_the_news_rule(self):
        assert not websearch.is_excluded("https://pmvishwakarma.gov.in/")
        assert websearch.tier_for("https://pmvishwakarma.gov.in/") == 1

    def test_every_fetched_page_waits_for_review_even_tier_one(self, monkeypatch):
        page = websearch.SearchResult(
            title="PM Vishwakarma", url="https://pmvishwakarma.gov.in/",
            domain="pmvishwakarma.gov.in", snippet="",
            trust_tier=1,
            # Rendered, by looks_rendered's measure: plenty of distinct words.
            raw_content=" ".join(f"artisan{i} training" for i in range(120)) + ".",
        )
        stored: list[dict] = []

        async def fake_search(query, *, official_only=True):
            return [page]

        async def fake_ingest(**kwargs):
            stored.append(kwargs)
            return 1, 3

        async def no_network(url):  # pragma: no cover - must not run
            raise AssertionError("fetched over the network in a unit test")

        monkeypatch.setattr(websearch, "search", fake_search)
        monkeypatch.setattr(websearch, "fetch_page", no_network)
        monkeypatch.setattr(retrieval, "ingest", fake_ingest)
        outcomes = asyncio.run(websearch.search_and_ingest("PM Vishwakarma training"))

        assert stored and stored[0]["status"] == "pending_verification"
        assert outcomes[0]["status"] == "pending_verification"
