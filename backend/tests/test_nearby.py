"""The map: where things are, and what it refuses to do.

Runs offline. The Overpass fixture is a real response for central Salem,
trimmed -- OpenStreetMap data, (c) OpenStreetMap contributors, ODbL -- so the
categorisation is tested against how offices are actually tagged rather than
how we imagine they might be.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.data.places import PLACES
from app.main import app
from app.services import matching, places, schemes

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_salem.json"
SALEM = PLACES["salem"]


@pytest.fixture(autouse=True)
def _fresh_cache():
    places.reset_cache()
    yield
    places.reset_cache()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def overpass_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "places_provider", "overpass")


def _elements() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["elements"]


def _parse(**overrides):
    kwargs = dict(
        latitude=SALEM["latitude"],
        longitude=SALEM["longitude"],
        radius_km=10,
        categories=places.ALL_CATEGORIES,
    )
    kwargs.update(overrides)
    return places.parse_elements(_elements(), **kwargs)


class TestGazetteer:
    def test_every_place_the_scorer_knows_is_on_the_map(self):
        """Adding a town to matching without a coordinate fails here."""
        missing = set(matching.PLACE_ALIASES) - set(PLACES)
        assert not missing, f"no coordinates for {sorted(missing)}"

    @pytest.mark.parametrize("key", sorted(PLACES))
    def test_coordinates_are_in_tamil_nadu(self, key):
        entry = PLACES[key]
        assert 8.0 <= entry["latitude"] <= 13.6
        assert 76.2 <= entry["longitude"] <= 80.4

    @pytest.mark.parametrize("key", sorted(PLACES))
    def test_every_place_is_named_in_all_three_scripts(self, key):
        assert set(PLACES[key]["names"]) == {"en", "ta", "hi"}

    def test_every_catalogue_town_is_placed(self):
        from app.data.catalogue import SCHEMES

        for entry in SCHEMES:
            assert places.place_key(entry["location"]) or places.place_key(
                entry["district"]
            ), entry["location"]


class TestDistance:
    def test_same_point_is_zero(self):
        assert places.haversine_km(11.66, 78.14, 11.66, 78.14) == 0

    def test_salem_to_erode_is_about_sixty_km_as_the_crow_flies(self):
        erode = PLACES["erode"]
        d = places.haversine_km(
            SALEM["latitude"], SALEM["longitude"], erode["latitude"], erode["longitude"]
        )
        assert 50 < d < 70

    def test_symmetric(self):
        a = places.haversine_km(11.0, 77.0, 12.0, 78.0)
        b = places.haversine_km(12.0, 78.0, 11.0, 77.0)
        assert a == pytest.approx(b)


class TestCentre:
    @pytest.mark.parametrize("said", ["Salem", "சேலத்துல", "सेलम", "Salem, Tamil Nadu"])
    def test_a_spoken_place_in_any_script_centres_on_that_town(self, said):
        centre = places.resolve_centre(
            place=said, latitude=None, longitude=None, catalogue=[]
        )
        assert centre.source == "place"
        assert centre.key == "salem"
        assert centre.names["ta"] == "சேலம்"

    def test_device_location_wins_over_a_spoken_place(self):
        centre = places.resolve_centre(
            place="Erode", latitude=11.66431, longitude=78.14601, catalogue=[]
        )
        assert centre.source == "gps"
        assert centre.key is None

    def test_device_location_is_coarsened_before_anything_uses_it(self):
        centre = places.resolve_centre(
            place=None, latitude=11.664317, longitude=78.146089, catalogue=[]
        )
        assert (centre.latitude, centre.longitude) == (11.66, 78.15)

    async def test_an_unknown_place_says_so_and_shows_where_the_openings_are(self):
        catalogue = await schemes.list_active()
        centre = places.resolve_centre(
            place="Kolkata", latitude=None, longitude=None, catalogue=catalogue
        )
        assert centre.source == "default"
        # Most of the seeded catalogue is in Salem.
        assert centre.key == "salem"

    def test_no_place_at_all_is_the_same_honest_default(self):
        centre = places.resolve_centre(
            place=None, latitude=None, longitude=None, catalogue=[]
        )
        assert centre.source == "default"
        assert centre.key in PLACES


class TestOpenings:
    async def test_every_active_opening_appears_exactly_once(self):
        catalogue = await schemes.list_active()
        centre = places.resolve_centre(
            place="Salem", latitude=None, longitude=None, catalogue=catalogue
        )
        groups, unplaced = places.scheme_places(catalogue, centre)
        placed = [s.id for g in groups for s in g.schemes]
        assert sorted(placed + [s.id for s in unplaced]) == sorted(s.id for s in catalogue)
        assert len(placed) == len(set(placed))

    async def test_openings_are_grouped_by_town_nearest_first(self):
        catalogue = await schemes.list_active()
        centre = places.resolve_centre(
            place="Erode", latitude=None, longitude=None, catalogue=catalogue
        )
        groups, _ = places.scheme_places(catalogue, centre)
        assert groups[0].key == "erode"
        assert groups[0].distance_km == 0
        distances = [g.distance_km for g in groups]
        assert distances == sorted(distances)

    def test_a_town_the_map_does_not_know_is_reported_not_dropped(self):
        from app.services.schemes import Scheme

        nowhere = Scheme(
            id=99, title="T", organization="O", location="Atlantis", district="Atlantis",
            type="Full-time", minimum_experience=0, certifications_required=[],
            salary_min=None, salary_max=None, nsqf_level=None, source_reference=None,
            description=None,
        )
        centre = places.resolve_centre(place="Salem", latitude=None, longitude=None, catalogue=[])
        groups, unplaced = places.scheme_places([nowhere], centre)
        assert groups == []
        assert [s.id for s in unplaced] == [99]


class TestCategorise:
    @pytest.mark.parametrize(
        "tags,expected",
        [
            ({"amenity": "college", "name": "Govt ITI"}, "training"),
            ({"amenity": "college", "name": "St. Theresa's Industrial Training Institute"}, "training"),
            ({"amenity": "school", "name": "Govt. I.T.I. Attur"}, "training"),
            ({"amenity": "college", "name": "Thiagarajar Polytechnic College"}, "training"),
            ({"amenity": "training", "name": "PMKVY Centre"}, "training"),
            ({"amenity": "college", "name": "அரசு தொழிற்பயிற்சி நிலையம்"}, "training"),
            ({"amenity": "college", "name": "LAW College"}, None),
            ({"amenity": "college", "name": "Salem Mohan Kumaramangalam Medical College"}, None),
            # "iti" inside a word is not an ITI.
            ({"amenity": "school", "name": "Kitimat Public School"}, None),
            ({"office": "employment_agency", "name": "District Employment Office"}, "employment"),
            ({"office": "government", "name": "Collectorate"}, "government"),
            ({"amenity": "townhall", "name": "Salem City Corporation"}, "government"),
            ({"office": "government", "government": "police", "name": "DSP Office"}, None),
            ({"office": "government", "government": "tax", "name": "Excise"}, None),
            # Untagged, as most of them are in the real Salem data.
            ({"office": "government", "name": "Income tax Office"}, None),
            ({"office": "government", "name": "Salem GST Division II"}, None),
            ({"office": "government", "name": "Central Excise Office"}, None),
            # Named only in English -- real Salem data, and the filter used to
            # read `name` alone and let these through.
            ({"office": "government", "name:en": "Salem GST Division II"}, None),
            ({"amenity": "college", "name:ta": "அரசு தொழிற்பயிற்சி நிலையம்"}, "training"),
            # A licence is what the driving openings ask for.
            ({"office": "government", "name": "RTO Salem East"}, "government"),
            ({"office": "government", "name": "Thathampatti Village Administration Office"}, "government"),
            ({"amenity": "bank", "name": "Indian Bank"}, "bank"),
            ({"amenity": "cafe", "name": "Tea shop"}, None),
        ],
    )
    def test_kinds_of_help(self, tags, expected):
        assert places.categorize(tags) == expected


class TestParse:
    def test_real_salem_data_finds_the_itis_and_skips_the_noise(self):
        found = _parse()
        names = {p.name for p in found}
        assert "Govt ITI" in names
        assert "St. Theresa's Industrial Training Institute" in names
        assert "Indian Institute of Handloom Technology Salem" in names
        assert "LAW College" not in names
        assert "GOVERNMENT ARTS COLLEGE" not in names
        assert "Deputy Superintendent of Police" not in names
        assert "Central Excise Commissinorate" not in names

    def test_unnamed_features_are_dropped(self):
        assert all(p.name for p in _parse())

    def test_one_office_mapped_twice_is_listed_once(self):
        names = [p.name for p in _parse()]
        assert names.count("Register Office - Salem (E)") == 1

    def test_buildings_use_their_centre(self):
        corporation = next(p for p in _parse() if p.name == "Salem City Corporation")
        assert corporation.id.startswith("way/")
        assert corporation.osm_url == f"https://www.openstreetmap.org/{corporation.id}"

    def test_nearest_first(self):
        distances = [p.distance_km for p in _parse()]
        assert distances == sorted(distances)

    def test_only_the_categories_asked_for(self):
        found = _parse(categories=("bank",))
        assert found and {p.category for p in found} == {"bank"}

    def test_nothing_beyond_the_radius(self):
        assert all(p.distance_km <= 1 * 1.05 for p in _parse(radius_km=1))

    def test_names_in_other_scripts_pass_through(self):
        element = {
            "type": "node", "id": 1, "lat": 11.66, "lon": 78.14,
            "tags": {"amenity": "bank", "name": "Indian Bank", "name:ta": "இந்தியன் வங்கி"},
        }
        [found] = places.parse_elements(
            [element], latitude=11.66, longitude=78.14, radius_km=5,
            categories=places.ALL_CATEGORIES,
        )
        assert found.names == {"ta": "இந்தியன் வங்கி"}

    def test_the_query_is_built_from_numbers_and_fixed_tables_only(self):
        query = places.build_query(11.66, 78.15, 10, ["training", "bank"])
        assert "(around:10000,11.6600,78.1500)" in query
        assert '"amenity"="bank"' in query
        assert "employment_agency" not in query
        # Overpass treats a backslash as its own escape.
        assert "\\" not in query


class TestSupportLookup:
    async def test_offline_does_not_touch_the_network(self, monkeypatch):
        async def boom(query):  # pragma: no cover - must not run
            raise AssertionError("network used while offline")

        monkeypatch.setattr(places, "fetch_elements", boom)
        found, status = await places.support_places(
            latitude=11.66, longitude=78.15, radius_km=10, categories=places.ALL_CATEGORIES
        )
        assert (found, status) == ([], "offline")

    async def test_a_repeated_search_is_answered_from_memory(self, monkeypatch, overpass_on):
        calls = []

        async def fake(query):
            calls.append(query)
            return _elements()

        monkeypatch.setattr(places, "fetch_elements", fake)
        for _ in range(3):
            found, status = await places.support_places(
                latitude=SALEM["latitude"], longitude=SALEM["longitude"],
                radius_km=10, categories=places.ALL_CATEGORIES,
            )
            assert status == "ok" and found
        assert len(calls) == 1

    async def test_the_query_never_carries_a_precise_location(self, monkeypatch, overpass_on):
        sent = []

        async def fake(query):
            sent.append(query)
            return []

        monkeypatch.setattr(places, "fetch_elements", fake)
        await places.support_places(
            latitude=11.664317, longitude=78.146089, radius_km=10, categories=["bank"]
        )
        assert "11.6643" not in sent[0] and "78.1460" not in sent[0]
        assert "11.6600,78.1500" in sent[0]

    async def test_failure_is_reported_not_disguised_as_none_nearby(
        self, monkeypatch, overpass_on
    ):
        calls = []

        async def down(query):
            calls.append(query)
            raise places.PlacesUnavailable("busy")

        monkeypatch.setattr(places, "fetch_elements", down)
        found, status = await places.support_places(
            latitude=11.66, longitude=78.15, radius_km=10, categories=places.ALL_CATEGORIES
        )
        assert (found, status) == ([], "unavailable")

        # And the next request does not wait out the same failure again.
        await places.support_places(
            latitude=11.0, longitude=77.0, radius_km=10, categories=places.ALL_CATEGORIES
        )
        assert len(calls) == 1

    async def test_every_endpoint_is_tried_before_giving_up(self, monkeypatch, overpass_on):
        monkeypatch.setattr(
            get_settings(), "overpass_urls", "https://first.invalid,https://second.invalid"
        )
        tried = []

        async def post(url, query):
            tried.append(url)
            if url == "https://first.invalid":
                raise places.PlacesUnavailable("busy")
            return _elements()

        monkeypatch.setattr(places, "_post", post)
        found, status = await places.support_places(
            latitude=SALEM["latitude"], longitude=SALEM["longitude"],
            radius_km=10, categories=places.ALL_CATEGORIES,
        )
        assert status == "ok" and found
        assert tried == ["https://first.invalid", "https://second.invalid"]


class TestRoutes:
    def test_nearby_centres_on_the_place_they_said(self, client):
        body = client.post("/api/places/nearby", json={"place": "ஈரோடு"}).json()
        assert body["centre"]["source"] == "place"
        assert body["centre"]["key"] == "erode"
        assert body["scheme_places"][0]["key"] == "erode"
        assert all(g["approximate"] for g in body["scheme_places"])

    def test_nearby_without_a_place_is_honest_about_it(self, client):
        body = client.post("/api/places/nearby", json={}).json()
        assert body["centre"]["source"] == "default"

    def test_half_a_location_is_refused(self, client):
        response = client.post("/api/places/nearby", json={"latitude": 11.66})
        assert response.status_code == 422

    @pytest.mark.parametrize("lat,lng", [(91, 78), (11, 181), (-91, 0)])
    def test_impossible_coordinates_are_refused(self, client, lat, lng):
        response = client.post(
            "/api/places/nearby", json={"latitude": lat, "longitude": lng}
        )
        assert response.status_code == 422

    def test_device_location_comes_back_coarsened(self, client):
        body = client.post(
            "/api/places/nearby", json={"latitude": 11.664317, "longitude": 78.146089}
        ).json()
        assert body["centre"] == {
            "latitude": 11.66, "longitude": 78.15, "source": "gps", "key": None, "names": {},
        }

    def test_support_offline_says_offline(self, client):
        body = client.post(
            "/api/places/support", json={"latitude": 11.66, "longitude": 78.15}
        ).json()
        assert body["support_status"] == "offline"
        assert body["degraded"] is True
        assert body["support_places"] == []
        assert "OpenStreetMap" in body["attribution"]

    def test_support_radius_is_bounded(self, client):
        response = client.post(
            "/api/places/support",
            json={"latitude": 11.66, "longitude": 78.15, "radius_km": 500},
        )
        assert response.status_code == 422

    def test_support_with_data(self, client, monkeypatch, overpass_on):
        async def fake(query):
            return _elements()

        monkeypatch.setattr(places, "fetch_elements", fake)
        body = client.post(
            "/api/places/support",
            json={
                "latitude": SALEM["latitude"], "longitude": SALEM["longitude"],
                "categories": ["training"],
            },
        ).json()
        assert body["support_status"] == "ok"
        assert {p["category"] for p in body["support_places"]} == {"training"}
        assert any(p["name"] == "Govt ITI" for p in body["support_places"])

    def test_known_places_lists_the_gazetteer(self, client):
        body = client.get("/api/places/known").json()
        assert {p["key"] for p in body} == set(PLACES)

    def test_health_names_the_places_provider(self, client):
        body = client.get("/health").json()
        assert body["providers"]["places"] == "offline"
        assert "places" in body["degraded"]


class TestBoundary:
    def test_ranking_does_not_know_the_map_exists(self):
        """Distance on the map is information, never a score.

        The location term in matching has its own district table; if it ever
        started reading coordinates from here, the arithmetic a jury can audit
        would quietly depend on a third-party map.
        """
        import ast

        source = Path(matching.__file__).read_text(encoding="utf-8")
        imported = {
            alias.name if isinstance(node, ast.Import) else node.module
            for node in ast.walk(ast.parse(source))
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in (node.names if isinstance(node, ast.Import) else [node])
        }
        assert not any("places" in (name or "") for name in imported)
