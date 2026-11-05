"""Every Tamil Nadu district headquarters is a place the map and matcher know.

Added 2026-11-05: the 27 district headquarters the gazetteer lacked. Their
coordinates and Tamil and Hindi names come from OpenStreetMap, with Wikidata
where OSM had none (app/data/places.py notes the object for each).
"""

from __future__ import annotations

import pytest

from app.data.places import PLACES
from app.services.matching import PLACE_ALIASES, TOWN_DISTRICT, _norm, canonical_place
from app.services.places import localized_place

NEW = [
    "ariyalur", "chengalpattu", "cuddalore", "dindigul", "kallakurichi", "kanchipuram",
    "nagercoil", "mayiladuthurai", "nagapattinam", "udhagamandalam", "perambalur",
    "pudukkottai", "ramanathapuram", "ranipet", "sivaganga", "tenkasi", "thanjavur", "theni",
    "thoothukudi", "tirunelveli", "tirupathur", "tiruvallur", "tiruvannamalai", "tiruvarur",
    "vellore", "viluppuram", "virudhunagar",
]


def test_all_thirty_eight_districts_have_a_town():
    districts = {entry["district"] for entry in PLACES.values()}
    assert len(districts) == 38


@pytest.mark.parametrize("key", NEW)
def test_each_new_town_is_in_tamil_nadu(key):
    entry = PLACES[key]
    # Tamil Nadu's bounding box, roughly: nothing pinned in the sea or Kerala.
    assert 8.0 <= entry["latitude"] <= 13.6
    assert 76.2 <= entry["longitude"] <= 80.4
    assert key in PLACE_ALIASES


def test_no_alias_is_a_prefix_of_another_towns():
    """The matcher reads a place by prefix, both ways, from four characters --
    which absorbs case endings, and would also let one town swallow another."""
    aliases = [(key, _norm(a)) for key, forms in PLACE_ALIASES.items() for a in forms]
    clashes = [
        (k1, a1, k2, a2)
        for k1, a1 in aliases
        for k2, a2 in aliases
        if k1 < k2 and min(len(a1), len(a2)) >= 4 and (a1.startswith(a2) or a2.startswith(a1))
    ]
    assert clashes == []


@pytest.mark.parametrize("said, key", [
    ("Thanjavur", "thanjavur"),
    ("Tanjore", "thanjavur"),
    ("தஞ்சாவூரில்", "thanjavur"),            # locative case ending
    ("இராமநாதபுரத்தில்", "ramanathapuram"),
    ("ராமநாதபுரம்", "ramanathapuram"),         # written without the leading இ
    ("Tuticorin", "thoothukudi"),
    ("Ooty", "udhagamandalam"),
    ("Nilgiris", "udhagamandalam"),
    ("नागरकोइल में", "nagercoil"),
    ("Villupuram, Tamil Nadu", "viluppuram"),
    ("நெல்லையில்", "tirunelveli"),
    ("திருப்பூர்", "tiruppur"),                 # not Tirupathur
    ("திருப்பத்தூர்", "tirupathur"),            # not Tiruppur
])
def test_spoken_forms_find_the_town(said, key):
    assert canonical_place(said) == key


def test_headquarters_with_a_differently_named_district():
    assert TOWN_DISTRICT["nagercoil"] == "kanniyakumari"
    assert TOWN_DISTRICT["udhagamandalam"] == "nilgiris"


def test_names_reach_the_reader():
    assert localized_place("Thanjavur", "ta") == "தஞ்சாவூர்"
    assert localized_place("Vellore", "hi") == "वेल्लोर"
