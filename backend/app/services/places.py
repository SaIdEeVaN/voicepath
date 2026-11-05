"""What is near a person: openings from the catalogue, and offices that can help.

Two sources, kept apart because they deserve different amounts of trust.

**Openings** come from the catalogue. A scheme's record names its town and
nothing finer, so each one is pinned at that town's centre
(``app/data/places.py``) and openings sharing a town are grouped into one pin.
Eleven pins stacked on one point would read as eleven street addresses, and
the record does not have one of those to give.

**Support offices** -- ITIs and training centres, employment offices,
government offices, banks -- come from OpenStreetMap through the Overpass API.
They are community-kept, passed through as they arrive, and never invented: an
office the map does not have is absent here too, and the interface says the
list can be out of date.

Three things this module will not do.

It does not rank. Distances are information shown beside an opening; the
ranked list on ``/schemes`` is ``matching.py``'s, and ``matching.py`` does not
import this file. ``tests/test_nearby.py`` holds that line.

It does not keep a location. A device location is rounded to two decimals
(about a kilometre) before it is used for anything -- the cache key and the
query sent to Overpass included. Nothing here writes to the database, and no
coordinate is logged.

It does not fail the screen. Overpass is a volunteer service; when every
endpoint is busy the openings are still returned, with ``support_status``
saying the offices could not be loaded rather than pretending there are none.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, NamedTuple

import httpx

from app.config import get_settings
from app.data.places import PLACES
from app.services.matching import canonical_place
from app.services.schemes import Scheme

logger = logging.getLogger(__name__)

ATTRIBUTION = "© OpenStreetMap contributors"

# Overpass asks clients to identify themselves. Generic on purpose: no person's
# contact details travel with a request made on someone else's behalf.
USER_AGENT = "VoicePath/1.0 (+https://github.com/saideevan/voicepath)"

# Two decimals of a degree is about 1.1 km. Coarse enough that the point sent
# on is an area rather than a doorstep, fine enough that "nearest" still means
# something in a town.
COORDINATE_DECIMALS = 2

# Per category, nearest first. A town centre has dozens of bank branches; a
# list of forty banks buries the one ITI.
PER_CATEGORY_LIMIT = 12

ALL_CATEGORIES: tuple[str, ...] = ("training", "employment", "government", "bank")

# A college or school counts as a training centre only by its name. Without
# this the list fills with arts, law and medical colleges, which are not where
# someone goes to certify the welding they already do.
#
# Written without backslashes because it is sent to Overpass as well, whose
# string literals treat a backslash as an escape of their own. The ITI
# alternative is bounded by non-letters so "iti" inside a word does not count.
TRAINING_NAME_PATTERN = (
    "(^|[^A-Za-z])I[.]?T[.]?I([^A-Za-z]|$)|Industrial Training|Polytechnic|"
    "Skill|Vocational|Training|Kaushal|Handloom|"
    "தொழிற்பயிற்சி|திறன்|औद्योगिक|कौशल"
)
_TRAINING_NAME = re.compile(TRAINING_NAME_PATTERN, re.IGNORECASE)

# Government offices that are not somewhere to ask about a scheme. By tag
# where the mapper gave one, and by name where they did not -- in real Salem
# data most tax offices carry no `government=` tag at all, and a list headed
# "places that can help" was opening with the Income Tax office.
#
# The RTO stays: it is where a driving licence comes from, and a licence is
# what the driving openings ask for.
_NOT_SUPPORT_GOVERNMENT = {"police", "tax", "customs", "prosecutor"}
_NOT_SUPPORT_NAME = re.compile(
    r"income[ -]?tax|\bGST\b|excise|customs|police", re.IGNORECASE
)


class PlacesUnavailable(RuntimeError):
    """No Overpass endpoint answered usefully."""


def provider_name() -> str:
    return get_settings().places_provider


def is_available() -> bool:
    return provider_name() != "offline"


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance. Straight-line, not by road -- shown as such."""
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1.0, a)))


def coarsen(value: float) -> float:
    return round(value, COORDINATE_DECIMALS)


# ---------------------------------------------------------------------------
# Where the person is
# ---------------------------------------------------------------------------


