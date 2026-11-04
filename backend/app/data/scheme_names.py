"""Which scheme a question names, and which documents cover it.

The corpus titles cannot do this on their own: the PM-AJAY guidelines are
stored as "Guidelines", and PMAGY's as "pmagyguidelines". People say the
scheme's name, not the file's, so the names are listed here by hand.

Three uses, all in services/retrieval.py and services/scheme_qa.py:

* **Routing.** A question that names a scheme the documents cover goes to the
  documents, even if it also contains a word like "years" or "pay" that would
  otherwise send it to the listing on screen.
* **Precision.** Retrieval searches only the named scheme's documents. Without
  this, a question about PM-AJAY was answered from an e-Shram help page and
  presented as PM-AJAY's rules.
* **A fallback.** When the language model is unavailable, a passage from the
  named scheme's own document can be quoted with its citation; a passage that
  merely sounds similar cannot.

Names are matched as whole words in Latin script ("ajay" does not match inside
"vijayan") and as substrings in Tamil and Devanagari, where case endings attach
to the name ("சிகரம்தொடு", "विश्वकर्मा के"). Only names that clearly mean one
scheme are listed; an ambiguous abbreviation is worse than none, because it
would narrow a search to the wrong document.

``sources`` must match ``scheme_documents.source`` exactly.
``tests/test_scheme_names.py`` checks that every one is a file in
``data/scheme_docs`` or a recorded URL.
"""

from __future__ import annotations

from typing import TypedDict


class SchemeName(TypedDict):
    names: list[str]
    sources: list[str]


SCHEME_NAMES: dict[str, SchemeName] = {
    "pm-ajay": {
        "names": ["pm-ajay", "pm ajay", "pmajay", "anusuchit jaati abhyuday",
                  "பிஎம் அஜய்", "பி.எம். அஜய்", "பிஎம்-அஜய்",
                  "पीएम अजय", "पीएम-अजय", "पी.एम. अजय"],
        "sources": ["Guidelines.pdf"],
    },
    "pmagy": {
        "names": ["pmagy", "adarsh gram", "आदर्श ग्राम", "ஆதர்ஷ் கிராம்"],
        "sources": ["pmagyguidelines.pdf"],
    },
    "sigaram-thodu": {
        "names": ["sigaram thodu", "sigaram", "naan mudhalvan",
                  "சிகரம் தொடு", "சிகரம்", "நான் முதல்வன்",
                  "सिगरम थोडु", "नान मुधलवन"],
        "sources": ["EOI_Sigaram_Thodu_2024.pdf"],
    },
    "pm-vishwakarma": {
        "names": ["vishwakarma", "விஸ்வகர்மா", "विश्वकर्मा"],
        "sources": ["https://pmvishwakarma.gov.in/"],
    },
    "fund-of-funds": {
        "names": ["fund of funds"],
        "sources": ["Fund_of_Funds_for_Startups_Detailed_Scheme_Information.pdf"],
    },
    "khadi": {
        "names": ["khadi", "kvic", "village industries", "காதி", "खादी"],
        "sources": ["Khadi_and_Village_Industries_Programmes_Detailed_Information.pdf"],
    },
    "nssh": {
        "names": ["nssh", "sc st hub", "sc-st hub", "national sc st hub"],
        "sources": ["National_SC_ST_Hub_NSSH_Detailed_Scheme_Information.pdf"],
    },
    "nlm": {
        "names": ["national livestock mission", "livestock mission"],
        "sources": ["NLMGuidelinesJan2025.pdf"],
    },
    "nmdfc": {
        "names": ["nmdfc"],
        "sources": ["NMDFC_Scheme_Information_Summary.pdf"],
    },
    "nulm-suh": {
        "names": ["nulm", "shelter for urban homeless", "urban homeless"],
        "sources": ["NULM-SUH-Guidelines.pdf"],
    },
    "fishermen": {
        "names": ["fishermen", "fisherman", "மீனவர்", "मछुआरे"],
        "sources": ["PM_Fishermen_Welfare_Programmes_Information_Summary.pdf"],
    },
    "unnati": {
        "names": ["unnati", "உன்னதி", "उन्नति"],
        "sources": ["Project_UNNATI_Rural_Skilling_Detailed_Summary.pdf"],
    },
    "scdc": {
        "names": ["scdc", "scdcs", "scheduled castes development corporation"],
        "sources": ["SCDCs_Scheme_Information_Summary.pdf"],
    },
    "sfurti": {
        "names": ["sfurti"],
        "sources": ["SFURTI_Scheme_Information_Summary.pdf"],
    },
    "smam": {
        "names": ["smam", "sub-mission on agricultural mechanization",
                  "sub mission on agricultural mechanisation",
                  "agricultural mechanization", "agricultural mechanisation",
                  "farm mechanization", "farm mechanisation"],
        "sources": ["SMAM_Detailed_Scheme_Information_Summary.pdf"],
    },
    "startup-india": {
        "names": ["startup india", "startup schemes"],
        "sources": ["Startup-Schemes-Playbook-June-2026.pdf"],
    },
    "pmgsy": {
        "names": ["pmgsy", "gram sadak", "rcplwe"],
        "sources": ["PMGSY_RCPLWE_Road_Connectivity_Guidelines_2017.pdf"],
    },
    "pm-setu": {
        "names": ["pm setu", "pm-setu", "iti upgradation"],
        "sources": ["PM_SETU_ITI_Upgradation_Guidelines.pdf"],
    },
    "handicrafts": {
        "names": ["handicraft", "handicrafts", "கைவினை", "हस्तशिल्प"],
        "sources": ["NHDP_Handicrafts_Guidelines_2021-26.pdf"],
    },
    "handloom": {
        "names": ["handloom", "handlooms", "கைத்தறி", "हथकरघा"],
        "sources": ["NHDP_Handloom_Revised_Guidelines_2023.pdf"],
    },
    "msme": {
        "names": ["msme", "small scale industries"],
        "sources": [
            "https://www.india.gov.in/category/infrastructure-industries/"
            "subcategory/manufacturing-retail/details/"
            "schemes-for-ssis-in-priority-sector-by-ministry-of-msme",
            "National_SC_ST_Hub_NSSH_Detailed_Scheme_Information.pdf",
            "SFURTI_Scheme_Information_Summary.pdf",
        ],
    },
}
