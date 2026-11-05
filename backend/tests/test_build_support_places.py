"""Building the offices snapshot from an OpenStreetMap extract.

The Overpass route fetched nothing on 2026-11-04 -- every query timed out or
504'd from GitHub's network -- so the workflow now filters a Geofabrik extract
with osmium and this script builds the snapshot from its features. These hold
that what comes out is the same snapshot the API already reads, with the same
filtering, and that the API answers from it.
"""

from __future__ import annotations

import json

import pytest

from app.data.places import PLACES
from app.scripts import build_support_places as build
from app.services import places

SALEM = PLACES["salem"]
ERODE = PLACES["erode"]


def node(n: int, lat: float, lon: float, **tags) -> dict:
    return {"type": "Feature", "id": f"n{n}", "properties": tags,
            "geometry": {"type": "Point", "coordinates": [lon, lat]}}


def area(area_id: int, lat: float, lon: float, **tags) -> dict:
    d = 0.001
    ring = [[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d],
            [lon - d, lat + d], [lon - d, lat - d]]
    return {"type": "Feature", "id": f"a{area_id}", "properties": tags,
            "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]}}


FEATURES = [
    node(1, SALEM["latitude"] + 0.01, SALEM["longitude"], amenity="training",
         name="Government ITI Salem"),
    area(200, ERODE["latitude"], ERODE["longitude"] + 0.01, amenity="bank",
         name="State Bank of India"),                        # way/100
    area(301, SALEM["latitude"], SALEM["longitude"] - 0.02, office="employment_agency",
         name="District Employment Office"),                 # relation/150
    node(4, SALEM["latitude"], SALEM["longitude"] + 0.01, office="government",
         government="police", name="Town Police Station"),   # not a place that helps
    node(5, SALEM["latitude"], SALEM["longitude"] + 0.02, amenity="school",
         name="St. Mary's Higher Secondary School"),         # a school, not training
    node(6, SALEM["latitude"], SALEM["longitude"] + 0.03, amenity="bank"),  # no name
    # Outside every circle. Was Kanyakumari until Nagercoil, 17 km away,
    # joined the map on 2026-11-05; Bengaluru is 80 km from the nearest town.
    node(7, 12.9716, 77.5946, amenity="bank", name="Bengaluru Branch"),
]


@pytest.fixture
def snapshot():
    return build.build(FEATURES, "2026-11-04")


class TestWhatGoesIn:
    def test_only_what_the_map_would_show(self, snapshot):
        names = sorted(e["tags"]["name"] for e in snapshot["elements"])
        assert names == ["District Employment Office", "Government ITI Salem",
                         "State Bank of India"]

    def test_areas_become_their_real_osm_objects(self, snapshot):
        idents = {(e["type"], e["id"]) for e in snapshot["elements"]}
        assert ("way", 100) in idents and ("relation", 150) in idents
        assert ("node", 1) in idents

    def test_an_area_is_pinned_at_its_centre(self, snapshot):
        bank = next(e for e in snapshot["elements"] if e["id"] == 100)
        assert bank["lat"] == pytest.approx(ERODE["latitude"], abs=1e-6)
        assert bank["lon"] == pytest.approx(ERODE["longitude"] + 0.01, abs=1e-6)

    def test_a_feature_belongs_to_every_town_whose_circle_it_is_in(self, snapshot):
        assert "node/1" in snapshot["towns"]["salem"]["ids"]
        assert "way/100" in snapshot["towns"]["erode"]["ids"]
        assert "node/1" not in snapshot["towns"]["madurai"]["ids"]

    def test_the_same_closed_way_as_line_and_area_is_kept_once(self):
        twice = [
            area(200, ERODE["latitude"], ERODE["longitude"], amenity="bank", name="Bank"),
            {**area(200, ERODE["latitude"], ERODE["longitude"], amenity="bank", name="Bank"),
             "id": "w100"},
        ]
        assert len(build.build(twice, "2026-11-04")["elements"]) == 1


class TestTheFile:
    def test_it_is_attributed_and_dated(self, snapshot):
        assert "OpenStreetMap" in snapshot["attribution"]
        assert "ODbL" in snapshot["license"]
        assert snapshot["as_of"] == "2026-11-04"
        assert "Geofabrik" in snapshot["source"]

    def test_every_town_is_covered(self, snapshot):
        assert set(snapshot["towns"]) == set(PLACES)
        assert all(t["fetched"] for t in snapshot["towns"].values())

    def test_the_api_answers_from_it_without_the_network(self, snapshot, tmp_path, monkeypatch):
        import asyncio

        path = tmp_path / "support_places.json"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        monkeypatch.setattr(places, "SNAPSHOT_PATH", path)

        async def boom(query):  # pragma: no cover - must not run
            raise AssertionError("asked Overpass for a search the snapshot covers")

        monkeypatch.setattr(places, "fetch_elements", boom)
        places.reset_snapshot()
        try:
            result = asyncio.run(places.support_places(
                latitude=SALEM["latitude"], longitude=SALEM["longitude"],
                radius_km=10, categories=places.ALL_CATEGORIES,
            ))
        finally:
            places.reset_snapshot()
        assert result.source == "snapshot"
        assert {p.name for p in result.places} >= {"Government ITI Salem"}

    def test_reading_rfc_8142_sequences(self, tmp_path):
        path = tmp_path / "features.geojsonseq"
        path.write_text("\x1e" + json.dumps(FEATURES[0]) + "\n\n" + json.dumps(FEATURES[1])
                        + "\nnot json\n", encoding="utf-8")
        assert [f["id"] for f in build.read_features(path)] == ["n1", "a200"]


def test_the_bbox_holds_every_town():
    west, south, east, north = build.bbox()
    for entry in PLACES.values():
        assert west < entry["longitude"] < east
        assert south < entry["latitude"] < north


def test_the_osmium_filter_keeps_everything_categorize_can_use():
    """Filter and categorisation in step: a kind of help the filter drops
    would silently never reach the map."""
    kept: dict[str, set[str]] = {}
    for expression in build.OSMIUM_FILTERS:
        key, values = expression.split("/", 1)[1].split("=", 1)
        kept.setdefault(key, set()).update(values.split(","))
    every_tag = [
        {"amenity": "training"}, {"amenity": "college", "name": "Govt ITI"},
        {"amenity": "school", "name": "Skill Training Centre"},
        {"amenity": "university", "name": "Polytechnic"},
        {"office": "employment_agency"}, {"amenity": "bank"},
        {"office": "government"}, {"amenity": "townhall"},
    ]
    for tags in every_tag:
        assert places.categorize(tags) is not None, tags
        assert any(tags.get(k) in v for k, v in kept.items()), tags


async def test_the_overpass_script_stops_when_the_servers_are_down(tmp_path, monkeypatch):
    """It spent 150 minutes on 22 towns against servers that never answered."""
    from app.scripts import fetch_support_places as fetch

    calls: list[str] = []

    async def down(client, key):
        calls.append(key)
        return None

    monkeypatch.setattr(fetch, "_fetch_town", down)
    monkeypatch.setattr(fetch, "OUTPUT", tmp_path / "support_places.json")
    towns = sorted(PLACES)[:8]
    assert await fetch.main(towns) == 1
    assert len(calls) == fetch.GIVE_UP_AFTER_TOWNS
    written = json.loads((tmp_path / "support_places.json").read_text(encoding="utf-8"))
    assert set(written["towns"]) == set(towns)
    assert not any(t["fetched"] for t in written["towns"].values())


def test_a_police_training_college_is_not_a_training_centre():
    assert places.categorize({"amenity": "college", "name": "Police Training College"}) is None
    assert places.categorize({"amenity": "training", "name": "Police Recruits Training"}) is None
    assert places.categorize({"amenity": "college", "name": "Govt Polytechnic"}) == "training"
