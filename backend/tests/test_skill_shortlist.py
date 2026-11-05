"""Skills described in a person's own words reach the taxonomy.

Of the first 66 skills people described in production, 12 matched nothing --
five of them an engine mechanic's, six from the medicine trade -- and while
the embedder was out of credits (2026-11) every skill not said by its exact
name landed nowhere. These tests hold the fix:

* the phrases people actually used now reach a skill, by alias or shortlist;
* a shortlist is only ever offered -- to the model, constrained to it, or to
  the person -- and never accepted on shared words alone;
* words that say nothing about a trade ("work", "problem", "drug dealer")
  shortlist nothing.
"""

from __future__ import annotations

import pytest

from app.data.catalogue import DISPLAY_NAMES, SCHEMES, TAXONOMY
from app.services import embeddings, llm, normalization, taxonomy


@pytest.fixture
def embedder_down(monkeypatch):
    def refuse(texts):
        raise embeddings.EmbeddingUnavailable("Embedding API returned 402: credits spent")

    monkeypatch.setattr(embeddings, "embed_queries", refuse)


@pytest.fixture
def no_model(monkeypatch):
    monkeypatch.setattr(llm, "is_available", lambda: False)


def _codes(scored) -> list[str]:
    return [c.skill.code for c in scored]


# (raw name, evidence) exactly as stored in production, and the skill each is.
PRODUCTION_PHRASES = [
    ("identifying engine problems by sound", "when the sound of an engine hears", "SK014"),
    ("engine work", "engine engine-aa velai paarthen", "SK016"),
    ("diagnosing problems", "I diagnose it", "SK014"),
    ("இன்ஜினோட சத்தம் கேட்டா எனக்கு என்ன பிரச்சனை அதெல்லாம் எனக்கு தெரியும் நல்லா",
     "இன்ஜினோட சத்தம் கேட்டா எனக்கு என்ன பிரச்சனை அதெல்லாம் எனக்கு தெரியும் நல்லா", "SK014"),
    ("Pharmacist", "working as a Pharmacist", "SK118"),
    ("pharmaceutical business work",
     "2 வருடம் pharmaceutical businessல் எனக்கு வேலை கிடைசுது", "SK096"),
    ("pharmaceutical drug dealer", "பார்மசூட்டிக்கல் ட்ரக் டீலரா", "SK096"),
    ("pharmaceutical drug dealing", "working as a pharmaceutical drug dealer", "SK096"),
]


class TestTheNewSkills:
    def test_they_are_in_the_taxonomy_with_names_in_all_three_languages(self):
        codes = {e["code"] for e in TAXONOMY}
        for code in ("SK016", "SK096", "SK118"):
            assert code in codes
            assert DISPLAY_NAMES[code]["ta"] and DISPLAY_NAMES[code]["hi"]

    def test_schemes_open_to_any_trade_include_them(self):
        pmkvy = next(s for s in SCHEMES if s["source_reference"] == "GOI/PMKVY4/2025-02-07")
        linked = {code: weight for code, weight, _ in pmkvy["skills"]}
        for code in ("SK016", "SK096", "SK118"):
            assert linked[code] == pytest.approx(0.4)

    def test_bare_drug_dealer_is_not_an_alias(self):
        aliases = {a.casefold() for e in TAXONOMY for a in e["aliases"]}
        assert "drug dealer" not in aliases
        assert "pharmaceutical drug dealer" in aliases


class TestWhatPeopleActuallySaid:
    @pytest.mark.parametrize("raw, evidence, code", PRODUCTION_PHRASES)
    async def test_reaches_the_right_skill_with_the_embedder_down(
        self, raw, evidence, code, embedder_down, no_model
    ):
        (skill,) = await normalization.normalize_many([(raw, evidence)])
        reached = [skill.code] if skill.code else _codes(skill.candidates)
        assert code in reached, (raw, skill.code, _codes(skill.candidates))


class TestTheShortlistOnlyOffers:
    async def test_shared_words_alone_never_accept_a_skill(self, embedder_down, no_model):
        (skill,) = await normalization.normalize_many([("diagnosing problems", "I diagnose it")])
        assert skill.skill_id is None
        assert skill.needs_disambiguation is True
        assert "SK014" in _codes(skill.candidates)

    async def test_the_model_may_choose_from_the_shortlist(self, embedder_down, monkeypatch):
        async def choose(system, prompt, **kwargs):
            assert "SK014" in prompt
            return {"skill_code": "SK014", "confidence": 0.9}

        monkeypatch.setattr(llm, "is_available", lambda: True)
        monkeypatch.setattr(llm, "complete_json", choose)
        (skill,) = await normalization.normalize_many([("diagnosing problems", "I diagnose it")])
        assert skill.code == "SK014"
        assert skill.confidence == pytest.approx(0.9)

    async def test_the_model_cannot_choose_outside_it(self, embedder_down, monkeypatch):
        async def invent(system, prompt, **kwargs):
            return {"skill_code": "SK022", "confidence": 0.95}

        monkeypatch.setattr(llm, "is_available", lambda: True)
        monkeypatch.setattr(llm, "complete_json", invent)
        (skill,) = await normalization.normalize_many([("diagnosing problems", "I diagnose it")])
        assert skill.skill_id is None
        assert skill.needs_disambiguation is True

    async def test_an_exact_alias_still_wins_outright(self, embedder_down, no_model):
        (skill,) = await normalization.normalize_many(
            [("identifying engine problems by sound", "when the sound of an engine hears")]
        )
        assert skill.code == "SK014"
        assert skill.confidence == 1.0


class TestWordsThatSayNothing:
    @pytest.mark.parametrize("phrase", [
        "knowing the problem",
        "repair work",
        "drug dealer",
        "desire doue or ousmane dembele ?",
        "I worked for many years",
        "எனக்கு நல்லா தெரியும்",
        "मैं काम करता हूँ",
        "",
    ])
    async def test_shortlist_nothing(self, phrase):
        assert await taxonomy.keyword_candidates(phrase) == []


class TestTheShortlist:
    async def test_tamil_case_endings_do_not_hide_the_word(self):
        # "இன்ஜினோட" is "இன்ஜின்" (engine) with a genitive ending.
        assert "SK014" in _codes(await taxonomy.keyword_candidates("இன்ஜினோட சத்தம்"))

    async def test_english_word_forms_meet(self):
        for phrase in ("diagnosing", "diagnose", "pharmacy", "pharmaceutical sales"):
            assert await taxonomy.keyword_candidates(phrase), phrase

    async def test_the_evidence_helps_but_counts_less_than_the_name(self):
        alone = await taxonomy.keyword_candidates("sound")
        with_evidence = await taxonomy.keyword_candidates("sound", "the engine sound")
        assert "SK014" in _codes(with_evidence)
        assert len(with_evidence) >= len(alone)

    async def test_scores_are_shares_not_similarities(self):
        for candidate in await taxonomy.keyword_candidates("selling medicines to hospitals"):
            assert 0.0 < candidate.similarity <= 1.0

    async def test_at_most_the_limit(self):
        assert len(await taxonomy.keyword_candidates("cooking in a hotel", limit=2)) <= 2
