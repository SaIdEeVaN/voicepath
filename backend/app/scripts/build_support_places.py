"""Build the offices snapshot from an OpenStreetMap extract, not a query server.

    python -m app.scripts.build_support_places --bbox
    python -m app.scripts.build_support_places --features filtered.geojsonseq --as-of 2026-11-04

Why this exists: on 2026-11-04 the "Refresh the offices snapshot" workflow ran
for its full 150 minutes and fetched nothing. From GitHub's network the main
public Overpass server timed out on every connection and its mirror answered
every query with 504 -- the same servers that had been unreachable from the
deployed backend the day before. Volunteer-run query servers are not
something a monthly job can rely on.

So the workflow downloads a regional extract from Geofabrik instead (the same
OpenStreetMap data, under the same ODbL), cuts it to the area around the
gazetteer's towns with ``osmium``, keeps only the tags the map reads, and
exports them as GeoJSON features. This script turns those features into the
snapshot the API already reads (``app/data/support_places.json``), through
the same ``places.categorize`` and the same element shape as
``fetch_support_places.py``. Nothing downstream can tell the two apart except
the ``source`` line, which says which way it was made.

Every town is covered, because the extract holds everything inside its area:
there is no per-town failure to record. A feature belongs to each town whose
25 km circle it sits in, exactly as with the per-town queries.

``--bbox`` prints the area to cut, from the gazetteer, and ``--filters`` the
tags to keep, so the workflow and this script never disagree about either.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.data.places import PLACES
from app.scripts.fetch_support_places import OUTPUT, RADIUS_KM, _flatten
from app.services import places

logger = logging.getLogger("build_support_places")

# osmium's ``--add-unique-id=type_id``: "n123" a node, "w123" a way exported as
# a line, "a246" an area. An area's number is libosmium's area id -- twice the
# way's id for a closed way, twice the relation's plus one for a multipolygon
# -- so it is turned back into the real OSM object here. The same closed way
# can come out both as a line and as an area; both become way/123, once.
_TYPES = {"n": "node", "w": "way", "r": "relation"}


def _osm_object(ident: str) -> tuple[str, int] | None:
    prefix, number = ident[:1], ident[1:]
    if not number.isdigit():
        return None
    value = int(number)
    if prefix == "a":
        return ("way", value // 2) if value % 2 == 0 else ("relation", (value - 1) // 2)
    kind = _TYPES.get(prefix)
    return (kind, value) if kind else None

# What ``osmium tags-filter`` keeps: every tag ``places.categorize`` can turn
# into a kind of help. Printed with ``--filters`` for the workflow, so the
# filter and the categorisation cannot drift apart; a test checks they agree.
OSMIUM_FILTERS = (
    "nwr/amenity=training,college,school,university,bank,townhall",
    "nwr/office=employment_agency,government",
)

# Degrees of margin around the towns when cutting the extract: a little more
# than RADIUS_KM, so a feature at the edge of a town's circle is never cut off.
_MARGIN_DEGREES = 0.35


def bbox() -> tuple[float, float, float, float]:
    """west, south, east, north around every gazetteer town, with margin."""
    lats = [p["latitude"] for p in PLACES.values()]
    lons = [p["longitude"] for p in PLACES.values()]
    return (
        round(min(lons) - _MARGIN_DEGREES, 3),
        round(min(lats) - _MARGIN_DEGREES, 3),
        round(max(lons) + _MARGIN_DEGREES, 3),
        round(max(lats) + _MARGIN_DEGREES, 3),
    )


def _points(geometry: dict) -> list[tuple[float, float]]:
    """Every (lon, lat) in a GeoJSON geometry, at any nesting depth."""
    out: list[tuple[float, float]] = []

    def walk(value) -> None:
        if (
            isinstance(value, list) and len(value) >= 2
            and all(isinstance(v, (int, float)) for v in value[:2])
        ):
            out.append((float(value[0]), float(value[1])))
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(geometry.get("coordinates"))
    return out


def feature_to_element(feature: dict) -> dict | None:
    """A GeoJSON feature from ``osmium export`` as an Overpass-style element.

    Ways and areas get the centre of their bounding box, which is what
    Overpass's ``out center`` gives -- so a building has the same pin either
    way the snapshot was made.
    """
    found = _osm_object(str(feature.get("id") or ""))
    if found is None:
        return None
    kind, osm_id = found
    tags = {str(k): str(v) for k, v in (feature.get("properties") or {}).items()
            if not str(k).startswith("@")}
    points = _points(feature.get("geometry") or {})
    if not points:
        return None
    element: dict = {"type": kind, "id": osm_id, "tags": tags}
    if kind == "node" and len(points) == 1:
        element["lon"], element["lat"] = points[0]
    else:
        lons = [p[0] for p in points]
        lats = [p[1] for p in points]
        element["center"] = {
            "lon": (min(lons) + max(lons)) / 2,
            "lat": (min(lats) + max(lats)) / 2,
        }
    return element


def read_features(path: Path):
    """GeoJSON Text Sequences (RFC 8142): one feature per line, maybe RS-led."""
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip().lstrip("\x1e").strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                logger.warning("Skipping a line that is not JSON")


def build(features, as_of: str) -> dict:
    """The snapshot, from an iterable of features."""
    by_id: dict[str, dict] = {}
    ids_by_town: dict[str, set[str]] = {key: set() for key in PLACES}

    for feature in features:
        element = feature_to_element(feature)
        if element is None:
            continue
        flat = _flatten(element)
        if flat is None:
            continue
        ident = f"{flat['type']}/{flat['id']}"
        for key, entry in PLACES.items():
            distance = places.haversine_km(
                entry["latitude"], entry["longitude"], flat["lat"], flat["lon"]
            )
            if distance <= RADIUS_KM:
                ids_by_town[key].add(ident)
                by_id[ident] = flat

    return {
        "source": "OpenStreetMap, via a Geofabrik regional extract filtered with osmium",
        "license": "ODbL 1.0 -- (c) OpenStreetMap contributors, openstreetmap.org/copyright",
        "attribution": places.ATTRIBUTION,
        "radius_km": RADIUS_KM,
        "as_of": as_of,
        "towns": {
            key: {"fetched": True, "fetched_on": as_of, "ids": sorted(ids_by_town[key])}
            for key in sorted(PLACES)
        },
        "elements": sorted(by_id.values(), key=lambda e: (e["type"], e["id"])),
    }


def main(features_path: Path, as_of: str) -> int:
    snapshot = build(read_features(features_path), as_of)
    OUTPUT.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    empty = [k for k, v in snapshot["towns"].items() if not v["ids"]]
    logger.info(
        "Wrote %s: %d offices around %d towns, as of %s%s",
        OUTPUT, len(snapshot["elements"]), len(snapshot["towns"]), as_of,
        f" (no offices found around: {', '.join(empty)})" if empty else "",
    )
    # A town with nothing at all around it means the extract did not cover
    # it -- a wrong area or a broken download -- not a town with no bank.
    return 1 if empty else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bbox", action="store_true",
                        help="Print west,south,east,north for osmium extract and exit")
    parser.add_argument("--filters", action="store_true",
                        help="Print the osmium tags-filter expressions and exit")
    parser.add_argument("--features", type=Path, help="osmium export output (geojsonseq)")
    parser.add_argument("--as-of", help="The extract's date, YYYY-MM-DD")
    args = parser.parse_args()
    if args.bbox:
        print(",".join(str(v) for v in bbox()))
        sys.exit(0)
    if args.filters:
        print(" ".join(OSMIUM_FILTERS))
        sys.exit(0)
    if not args.features or not args.as_of:
        parser.error("--features and --as-of are required (or --bbox)")
    sys.exit(main(args.features, args.as_of))
