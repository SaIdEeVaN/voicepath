"""Where the places VoicePath knows about actually are.

One entry per canonical key in ``matching.PLACE_ALIASES`` -- the towns and
districts the matcher can already recognise in Tamil, Hindi and English.
``tests/test_nearby.py`` fails if a key is added there and not here, so the
map can never know fewer places than the scorer does.

Coordinates are the town centre, to four decimals (about ten metres). They
are a fact about the town, not about any opening in it: the catalogue records
the town a scheme is in, never its street address, so every opening is pinned
here and the interface says so. Nothing in this file is used for scoring --
``matching.py`` has its own district table and never reads a coordinate.

Names are given in each script so the map can label a place the way the
person reading it writes it. English is the fallback.
"""

from __future__ import annotations

from typing import TypedDict


class PlaceEntry(TypedDict):
    latitude: float
    longitude: float
    district: str
    names: dict[str, str]


PLACES: dict[str, PlaceEntry] = {
    # -- Salem district ------------------------------------------------------
    "salem": {"latitude": 11.6643, "longitude": 78.1460, "district": "salem",
              "names": {"en": "Salem", "ta": "சேலம்", "hi": "सेलम"}},
    "attur": {"latitude": 11.5947, "longitude": 78.6010, "district": "salem",
              "names": {"en": "Attur", "ta": "ஆத்தூர்", "hi": "आत्तूर"}},
    "mettur": {"latitude": 11.7863, "longitude": 77.8008, "district": "salem",
               "names": {"en": "Mettur", "ta": "மேட்டூர்", "hi": "मेट्टूर"}},
    "omalur": {"latitude": 11.7441, "longitude": 78.0465, "district": "salem",
               "names": {"en": "Omalur", "ta": "ஓமலூர்", "hi": "ओमलूर"}},
    "sankagiri": {"latitude": 11.4740, "longitude": 77.8695, "district": "salem",
                  "names": {"en": "Sankagiri", "ta": "சங்ககிரி", "hi": "संकगिरि"}},
    "edappadi": {"latitude": 11.5856, "longitude": 77.8386, "district": "salem",
                 "names": {"en": "Edappadi", "ta": "இடப்பாடி", "hi": "एडप्पाडी"}},
    # -- Erode district ------------------------------------------------------
    "erode": {"latitude": 11.3410, "longitude": 77.7172, "district": "erode",
              "names": {"en": "Erode", "ta": "ஈரோடு", "hi": "इरोड"}},
    "bhavani": {"latitude": 11.4456, "longitude": 77.6826, "district": "erode",
                "names": {"en": "Bhavani", "ta": "பவானி", "hi": "भवानी"}},
    "perundurai": {"latitude": 11.2757, "longitude": 77.5874, "district": "erode",
                   "names": {"en": "Perundurai", "ta": "பெருந்துறை", "hi": "पेरुंदुरै"}},
    "gobichettipalayam": {"latitude": 11.4550, "longitude": 77.4429, "district": "erode",
                          "names": {"en": "Gobichettipalayam", "ta": "கோபிசெட்டிபாளையம்",
                                    "hi": "गोबिचेट्टिपालयम"}},
    "sathyamangalam": {"latitude": 11.5048, "longitude": 77.2384, "district": "erode",
                       "names": {"en": "Sathyamangalam", "ta": "சத்தியமங்கலம்",
                                 "hi": "सत्यमंगलम"}},
    # -- Namakkal district ---------------------------------------------------
    "namakkal": {"latitude": 11.2189, "longitude": 78.1677, "district": "namakkal",
                 "names": {"en": "Namakkal", "ta": "நாமக்கல்", "hi": "नामक्कल"}},
    "rasipuram": {"latitude": 11.4600, "longitude": 78.1866, "district": "namakkal",
                  "names": {"en": "Rasipuram", "ta": "ராசிபுரம்", "hi": "रासीपुरम"}},
    "tiruchengode": {"latitude": 11.3796, "longitude": 77.8946, "district": "namakkal",
                     "names": {"en": "Tiruchengode", "ta": "திருச்செங்கோடு",
                               "hi": "तिरुचेंगोड"}},
    # -- Neighbouring districts ----------------------------------------------
    "dharmapuri": {"latitude": 12.1211, "longitude": 78.1582, "district": "dharmapuri",
                   "names": {"en": "Dharmapuri", "ta": "தருமபுரி", "hi": "धर्मपुरी"}},
    "krishnagiri": {"latitude": 12.5186, "longitude": 78.2137, "district": "krishnagiri",
                    "names": {"en": "Krishnagiri", "ta": "கிருஷ்ணகிரி", "hi": "कृष्णगिरि"}},
    "tiruppur": {"latitude": 11.1085, "longitude": 77.3411, "district": "tiruppur",
                 "names": {"en": "Tiruppur", "ta": "திருப்பூர்", "hi": "तिरुप्पूर"}},
    "coimbatore": {"latitude": 11.0168, "longitude": 76.9558, "district": "coimbatore",
                   "names": {"en": "Coimbatore", "ta": "கோயம்புத்தூர்", "hi": "कोयंबटूर"}},
    "karur": {"latitude": 10.9601, "longitude": 78.0766, "district": "karur",
              "names": {"en": "Karur", "ta": "கரூர்", "hi": "करूर"}},
    "tiruchirappalli": {"latitude": 10.7905, "longitude": 78.7047,
                        "district": "tiruchirappalli",
                        "names": {"en": "Tiruchirappalli", "ta": "திருச்சிராப்பள்ளி",
                                  "hi": "तिरुचिरापल्ली"}},
    # -- State cities people name when they have moved for work --------------
    "chennai": {"latitude": 13.0827, "longitude": 80.2707, "district": "chennai",
                "names": {"en": "Chennai", "ta": "சென்னை", "hi": "चेन्नई"}},
    "madurai": {"latitude": 9.9252, "longitude": 78.1198, "district": "madurai",
                "names": {"en": "Madurai", "ta": "மதுரை", "hi": "मदुरै"}},
}
