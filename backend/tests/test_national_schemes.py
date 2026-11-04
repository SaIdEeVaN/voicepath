"""The national schemes say only what their official releases say.

Added 2026-11-04 from PIB and ministry releases. The explanation layer may
ground itself only in a scheme's description, so a description that drifted
from the government's wording -- a figure rounded, a condition dropped -- would
put words in the government's mouth. Each one is sentences copied exactly from
an official release, and the release itself is in data/scheme_docs, so this
test can check every sentence without the network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.data.catalogue import ANY_TRADE, SCHEMES, TAXONOMY, VISHWAKARMA_TRADES
from app.data.scheme_names import SCHEME_NAMES

DOCS = Path(__file__).resolve().parents[1] / "data" / "scheme_docs"
NATIONAL = [e for e in SCHEMES if e["source_reference"].startswith("GOI/")]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.fixture(scope="module")
def official_text() -> str:
    return _norm(" ".join(p.read_text(encoding="utf-8") for p in DOCS.glob("*.md")))


@pytest.fixture(scope="module")
def recorded_urls() -> set[str]:
    urls = json.loads((DOCS / "sources.json").read_text(encoding="utf-8"))
    named = {s for entry in SCHEME_NAMES.values() for s in entry["sources"]}
    return {v for k, v in urls.items() if k != "_README" and v} | named


def test_there_are_national_schemes():
    assert len(NATIONAL) >= 10


@pytest.mark.parametrize("entry", NATIONAL, ids=lambda e: e["source_reference"])
class TestEachScheme:
    def test_every_sentence_is_in_an_official_release(self, entry, official_text):
        sentences = re.split(r"(?<=[.;])\s+(?=[A-Z])", entry["description"])
        missing = [s for s in sentences if _norm(s) not in official_text]
        assert not missing, missing

    def test_its_link_comes_from_an_official_release(self, entry, official_text, recorded_urls):
        url = entry["official_url"]
        assert url.startswith("https://")
        # Either a release on file, or an address a release itself gives.
        assert url in recorded_urls or url in official_text, url

    def test_it_is_open_across_india(self, entry):
        assert entry["location"] == "All India"
        assert entry["district"] == "All India"

    def test_it_matches_on_any_one_trade(self, entry):
        assert entry.get("skill_match") == "any"
        known = {t["code"] for t in TAXONOMY}
        assert {code for code, _, _ in entry["skills"]} <= known

    def test_no_pay_is_invented(self, entry):
        # A stipend per day or a loan is not a monthly wage; none is recorded.
        assert entry["salary_min"] is None and entry["salary_max"] is None


def test_pm_vishwakarma_names_its_eighteen_trades():
    entry = next(e for e in NATIONAL if e["title"] == "PM Vishwakarma")
    codes = {code for code, weight, _ in entry["skills"] if weight == 1.0}
    assert codes == set(VISHWAKARMA_TRADES)
    assert len(VISHWAKARMA_TRADES) == 19  # 18 trades; sculptor and stone breaker share one


def test_open_to_any_trade_is_weighted_below_a_named_trade():
    assert 0 < ANY_TRADE < 1.0


def test_every_new_document_has_its_official_address():
    urls = json.loads((DOCS / "sources.json").read_text(encoding="utf-8"))
    for path in DOCS.glob("PIB_*.md"):
        assert urls.get(path.name, "").startswith("https://"), path.name
        assert urls[path.name] in path.read_text(encoding="utf-8"), path.name
