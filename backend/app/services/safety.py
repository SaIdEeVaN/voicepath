"""Someone saying they, or a person near them, is in danger.

Found in the production question log: "என் பக்கத்தில் ஒரு படிக்கு தெரியாத
பெண்ணு இருக்கு, பிள்ளீஸ் காப்பாற்றுங்கள்" -- there is an illiterate woman next
to me, please save her -- was asked three times, and each time the assistant
explained that their voice had not been recorded. A skills service is not an
emergency service, but it must not answer a plea for help with a privacy
notice. It should say, first and plainly, who can help: 112.

Deterministic, not a model's judgement, for the same reason the ranking is:
it has to work when Groq is rate-limited, offline, or slow, and it has to be
testable. The cost of that is phrasing it does not know, so the assistant's
prompt carries the same instruction as a second line of defence.

Tuned against false alarms from the people this product serves, whose own
work descriptions use the same words:

* "குடும்பத்தை காப்பாற்ற வேலை வேண்டும்" -- I need a job to support my family
  -- is not a plea, so only the pleading forms of காப்பாற்று count.
* "பெயிண்ட் அடிக்கிறேன்" -- I paint -- and "டைப் அடிப்பேன்" -- I type -- use
  the verb for beating, so beating counts only with a person as its object.
* "my job is in danger" is not an emergency; "I am in danger" is.
* "पैसे बचाओ" (save money) is rare next to "बचाओ" as a cry for help, and a
  false alarm here costs one helpline message, which is the right way round.

The numbers are India's national lines, free from any phone: 112 (emergency,
ERSS), 181 (women's helpline), 1098 (children, Childline), 14416 (Tele-MANAS,
mental health). Nothing here dials, reports or stores anything.
"""

from __future__ import annotations

import re
import unicodedata

_ENGLISH = [
    r"\b(please\s+)?(save|rescue)\s+(me|her|him|us|them|my\s+\w+)\b",
    (
        r"\b(i\s*am|i'?m|she\s*is|she'?s|he\s*is|he'?s|we\s*are|we'?re|they\s*are|"
        r"someone\s+is|somebody\s+is|"
        r"my\s+(wife|husband|child|son|daughter|mother|mom|amma|father|dad|appa|"
        r"sister|brother|friend|family|neighbou?r|baby|kid|kids|children)\s+(is|are))"
        r"\s+in\s+danger\b"
    ),
    r"\b(my\s+)?life\s+is\s+in\s+danger\b",
    (
        r"\b(beat|beats|beating|beaten|hits|hitting|hurts|hurting|abuses|abusing|"
        r"abused|tortur\w*)\s+(me|her|him|us|my)\b"
    ),
    r"\bkill(ing)?\s+(myself|me|her|him|us)\b",
    r"\bsuicid\w*\b",
    r"\bend\s+my\s+life\b",
    r"\bwant\s+to\s+die\b",
    r"\b(raped?|raping|molest\w*|sexually\s+harass\w*|sexual\s+harassment)\b",
    r"\bkidnap\w*\b",
    r"\btraffick\w*\b",
    r"\b(locked|trapped)\s+(me|her|him|us)\b",
]

# Tamil and Devanagari attach endings to the word itself, so these are
# substrings rather than whole words -- but each is a form that only a plea or
# a report of harm takes.
_TAMIL = [
    r"காப்பாற்றுங்க",          # please save (formal and colloquial endings)
    r"காப்பாத்துங்க",
    r"காப்பாற்றுங்கள்",
    r"(என்னை|அவளை|அவனை|அவரை|எங்களை|எங்க\s*அம்மாவை)\s*(அடிக்க|அடிச்சு|அடிக்கிற|அடித்து)",
    r"தற்கொலை",                 # suicide
    r"(சாகப்போ|சாக\s*வேண்டும்|சாகணும்)",  # going to / want to die
    r"(கொல்லப்போ|கொன்னுடுவ|கொன்று\s*விடுவ)",  # will kill
    r"(நான்|அவள்|அவன்|நாங்கள்|உயிர்)\s*ஆபத்தில்",  # (I am / her life) in danger
    r"பாலியல்\s*(தொல்லை|வன்கொடுமை)",  # sexual harassment / assault
    r"கடத்தி(ட்டா|விட்டா|ட்டாங்க|னார்)",  # has been abducted
]

_HINDI = [
    r"बचाओ",
    r"बचाइए",
    r"बचा\s*लो",
    r"बचा\s*लीजिए",
    r"(मुझे|उसे|उसको|हमें|मेरी\s+\S+\s+को)\s*(मार\s*रहा|मार\s*रही|मारता|मारती|पीट)",
    r"आत्महत्या",
    r"मरना\s*चाहत",
    r"जान\s*से\s*मार",
    r"(मैं|वह|वो|हम|जान)\s*(ख़तरे|खतरे)\s*में",
    r"बलात्कार",
    r"अपहरण",
    r"यौन\s*उत्पीड़न",
    r"छेड़छाड़",
]

_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _ENGLISH + _TAMIL + _HINDI]


def detect_distress(text: str | None) -> bool:
    """True when the text says someone is in danger or being harmed."""
    clean = unicodedata.normalize("NFC", text or "").strip()
    if not clean:
        return False
    return any(pattern.search(clean) for pattern in _PATTERNS)


HELPLINES: dict[str, str] = {
    "en": (
        "If you or someone near you is in danger, call 112 now. It is free from "
        "any phone, day and night, and you can speak Tamil, Hindi or English. "
        "Women's helpline: 181. For a child: 1098. If you are thinking of ending "
        "your life, call 14416. VoicePath cannot send help itself."
    ),
    "ta": (
        "நீங்களோ உங்கள் அருகில் உள்ள ஒருவரோ ஆபத்தில் இருந்தால், உடனே 112-க்கு "
        "அழையுங்கள். எந்த போனிலிருந்தும் இலவசம், இரவும் பகலும், தமிழில் பேசலாம். "
        "பெண்கள் உதவி எண்: 181. குழந்தைகளுக்கு: 1098. உயிரை மாய்த்துக்கொள்ள "
        "நினைத்தால்: 14416. VoicePath தானே உதவி அனுப்ப முடியாது."
    ),
    "hi": (
        "अगर आप या आपके पास कोई ख़तरे में है, तो अभी 112 पर कॉल कीजिए। किसी भी "
        "फ़ोन से मुफ़्त, दिन-रात, और आप हिंदी में बात कर सकते हैं। महिला हेल्पलाइन: "
        "181। बच्चों के लिए: 1098। अगर आप अपनी जान लेने की सोच रहे हैं, तो 14416 पर "
        "कॉल कीजिए। VoicePath ख़ुद मदद नहीं भेज सकता।"
    ),
}

SOURCE_NOTE: dict[str, str] = {
    "en": "emergency helplines",
    "ta": "அவசர உதவி எண்கள்",
    "hi": "आपातकालीन हेल्पलाइन",
}


def helpline_answer(language: str | None) -> str:
    return HELPLINES.get((language or "en").split("-")[0], HELPLINES["en"])


def source_note(language: str | None) -> str:
    return SOURCE_NOTE.get((language or "en").split("-")[0], SOURCE_NOTE["en"])
