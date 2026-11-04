"""Offline mirror of the seeded catalogue.

When ``DATABASE_URL`` is unset the API serves the taxonomy and schemes
from here, so the whole pipeline can be exercised without Supabase.

This file and ``db/003_seed.sql`` describe the same catalogue.
``tests/test_catalogue_sync.py`` parses the SQL and fails if the two drift, so
adding a skill or a scheme means editing both -- the test will tell you
if you forgot.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class TaxonomyEntry(TypedDict):
    code: str
    name: str
    category: str
    hint: str
    aliases: list[str]


class SchemeEntry(TypedDict):
    source_reference: str
    # NotRequired rather than total=False: every other field here is still
    # mandatory. A district opening has no government page, and inventing
    # one would be worse than leaving it out.
    official_url: NotRequired[str]
    title: str
    organization: str
    location: str
    district: str
    type: str
    minimum_experience: float
    certifications_required: list[str]
    salary_min: int | None
    salary_max: int | None
    nsqf_level: str | None
    description: str
    skills: list[tuple[str, float, bool]]  # (skill code, weight, is_essential)
    # "all" (the default): the work needs every listed skill, weighted -- a
    # welding job. "any": one listed trade is enough -- PM Vishwakarma covers
    # eighteen trades and a tailor fits it fully. See matching.skill_similarity.
    skill_match: NotRequired[str]


TAXONOMY: list[TaxonomyEntry] = [
    {"code": "SK001", "name": "Two-Wheeler Repair", "category": "Mechanical",
     "hint": "Fixing bikes and scooters -- brakes, clutch, chain, general service.",
     "aliases": ["bike repair", "bike mechanic", "two wheeler mechanic", "scooter repair",
                 "motorcycle repair", "बाइक रिपेयर", "बाइक मैकेनिक", "दोपहिया मरम्मत",
                 "மோட்டார் சைக்கிள் ரிப்பேர்", "பைக் ரிப்பேர்", "இருசக்கர வாகன பழுது"]},
    {"code": "SK002", "name": "Four-Wheeler Repair", "category": "Mechanical",
     "hint": "Car and light vehicle servicing.",
     "aliases": ["car mechanic", "car repair", "four wheeler mechanic", "कार मैकेनिक",
                 "गाड़ी रिपेयर", "கார் மெக்கானிக்"]},
    {"code": "SK003", "name": "Heavy Vehicle Maintenance", "category": "Mechanical",
     "hint": "Trucks, buses and tractors.",
     "aliases": ["truck mechanic", "lorry repair", "bus maintenance", "ट्रक मैकेनिक",
                 "லாரி ரிப்பேர்"]},
    {"code": "SK014", "name": "Engine Diagnostics", "category": "Mechanical",
     "hint": "Finding the fault -- by sound, by feel, or with a tester.",
     "aliases": ["engine problem finding", "engine fault", "diagnose engine", "engine sound",
                 "इंजन जाँच", "इंजन की दिक्कत पहचानना", "எஞ்சின் கோளாறு கண்டறிதல்",
                 "எஞ்சின் சத்தம்"]},
    {"code": "SK015", "name": "Vehicle Electrical Work", "category": "Mechanical",
     "hint": "Wiring, battery, lights and starter on vehicles.",
     "aliases": ["auto electrician", "vehicle wiring", "battery work", "ऑटो इलेक्ट्रीशियन",
                 "வாகன வயரிங்"]},
    {"code": "SK022", "name": "Welding", "category": "Metalwork",
     "hint": "Joining metal. Includes arc, gas and spot welding.",
     "aliases": ["welding", "welder", "gas welding", "arc welding", "वेल्डिंग", "वेल्डर",
                 "வெல்டிங்"]},
    {"code": "SK023", "name": "Arc Welding", "category": "Metalwork",
     "hint": "Stick / MMA welding with an electrode -- gates, grills, frames.",
     "aliases": ["arc welding", "stick welding", "MMA welding", "electrode welding",
                 "आर्क वेल्डिंग", "ஆர்க் வெல்டிங்"]},
    {"code": "SK024", "name": "Gas Welding", "category": "Metalwork",
     "hint": "Oxy-acetylene welding and cutting -- sheet metal, pipes, repairs.",
     "aliases": ["gas welding", "oxy welding", "cutting torch", "गैस वेल्डिंग",
                 "கேஸ் வெல்டிங்"]},
    {"code": "SK025", "name": "Sheet Metal Fabrication", "category": "Metalwork",
     "hint": "Cutting, bending and shaping sheet metal.",
     "aliases": ["sheet metal", "fabrication", "denting", "शीट मेटल", "தகடு வேலை"]},
    {"code": "SK026", "name": "Lathe / Machining", "category": "Metalwork",
     "hint": "Turning and shaping parts on a lathe.",
     "aliases": ["lathe operator", "turner", "machining", "लेथ मशीन", "லேத் ஆபரேட்டர்"]},
    {"code": "SK031", "name": "Electrical Wiring", "category": "Electrical",
     "hint": "House and shop wiring, switchboards, fittings.",
     "aliases": ["electrician", "house wiring", "electric work", "इलेक्ट्रीशियन",
                 "बिजली का काम", "எலெக்ட்ரீஷியன்", "வயரிங்"]},
    {"code": "SK032", "name": "Appliance Repair", "category": "Electrical",
     "hint": "Fans, mixers, motors, small household appliances.",
     "aliases": ["appliance repair", "motor rewinding", "fan repair", "मोटर रिवाइंडिंग",
                 "மோட்டார் ரிப்பேர்"]},
    {"code": "SK033", "name": "Air Conditioning and Refrigeration", "category": "Electrical",
     "hint": "AC and fridge installation and servicing.",
     "aliases": ["AC repair", "fridge repair", "refrigeration", "एसी रिपेयर", "ஏசி ரிப்பேர்"]},
    {"code": "SK041", "name": "Masonry", "category": "Construction",
     "hint": "Brickwork, plastering, concrete.",
     "aliases": ["mason", "brick work", "plastering", "राजमिस्त्री", "मिस्त्री", "கொத்தனார்"]},
    {"code": "SK042", "name": "Carpentry", "category": "Construction",
     "hint": "Woodwork -- doors, windows, furniture, frames.",
     "aliases": ["carpenter", "wood work", "furniture making", "बढ़ई", "लकड़ी का काम",
                 "தச்சு வேலை"]},
    {"code": "SK043", "name": "Painting (Building)", "category": "Construction",
     "hint": "Wall painting, putty, finishing.",
     "aliases": ["painter", "wall painting", "पेंटर", "पुताई", "பெயிண்டிங்"]},
    {"code": "SK044", "name": "Plumbing", "category": "Construction",
     "hint": "Pipes, taps, tanks, bathroom fittings.",
     "aliases": ["plumber", "pipe fitting", "प्लंबर", "नल का काम", "பிளம்பர்"]},
    {"code": "SK045", "name": "Bar Bending and Steel Fixing", "category": "Construction",
     "hint": "Cutting and tying reinforcement steel on site.",
     "aliases": ["bar bender", "steel fixer", "सरिया बांधना", "கம்பி வளைத்தல்"]},
    {"code": "SK051", "name": "Tailoring", "category": "Textile",
     "hint": "Stitching garments to measure.",
     "aliases": ["tailor", "stitching", "sewing", "दर्जी", "सिलाई", "தையல்"]},
    {"code": "SK052", "name": "Embroidery", "category": "Textile",
     "hint": "Hand and machine embroidery work.",
     "aliases": ["embroidery", "zari work", "कढ़ाई", "எம்பிராய்டரி"]},
    {"code": "SK053", "name": "Power Loom Operation", "category": "Textile",
     "hint": "Running and minding power looms.",
     "aliases": ["power loom", "loom operator", "पावरलूम", "விசைத்தறி"]},
    {"code": "SK054", "name": "Textile Machine Maintenance", "category": "Textile",
     "hint": "Keeping looms and spinning machines running.",
     "aliases": ["loom mechanic", "textile machine repair", "लूम मैकेनिक", "தறி மெக்கானிக்"]},
    {"code": "SK061", "name": "Cooking (Commercial)", "category": "Hospitality",
     "hint": "Cooking at scale -- hotel, canteen, catering.",
     "aliases": ["cook", "chef", "catering", "हलवाई", "रसोइया", "சமையல்", "குக்"]},
    {"code": "SK062", "name": "Baking", "category": "Hospitality",
     "hint": "Bread, buns, cakes and bakery items.",
     "aliases": ["baker", "bakery work", "बेकरी", "பேக்கரி"]},
    {"code": "SK063", "name": "Housekeeping", "category": "Hospitality",
     "hint": "Cleaning and upkeep in hotels, hospitals, offices.",
     "aliases": ["housekeeping", "cleaning staff", "हाउसकीपिंग", "சுத்தம் செய்தல்"]},
    {"code": "SK071", "name": "Farming and Crop Production", "category": "Agriculture",
     "hint": "Growing crops -- sowing, irrigation, harvest.",
     "aliases": ["farming", "agriculture", "cultivation", "खेती", "किसानी", "விவசாயம்"]},
    {"code": "SK072", "name": "Dairy and Livestock", "category": "Agriculture",
     "hint": "Cattle rearing, milking, animal care.",
     "aliases": ["dairy", "cattle rearing", "milking", "डेयरी", "पशुपालन",
                 "கால்நடை வளர்ப்பு"]},
    {"code": "SK073", "name": "Poultry Farming", "category": "Agriculture",
     "hint": "Raising chickens for eggs or meat.",
     "aliases": ["poultry", "chicken farming", "मुर्गी पालन", "கோழி வளர்ப்பு"]},
    {"code": "SK074", "name": "Farm Machinery Operation", "category": "Agriculture",
     "hint": "Tractors, tillers, harvesters.",
     "aliases": ["tractor driving", "tiller", "farm machinery", "ट्रैक्टर चलाना",
                 "டிராக்டர் ஓட்டுதல்"]},
    {"code": "SK081", "name": "Driving (Light Motor Vehicle)", "category": "Transport",
     "hint": "Driving cars, vans and small goods vehicles.",
     "aliases": ["driver", "car driving", "LMV", "ड्राइवर", "गाड़ी चलाना", "டிரைவர்"]},
    {"code": "SK082", "name": "Driving (Heavy Vehicle)", "category": "Transport",
     "hint": "Driving lorries and buses.",
     "aliases": ["heavy driver", "lorry driver", "truck driving", "ट्रक ड्राइवर",
                 "லாரி டிரைவர்"]},
    {"code": "SK083", "name": "Loading and Material Handling", "category": "Transport",
     "hint": "Loading, unloading and moving goods.",
     "aliases": ["loading", "unloading", "hamali", "लोडिंग", "சுமை ஏற்றுதல்"]},
    {"code": "SK091", "name": "Retail Sales", "category": "Commerce",
     "hint": "Selling in a shop, handling customers and stock.",
     "aliases": ["shop work", "salesman", "counter work", "दुकान का काम", "सेल्समैन",
                 "கடை வேலை"]},
    {"code": "SK092", "name": "Shop Bookkeeping", "category": "Commerce",
     "hint": "Keeping accounts and daily records for a small business.",
     "aliases": ["accounts", "bookkeeping", "billing", "हिसाब किताब", "கணக்கு வேலை"]},
    {"code": "SK093", "name": "Inventory and Stock Handling", "category": "Commerce",
     "hint": "Tracking what comes in and goes out of a store.",
     "aliases": ["stock keeping", "store keeper", "godown", "स्टोर कीपर",
                 "சரக்கு பராமரிப்பு"]},
    {"code": "SK094", "name": "Small Business Management", "category": "Commerce",
     "hint": "Running your own shop or unit end to end.",
     "aliases": ["own shop", "self employment", "business", "अपना धंधा", "சொந்த தொழில்"]},
    {"code": "SK101", "name": "Mobile Phone Repair", "category": "Electronics",
     "hint": "Screen, battery and board-level phone repair.",
     "aliases": ["mobile repair", "phone repair", "मोबाइल रिपेयर", "மொபைல் ரிப்பேர்"]},
    {"code": "SK102", "name": "Computer Hardware Repair", "category": "Electronics",
     "hint": "Assembling and fixing desktops and laptops.",
     "aliases": ["computer repair", "hardware", "कंप्यूटर रिपेयर", "கம்ப்யூட்டர் ரிப்பேர்"]},
    {"code": "SK103", "name": "Basic Computer Operation", "category": "Electronics",
     "hint": "Typing, internet, forms, basic office software.",
     "aliases": ["computer knowledge", "typing", "MS Office", "कंप्यूटर चलाना",
                 "கம்ப்யூட்டர் அறிவு"]},
    {"code": "SK108", "name": "Customer Handling", "category": "Service",
     "hint": "Talking to customers, understanding what they need.",
     "aliases": ["customer service", "talking to customers", "dealing with people",
                 "ग्राहक व्यवहार", "ग्राहकों से बात", "வாடிக்கையாளர் கையாளுதல்",
                 "கஸ்டமர் சர்வீஸ்"]},
    {"code": "SK109", "name": "Team Supervision", "category": "Service",
     "hint": "Leading a small crew and organising the day's work.",
     "aliases": ["supervisor", "team lead", "foreman", "सुपरवाइजर", "மேற்பார்வையாளர்"]},
    {"code": "SK110", "name": "Security Services", "category": "Service",
     "hint": "Guarding premises, gate duty, patrolling.",
     "aliases": ["security guard", "watchman", "गार्ड", "चौकीदार", "செக்யூரிட்டி"]},
    {"code": "SK111", "name": "Beauty and Wellness", "category": "Service",
     "hint": "Salon work -- hair, skin, grooming.",
     "aliases": ["beautician", "salon", "parlour", "ब्यूटीशियन", "பியூட்டீஷியன்"]},
    {"code": "SK112", "name": "Healthcare Support", "category": "Service",
     "hint": "Assisting patients and nursing staff.",
     "aliases": ["ward boy", "nursing assistant", "patient care", "नर्सिंग सहायक",
                 "மருத்துவ உதவியாளர்"]},

    # -- Added 2026-11-04 -------------------------------------------------
    # The trades the national schemes name. PM Vishwakarma's eighteen are
    # listed in its official release (PIB 1959098): carpenter, mason and tailor
    # were already here; the rest are below, most under "Traditional Crafts".
    # PM SVANidhi names street vending, NAMASTE sanitation work and waste
    # picking. Each carries the words people use for the work, in all three
    # languages, because normalization reaches a skill through its aliases.
    {"code": "SK034", "name": "Solar Panel Installation", "category": "Electrical",
     "hint": "Fitting and wiring rooftop solar panels.",
     "aliases": ["solar panel fitting", "solar installer", "rooftop solar", "solar technician",
                 "सोलर पैनल लगाना", "सोलर मिस्त्री", "சோலார் பேனல் பொருத்துதல்", "சோலார் வேலை"]},
    {"code": "SK055", "name": "Handloom Weaving", "category": "Textile",
     "hint": "Weaving cloth on a hand-operated loom.",
     "aliases": ["handloom", "weaver", "hand weaving", "saree weaving", "हथकरघा", "बुनकर",
                 "कपड़ा बुनना", "கைத்தறி", "நெசவு", "நெசவாளர்", "தறி நெய்தல்"]},
    {"code": "SK064", "name": "Food Processing", "category": "Hospitality",
     "hint": "Making pickles, papad, snacks, spice powders and similar food for sale.",
     "aliases": ["pickle making", "papad making", "snacks making", "masala powder",
                 "अचार बनाना", "पापड़ बनाना", "नमकीन बनाना", "ஊறுகாய் தயாரித்தல்",
                 "அப்பளம் தயாரித்தல்", "மசாலா பொடி"]},
    {"code": "SK075", "name": "Fishing", "category": "Agriculture",
     "hint": "Catching fish from sea, river or pond, by boat or net.",
     "aliases": ["fisherman", "fishing", "fish catching", "boat fishing", "मछली पकड़ना",
                 "मछुआरा", "மீன்பிடித்தல்", "மீனவர்", "மீன் பிடிப்பு"]},
    {"code": "SK095", "name": "Street Vending", "category": "Commerce",
     "hint": "Selling goods or food from a cart, stall or footpath, or moving place to place.",
     "aliases": ["street vendor", "hawker", "cart vendor", "vegetable vendor", "fruit seller",
                 "tea stall", "ठेला", "रेहड़ी", "फेरीवाला", "सब्ज़ी बेचना", "தள்ளுவண்டி வியாபாரம்",
                 "தெருவோர வியாபாரம்", "காய்கறி விற்பனை", "டீ கடை"]},
    {"code": "SK113", "name": "Barbering", "category": "Service",
     "hint": "Haircuts and shaving.",
     "aliases": ["barber", "hair cutting", "shaving", "naai", "saloon", "नाई", "बाल काटना",
                 "हजामत", "முடி திருத்துதல்", "நாவிதர்", "சவரம்", "முடி வெட்டுதல்"]},
    {"code": "SK114", "name": "Washing and Ironing", "category": "Service",
     "hint": "Laundry -- washing, starching and ironing clothes.",
     "aliases": ["washerman", "dhobi", "laundry", "ironing", "press wala", "धोबी", "कपड़े धोना",
                 "इस्त्री", "प्रेस करना", "சலவை", "வண்ணார்", "இஸ்திரி", "துணி துவைத்தல்"]},
    {"code": "SK115", "name": "Sanitation Work", "category": "Service",
     "hint": "Cleaning sewers, septic tanks, drains and public toilets.",
     "aliases": ["sanitation worker", "sewer cleaning", "septic tank cleaning",
                 "drain cleaning", "safai karamchari", "सफ़ाई कर्मचारी", "सीवर सफ़ाई",
                 "सेप्टिक टैंक सफ़ाई", "துப்புரவுப் பணி", "சாக்கடை சுத்தம்",
                 "செப்டிக் டேங்க் சுத்தம்", "துப்புரவுத் தொழிலாளி"]},
    {"code": "SK116", "name": "Waste Collection and Recycling", "category": "Service",
     "hint": "Collecting and sorting waste, scrap and recyclables.",
     "aliases": ["waste picker", "rag picker", "scrap collection", "kabadi", "garbage collection",
                 "कचरा बीनना", "कबाड़", "कबाड़ी", "குப்பை சேகரிப்பு", "பழைய பொருள் சேகரிப்பு",
                 "மறுசுழற்சி"]},
    {"code": "SK117", "name": "Domestic Work", "category": "Service",
     "hint": "Cooking, cleaning and caring in other people's homes.",
     "aliases": ["house maid", "domestic help", "house help", "cook in houses", "घरेलू काम",
                 "घर का काम", "बाई", "வீட்டு வேலை", "வீட்டுப் பணியாளர்"]},
    {"code": "SK121", "name": "Boat Making", "category": "Traditional Crafts",
     "hint": "Building and repairing wooden boats.",
     "aliases": ["boat maker", "boat building", "boat repair", "नाव बनाना", "नाव बनाने वाला",
                 "படகு கட்டுதல்", "படகு செய்தல்"]},
    {"code": "SK122", "name": "Armourer (Traditional)", "category": "Traditional Crafts",
     "hint": "Forging traditional weapons, armour and metal implements.",
     "aliases": ["armourer", "armorer", "weapon making", "अस्त्र बनाना", "हथियार बनाने वाला",
                 "ஆயுதம் செய்தல்"]},
    {"code": "SK123", "name": "Blacksmithing", "category": "Traditional Crafts",
     "hint": "Forging iron -- farm tools, implements, repairs.",
     "aliases": ["blacksmith", "lohar", "iron work", "forging", "लोहार", "लोहे का काम",
                 "கொல்லர்", "கொல்லர் வேலை", "இரும்பு அடித்தல்"]},
    {"code": "SK124", "name": "Hammer and Tool Kit Making", "category": "Traditional Crafts",
     "hint": "Making hand tools such as hammers, chisels and sickles.",
     "aliases": ["tool maker", "hammer making", "hand tool making", "औज़ार बनाना",
                 "हथौड़ा बनाना", "கருவி செய்தல்", "சுத்தியல் செய்தல்"]},
    {"code": "SK125", "name": "Locksmithing", "category": "Traditional Crafts",
     "hint": "Making and repairing locks and keys.",
     "aliases": ["locksmith", "key making", "duplicate key", "lock repair", "ताला चाबी",
                 "चाबी बनाना", "ताला बनाना", "பூட்டு சாவி", "சாவி செய்தல்", "பூட்டு பழுது"]},
    {"code": "SK126", "name": "Goldsmithing", "category": "Traditional Crafts",
     "hint": "Making and repairing gold and silver jewellery.",
     "aliases": ["goldsmith", "jewellery making", "jeweller", "sonar", "सुनार", "गहने बनाना",
                 "பொற்கொல்லர்", "ஆசாரி", "நகை செய்தல்", "நகை வேலை"]},
    {"code": "SK127", "name": "Pottery", "category": "Traditional Crafts",
     "hint": "Shaping and firing clay pots, lamps and tiles.",
     "aliases": ["potter", "kumhar", "clay pots", "pot making", "कुम्हार", "मिट्टी के बर्तन",
                 "குயவர்", "மண்பாண்டம்", "மண்பானை செய்தல்"]},
    {"code": "SK128", "name": "Sculpture and Stone Carving", "category": "Traditional Crafts",
     "hint": "Carving idols and figures in stone or other material.",
     "aliases": ["sculptor", "stone carver", "idol making", "moortikar", "मूर्तिकार",
                 "मूर्ति बनाना", "पत्थर तराशना", "சிற்பி", "சிற்ப வேலை", "கல் செதுக்குதல்"]},
    {"code": "SK129", "name": "Stone Breaking", "category": "Traditional Crafts",
     "hint": "Breaking and dressing stone by hand, in quarries or on site.",
     "aliases": ["stone breaker", "quarry work", "stone cutting", "पत्थर तोड़ना",
                 "पत्थर तोड़ने का काम", "கல் உடைத்தல்", "கல் உடைப்பு", "குவாரி வேலை"]},
    {"code": "SK130", "name": "Footwear Making and Repair", "category": "Traditional Crafts",
     "hint": "Making and mending shoes and sandals; leather work.",
     "aliases": ["cobbler", "shoe repair", "shoemaker", "chappal repair", "leather work",
                 "मोची", "जूते बनाना", "जूता मरम्मत", "செருப்பு தைத்தல்", "காலணி பழுது",
                 "தோல் வேலை"]},
    {"code": "SK131", "name": "Basket, Mat, Broom and Coir Weaving", "category": "Traditional Crafts",
     "hint": "Weaving baskets, mats and brooms; coir rope and products.",
     "aliases": ["basket weaving", "mat weaving", "broom making", "coir work", "bamboo work",
                 "टोकरी बुनना", "चटाई बुनना", "झाड़ू बनाना", "கூடை முடைதல்", "பாய் நெய்தல்",
                 "துடைப்பம் செய்தல்", "கயிறு திரித்தல்"]},
    {"code": "SK132", "name": "Traditional Doll and Toy Making", "category": "Traditional Crafts",
     "hint": "Making dolls and toys by hand in wood, clay or cloth.",
     "aliases": ["toy maker", "doll making", "wooden toys", "खिलौने बनाना", "गुड़िया बनाना",
                 "பொம்மை செய்தல்", "மரப்பொம்மை"]},
    {"code": "SK133", "name": "Garland Making", "category": "Traditional Crafts",
     "hint": "Stringing flower garlands for sale, temples and functions.",
     "aliases": ["garland maker", "flower garland", "malakar", "flower stringing", "माला बनाना",
                 "फूलों की माला", "மாலை கட்டுதல்", "பூ கட்டுதல்", "பூமாலை"]},
    {"code": "SK134", "name": "Fishing Net Making", "category": "Traditional Crafts",
     "hint": "Knotting and mending fishing nets.",
     "aliases": ["net maker", "net mending", "fishing net", "जाल बनाना", "मछली का जाल",
                 "வலை பின்னுதல்", "மீன் வலை"]},
]


SCHEMES: list[SchemeEntry] = [
    {"source_reference": "OGD/TN/SLM/AUTO/2024/0117",
     "title": "Two-Wheeler Service Technician", "organization": "Ratnam Auto Works",
     "location": "Salem", "district": "Salem", "type": "Full-time",
     "minimum_experience": 2, "certifications_required": [],
     "salary_min": 14000, "salary_max": 18000, "nsqf_level": "4",
     "description": "Servicing and repair of motorcycles and scooters at a workshop in "
                    "Salem town. Two years of hands-on repair experience expected. No "
                    "formal certificate required -- the workshop trains on the job. "
                    "Six-day week.",
     "skills": [("SK001", 1.00, True), ("SK014", 0.80, True), ("SK108", 0.40, False)]},

    {"source_reference": "PMAJAY/SKILL/TN/SLM/ITI/2024/0042",
     "title": "Advanced Two-Wheeler Mechanic Training", "organization": "Government ITI Salem",
     "location": "Salem", "district": "Salem", "type": "Training",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": 3000, "salary_max": 3000, "nsqf_level": "4",
     "description": "Four-month certificate course in advanced two-wheeler mechanics. "
                    "Monthly stipend of Rs 3,000. No course fee for SC candidates under "
                    "PM-AJAY. Certificate is NSQF Level 4 aligned.",
     "skills": [("SK001", 1.00, True), ("SK014", 0.70, False)]},

    {"source_reference": "PMAJAY/LIV/TN/SLM/2024/0008",
     "title": "Own Workshop Setup Support", "organization": "PM-AJAY Livelihood Cell",
     "location": "Salem", "district": "Salem", "type": "Self-employment support",
     "minimum_experience": 3, "certifications_required": [],
     "salary_min": None, "salary_max": 200000, "nsqf_level": None,
     "description": "Capital support of up to Rs 2,00,000 for setting up an independent "
                    "repair workshop. Applicants should have practical trade experience "
                    "and some exposure to running a shop. Support is disbursed in two "
                    "tranches against a simple business plan.",
     "skills": [("SK001", 0.80, True), ("SK094", 0.90, True), ("SK108", 0.60, False)]},

    {"source_reference": "OGD/TN/ERD/TRANS/2024/0233",
     "title": "Light Motor Vehicle Assistant", "organization": "Kongu Transport",
     "location": "Erode", "district": "Erode", "type": "Full-time",
     "minimum_experience": 1, "certifications_required": [],
     "salary_min": 12000, "salary_max": 15000, "nsqf_level": "3",
     "description": "Assisting with maintenance and running repairs on a light commercial "
                    "vehicle fleet in Erode. Mechanical aptitude expected; heavy vehicle "
                    "experience is not required.",
     "skills": [("SK002", 0.90, True), ("SK014", 0.80, True)]},

    {"source_reference": "OGD/TN/SLM/AUTO/2024/0189",
     "title": "Auto Electrician", "organization": "Sri Balaji Motors",
     "location": "Salem", "district": "Salem", "type": "Full-time",
     "minimum_experience": 2, "certifications_required": [],
     "salary_min": 15000, "salary_max": 20000, "nsqf_level": "4",
     "description": "Vehicle electrical work -- wiring, battery, lighting and starter "
                    "systems -- for two and four wheelers. Prior workshop experience "
                    "expected.",
     "skills": [("SK015", 1.00, True), ("SK014", 0.60, False), ("SK001", 0.50, False)]},

    {"source_reference": "OGD/TN/SLM/FAB/2024/0074",
     "title": "Welder (Fabrication Unit)", "organization": "Annai Steel Fabricators",
     "location": "Salem", "district": "Salem", "type": "Full-time",
     "minimum_experience": 1, "certifications_required": [],
     "salary_min": 16000, "salary_max": 21000, "nsqf_level": "4",
     "description": "Arc and gas welding on gates, grills and structural frames. "
                    "Fabrication unit on the Salem-Attur road. Safety gear provided.",
     "skills": [("SK023", 1.00, True), ("SK024", 0.80, False), ("SK025", 0.60, False)]},

    {"source_reference": "PMAJAY/SKILL/TN/SLM/ITI/2024/0051",
     "title": "Welding Certification Course (NSQF 4)", "organization": "Government ITI Salem",
     "location": "Salem", "district": "Salem", "type": "Training",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": 2500, "salary_max": 2500, "nsqf_level": "4",
     "description": "Three-month welding certificate course with a monthly stipend of "
                    "Rs 2,500. Fee waived for SC candidates under PM-AJAY.",
     "skills": [("SK022", 1.00, True)]},

    {"source_reference": "OGD/TN/SLM/RET/2024/0311",
     "title": "Retail Counter Assistant", "organization": "Sakthi Spare Parts",
     "location": "Salem", "district": "Salem", "type": "Full-time",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": 11000, "salary_max": 13000, "nsqf_level": "3",
     "description": "Counter sales of automobile spare parts. Involves handling customers "
                    "and keeping stock records. Familiarity with vehicle parts is an "
                    "advantage.",
     "skills": [("SK091", 1.00, True), ("SK108", 0.80, True), ("SK093", 0.60, False)]},

    {"source_reference": "OGD/TN/ERD/TEX/2024/0402",
     "title": "Machine Operator (Power Loom)", "organization": "Erode Textile Mills",
     "location": "Erode", "district": "Erode", "type": "Full-time",
     "minimum_experience": 1, "certifications_required": [],
     "salary_min": 13000, "salary_max": 16000, "nsqf_level": "3",
     "description": "Operating and minding power looms on a shift basis. Training "
                    "provided for the first month.",
     "skills": [("SK053", 1.00, True)]},

    {"source_reference": "OGD/TN/ERD/TEX/2024/0403",
     "title": "Loom Maintenance Technician", "organization": "Erode Textile Mills",
     "location": "Erode", "district": "Erode", "type": "Full-time",
     "minimum_experience": 2, "certifications_required": [],
     "salary_min": 15000, "salary_max": 19000, "nsqf_level": "4",
     "description": "Keeping power looms and spinning machines running. Mechanical repair "
                    "background expected; loom-specific training is given on site.",
     "skills": [("SK054", 1.00, True), ("SK026", 0.50, False)]},

    {"source_reference": "OGD/TN/SLM/CON/2024/0155",
     "title": "Electrician (Building Sites)", "organization": "Vetri Constructions",
     "location": "Salem", "district": "Salem", "type": "Full-time",
     "minimum_experience": 2, "certifications_required": [],
     "salary_min": 15000, "salary_max": 19000, "nsqf_level": "4",
     "description": "House and commercial wiring on residential sites across Salem "
                    "district.",
     "skills": [("SK031", 1.00, True)]},

    {"source_reference": "PMAJAY/LIV/TN/SLM/2024/0011",
     "title": "Tailoring Unit Support", "organization": "PM-AJAY Livelihood Cell",
     "location": "Salem", "district": "Salem", "type": "Self-employment support",
     "minimum_experience": 1, "certifications_required": [],
     "salary_min": None, "salary_max": 100000, "nsqf_level": None,
     "description": "Capital support of up to Rs 1,00,000 for setting up a tailoring "
                    "unit, including machine purchase. Basic stitching experience "
                    "expected.",
     "skills": [("SK051", 1.00, True), ("SK094", 0.70, False)]},

    {"source_reference": "PMAJAY/SKILL/TN/SLM/DSC/2024/0027",
     "title": "Mobile Phone Repair Training", "organization": "District Skill Centre",
     "location": "Salem", "district": "Salem", "type": "Training",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": 2000, "salary_max": 2000, "nsqf_level": "3",
     "description": "Two-month course in mobile phone repair with a monthly stipend of "
                    "Rs 2,000. Includes screen, battery and basic board-level work.",
     "skills": [("SK101", 1.00, True)]},

    {"source_reference": "OGD/TN/ERD/TRANS/2024/0240",
     "title": "Driver (Light Commercial Vehicle)", "organization": "Kongu Transport",
     "location": "Erode", "district": "Erode", "type": "Full-time",
     "minimum_experience": 2, "certifications_required": ["LMV Driving Licence"],
     "salary_min": 14000, "salary_max": 17000, "nsqf_level": "3",
     "description": "Driving a light goods vehicle on district routes. A valid LMV "
                    "licence is required.",
     "skills": [("SK081", 1.00, True)]},

    {"source_reference": "PMAJAY/LIV/TN/SLM/2024/0019",
     "title": "Dairy Unit Support", "organization": "PM-AJAY Livelihood Cell",
     "location": "Attur", "district": "Salem", "type": "Self-employment support",
     "minimum_experience": 1, "certifications_required": [],
     "salary_min": None, "salary_max": 150000, "nsqf_level": None,
     "description": "Capital support of up to Rs 1,50,000 towards cattle purchase and "
                    "shed construction for a small dairy unit.",
     "skills": [("SK072", 1.00, True), ("SK094", 0.60, False)]},

    {"source_reference": "OGD/TN/SLM/HLT/2024/0088",
     "title": "Housekeeping Supervisor", "organization": "Salem Multispeciality Hospital",
     "location": "Salem", "district": "Salem", "type": "Full-time",
     "minimum_experience": 3, "certifications_required": [],
     "salary_min": 14000, "salary_max": 17000, "nsqf_level": "4",
     "description": "Supervising a housekeeping team across hospital wards. Experience of "
                    "leading a small crew is expected.",
     "skills": [("SK063", 1.00, True), ("SK109", 0.80, True)]},
]


# ---------------------------------------------------------------------------
# National schemes -- added 2026-11-04
#
# Open to anyone in India who fits them, so location is "All India" and
# matching scores them as available wherever the person is
# (matching.LOCATION_NATIONWIDE). Every description is sentences copied
# exactly from the official release named in official_url or source_reference
# -- the explanation layer grounds itself only in this text, so nothing here
# is paraphrased. The full releases are in data/scheme_docs for the assistant.
#
# Skill weights mean something different under skill_match "any": not a share
# of the work but how squarely the scheme names the trade. 1.0 is a trade the
# official text names (PM Vishwakarma's eighteen, street vending for PM
# SVANidhi). ANY_TRADE is "open to any trade" -- PMKVY, PMEGP, Mudra -- so a
# scheme that names your trade ranks above one that merely admits it, and an
# explanation never claims a scheme was made for your trade when it was made
# for everyone's.
#
# 0.4, measured against the catalogue: a welder's own local fabrication job
# (welding plus sheet metal, half covered) scores 0.74, and a generic national
# scheme at 0.4 scores 0.685 -- below it, as it should be. At 0.6 it scored
# 0.785 and seven of them pushed the job off the first page.
# ---------------------------------------------------------------------------

ANY_TRADE = 0.4

VISHWAKARMA_TRADES = [
    "SK042",  # Carpenter (Suthar/Badhai)
    "SK121",  # Boat Maker
    "SK122",  # Armourer
    "SK123",  # Blacksmith (Lohar)
    "SK124",  # Hammer and Tool Kit Maker
    "SK125",  # Locksmith
    "SK126",  # Goldsmith (Sonar)
    "SK127",  # Potter (Kumhaar)
    "SK128",  # Sculptor (Moortikar, stone carver)
    "SK129",  # Stone breaker
    "SK130",  # Cobbler (Charmkar)/Shoesmith/Footwear artisan
    "SK041",  # Mason (Rajmistri)
    "SK131",  # Basket/Mat/Broom Maker/Coir Weaver
    "SK132",  # Doll & Toy Maker (Traditional)
    "SK113",  # Barber (Naai)
    "SK133",  # Garland maker (Malakaar)
    "SK114",  # Washerman (Dhobi)
    "SK051",  # Tailor (Darzi)
    "SK134",  # Fishing Net Maker
]


def _any_trade(named: dict[str, float] | None = None) -> list[tuple[str, float, bool]]:
    """Every skill at ANY_TRADE, with the ones the scheme names raised."""
    named = named or {}
    return [(e["code"], named.get(e["code"], ANY_TRADE), False) for e in TAXONOMY]


PIB = "https://www.pib.gov.in/PressReleasePage.aspx?PRID="

SCHEMES += [
    {"source_reference": "GOI/PMVISHWAKARMA/2023-09-20",
     "official_url": "https://pmvishwakarma.gov.in/",
     "title": "PM Vishwakarma",
     "organization": "Ministry of Micro, Small & Medium Enterprises",
     "location": "All India", "district": "All India", "type": "Self-employment support",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "PM Vishwakarma, a Central Sector Scheme, was launched on 17 th September, "
                    "2023 by the Prime Minister to provide end-to-end support to artisans and "
                    "craftspeople who work with their hands and tools. Skill Upgradation : Basic "
                    "Training of 5-7 days and Advanced Training of 15 days or more, with a stipend "
                    "of Rs. 500 per day; Toolkit Incentive : A toolkit incentive of upto Rs. 15,000 "
                    "in the form of e-vouchers at the beginning of Basic Skill Training. Credit "
                    "Support : Collateral free ‘Enterprise Development Loans’ of upto Rs. 3 lakh in "
                    "two tranches of Rs. 1 lakh and Rs. 2 lakh with tenures of 18 months and 30 "
                    "months, respectively, at a concessional rate of interest fixed at 5%, with "
                    "Government of India subvention to the extent of 8%. Enrolment of beneficiaries "
                    "shall be done through Common Service Centres with Aadhaar-based biometric "
                    "authentication on PM Vishwakarma portal.",
     "skill_match": "any",
     "skills": [(code, 1.00, False) for code in VISHWAKARMA_TRADES]},

    {"source_reference": "GOI/PMKVY4/2025-02-07",
     "official_url": "https://www.skillindiadigital.gov.in/home",
     "title": "Pradhan Mantri Kaushal Vikas Yojana 4.0 (PMKVY 4.0)",
     "organization": "Ministry of Skill Development and Entrepreneurship",
     "location": "All India", "district": "All India", "type": "Training",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "PMKVY 4.0 scheme provides NSQF aligned skill development training through "
                    "Short-Term Training (STT) including Special Projects (SP) and reskilling and "
                    "upskilling through Recognition of Prior Learning (RPL) with its target "
                    "beneficiary being 15-59 years of age. A key shift under the scheme is the "
                    "integration of On-the-Job Training (OJT) within short-term skilling programs, "
                    "ensuring that trainees gain real-world exposure and industry experience. "
                    "PMKVY 4.0 ensures industry-aligned training with curriculum available in "
                    "multiple regional languages, making skilling more inclusive and accessible.",
     "skill_match": "any",
     "skills": _any_trade()},

    {"source_reference": "GOI/PMNAPS/2025-02-07",
     "official_url": PIB + "2100845",
     "title": "PM National Apprenticeship Promotion Scheme (PM-NAPS)",
     "organization": "Ministry of Skill Development and Entrepreneurship",
     "location": "All India", "district": "All India", "type": "Apprenticeship",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "Apprenticeship training can play a major role for on-the-job vocational "
                    "training where youth can acquire skills by working at actual workplace and "
                    "earn some stipend, at the same time, to financially support himself. To "
                    "support both apprentices and establishments in India, 25% of the stipend, up "
                    "to Rs.1,500 per month per apprentice, will be provided through Direct Benefit "
                    "Transfer (DBT) during the training period, provided by the Central Government. "
                    "The scheme is designed for individuals aged 14 to 35 years, ensuring inclusive "
                    "access to skill development opportunities across various demographics.",
     "skill_match": "any",
     "skills": _any_trade()},

    {"source_reference": "GOI/JSS/2025-12-01",
     "official_url": PIB + "2197057",
     "title": "Jan Shikshan Sansthan (JSS)",
     "organization": "Ministry of Skill Development and Entrepreneurship",
     "location": "All India", "district": "All India", "type": "Training",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "The Jan Shikshan Sansthan (JSS) Scheme, initially launched as Shramik "
                    "Vidyapeeth (SVP) in 1967, aims to provide skill training in a non-formal mode "
                    "at the doorsteps of the beneficiary through registered Societies (NGOs) with "
                    "100% grant from the Government of India. The objective of the scheme is to "
                    "increase the household income by promoting self/wage employment through skill "
                    "development training. The target beneficiaries of the scheme are non-literates, "
                    "neo-literates and persons having rudimentary level of education, school "
                    "dropouts up to class 12th in the age group of 15-45 years. The priority groups "
                    "are women, SCs, STs, OBCs and minorities in the rural areas and urban "
                    "low-income areas.",
     "skill_match": "any",
     "skills": _any_trade()},

    {"source_reference": "GOI/DDUGKY/2026-01-01",
     "official_url": PIB + "2210378",
     "title": "Deen Dayal Upadhyaya Grameen Kaushalya Yojana (DDU-GKY)",
     "organization": "Ministry of Rural Development",
     "location": "All India", "district": "All India", "type": "Training",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "The program occupies a unique position amongst other skill training "
                    "programs, due to its focus on the rural poor youth and its emphasis on "
                    "sustainable employment through the prominence and incentives given to "
                    "post-placement tracking, retention and career progression. Mandatory social "
                    "inclusion: SC/ST (50%), Women (33%), and PwDs (5%). Minimum 70% placement "
                    "(Minimum 50% wage employment and maximum 20% self employment). Salary to the "
                    "placed candidates are given as per the Minimum wages or above. The target "
                    "group for DDU-GKY is poor rural youth in the age group 15-35.",
     "skill_match": "any",
     "skills": _any_trade()},

    {"source_reference": "GOI/RSETI/2026-01-01",
     "official_url": PIB + "2210378",
     "title": "Rural Self Employment Training Institutes (RSETIs)",
     "organization": "Ministry of Rural Development, with sponsor banks",
     "location": "All India", "district": "All India", "type": "Training",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "The Rural Self Employment Training Institutes (RSETIs) are dedicated, "
                    "district-level training center’s set up under the sponsorship of public "
                    "sector/private banks, in collaboration with the Ministry of Rural Development "
                    "(MoRD). The scheme provides free, short-term, residential training to rural "
                    "youth with boarding and lodging facilities. To provide free, residential, "
                    "demand-driven skill training to rural unemployed youth in the age group of "
                    "18–50 years. Post-training, trainees receive handholding support for two "
                    "years to facilitate self-employment, micro-enterprise development, or wage "
                    "employment, with strong emphasis on credit linkage through banks.",
     "skill_match": "any",
     "skills": _any_trade()},

    {"source_reference": "GOI/PMEGP/2026-05-14",
     "official_url": "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/may/"
                     "doc2026514869801.pdf",
     "title": "Prime Minister’s Employment Generation Programme (PMEGP)",
     "organization": "Ministry of Micro, Small & Medium Enterprises, through KVIC",
     "location": "All India", "district": "All India", "type": "Self-employment support",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "PMEGP supports prospective entrepreneurs in establishing new micro-enterprises "
                    "in the non-farm sector by providing Margin Money (MM) subsidy on bank loans. "
                    "The scheme primarily aims to create self-employment opportunities for "
                    "first-generation entrepreneurs and promote sustainable livelihoods in the "
                    "manufacturing and services sectors, especially in rural areas. The maximum "
                    "project cost eligible for Margin Money subsidy is ₹50 lakh for the "
                    "manufacturing sector and ₹20 lakh for the service/business sector. For special "
                    "categories, the subsidy is 35% of the project cost in rural areas. It is 25% "
                    "in urban areas. Special category includes SC/ST, OBC, minorities, women, "
                    "ex-servicemen, persons with disabilities, and applicants from the North-East "
                    "Region, Hill and Border areas.",
     "skill_match": "any",
     "skills": _any_trade({"SK094": 1.00})},

    {"source_reference": "GOI/PMSVANIDHI/2026-05-30",
     "official_url": PIB + "2267102",
     "title": "PM SVANidhi",
     "organization": "Ministry of Housing and Urban Affairs and Department of Financial Services",
     "location": "All India", "district": "All India", "type": "Self-employment support",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "PM SVANidhi is a Central Sector Scheme supporting street vendors through "
                    "affordable working capital, financial inclusion and social protection "
                    "measures. The lending period has been extended until March 2030. Street "
                    "vendors receive collateral-free working capital loans of ₹15,000, ₹25,000 and "
                    "₹50,000 through progressive loan tranches. PM SVANidhi encourages timely and "
                    "early repayment by providing an interest subsidy of 7 percent per annum. A "
                    "street vendor holding a valid Letter of Recommendation or Certificate of "
                    "Vending can apply for a PM SVANidhi loan through the scheme portal or Mobile "
                    "App or with the assistance of Urban Local Bodies (ULBs).",
     "skill_match": "any",
     # The release names street vending, and among street services "barber
     # shops, cobblers, laundry services"; fruit, vegetables and street food
     # among the goods. Only vending itself is the scheme's own trade.
     "skills": [("SK095", 1.00, False), ("SK113", ANY_TRADE, False),
                ("SK130", ANY_TRADE, False), ("SK114", ANY_TRADE, False),
                ("SK091", ANY_TRADE, False), ("SK061", ANY_TRADE, False)]},

    {"source_reference": "GOI/PMMY/2026-04-08",
     "official_url": PIB + "2249915",
     "title": "Pradhan Mantri MUDRA Yojana (PMMY)",
     "organization": "Ministry of Finance, through banks, RRBs, NBFCs and MFIs",
     "location": "All India", "district": "All India", "type": "Self-employment support",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "This initiative has been designed to bridge the gap in financial "
                    "accessibility, offering streamlined, easy collateral-free loans up to ₹20 lakh "
                    "to support small-scale business ventures for non-corporate and non-farm "
                    "income-generating activities. Loans cover term financing and working capital "
                    "needs across manufacturing, trading and service sectors, including activities "
                    "allied to agriculture like poultry, dairy, and beekeeping, etc. The interest "
                    "rate is governed by RBI guidelines, with flexible repayment terms.",
     "skill_match": "any",
     "skills": _any_trade({"SK094": 1.00})},

    {"source_reference": "GOI/NAMASTE/2026-07-20",
     "official_url": PIB + "2286726",
     "title": "National Action for Mechanised Sanitation Ecosystem (NAMASTE)",
     "organization": "Ministry of Social Justice and Empowerment, with the Ministry of Housing "
                     "and Urban Affairs",
     "location": "All India", "district": "All India", "type": "Self-employment support",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "The main aim of this scheme is to ensure the safety, dignity, and social "
                    "security of sanitation workers and to promote safe, machine-based sanitation "
                    "across the country. Its main goal is to completely end the dangerous practice "
                    "of manually cleaning sewers and septic tanks. Under the NAMASTE Scheme, "
                    "sanitation workers are being identified and provided with Personal Protective "
                    "Equipment (PPE) kits, health insurance, Ayushman Bharat benefits, safety "
                    "training, skill development, financial support for self-employment, and "
                    "access to modern sanitation machines.",
     "skill_match": "any",
     "skills": [("SK115", 1.00, False), ("SK116", 1.00, False)]},

    {"source_reference": "GOI/PMDAKSH/2026-03-11",
     "official_url": PIB + "2238229",
     "title": "PM-DAKSH (Pradhan Mantri Dakshata Aur Kushalta Sampann Hitgrahi Yojana)",
     "organization": "Ministry of Social Justice and Empowerment, through NSFDC, NBCFDC and "
                     "NSKFDC",
     "location": "All India", "district": "All India", "type": "Training",
     "minimum_experience": 0, "certifications_required": [],
     "salary_min": None, "salary_max": None, "nsqf_level": None,
     "description": "Pradhan Mantri Dakshata Aur Kushalta Sampann Hitgrahi Yojana (PM-DAKSH) "
                    "Scheme is a Central Sector Scheme to provide skill development training to "
                    "Scheduled Castes, Other Backward Communities, Economically weaker Sections, "
                    "De- Notified Tribes, Safai Karamcharis including Waste Pickers through the "
                    "empaneled training institutes. Under the PM-DAKSH Scheme, National Skills "
                    "Qualifications Framework (NSQF) compliant, employment-oriented Skill "
                    "Development Training Programmes are implemented. Upon completion of the "
                    "training programmes, the trainees are extended assistance for placement in "
                    "wage employment and in the case of trainees opting for self-employment, "
                    "necessary guidance is provided for setting up their own ventures.",
     "skill_match": "any",
     # Safai Karamcharis and waste pickers are named in the release.
     "skills": _any_trade({"SK115": 1.00, "SK116": 1.00})},
]


# What each skill is called in the person's own language.
#
# Without this, a Tamil explanation reads "நீங்கள் Welding செய்கிறீர்கள்" -- a
# Tamil sentence with an English noun dropped into it. The taxonomy code stays
# language-independent (PRD section 3); only the label shown to a person is
# translated. English lives in TAXONOMY["name"] and is the fallback.
DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "SK001": {"ta": "இருசக்கர வாகன பழுது நீக்கம்", "hi": "दोपहिया मरम्मत"},
    "SK002": {"ta": "கார் பழுது நீக்கம்", "hi": "कार मरम्मत"},
    "SK003": {"ta": "கனரக வாகன பராமரிப்பு", "hi": "भारी वाहन रखरखाव"},
    "SK014": {"ta": "எஞ்சின் கோளாறு கண்டறிதல்", "hi": "इंजन जाँच"},
    "SK015": {"ta": "வாகன மின் வேலை", "hi": "वाहन बिजली का काम"},
    "SK022": {"ta": "வெல்டிங்", "hi": "वेल्डिंग"},
    "SK023": {"ta": "ஆர்க் வெல்டிங்", "hi": "आर्क वेल्डिंग"},
    "SK024": {"ta": "கேஸ் வெல்டிங்", "hi": "गैस वेल्डिंग"},
    "SK025": {"ta": "தகடு வேலை", "hi": "शीट मेटल का काम"},
    "SK026": {"ta": "லேத் வேலை", "hi": "लेथ मशीन का काम"},
    "SK031": {"ta": "மின் வயரிங்", "hi": "बिजली की वायरिंग"},
    "SK032": {"ta": "வீட்டு உபகரண பழுது", "hi": "उपकरण मरम्मत"},
    "SK033": {"ta": "ஏசி மற்றும் குளிர்சாதன பணி", "hi": "एसी और फ्रिज का काम"},
    "SK041": {"ta": "கொத்து வேலை", "hi": "राजमिस्त्री का काम"},
    "SK042": {"ta": "தச்சு வேலை", "hi": "बढ़ई का काम"},
    "SK043": {"ta": "கட்டட வர்ணம் பூசுதல்", "hi": "रंगाई-पुताई"},
    "SK044": {"ta": "குழாய் பணி", "hi": "प्लंबिंग"},
    "SK045": {"ta": "கம்பி வளைத்தல்", "hi": "सरिया बांधने का काम"},
    "SK051": {"ta": "தையல் வேலை", "hi": "सिलाई"},
    "SK052": {"ta": "எம்பிராய்டரி", "hi": "कढ़ाई"},
    "SK053": {"ta": "விசைத்தறி இயக்குதல்", "hi": "पावरलूम चलाना"},
    "SK054": {"ta": "தறி இயந்திர பராமரிப்பு", "hi": "लूम मशीन रखरखाव"},
    "SK061": {"ta": "சமையல் வேலை", "hi": "रसोई का काम"},
    "SK062": {"ta": "பேக்கரி வேலை", "hi": "बेकरी का काम"},
    "SK063": {"ta": "சுத்தம் செய்யும் பணி", "hi": "साफ़-सफ़ाई का काम"},
    "SK071": {"ta": "விவசாயம்", "hi": "खेती"},
    "SK072": {"ta": "கால்நடை வளர்ப்பு", "hi": "पशुपालन"},
    "SK073": {"ta": "கோழி வளர்ப்பு", "hi": "मुर्गी पालन"},
    "SK074": {"ta": "பண்ணை இயந்திர இயக்கம்", "hi": "खेती की मशीन चलाना"},
    "SK081": {"ta": "லேசான வாகனம் ஓட்டுதல்", "hi": "हल्का वाहन चलाना"},
    "SK082": {"ta": "கனரக வாகனம் ஓட்டுதல்", "hi": "भारी वाहन चलाना"},
    "SK083": {"ta": "சுமை ஏற்றி இறக்குதல்", "hi": "लोडिंग-अनलोडिंग"},
    "SK091": {"ta": "கடை விற்பனை", "hi": "दुकान की बिक्री"},
    "SK092": {"ta": "கடை கணக்கு வேலை", "hi": "दुकान का हिसाब"},
    "SK093": {"ta": "சரக்கு பராமரிப்பு", "hi": "स्टॉक संभालना"},
    "SK094": {"ta": "சொந்த தொழில் நடத்துதல்", "hi": "अपना काम चलाना"},
    "SK101": {"ta": "மொபைல் போன் பழுது", "hi": "मोबाइल मरम्मत"},
    "SK102": {"ta": "கம்ப்யூட்டர் பழுது", "hi": "कंप्यूटर मरम्मत"},
    "SK103": {"ta": "கம்ப்யூட்டர் பயன்பாடு", "hi": "कंप्यूटर चलाना"},
    "SK108": {"ta": "வாடிக்கையாளர் கையாளுதல்", "hi": "ग्राहक व्यवहार"},
    "SK109": {"ta": "குழு மேற்பார்வை", "hi": "टीम की देखरेख"},
    "SK110": {"ta": "பாதுகாப்புப் பணி", "hi": "सुरक्षा का काम"},
    "SK111": {"ta": "அழகுக் கலை", "hi": "ब्यूटी का काम"},
    "SK112": {"ta": "மருத்துவ உதவிப் பணி", "hi": "मरीज़ की देखभाल"},
    "SK034": {"ta": "சோலார் பேனல் பொருத்துதல்", "hi": "सोलर पैनल लगाना"},
    "SK055": {"ta": "கைத்தறி நெசவு", "hi": "हथकरघा बुनाई"},
    "SK064": {"ta": "உணவுப் பதப்படுத்துதல்", "hi": "खाद्य प्रसंस्करण"},
    "SK075": {"ta": "மீன்பிடித்தல்", "hi": "मछली पकड़ना"},
    "SK095": {"ta": "தெருவோர வியாபாரம்", "hi": "रेहड़ी-पटरी पर बिक्री"},
    "SK113": {"ta": "முடி திருத்துதல்", "hi": "नाई का काम"},
    "SK114": {"ta": "சலவை மற்றும் இஸ்திரி", "hi": "कपड़े धोना और इस्त्री"},
    "SK115": {"ta": "துப்புரவுப் பணி", "hi": "सफ़ाई का काम"},
    "SK116": {"ta": "குப்பை சேகரிப்பு மற்றும் மறுசுழற்சி", "hi": "कचरा संग्रह और रीसाइक्लिंग"},
    "SK117": {"ta": "வீட்டு வேலை", "hi": "घरेलू काम"},
    "SK121": {"ta": "படகு கட்டுதல்", "hi": "नाव बनाना"},
    "SK122": {"ta": "பாரம்பரிய ஆயுதம் செய்தல்", "hi": "पारंपरिक अस्त्र बनाना"},
    "SK123": {"ta": "கொல்லர் வேலை", "hi": "लोहार का काम"},
    "SK124": {"ta": "சுத்தியல் மற்றும் கருவி செய்தல்", "hi": "हथौड़ा और औज़ार बनाना"},
    "SK125": {"ta": "பூட்டு சாவி வேலை", "hi": "ताला-चाबी का काम"},
    "SK126": {"ta": "பொற்கொல்லர் வேலை", "hi": "सुनार का काम"},
    "SK127": {"ta": "மண்பாண்டம் செய்தல்", "hi": "मिट्टी के बर्तन बनाना"},
    "SK128": {"ta": "சிற்ப வேலை", "hi": "मूर्ति और पत्थर की नक्काशी"},
    "SK129": {"ta": "கல் உடைத்தல்", "hi": "पत्थर तोड़ना"},
    "SK130": {"ta": "காலணி செய்தல் மற்றும் பழுது", "hi": "जूते बनाना और मरम्मत"},
    "SK131": {"ta": "கூடை, பாய், துடைப்பம், கயிறு வேலை", "hi": "टोकरी, चटाई, झाड़ू और रस्सी का काम"},
    "SK132": {"ta": "பாரம்பரிய பொம்மை செய்தல்", "hi": "पारंपरिक खिलौने बनाना"},
    "SK133": {"ta": "மாலை கட்டுதல்", "hi": "माला बनाना"},
    "SK134": {"ta": "மீன்பிடி வலை பின்னுதல்", "hi": "मछली का जाल बनाना"},
}


def display_names_for(code: str, english: str) -> dict[str, str]:
    """All labels for a skill, English always present."""
    return {"en": english, **DISPLAY_NAMES.get(code, {})}


def taxonomy_by_code() -> dict[str, TaxonomyEntry]:
    return {entry["code"]: entry for entry in TAXONOMY}


def embedding_text(entry: TaxonomyEntry) -> str:
    """Text embedded for a taxonomy node.

    Aliases are included so that "bike repair", "बाइक रिपेयर" and
    "மோட்டார் சைக்கிள் ரிப்பேர்" all land near the same point in the space --
    that is the whole mechanism behind PRD section 4.3.
    """
    parts: list[Any] = [entry["name"], entry["category"], *entry["aliases"]]
    return " | ".join(str(p) for p in parts if p)
