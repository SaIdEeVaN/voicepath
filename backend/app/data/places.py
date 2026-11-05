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
    # -- District headquarters, added 2026-11-05 ------------------------------
    # Every Tamil Nadu district the map did not know. Coordinates and Tamil and
    # Hindi names are OpenStreetMap's (the place object noted beside each),
    # looked up through Nominatim; where OSM has no Hindi name -- or, for
    # Ramanathapuram, a corrupted one -- or no town object at all, Wikidata's
    # (the item noted). Nothing here is a spelling made up on the spot.
    # osm node/245589617
    "ariyalur": {"latitude": 11.1358, "longitude": 79.0723, "district": "ariyalur",
        "names": {"en": "Ariyalur", "ta": "அரியலூர்", "hi": "अरियालुर"}},
    # osm node/2393005789; Hindi: wikidata Q888769
    "chengalpattu": {"latitude": 12.6841, "longitude": 79.9836, "district": "chengalpattu",
        "names": {"en": "Chengalpattu", "ta": "செங்கல்பட்டு", "hi": "चेंगलपट्टू"}},
    # osm way/164051966
    "cuddalore": {"latitude": 11.7427, "longitude": 79.7503, "district": "cuddalore",
        "names": {"en": "Cuddalore", "ta": "கடலூர்", "hi": "कडलूर"}},
    # osm node/245586375
    "dindigul": {"latitude": 10.3656, "longitude": 77.9693, "district": "dindigul",
        "names": {"en": "Dindigul", "ta": "திண்டுக்கல்", "hi": "डिंडिगुल"}},
    # osm node/245598247; Hindi: wikidata Q2308206
    "kallakurichi": {"latitude": 11.7406, "longitude": 78.9637, "district": "kallakurichi",
        "names": {"en": "Kallakurichi", "ta": "கள்ளக்குறிச்சி", "hi": "कल्लाकुरिची"}},
    # osm node/256777854
    "kanchipuram": {"latitude": 12.8364, "longitude": 79.7053, "district": "kanchipuram",
        "names": {"en": "Kanchipuram", "ta": "காஞ்சிபுரம்", "hi": "कांचीपुरम"}},
    # osm node/245580128
    "nagercoil": {"latitude": 8.1840, "longitude": 77.4315, "district": "kanniyakumari",
        "names": {"en": "Nagercoil", "ta": "நாகர்கோவில்", "hi": "नागरकोइल"}},
    # osm node/2271360789; Hindi: wikidata Q339986
    "mayiladuthurai": {"latitude": 11.1019, "longitude": 79.6503, "district": "mayiladuthurai",
        "names": {"en": "Mayiladuthurai", "ta": "மயிலாடுதுறை", "hi": "मयीलाडूतुरै"}},
    # osm node/891394162
    "nagapattinam": {"latitude": 10.7648, "longitude": 79.8431, "district": "nagapattinam",
        "names": {"en": "Nagapattinam", "ta": "நாகப்பட்டினம்", "hi": "नागपट्टनम"}},
    # osm node/245592179
    "udhagamandalam": {"latitude": 11.4127, "longitude": 76.7031, "district": "nilgiris",
        "names": {"en": "Udhagamandalam", "ta": "உதகமண்டலம்", "hi": "उदगमंदलम"}},
    # osm way/84737219
    "perambalur": {"latitude": 11.2357, "longitude": 78.8688, "district": "perambalur",
        "names": {"en": "Perambalur", "ta": "பெரம்பலூர்", "hi": "पेरम्बलूर"}},
    # wikidata Q921719
    "pudukkottai": {"latitude": 10.3833, "longitude": 78.8167, "district": "pudukkottai",
        "names": {"en": "Pudukkottai", "ta": "புதுக்கோட்டை", "hi": "पुदुकोट्टई"}},
    # osm way/90779286; Hindi: wikidata Q775255
    "ramanathapuram": {"latitude": 9.3652, "longitude": 78.8343, "district": "ramanathapuram",
        "names": {"en": "Ramanathapuram", "ta": "இராமநாதபுரம்", "hi": "रामानाथपुरम"}},
    # osm node/263014503; Hindi: wikidata Q1421308
    "ranipet": {"latitude": 12.9292, "longitude": 79.3322, "district": "ranipet",
        "names": {"en": "Ranipet", "ta": "இராணிப்பேட்டை", "hi": "रानीपेट"}},
    # osm node/1053978493
    "sivaganga": {"latitude": 9.8487, "longitude": 78.4870, "district": "sivaganga",
        "names": {"en": "Sivaganga", "ta": "சிவகங்கை", "hi": "शिवगंगा"}},
    # osm node/245582256
    "tenkasi": {"latitude": 8.9568, "longitude": 77.3121, "district": "tenkasi",
        "names": {"en": "Tenkasi", "ta": "தென்காசி", "hi": "तेंकाशी"}},
    # osm node/245587589
    "thanjavur": {"latitude": 10.7860, "longitude": 79.1381, "district": "thanjavur",
        "names": {"en": "Thanjavur", "ta": "தஞ்சாவூர்", "hi": "तंजावुर"}},
    # osm way/84638887
    "theni": {"latitude": 10.0108, "longitude": 77.4810, "district": "theni",
        "names": {"en": "Theni", "ta": "தேனி", "hi": "तेनी"}},
    # osm node/5443775116
    "thoothukudi": {"latitude": 8.8053, "longitude": 78.1453, "district": "thoothukudi",
        "names": {"en": "Thoothukudi", "ta": "தூத்துக்குடி", "hi": "तूतुकुडी"}},
    # osm node/245581857
    "tirunelveli": {"latitude": 8.7332, "longitude": 77.7103, "district": "tirunelveli",
        "names": {"en": "Tirunelveli", "ta": "திருநெல்வேலி", "hi": "तिरूनेलवेली"}},
    # osm node/4685494147; Hindi: wikidata Q1109865
    "tirupathur": {"latitude": 12.4909, "longitude": 78.5647, "district": "tirupathur",
        "names": {"en": "Tirupathur", "ta": "திருப்பத்தூர்", "hi": "तिरुपत्तुर"}},
    # osm node/335885603; Hindi: wikidata Q608181
    "tiruvallur": {"latitude": 13.1394, "longitude": 79.9071, "district": "tiruvallur",
        "names": {"en": "Tiruvallur", "ta": "திருவள்ளூர்", "hi": "तिरुवल्लुर"}},
    # osm way/84649892
    "tiruvannamalai": {"latitude": 12.2343, "longitude": 79.0762, "district": "tiruvannamalai",
        "names": {"en": "Tiruvannamalai", "ta": "திருவண்ணாமலை", "hi": "तिरुवन्नमलई"}},
    # osm node/3829101958; Hindi: wikidata Q1025399
    "tiruvarur": {"latitude": 10.7667, "longitude": 79.6352, "district": "tiruvarur",
        "names": {"en": "Tiruvarur", "ta": "திருவாரூர்", "hi": "तिरुवारूर"}},
    # osm node/243713144
    "vellore": {"latitude": 12.9072, "longitude": 79.1310, "district": "vellore",
        "names": {"en": "Vellore", "ta": "வேலூர்", "hi": "वेल्लोर"}},
    # wikidata Q1325683
    "viluppuram": {"latitude": 11.9333, "longitude": 79.4833, "district": "viluppuram",
        "names": {"en": "Viluppuram", "ta": "விழுப்புரம்", "hi": "विलुप्पुरम"}},
    # osm node/245584469; Hindi: wikidata Q937745
    "virudhunagar": {"latitude": 9.5822, "longitude": 77.9537, "district": "virudhunagar",
        "names": {"en": "Virudhunagar", "ta": "விருதுநகர்", "hi": "विरुधुनगर"}},
}
