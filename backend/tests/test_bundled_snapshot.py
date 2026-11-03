"""The offices snapshot that ships: app/data/support_places.json.

It is produced by app/scripts/fetch_support_places.py, normally through the
"Refresh the offices snapshot" GitHub Actions workflow, because the public
Overpass servers are not reliably reachable from everywhere this project is
developed.

Until the first refresh lands there is no file, and that is a supported state:
the API answers every office search live, as it did before the snapshot
existed. So these skip when the file is absent -- and the workflow runs them
with REQUIRE_SNAPSHOT=1, which turns a missing or malformed file into a
failure before any pull request is opened.
"""

from __future__ import annotations

import json
import os

import pytest

from app.data.places import PLACES
from app.services import places

REQUIRED = os.environ.get("REQUIRE_SNAPSHOT") == "1"


@pytest.fixture
def bundled():
    path = places.SNAPSHOT_PATH
    if not path.exists():
        if REQUIRED:
            pytest.fail(f"REQUIRE_SNAPSHOT=1 but there is no snapshot at {path}")
        pytest.skip(
            "No offices snapshot yet. Run the 'Refresh the offices snapshot' "
            "workflow, or python -m app.scripts.fetch_support_places."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def test_it_is_attributed(bundled):
    assert "OpenStreetMap" in bundled["attribution"]
    assert "ODbL" in bundled["license"]
    assert bundled["as_of"]


def test_every_town_the_map_knows_is_accounted_for(bundled):
    assert set(bundled["towns"]) == set(PLACES)


def test_the_towns_with_openings_are_covered(bundled):
    """Where the catalogue's openings are is where people will look."""
    for town in ("salem", "erode", "attur"):
        assert bundled["towns"][town]["fetched"], town


def test_every_element_is_something_the_map_would_show(bundled):
    for element in bundled["elements"]:
        assert places.categorize(element["tags"]) is not None, element
        assert isinstance(element["lat"], float) and isinstance(element["lon"], float)


def test_it_covers_a_search_from_each_fetched_town(bundled):
    snap = places.Snapshot(
        radius_km=bundled["radius_km"],
        as_of=bundled["as_of"],
        fetched_towns=tuple(k for k, v in bundled["towns"].items() if v["fetched"]),
        elements=tuple(bundled["elements"]),
    )
    for key in snap.fetched_towns:
        entry = PLACES[key]
        assert places.snapshot_covers(snap, entry["latitude"], entry["longitude"], 25)


def test_the_api_answers_salem_from_it_without_the_network(bundled, monkeypatch):
    import asyncio

    async def boom(query):  # pragma: no cover - must not run
        raise AssertionError("asked Overpass for a search the snapshot covers")

    monkeypatch.setattr(places, "fetch_elements", boom)
    places.reset_snapshot()
    salem = PLACES["salem"]
    result = asyncio.run(
        places.support_places(
            latitude=salem["latitude"], longitude=salem["longitude"],
            radius_km=10, categories=places.ALL_CATEGORIES,
        )
    )
    places.reset_snapshot()
    assert result.status == "ok" and result.source == "snapshot"
    assert result.places, "a snapshot covering Salem found no offices at all"
