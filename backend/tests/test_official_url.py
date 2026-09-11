"""The official government page: quoted when present, never invented.

A URL is the field where a plausible guess does the most damage. A wrong salary
is a disappointment; a wrong government URL looks authoritative and sends
someone to the wrong place, or to a page that will take their details.

So the rule is the same shape as the one extraction follows: say what the record
holds, or say the record does not hold it.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.services.assistant import QueryContext, answer_offline, detect_intent
from app.services.schemes import Scheme

URL = "https://pmvishwakarma.gov.in/"


@pytest.fixture
def scheme() -> Scheme:
    return Scheme(
        id=1,
        title="Pradhan Mantri Vishwakarma Scheme",
        organization="Ministry of MSME",
        location="Salem",
        district="Salem",
        type="Training",
        minimum_experience=0,
        certifications_required=[],
        salary_min=None,
        salary_max=None,
        nsqf_level=None,
        source_reference="PMV/TN/SLM/2024/0001",
        description="Toolkit and skill training for traditional artisans.",
        official_url=URL,
    )


class TestIntent:
    @pytest.mark.parametrize(
        "question",
        [
            "what is the official website?",
            "give me the link",
            "where can I read about this officially?",
            "इसकी सरकारी वेबसाइट क्या है?",
            "இதன் அரசு இணையதளம் என்ன?",
        ],
    )
    def test_asking_for_the_page_is_recognised_in_every_language(self, question):
        assert detect_intent(question) == "official_page"

    def test_a_question_about_place_is_still_about_place(self):
        """"Where" belongs to both intents, and the specific one must win.

        Keyword intents resolve in insertion order, so this fails the moment
        `location` is moved above `official_page` again.
        """
        assert detect_intent("where is this job?") == "location"
        assert detect_intent("where can I read about this officially?") == "official_page"


class TestAnswer:
    def test_the_url_is_quoted_exactly(self, scheme):
        answer = answer_offline(
            "what is the official website?", QueryContext(scheme=scheme)
        )
        assert URL in answer.answer_text
        assert answer.answered_from_data is True

    def test_no_url_in_the_record_means_no_url_in_the_answer(self, scheme):
        """The failure that matters: a guess would look official."""
        bare = dataclasses.replace(scheme, official_url=None)
        answer = answer_offline(
            "what is the official website?", QueryContext(scheme=bare)
        )
        assert "http" not in answer.answer_text.lower()
        assert answer.answered_from_data is False

    def test_the_title_is_not_turned_into_a_url(self, scheme):
        """A model that knows the scheme must still not supply the address.

        "Pradhan Mantri Vishwakarma" has an obvious-looking domain, which is
        exactly why the offline path may not construct one.
        """
        bare = dataclasses.replace(scheme, official_url=None)
        answer = answer_offline("give me the link", QueryContext(scheme=bare))
        assert "vishwakarma" not in answer.answer_text.lower()

    @pytest.mark.parametrize("language", ["ta", "hi"])
    def test_the_answer_is_in_the_language_asked(self, scheme, language):
        answer = answer_offline(
            "what is the official website?",
            QueryContext(scheme=scheme),
            language=language,
        )
        # The URL stays Latin; the sentence around it must not.
        assert URL in answer.answer_text
        assert any(ord(ch) > 0x0900 for ch in answer.answer_text)