def place_key(value: str | None) -> str | None:
    """A spoken or written place, resolved to a gazetteer key, or None.

    Goes through the matcher's own resolver, so "சேலத்துல", "सेलम में" and
    "Salem, Tamil Nadu" all land on the same town the scorer already uses.
    """
    key = canonical_place(value)
    return key if key in PLACES else None


def place_names(value: str | None) -> dict[str, str]:
    """A known town's name in each script the gazetteer holds; {} otherwise.

    The names are the gazetteer's, the same ones the map labels towns with --
    never a transliteration made up on the spot. A place the gazetteer does
    not know keeps the spelling the catalogue gave it.
    """
    key = place_key(value)
    return dict(PLACES[key]["names"]) if key else {}


def localized_place(value: str | None, language: str | None) -> str:
    """A place as a reader of ``language`` writes it, falling back to as given."""
    code = (language or "en").split("-")[0].lower()
    return place_names(value).get(code) or (value or "")


def _scheme_place_key(scheme: Scheme) -> str | None:
    return place_key(scheme.location) or place_key(scheme.district)


@dataclass(frozen=True)
class Centre:
    latitude: float
    longitude: float
    source: str  # "gps" | "place" | "default"
    key: str | None = None

    @property
    def names(self) -> dict[str, str]:
        return dict(PLACES[self.key]["names"]) if self.key else {}


def _default_key(catalogue: Iterable[Scheme]) -> str:
    """The town with the most openings: "where the openings are".

    Used only when we do not know where the person is, and the interface says
    that is what it is showing. Ties break on the key, so it is stable.
    """
    counts: dict[str, int] = {}
    for scheme in catalogue:
        key = _scheme_place_key(scheme)
        if key:
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return next(iter(PLACES))
    return min(counts, key=lambda k: (-counts[k], k))


def resolve_centre(
    *,
    place: str | None,
    latitude: float | None,
    longitude: float | None,
    catalogue: list[Scheme],
) -> Centre:
    """Device location first, then the place they named, then the openings."""
    if latitude is not None and longitude is not None:
        return Centre(coarsen(latitude), coarsen(longitude), "gps")

    key = place_key(place)
    if key is not None:
        entry = PLACES[key]
        return Centre(entry["latitude"], entry["longitude"], "place", key)

    key = _default_key(catalogue)
    entry = PLACES[key]
    return Centre(entry["latitude"], entry["longitude"], "default", key)


# ---------------------------------------------------------------------------
# Openings
# ---------------------------------------------------------------------------


@dataclass
class SchemePlace:
    key: str
    names: dict[str, str]
    latitude: float
    longitude: float
    distance_km: float
    schemes: list[Scheme] = field(default_factory=list)


def scheme_places(
    catalogue: list[Scheme], centre: Centre
) -> tuple[list[SchemePlace], list[Scheme]]:
    """Openings grouped by town, nearest town first.

    Returns the groups and the openings whose town is not in the
    gazetteer. Those are reported rather than dropped: a scheme missing from
    the map is still a scheme, and the person should still be able to find it.
    """
    groups: dict[str, SchemePlace] = {}
    unplaced: list[Scheme] = []
    for scheme in sorted(catalogue, key=lambda s: s.id):
        key = _scheme_place_key(scheme)
        if key is None:
            unplaced.append(scheme)
            continue
        group = groups.get(key)
        if group is None:
            entry = PLACES[key]
            group = groups[key] = SchemePlace(
                key=key,
                names=dict(entry["names"]),
                latitude=entry["latitude"],
                longitude=entry["longitude"],
                distance_km=round(
                    haversine_km(
                        centre.latitude, centre.longitude,
                        entry["latitude"], entry["longitude"],
                    ),
                    1,
                ),
            )
        group.schemes.append(scheme)
    ordered = sorted(groups.values(), key=lambda g: (g.distance_km, g.key))
    return ordered, unplaced


# ---------------------------------------------------------------------------
# Support offices (OpenStreetMap)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SupportPlace:
    id: str
    category: str
    name: str
    names: dict[str, str]
    latitude: float
    longitude: float
    distance_km: float
    address: str | None
    opening_hours: str | None
    osm_url: str


