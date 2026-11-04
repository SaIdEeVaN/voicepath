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
        "sources": ["https://pmvishwakarma.gov.in/",
                    "PIB_PM_Vishwakarma_Salient_Features_2023-09-20.md",
                    "PIB_MSME_Grassroots_Economy_PMEGP_PM_Vishwakarma_2026-05-14.md"],
    },
    # -- National schemes added 2026-11-04, from official PIB releases ------
    "pmkvy": {
        "names": ["pmkvy", "pmkvy 4.0", "kaushal vikas", "pradhan mantri kaushal",
                  "recognition of prior learning", "skill india programme",
                  "கௌஷல் விகாஸ்", "कौशल विकास"],
        "sources": ["PIB_Skill_India_Programme_PMKVY_NAPS_JSS_2025-02-07.md"],
    },
    "naps": {
        "names": ["naps", "pm-naps", "apprenticeship promotion", "national apprenticeship",
                  "அப்ரண்டிஸ்", "अप्रेंटिसशिप"],
        "sources": ["PIB_National_Apprenticeship_Schemes_NAPS_2026-02-11.md",
                    "PIB_Skill_India_Programme_PMKVY_NAPS_JSS_2025-02-07.md"],
    },
    "jss": {
        "names": ["jan shikshan", "shikshan sansthan", "ஜன் ஷிக்ஷன்", "जन शिक्षण"],
        "sources": ["PIB_Jan_Shikshan_Sansthan_2025-12-01.md",
                    "PIB_Skill_India_Programme_PMKVY_NAPS_JSS_2025-02-07.md"],
    },
    "ddu-gky": {
        "names": ["ddu-gky", "ddugky", "ddu gky", "grameen kaushalya", "kaushalya yojana",
                  "दीनदयाल उपाध्याय ग्रामीण कौशल्य", "கிராமீன் கௌஷல்யா"],
        "sources": ["PIB_DDU-GKY_and_RSETI_2026-01-01.md"],
    },
    "rseti": {
        "names": ["rseti", "rsetis", "rural self employment training",
                  "ஆர்செட்டி", "आरसेटी"],
        "sources": ["PIB_DDU-GKY_and_RSETI_2026-01-01.md"],
    },
    "pmegp": {
        "names": ["pmegp", "employment generation programme", "employment generation program",
                  "பிஎம்இஜிபி", "पीएमईजीपी"],
        "sources": ["PIB_PMEGP_15th_Finance_Commission_Cycle_2026-05-07.md",
                    "PIB_MSME_Grassroots_Economy_PMEGP_PM_Vishwakarma_2026-05-14.md",
                    "PIB_PMEGP_and_Mudra_for_SC_Beneficiaries_2025-08-21.md"],
    },
    "pm-svanidhi": {
        "names": ["svanidhi", "street vendor", "street vendors", "ஸ்வநிதி", "स्वनिधि"],
        "sources": ["PIB_PM_SVANidhi_FAQ_2026-05-30.md"],
    },
    "mudra": {
        "names": ["mudra", "pmmy", "shishu loan", "kishor loan", "tarun loan",
                  "முத்ரா", "मुद्रा"],
        "sources": ["PIB_PM_Mudra_Yojana_11_Years_2026-04-08.md",
                    "PIB_PMEGP_and_Mudra_for_SC_Beneficiaries_2025-08-21.md"],
    },
    "namaste": {
        "names": ["namaste scheme", "namaste yojana", "mechanised sanitation",
                  "நமஸ்தே திட்டம்", "नमस्ते योजना"],
        "sources": ["PIB_NAMASTE_Sanitation_Workers_2026-07-20.md"],
    },
    "pm-daksh": {
        "names": ["pm-daksh", "pm daksh", "pmdaksh", "dakshata", "பிஎம் தக்ஷ்", "पीएम दक्ष",
                  "पीएम-दक्ष"],
        "sources": ["PIB_PM-DAKSH_Skill_Development_2026-03-11.md",
                    "PIB_PM-DAKSH_Yojana_2023-09-04.md"],
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
