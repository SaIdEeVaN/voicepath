"""Fetch the snapshot of support offices the map serves from.

    python -m app.scripts.fetch_support_places
    python -m app.scripts.fetch_support_places --towns salem,erode

The public Overpass servers are volunteer-run, and on 2026-11-03 neither the
main one nor its mirror would answer the deployed backend in time: the map
showed openings but no offices. So the offices around every town the map knows
are fetched here, once, and saved to ``app/data/support_places.json``. The API
answers from that file for any search it covers and asks Overpass live only
for the rest.

This script can wait where a person cannot: long server-side timeouts, every
configured endpoint, POST and GET, retries with backoff. A town that still
fails is recorded as not fetched, so the API knows not to claim coverage there.
With ``--towns`` only those are refetched and the rest of the file is kept.

The data is OpenStreetMap's, under the ODbL. The file says so and the
interface attributes it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path

import httpx

from app.config import get_settings
from app.data.places import PLACES
from app.services import places

logger = logging.getLogger("fetch_support_places")

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "support_places.json"

# The largest radius a request may ask for. A search is answered from the
# snapshot only when its whole circle sits inside a fetched town's circle.
RADIUS_KM = 25

# Per query. One kind of office around one town at a time: a single query for
# all four kinds over 25 km timed out on a busy server again and again, where
# four small ones get through.
SERVER_TIMEOUT_SECONDS = 60
ATTEMPTS = 6

# Only what the API reads. Everything else a mapper tagged stays on OSM.
_KEEP_EXACT = {"name", "amenity", "office", "government", "opening_hours"}
_KEEP_PREFIX = ("name:", "addr:")


def _trim(tags: dict[str, str]) -> dict[str, str]:
    return {
        k: v for k, v in tags.items() if k in _KEEP_EXACT or k.startswith(_KEEP_PREFIX)
    }


def _flatten(element: dict) -> dict | None:
    """One element as the API stores it, or None if the API would not show it."""
    tags = element.get("tags") or {}
    if places.categorize(tags) is None:
        return None
    if not any(tags.get(k) for k in ("name", "name:en", "name:ta", "name:hi")):
        return None
    if "lat" in element and "lon" in element:
        lat, lon = element["lat"], element["lon"]
    elif isinstance(element.get("center"), dict):
        lat, lon = element["center"].get("lat"), element["center"].get("lon")
    else:
        return None
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    return {
        "type": element.get("type", "node"),
        "id": element.get("id"),
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
        "tags": _trim(tags),
    }


async def _query(client: httpx.AsyncClient, label: str, query: str) -> list[dict] | None:
    """One query, every endpoint and both methods, with backoff."""
    urls = get_settings().overpass_url_list
    for attempt in range(ATTEMPTS):
        url = urls[(attempt // 2) % len(urls)]
        # GET first: through a busy mirror it got answers when POST got 504s.
        method = "GET" if attempt % 2 == 0 else "POST"
        try:
            if method == "POST":
                response = await client.post(url, data={"data": query})
            else:
                response = await client.get(url, params={"data": query})
            if response.status_code != 200:
                raise places.PlacesUnavailable(f"HTTP {response.status_code}")
            payload = response.json()
            remark = str(payload.get("remark") or "")
            if "error" in remark.lower():
                raise places.PlacesUnavailable(remark[:120])
            elements = list(payload.get("elements") or [])
            logger.info("%-30s %4d elements  (%s %s)", label, len(elements), method, url)
            return elements
        except (httpx.HTTPError, ValueError, places.PlacesUnavailable) as exc:
            wait = min(45, 5 * (attempt + 1))
            logger.warning(
                "%-30s attempt %d/%d via %s %s: %s %s -- retrying in %ds",
                label, attempt + 1, ATTEMPTS, method, url, type(exc).__name__,
                str(exc)[:80], wait,
            )
            await asyncio.sleep(wait)
    logger.error("%-30s gave up after %d attempts", label, ATTEMPTS)
    return None


async def _fetch_town(client: httpx.AsyncClient, key: str) -> list[dict] | None:
    """Every kind of office around one town, or None if any kind failed.

    All or nothing: a town recorded as fetched is one the API will claim to
    cover, and a town missing its ITIs is not covered.
    """
    entry = PLACES[key]
    found: list[dict] = []
    for category in places.ALL_CATEGORIES:
        query = places.build_query(
            entry["latitude"], entry["longitude"], RADIUS_KM, [category],
            timeout_seconds=SERVER_TIMEOUT_SECONDS,
        )
        elements = await _query(client, f"{key}/{category}", query)
        if elements is None:
            return None
        found.extend(elements)
    return found


def _load_existing() -> dict:
    if OUTPUT.exists():
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    return {"towns": {}, "elements": []}


async def main(towns: list[str]) -> int:
    existing = _load_existing()
    town_status: dict[str, dict] = dict(existing.get("towns") or {})
    by_id: dict[str, dict] = {
        f"{e['type']}/{e['id']}": e for e in existing.get("elements") or []
    }
    # Elements belong to every town whose circle they sit in; refetching a town
    # replaces only what that town contributed.
    contributed: dict[str, set[str]] = {
        k: set(v.get("ids") or []) for k, v in town_status.items()
    }

    timeout = httpx.Timeout(SERVER_TIMEOUT_SECONDS + 15)
    async with httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": places.USER_AGENT}
    ) as client:
        for key in towns:
            raw = await _fetch_town(client, key)
            if raw is None:
                town_status[key] = {"fetched": False, "ids": []}
                contributed[key] = set()
                continue
            ids: set[str] = set()
            for element in raw:
                flat = _flatten(element)
                if flat is None:
                    continue
                ident = f"{flat['type']}/{flat['id']}"
                by_id[ident] = flat
                ids.add(ident)
            contributed[key] = ids
            town_status[key] = {
                "fetched": True,
                "fetched_on": date.today().isoformat(),
                "ids": sorted(ids),
            }

    # Drop anything no town contributes any more.
    wanted = set().union(*contributed.values()) if contributed else set()
    elements = sorted(
        (e for ident, e in by_id.items() if ident in wanted),
        key=lambda e: (e["type"], e["id"]),
    )

    fetched_days = [
        s["fetched_on"] for s in town_status.values() if s.get("fetched") and s.get("fetched_on")
    ]
    snapshot = {
        "source": "OpenStreetMap, via the Overpass API",
        "license": "ODbL 1.0 -- (c) OpenStreetMap contributors, openstreetmap.org/copyright",
        "attribution": places.ATTRIBUTION,
        "radius_km": RADIUS_KM,
        "as_of": min(fetched_days) if fetched_days else None,
        "towns": {k: town_status[k] for k in sorted(town_status)},
        "elements": elements,
    }
    OUTPUT.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    missing = [k for k, s in town_status.items() if not s.get("fetched")]
    logger.info(
        "Wrote %s: %d elements, %d/%d towns fetched%s",
        OUTPUT, len(elements), len(town_status) - len(missing), len(town_status),
        f" (missing: {', '.join(missing)})" if missing else "",
    )
    return 1 if missing else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--towns", default="", help="Comma-separated gazetteer keys; default all."
    )
    args = parser.parse_args()
    chosen = [t.strip() for t in args.towns.split(",") if t.strip()] or sorted(PLACES)
    unknown = [t for t in chosen if t not in PLACES]
    if unknown:
        parser.error(f"not in the gazetteer: {', '.join(unknown)}")
    sys.exit(asyncio.run(main(chosen)))