def categorize(tags: dict[str, str]) -> str | None:
    """Which of the four kinds of help an OSM feature is, if any.

    Mirrors the clauses in ``build_query``: Overpass narrows what comes back,
    and this decides what it means. Kept in step so a feature can never be
    fetched under one category and shown under another.
    """
    amenity = tags.get("amenity")
    office = tags.get("office")
    # Every name the feature carries, not only `name`. Real Salem data has
    # offices tagged with `name:en` alone, which slipped past a check on
    # `name` and were shown -- by the display fallback -- under the very
    # name the filter should have caught. An ITI mapped only in Tamil is the
    # same case the other way round.
    name = " ".join(
        value for key, value in tags.items() if key == "name" or key.startswith("name:")
    )

    if amenity in ("training", "college", "school", "university") and _NOT_SUPPORT_NAME.search(name):
        # A police training college is a police academy, not somewhere to
        # certify a trade. Found in the first extract-built snapshot.
        return None
    if amenity == "training":
        return "training"
    if amenity in ("college", "school", "university") and _TRAINING_NAME.search(name):
        return "training"
    if office == "employment_agency":
        return "employment"
    if amenity == "bank":
        return "bank"
    if office == "government" or amenity == "townhall":
        if tags.get("government") in _NOT_SUPPORT_GOVERNMENT:
            return None
        if _NOT_SUPPORT_NAME.search(name):
            return None
        return "government"
    return None


def build_query(
    latitude: float,
    longitude: float,
    radius_km: float,
    categories: Iterable[str],
    *,
    timeout_seconds: int | None = None,
) -> str:
    """Overpass QL for the requested categories around one point.

    Every value interpolated here is a number or comes from a fixed table, so
    nothing a person typed can reach the query. ``timeout_seconds`` is for the
    snapshot script, which can afford to wait where a person cannot.
    """
    around = f"(around:{int(radius_km * 1000)},{latitude:.4f},{longitude:.4f})"
    wanted = set(categories)
    clauses: list[str] = []
    if "training" in wanted:
        clauses.append(f'nwr["amenity"="training"]{around};')
        clauses.append(
            f'nwr["amenity"~"^(college|school|university)$"]'
            f'["name"~"{TRAINING_NAME_PATTERN}",i]{around};'
        )
    if "employment" in wanted:
        clauses.append(f'nwr["office"="employment_agency"]{around};')
    if "government" in wanted:
        clauses.append(f'nwr["office"="government"]{around};')
        clauses.append(f'nwr["amenity"="townhall"]{around};')
    if "bank" in wanted:
        clauses.append(f'nwr["amenity"="bank"]{around};')
    # A little under the HTTP timeout, so a slow query is ended by the server
    # with a remark we can read, rather than by us with a dropped connection.
    timeout = timeout_seconds or max(5, int(get_settings().places_timeout_seconds) - 2)
    limit = "" if timeout_seconds else " 500"
    return f"[out:json][timeout:{timeout}];(" + "".join(clauses) + f");out center tags{limit};"


def _address(tags: dict[str, str]) -> str | None:
    if tags.get("addr:full"):
        return tags["addr:full"]
    street = " ".join(
        part for part in (tags.get("addr:housenumber"), tags.get("addr:street")) if part
    )
    parts = [street, tags.get("addr:suburb"), tags.get("addr:city") or tags.get("addr:place")]
    joined = ", ".join(p for p in parts if p)
    return joined or None


