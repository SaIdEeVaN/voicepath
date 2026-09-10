"""``db/003_seed.sql`` and ``app/data/catalogue.py`` describe the same
catalogue. Nothing enforces that at runtime -- one is SQL and one is Python --
so this test does, and fails loudly when the two drift apart."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.data.catalogue import OPPORTUNITIES, TAXONOMY

SEED = Path(__file__).resolve().parents[2] / "db" / "003_seed.sql"


@pytest.fixture(scope="module")
def seed_sql() -> str:
    if not SEED.exists():
        pytest.skip(f"{SEED} not found")
    return SEED.read_text(encoding="utf-8")


def test_every_python_skill_code_is_in_the_sql(seed_sql: str):
    sql_codes = set(re.findall(r"'(SK\d{3,})'", seed_sql))
    python_codes = {e["code"] for e in TAXONOMY}
    missing = python_codes - sql_codes
    assert not missing, f"In catalogue.py but not in 003_seed.sql: {sorted(missing)}"


def test_every_sql_skill_code_is_in_python(seed_sql: str):
    sql_codes = set(re.findall(r"\('(SK\d{3,})', '", seed_sql))
    python_codes = {e["code"] for e in TAXONOMY}
    missing = sql_codes - python_codes
    assert not missing, f"In 003_seed.sql but not in catalogue.py: {sorted(missing)}"


def test_opportunity_source_references_match(seed_sql: str):
    sql_refs = set(re.findall(r"'((?:OGD|PMAJAY)/[A-Z0-9/]+)'", seed_sql))
    python_refs = {o["source_reference"] for o in OPPORTUNITIES}
    assert python_refs <= sql_refs, (
        f"In catalogue.py but not in 003_seed.sql: {sorted(python_refs - sql_refs)}"
    )


def test_skill_codes_are_unique():
    codes = [e["code"] for e in TAXONOMY]
    assert len(codes) == len(set(codes))


def test_source_references_are_unique():
    refs = [o["source_reference"] for o in OPPORTUNITIES]
    assert len(refs) == len(set(refs))


def test_every_opportunity_requires_a_real_skill():
    known = {e["code"] for e in TAXONOMY}
    for opportunity in OPPORTUNITIES:
        assert opportunity["skills"], f"{opportunity['title']} requires nothing"
        for code, _weight, _essential in opportunity["skills"]:
            assert code in known, f"{opportunity['title']} references unknown {code}"


def test_the_mockup_worked_example_survives():
    """The design's worked example pins these four codes. Renumbering them
    would silently break the demo the whole interface was drawn around."""
    codes = {e["code"] for e in TAXONOMY}
    for code in ("SK001", "SK014", "SK022", "SK108"):
        assert code in codes


def test_weights_are_in_range():
    for opportunity in OPPORTUNITIES:
        for code, weight, _essential in opportunity["skills"]:
            assert 0 < weight <= 1, f"{opportunity['title']}/{code} weight {weight}"


def test_salary_ranges_are_ordered():
    for opportunity in OPPORTUNITIES:
        low, high = opportunity["salary_min"], opportunity["salary_max"]
        if low is not None and high is not None:
            assert low <= high, opportunity["title"]


def test_types_match_the_database_constraint():
    allowed = {
        "Full-time", "Part-time", "Training", "Apprenticeship",
        "Self-employment support",
    }
    for opportunity in OPPORTUNITIES:
        assert opportunity["type"] in allowed, opportunity["title"]


def test_aliases_cover_all_three_languages():
    """Normalization reaches a node through its aliases. A node with only
    English aliases is unreachable for a Tamil or Hindi speaker."""
    def has_tamil(text: str) -> bool:
        return any("஀" <= c <= "௿" for c in text)

    def has_devanagari(text: str) -> bool:
        return any("ऀ" <= c <= "ॿ" for c in text)

    for entry in TAXONOMY:
        blob = " ".join(entry["aliases"])
        assert has_tamil(blob), f"{entry['code']} has no Tamil alias"
        assert has_devanagari(blob), f"{entry['code']} has no Hindi alias"
