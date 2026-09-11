"""Reading what a person was doing, without deciding anything for them.

The classifier routes; it never asserts. That matters for what is tested here:
the failure worth catching is not a misread label, it is a misread label that
changes what the system claims about someone. So the properties below are about
the question text staying theirs, and about neither flag being invented.

These run against the offline heuristic, deliberately. It is the path that runs
when there is no model, and it is the one that has to stay honest without one.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services import intent


def classify(text: str) -> intent.QueryIntent:
    return asyncio.run(intent.classify(text))


class TestDescribingWork:
    @pytest.mark.parametrize(
        "text",
        [
            "I repair two-wheelers",
            "I know welding",
            "எனக்கு வெல்டிங் தெரியும்",
            "मैं सिलाई का काम करता हूँ",
        ],
    )
    def test_work_is_recognised_in_every_language(self, text):
        assert classify(text).describes_work is True


class TestAsking:
    @pytest.mark.parametrize(
        "text",
        [
            "who is eligible for PM-AJAY?",
            "tell me about adarsh gram",
            "ஆதர்ஷ் கிராமம் என்றால் என்ன?",
            "क्या मुझे सर्टिफिकेट चाहिए?",
        ],
    )
    def test_questions_are_recognised_in_every_language(self, text):
        assert classify(text).asks_question is True

    def test_the_question_is_their_words(self):
        """Retrieval searches with this verbatim.

        A rephrasing here means answering a question the person did not ask,
        which is worse than not answering: it is confident and wrong.
        """
        text = "who is eligible for PM-AJAY?"
        result = classify(text)
        assert result.question is not None
        assert result.question in text or text in result.question


class TestNeither:
    @pytest.mark.parametrize("text", ["hello", "   ", ""])
    def test_noise_claims_nothing(self, text):
        """The important negative.

        Guessing "describes work" for a greeting sends extraction looking for a
        skill nobody mentioned, and every later step treats what it finds as
        something the person said.
        """
        result = classify(text)
        assert result.is_empty
        assert result.question is None

    def test_asking_nothing_carries_no_question(self):
        result = classify("I repair two-wheelers")
        if not result.asks_question:
            assert result.question is None


class TestBoth:
    def test_a_sentence_can_be_work_and_a_question(self):
        """The case the previous approach dropped half of.

        Inferring intent from "extraction found nothing" cannot see this at
        all: extraction finds welding, so the question was never asked.
        """
        result = classify("I do welding, is there a scheme for that?")
        assert result.describes_work is True
        assert result.asks_question is True


class TestBareTopics:
    """A search box gets search terms, not sentences.

    "PM-AJAY" asks nothing grammatically and is plainly a request to be told
    about PM-AJAY. Reading it as neither is how someone who typed a scheme name
    gets told nothing was found -- which is what happened before this existed.

    These need the corpus to distinguish a real name from noise, so they are
    skipped without a database rather than asserted against one that is not
    there.
    """

    @pytest.fixture(autouse=True)
    def _needs_corpus(self):
        from app.services import db, retrieval

        if not db.is_available():
            pytest.skip("no database; the topic check has nothing to ask")
        if not asyncio.run(retrieval.is_ready()):
            pytest.skip("no documents ingested")

    @pytest.mark.parametrize("text", ["pm ajay", "adarsh gram", "pm ajay skill development"])
    def test_a_scheme_name_is_a_request(self, text):
        assert classify(text).asks_question is True

    @pytest.mark.parametrize("text", ["hello", "hi there", "ok thanks", "asdfghjkl"])
    def test_a_greeting_is_not(self, text):
        """The half that matters.

        Every one of these scores above the similarity bar against this corpus
        -- "asdfghjkl" reaches 0.79 -- so nothing downstream would stop a
        confident answer about a document it shares no word with.
        """
        assert classify(text).asks_question is False