def parse_elements(
    elements: Iterable[dict],
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    categories: Iterable[str],
) -> list[SupportPlace]:
    """Overpass elements to support places, nearest first.

    Unnamed features are dropped -- "Bank" with no name is not somewhere a
    person can ask for. The same office mapped twice (as a point and as a
    building outline, which is common) is kept once, at the nearer of the two.
    """
    wanted = set(categories)
    candidates: list[SupportPlace] = []
    for element in elements:
        tags = element.get("tags") or {}
        name = (
            tags.get("name")
            or tags.get("name:en")
            or tags.get("name:ta")
            or tags.get("name:hi")
            or ""
        ).strip()
        if not name:
            continue
        category = categorize(tags)
        if category is None or category not in wanted:
            continue

        if "lat" in element and "lon" in element:
            lat, lon = element["lat"], element["lon"]
        elif isinstance(element.get("center"), dict):
            lat, lon = element["center"].get("lat"), element["center"].get("lon")
        else:
            continue
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue

        distance = haversine_km(latitude, longitude, lat, lon)
        # A building's centre can sit just outside a circle its edge is
        # inside. Anything further than that was not asked for.
        if distance > radius_km * 1.05:
            continue

        kind = element.get("type", "node")
        candidates.append(
            SupportPlace(
                id=f"{kind}/{element.get('id')}",
                category=category,
                name=name,
                names={
                    lang: tags[f"name:{lang}"]
                    for lang in ("en", "ta", "hi")
                    if tags.get(f"name:{lang}")
                },
                latitude=float(lat),
                longitude=float(lon),
                distance_km=round(distance, 1),
                address=_address(tags),
                opening_hours=tags.get("opening_hours"),
                osm_url=f"https://www.openstreetmap.org/{kind}/{element.get('id')}",
            )
        )

    candidates.sort(key=lambda p: (p.distance_km, p.name.casefold(), p.id))
    seen: set[tuple[str, str]] = set()
    per_category: dict[str, int] = {}
    kept: list[SupportPlace] = []
    for place in candidates:
        identity = (place.category, place.name.casefold())
        if identity in seen:
            continue
        if per_category.get(place.category, 0) >= PER_CATEGORY_LIMIT:
            continue
        seen.add(identity)
        per_category[place.category] = per_category.get(place.category, 0) + 1
        kept.append(place)
    return kept


# -- Transport ---------------------------------------------------------------

_cache: OrderedDict[tuple, tuple[float, list[dict]]] = OrderedDict()
_CACHE_MAX_ENTRIES = 256

# After every endpoint has failed, stop asking for this long. The public
# servers fail by being overloaded, and each attempt costs the person the full
# timeout on every endpoint -- forty seconds of spinner to learn what the last
# request already learned. Answering "unavailable" at once is the honest and
# the kind thing, and it stops piling load onto a server that is struggling.
FAILURE_BACKOFF_SECONDS = 60.0
_unavailable_until = 0.0


def reset_cache() -> None:
    global _unavailable_until
    _cache.clear()
    _unavailable_until = 0.0


def _cache_get(key: tuple) -> list[dict] | None:
    hit = _cache.get(key)
    if hit is None:
        return None
    expires_at, elements = hit
    if time.monotonic() >= expires_at:
        _cache.pop(key, None)
        return None
    _cache.move_to_end(key)
    return elements


def _cache_put(key: tuple, elements: list[dict]) -> None:
    ttl = get_settings().places_cache_hours * 3600
    _cache[key] = (time.monotonic() + ttl, elements)
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)


