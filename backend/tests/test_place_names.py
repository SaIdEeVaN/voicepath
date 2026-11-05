"""Town names in the reader's script.

Matching already understood "சேலத்துல" and "सेलम में" as Salem; only the
display stayed English, so a Tamil sentence read "இது Salemலேயே இருக்கிறது".
The names come from the gazetteer the map labels towns with
(``app/data/places.py``) -- never a spelling made up on the spot -- and a place
the gazetteer does not know keeps the spelling the catalogue gave it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data.places import PLACES
from app.main import app
from app.services import explanation, llm
from app.services.explanation import explain_offline
from app.services.matching import ProfileInput, score_one
from app.services.normalization import NormalizedSkill
from app.services.places import localized_place, place_names
from app.services.schemes import RequiredSkill, Scheme


def scheme(**overrides) -> Scheme:
    defaults = dict(
        id=1, title="Two-Wheeler Service Technician", organization="Ratnam Auto Works",
        location="Salem", district="Salem", type="Full-time", minimum_experience=2.0,
        certifications_required=[], salary_min=14000, salary_max=18000,
        nsqf_level="4", source_reference="OGD/TEST/1", description="Bike repair.",
        required_skills=[RequiredSkill(1, "SK001", "Two-Wheeler Repair", 1.0, True)],
    )
    defaults.update(overrides)
    return Scheme(**defaults)


def profile(location: str = "Salem") -> ProfileInput:
    return ProfileInput(
        experience_years=6.0, location=location, district=location, certifications=[],
        skills=[NormalizedSkill(raw_name="bike repair", evidence_phrase="I repair bikes",
                                skill_id=1, code="SK001", name="Two-Wheeler Repair")],
    )


class TestTheNames:
    def test_a_known_town_has_all_three_scripts(self):
        assert place_names("Salem") == PLACES["salem"]["names"]
        assert localized_place("Erode", "ta") == "ஈரோடு"
        assert localized_place("Attur", "hi") == "आत्तूर"

    def test_a_name_in_any_script_finds_the_town(self):
        assert localized_place("சேலம்", "en") == "Salem"

    @pytest.mark.parametrize("place", ["All India", "Somewhere Unknown", ""])
    def test_an_unknown_place_keeps_its_spelling(self, place):
        assert place_names(place) == {}
        assert localized_place(place, "ta") == place

    def test_every_gazetteer_town_has_tamil_and_hindi(self):
        for key, entry in PLACES.items():
            assert entry["names"].get("ta") and entry["names"].get("hi"), key


class TestTheApi:
    def test_listings_carry_the_town_in_each_script(self):
        with TestClient(app) as client:
            rows = client.get("/api/schemes").json()
        salem = next(r for r in rows if r["location"] == "Salem")
        assert salem["location_names"]["ta"] == "சேலம்"
        assert salem["location_names"]["hi"] == "सेलम"
        national = next(r for r in rows if r["location"] == "All India")
        assert national["location_names"] == {}


class TestTheExplanations:
    def test_tamil_says_the_town_in_tamil(self):
        match = score_one(profile("Salem"), scheme())
        text = " ".join(explain_offline(match, language="ta").bullets)
        assert "சேலம்" in text
        assert "Salem" not in text

    def test_hindi_says_the_town_in_hindi(self):
        match = score_one(profile("Salem"), scheme(location="Erode", district="Erode"))
        text = " ".join(explain_offline(match, language="hi").bullets)
        assert "इरोड" in text
        assert "Erode" not in text

    def test_english_is_unchanged(self):
        match = score_one(profile("Salem"), scheme())
        assert "It is in Salem, where you are." in explain_offline(match, language="en").bullets

    async def test_the_model_is_given_the_town_in_the_language_it_writes(self, monkeypatch):
        seen: list[str] = []

        async def capture(system, prompt, **kwargs):
            seen.append(prompt)
            return {"summary": "x", "bullets": ["y"]}

        monkeypatch.setattr(llm, "is_available", lambda: True)
        monkeypatch.setattr(llm, "complete_json", capture)
        await explanation.explain(score_one(profile("Salem"), scheme()), language="ta")
        assert seen and "சேலம்" in seen[0]
