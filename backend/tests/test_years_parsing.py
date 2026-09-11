"""Reading years of experience out of a transcript (spec section 4.2).

The offline path parses this with patterns rather than a model, and it matters
more than its name suggests: it runs whenever the LLM is unavailable, which on
a free tier includes every request after the daily token allowance is spent.
It was running in production when these tests were written.

Two defects, both in the spelled-out-number path:

**"two" matched inside "two-wheelers".** The search was a substring find, so
the number word did not have to be a word at all.

**The pairing window was too loose.** It accepted any year word within 22
characters, so in "I have been repairing two-wheelers for six years" the "two"
of "two-wheelers" paired with the "years" belonging to "six", and six years of
experience was recorded as two.

The existing comment shows the trap was known -- "requiring the pairing avoids
reading 'two bikes' as two years" -- but the guard only stopped a bare number,
not a number that belonged to a different phrase.

Experience is 25% of a match score, so reading six as two is not cosmetic.
"""

from __future__ import annotations

import pytest

from app.services.extraction import extract_offline


def _years(transcript: str) -> float | None:
    return extract_offline(transcript, language="en").experience_years


class TestDigits:
    @pytest.mark.parametrize(
        "transcript,expected",
        [
            ("i worked as a plumber for the past 5 years", 5.0),
            ("I have 6 years experience in welding", 6.0),
            ("10 yrs of tailoring", 10.0),
            ("I have 3+ years of driving", 3.0),
        ],
    )
    def test_a_stated_number_is_read(self, transcript, expected):
        assert _years(transcript) == expected


class TestSpelledOutNumbers:
    @pytest.mark.parametrize(
        "transcript,expected",
        [
            ("I have six years of experience repairing bikes", 6.0),
            ("I did tailoring for three years", 3.0),
            ("ten years of welding", 10.0),
        ],
    )
    def test_a_spelled_number_beside_a_year_word_is_read(self, transcript, expected):
        assert _years(transcript) == expected


class TestANumberInsideAnotherWord:
    def test_two_wheelers_is_not_two_years(self):
        """The reported shape, and the reason this file exists."""
        assert _years("I have been repairing two-wheelers for six years") == 6.0

    def test_two_wheelers_alone_states_no_experience(self):
        """No duration was given. Inventing one is worse than leaving it
        unknown -- matching treats unknown experience as 0.5 rather than
        scoring the person on a number they never said."""
        assert _years("I repair two-wheelers") is None

    def test_four_wheeler_work_is_not_four_years(self):
        assert _years("four-wheeler repair in Salem") is None


class TestANumberThatIsNotADuration:
    def test_a_count_of_things_is_not_years(self):
        """The case the original guard was written for. It must keep working."""
        assert _years("I fixed two bikes") is None

    def test_nothing_stated_is_none(self):
        assert _years("I do welding") is None


class TestOtherLanguages:
    def test_tamil_digits(self):
        assert _years("எனக்கு 6 வருட அனுபவம் உண்டு") == 6.0

    def test_hindi_digits(self):
        assert _years("मुझे 5 साल का अनुभव है") == 5.0

    def test_a_spelled_tamil_number(self):
        assert _years("எனக்கு ஆறு வருட அனுபவம்") == 6.0


class TestItStaysPlausible:
    def test_an_implausible_span_is_ignored(self):
        """A year read as a duration -- "since 1998" -- is not experience."""
        assert _years("I have been working since 1998") is None
