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
