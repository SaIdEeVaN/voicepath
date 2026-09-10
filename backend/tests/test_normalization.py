"""Skill normalization (PRD section 4.3).

The property that matters: a skill is either normalized on real evidence, or
left unnormalized and surfaced to the user. It is never quietly mapped to
something close enough.
"""

from __future__ import annotations

import pytest

from app.services import taxonomy
from app.services.normalization import normalize_many


class TestLexicalMatch:
    """Saying a skill's own name or alias should settle it, in any of the
    three languages, without depending on an embedding model agreeing."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "phrase,expected",
        [
            ("welding", "SK022"),
            ("bike repair", "SK001"),
            ("bike mechanic", "SK001"),
            ("electrician", "SK031"),
            ("tailor", "SK051"),
            ("बाइक रिपेयर", "SK001"),
            ("वेल्डिंग", "SK022"),
            ("दर्जी", "SK051"),
            ("பைக் ரிப்பேர்", "SK001"),
            ("வெல்டிங்", "SK022"),
            ("தையல்", "SK051"),
        ],
    )
    async def test_alias_in_any_language_reaches_the_same_node(self, phrase, expected):
        found = await taxonomy.lexical_match(phrase)
        assert found is not None, f"{phrase!r} matched nothing"
        assert found.code == expected

    @pytest.mark.asyncio
    async def test_case_and_spacing_do_not_matter(self):
        found = await taxonomy.lexical_match("  BIKE   REPAIR  ")
        assert found is not None and found.code == "SK001"

    @pytest.mark.asyncio
    async def test_a_longer_phrase_is_not_matched_by_substring(self):
        """"welding certificate" must not become Welding.

        Substring matching would silently upgrade a claim -- exactly what
        section 4.2 forbids. It falls through to embedding search instead,
        where it can be flagged rather than assumed.
        """
        assert await taxonomy.lexical_match("welding certificate") is None

    @pytest.mark.asyncio
    async def test_unrelated_phrase_matches_nothing(self):
        assert await taxonomy.lexical_match("astrophysics research") is None

    @pytest.mark.asyncio
    async def test_very_short_input_is_ignored(self):
        assert await taxonomy.lexical_match("ab") is None


class TestNormalizeMany:
    @pytest.mark.asyncio
    async def test_named_skills_normalize_with_full_confidence(self):
        result = await normalize_many(
            [("welding", "I know a little welding"),
             ("bike repair", "I have been repairing bikes")]
        )
        assert [s.code for s in result] == ["SK022", "SK001"]
        assert all(s.confidence == 1.0 for s in result)
        assert not any(s.needs_disambiguation for s in result)

    @pytest.mark.asyncio
    async def test_evidence_survives_normalization(self):
        """Section 7: a normalized skill must stay traceable to the words said."""
        evidence = "I know a little welding"
        result = await normalize_many([("welding", evidence)])
        assert result[0].evidence_phrase == evidence

    @pytest.mark.asyncio
    async def test_unrecognised_skill_is_left_unnormalized(self):
        result = await normalize_many([("quantum computing", "I do quantum computing")])
        assert result[0].skill_id is None
        assert result[0].code is None

    @pytest.mark.asyncio
    async def test_unnormalized_skill_keeps_its_evidence(self):
        """An unmatched skill stays in the profile rather than vanishing --
        it simply does not contribute to the skill-similarity term."""
        result = await normalize_many([("quantum computing", "I do quantum computing")])
        assert result[0].raw_name == "quantum computing"
        assert result[0].evidence_phrase == "I do quantum computing"

    @pytest.mark.asyncio
    async def test_empty_input_is_fine(self):
        assert await normalize_many([]) == []

    @pytest.mark.asyncio
    async def test_every_result_carries_an_embedding_for_matching(self):
        result = await normalize_many([("welding", "I weld")])
        assert result[0].embedding


class TestUserChoice:
    @pytest.mark.asyncio
    async def test_a_users_pick_overrides_everything(self):
        from app.services.normalization import apply_user_choice

        result = await normalize_many([("something vague", "I do that work")])
        entry = result[0]

        arc = await taxonomy.get_by_code("SK023")
        assert arc is not None

        updated = await apply_user_choice(entry, arc.id)
        assert updated.skill_id == arc.id
        assert updated.code == "SK023"
        assert updated.user_confirmed is True
        assert updated.needs_disambiguation is False
        assert updated.confidence == 1.0

    @pytest.mark.asyncio
    async def test_an_unknown_choice_changes_nothing(self):
        from app.services.normalization import apply_user_choice

        result = await normalize_many([("welding", "I weld")])
        before = result[0].code
        updated = await apply_user_choice(result[0], 999_999)
        assert updated.code == before
