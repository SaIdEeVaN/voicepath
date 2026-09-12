"""A citation someone can actually follow (spec sections 8 and 18).

An answer drawn from a guideline cited `NLMGuidelinesJan2025.pdf`. That is a
filename. The point of a citation in this product is that a person can go and
read the rule themselves, or take it to an office, and a name they cannot look
up does not do that.

`scheme_documents.source_url` had existed since 005, but only pages fetched by
web search ever carried one: the ingest script never passed a URL for a local
PDF, and `match_document_chunks` did not return the column, so nothing
downstream could have used it. `db/009` returns it and the ingest script reads
it from `data/scheme_docs/sources.json`.

**The URLs are typed in by hand and never derived.** `services/websearch.py`
consults no model at all precisely so that it cannot invent an address, and a
guessed government URL looks exactly as official as a real one. A document with
no recorded URL cites its name, which is what it did before.

This file also pins a second thing, found while doing the first:
`scheme_documents.status` was written and never read. A page from outside the
.gov.in family is stored `pending_verification` so an admin must approve it
before the system asserts anything from it -- and neither retrieval path
filtered on it, so a pending page was citable the moment it was stored and
rejecting one did not withdraw it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.scripts.ingest_documents import read_source_urls
from app.services import scheme_qa
from app.services.retrieval import Retrieved


def _passage(**overrides) -> Retrieved:
    defaults = dict(
        chunk_id=1,
        document_title="National Livestock Mission",
        source="NLMGuidelinesJan2025.pdf",
        heading=None,
        content="The Mission supports entrepreneurs in animal husbandry.",
        similarity=0.81,
    )
    defaults.update(overrides)
    return Retrieved(**defaults)


class TestTheCitationCarriesAUrl:
    def test_a_recorded_url_is_shown(self):
        cite = scheme_qa._cite(_passage(source_url="https://dahd.gov.in/nlm"))

        assert cite["source_url"] == "https://dahd.gov.in/nlm"
        assert cite["source"] == "NLMGuidelinesJan2025.pdf"

    def test_a_document_with_no_url_still_cites_its_name(self):
        """The common case, and it must stay comfortable rather than broken."""
        cite = scheme_qa._cite(_passage())

        assert cite["source_url"] is None
        assert cite["source"] == "NLMGuidelinesJan2025.pdf"

    def test_a_web_page_is_its_own_url(self):
        """A page fetched by search arrives with the URL as its source."""
        cite = scheme_qa._cite(
            _passage(source="https://pmvishwakarma.gov.in/", source_url=None)
        )

        assert cite["source_url"] == "https://pmvishwakarma.gov.in/"

    def test_a_recorded_url_wins_over_the_filename(self):
        cite = scheme_qa._cite(
            _passage(source="https://old.example/x", source_url="https://dahd.gov.in/nlm")
        )

        assert cite["source_url"] == "https://dahd.gov.in/nlm"


class TestUrlsAreReadNeverBuilt:
    def test_a_relative_path_is_refused(self, tmp_path: Path):
        """Half an address is worse than none: it cannot be followed, and it
        cannot be distinguished from a real one by the person reading it."""
        (tmp_path / "sources.json").write_text(
            json.dumps({"a.pdf": "/schemes/nlm", "b.pdf": "dahd.gov.in/nlm"}),
            encoding="utf-8",
        )

        assert read_source_urls(tmp_path) == {}

    def test_an_absolute_url_is_kept(self, tmp_path: Path):
        (tmp_path / "sources.json").write_text(
            json.dumps({"a.pdf": "https://dahd.gov.in/nlm"}), encoding="utf-8"
        )

        assert read_source_urls(tmp_path) == {"a.pdf": "https://dahd.gov.in/nlm"}

    def test_empty_entries_and_notes_are_skipped(self, tmp_path: Path):
        """The file ships with every filename listed and no URLs, so empty has
        to be the normal, quiet case."""
        (tmp_path / "sources.json").write_text(
            json.dumps({"_README": ["a note"], "a.pdf": "", "b.pdf": "   "}),
            encoding="utf-8",
        )

        assert read_source_urls(tmp_path) == {}

    def test_a_missing_file_is_not_an_error(self, tmp_path: Path):
        assert read_source_urls(tmp_path) == {}

    def test_broken_json_does_not_stop_an_ingest(self, tmp_path: Path):
        """Losing the URLs is a worse outcome than losing the documents."""
        (tmp_path / "sources.json").write_text("{not json", encoding="utf-8")

        assert read_source_urls(tmp_path) == {}


class TestTheShippedFileIsUsable:
    ROOT = Path(__file__).resolve().parents[1] / "data" / "scheme_docs"

    def test_it_is_valid_json(self):
        raw = json.loads((self.ROOT / "sources.json").read_text(encoding="utf-8"))
        assert isinstance(raw, dict)

    def test_every_pdf_has_an_entry(self):
        """A file with no line in here is one nobody was ever prompted to
        find a URL for."""
        raw = json.loads((self.ROOT / "sources.json").read_text(encoding="utf-8"))
        listed = {k for k in raw if not k.startswith("_")}
        on_disk = {p.name for p in self.ROOT.iterdir() if p.suffix.lower() == ".pdf"}

        assert on_disk - listed == set(), "PDFs with no entry in sources.json"

    def test_no_entry_is_a_guess(self):
        """Every value is either empty or an absolute http(s) URL. Nothing
        half-written, which is the shape an invented address takes."""
        raw = json.loads((self.ROOT / "sources.json").read_text(encoding="utf-8"))
        for name, url in raw.items():
            if name.startswith("_"):
                continue
            assert isinstance(url, str)
            assert url == "" or url.startswith(("http://", "https://")), name
