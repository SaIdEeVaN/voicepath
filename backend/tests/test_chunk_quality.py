"""What survives chunking, and what must not (spec section 9).

`_is_prose` exists to keep flattened tables out of the corpus: a statistics
grid becomes "Literacy Rate (Census, 2001) 54.7 64.8", which is meaningless but
still embeds to somewhere and competes for rank against a passage that would
actually answer the question.

It was calibrated against government *portal pages*, where a navigation menu
runs two to four words a line and the prose beside it runs fifteen and up. So
it rejected any block averaging under six words a line.

That test does not survive contact with a designed PDF. Ingesting a 107-page
government scheme playbook, **88 of 106 blocks were rejected and 150,000 of
188,000 characters thrown away** -- including the scheme descriptions
themselves, which the card layout wraps at four to five words a line. A block
reading "ADITI is a government program that supports startups and innovators
in building..." was dropped as though it were a menu.

Line breaks in a PDF are layout, not meaning. Measured across both documents,
what separates prose from furniture is **sentence-ender density**, counted
ignoring decimals so that "1.2 % of households" is not read as two sentences:

    playbook prose, wrongly rejected     0.64 enders per 100 chars
    playbook prose, kept                 0.61
    guidelines prose, kept               0.75
    guidelines furniture, rightly cut    0.28   <- contents, cover, score table

These cases are the samples that separation was drawn from.
"""

from __future__ import annotations

from pathlib import Path

from app.services.retrieval import _is_prose

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    """Real extracted text, kept verbatim on disk.

    Inlining these as string literals did not work. Two attempts at writing a
    faithful sample by hand landed at 6.0 words a line -- just over the old
    threshold -- and so passed a filter that rejected the real thing at 5.3.
    The bug lives in the exact line breaks, so the exact line breaks are the
    test.
    """
    return (FIXTURES / name).read_text(encoding="utf-8")


# One scheme's card from the 107-page startup playbook, as pypdf extracts it.
CARD_PROSE = _fixture("playbook_scheme_card.txt")

# A scoring grid from the PM-AJAY guidelines. Note its 1.2 / 1.3 section
# numbers: counting every full stop would read this as sentence-rich.
SCORING_TABLE = _fixture("guidelines_score_table.txt")

# Real prose, wrapped long. Always worked; must keep working.
LONG_PROSE = """\
The Adarsh Gram component aims to ensure the integrated development of villages with a
substantial Scheduled Caste population. Gap-filling funds are provided to the State
Government at the rate of twenty lakh rupees per village. The village must prepare a
Village Development Plan before any funds are released, and the plan is approved by the
district level convergence committee."""

TABLE_OF_CONTENTS = """\
Centrally Sponsored Scheme of Pradhan Mantri Anusuchit Jaati Abhyuday Yojana
CONTENTS
Chapter Topic Page No.
1 Introduction 4
2 Development of SC dominated villages 8
3 Grants-in-aid for District level 15
4 Construction of Hostels 22
5 Monitoring and Evaluation 30"""

NAVIGATION_MENU = """\
Screen Reader Access
Skip to main content
About Us
Contact Us
Sitemap
Help
Terms and Conditions
Privacy Policy
Related Links
Feedback"""


class TestProseIsKept:
    def test_a_card_layout_scheme_description_survives(self):
        """The regression this file exists for. 1618 characters describing a
        real scheme, at 5.3 words a line."""
        assert _is_prose(CARD_PROSE) is True

    def test_ordinary_wrapped_prose_still_survives(self):
        assert _is_prose(LONG_PROSE) is True


class TestFurnitureIsCut:
    def test_a_table_of_contents_is_rejected(self):
        assert _is_prose(TABLE_OF_CONTENTS) is False

    def test_a_numeric_scoring_table_is_rejected(self):
        assert _is_prose(SCORING_TABLE) is False

    def test_a_navigation_menu_is_rejected(self):
        """The case the original words-per-line test was written for. It has
        to keep working -- web pages reach this code through websearch."""
        assert _is_prose(NAVIGATION_MENU) is False

    def test_something_far_too_short_is_rejected(self):
        assert _is_prose("Eligibility.") is False