async def _post(url: str, query: str) -> list[dict]:
    """One endpoint, one attempt. Raises PlacesUnavailable on anything odd."""
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.places_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = await client.post(url, data={"data": query})
    if response.status_code != 200:
        raise PlacesUnavailable(f"{url} answered {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise PlacesUnavailable(f"{url} did not answer with JSON") from exc
    # A query that ran out of time still answers 200, with a remark and an
    # empty element list. That is a failure, not "nothing here".
    remark = str(payload.get("remark") or "")
    if "error" in remark.lower():
        raise PlacesUnavailable(f"{url}: {remark[:160]}")
    return list(payload.get("elements") or [])


async def fetch_elements(query: str) -> list[dict]:
    """Every configured endpoint in turn, until one answers."""
    failures: list[str] = []
    for url in get_settings().overpass_url_list:
        try:
            return await _post(url, query)
        except (httpx.HTTPError, PlacesUnavailable) as exc:
            failures.append(f"{type(exc).__name__}: {exc}"[:200])
    raise PlacesUnavailable("; ".join(failures) or "no Overpass endpoint configured")


# -- Snapshot ------------------------------------------------------------------
#
# The public servers could not answer the deployed backend in time on the day
# this shipped, so offices around every town the map knows are fetched ahead
# of time by ``app/scripts/fetch_support_places.py``. A search whose whole
# circle sits inside a fetched town's circle is answered from that file: no
# network, no waiting, and no dependence on a volunteer server being up.
# Anything else -- a device location far from every known town -- still asks
# Overpass live.

SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "data" / "support_places.json"


@dataclass(frozen=True)
class Snapshot:
    radius_km: float
    as_of: str | None
    fetched_towns: tuple[str, ...]
    elements: tuple[dict, ...]


_snapshot_cache: dict[str, Snapshot | None] = {}


def load_snapshot() -> Snapshot | None:
    """The bundled offices, or None if there is no usable file."""
    if "value" in _snapshot_cache:
        return _snapshot_cache["value"]
    snapshot: Snapshot | None = None
    try:
        raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        snapshot = Snapshot(
            radius_km=float(raw["radius_km"]),
            as_of=raw.get("as_of"),
            fetched_towns=tuple(
                key for key, status in (raw.get("towns") or {}).items()
                if status.get("fetched") and key in PLACES
            ),
            elements=tuple(raw.get("elements") or ()),
        )
    except FileNotFoundError:
        logger.info("No offices snapshot at %s; every lookup goes live", SNAPSHOT_PATH)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.error("Offices snapshot at %s is unreadable (%s); ignoring it", SNAPSHOT_PATH, exc)
    _snapshot_cache["value"] = snapshot
    return snapshot


def reset_snapshot() -> None:
    _snapshot_cache.clear()


def snapshot_covers(
    snapshot: Snapshot, latitude: float, longitude: float, radius_km: float
) -> bool:
    """Whether the snapshot holds everything inside this search circle.

    Only when the circle sits wholly inside a fetched town's circle. Partial
    overlap is not coverage: the missing part could hold the nearest ITI.
    """
    for key in snapshot.fetched_towns:
        entry = PLACES[key]
        distance = haversine_km(latitude, longitude, entry["latitude"], entry["longitude"])
        if distance + radius_km <= snapshot.radius_km + 1e-9:
            return True
    return False


class SupportResult(NamedTuple):
    places: list[SupportPlace]
    # ok: looked, and this is what is there (possibly nothing).
    # unavailable: could not look just now. offline: live lookups are off and
    # the snapshot does not cover this search.
    status: str
    # snapshot or live when status is ok; None otherwise.
    source: str | None = None
    # The day the snapshot was fetched, when the answer came from it.
    as_of: str | None = None


async def support_places(
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    categories: Iterable[str],
) -> SupportResult:
    """Offices near a point: from the snapshot if it covers them, else live.

    "None nearby" and "could not look" are different answers, and the status
    says which -- the caller tells the person.
    """
    wanted = tuple(sorted(set(categories) & set(ALL_CATEGORIES)))
    if not wanted:
        return SupportResult([], "ok", None)

    snapshot = load_snapshot()
    if snapshot is not None and snapshot_covers(snapshot, latitude, longitude, radius_km):
        return SupportResult(
            parse_elements(
                snapshot.elements,
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
                categories=wanted,
            ),
            "ok",
            "snapshot",
            snapshot.as_of,
        )

    if not is_available():
        return SupportResult([], "offline")

    global _unavailable_until
    lat, lng = coarsen(latitude), coarsen(longitude)
    key = (lat, lng, round(radius_km, 1), wanted)
    elements = _cache_get(key)
    if elements is None:
        if time.monotonic() < _unavailable_until:
            return SupportResult([], "unavailable")
        try:
            elements = await fetch_elements(build_query(lat, lng, radius_km, wanted))
        except PlacesUnavailable as exc:
            # The reason, never the coordinates.
            logger.warning("Nearby offices could not be loaded: %s", exc)
            _unavailable_until = time.monotonic() + FAILURE_BACKOFF_SECONDS
            return SupportResult([], "unavailable")
        _cache_put(key, elements)

    return SupportResult(
        parse_elements(
            elements,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            categories=wanted,
        ),
        "ok",
        "live",
    )


def known_places() -> list[tuple[str, dict]]:
    """Every town the map can centre on, for a person to pick from."""
    return sorted(PLACES.items(), key=lambda item: (item[1]["district"], item[0]))
