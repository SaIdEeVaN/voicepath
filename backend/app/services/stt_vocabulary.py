"""Priming Whisper with the trade words people say in Tamil and Hindi.

Whisper mishears English loanwords inside Tamil: "வெல்டிங்" (welding) came
back as "வெள்ளி" (silver), and extraction reported *silver work* -- grounded
in a transcript that was itself wrong. Whisper takes a short prompt that makes
the words in it likelier (``prompt`` on Groq, ``initial_prompt`` locally). This
is that prompt: the loanwords of the skill list's own aliases, in the script
they are spoken in (2026-11-09).

Kept short and in order of how much hangs on them: Whisper reads only the last
~224 tokens of a prompt, and Tamil or Devanagari costs several tokens a word.
Only for a language the person chose: a Tamil prompt on audio whose language
is being detected could tip the detection towards Tamil.

Whisper can also echo its prompt over silence. ``is_echo`` catches a
"transcript" made of nothing but prompt words, which the caller treats as
nothing heard.
"""

from __future__ import annotations

import re
import unicodedata

# Every word here is an alias in app/data/catalogue.py, in the script spoken;
# tests/test_stt_vocabulary.py holds that.
VOCABULARY: dict[str, tuple[str, ...]] = {
    # Each list fits PROMPT_BUDGET_BYTES, so none of it is cut off.
    "ta": (
        "வெல்டிங்", "மெக்கானிக்", "எலெக்ட்ரீஷியன்", "ரிப்பேர்", "வயரிங்", "பிளம்பர்",
        "பெயிண்டிங்",
    ),
    "hi": (
        "वेल्डिंग", "मैकेनिक", "इलेक्ट्रीशियन", "रिपेयर", "प्लंबर", "पेंटर", "ड्राइवर",
        "कंप्यूटर", "मिस्त्री",
    ),
}
# Whisper reads at most 224 tokens of prompt. At worst a token per byte --
# GPT-2's tokenizer spends exactly that on Tamil -- so a prompt within this
# many bytes is read whole.
PROMPT_BUDGET_BYTES = 224


def prompt_for(language: str | None) -> str | None:
    """The prompt for a chosen language, or None (English, or auto-detect)."""
    words = VOCABULARY.get((language or "").split("-")[0].lower())
    return ", ".join(words) + "." if words else None


_WORDS = re.compile(r"[^\W\d_]+(?:[஀-௿ऀ-ॿ]+)?", re.UNICODE)


def _tokens(text: str) -> list[str]:
    clean = unicodedata.normalize("NFC", text or "")
    return [t for t in re.split(r"[\s,.;:!?।]+", clean) if t]


def is_echo(transcript: str, language: str | None) -> bool:
    """True when the transcript is only the prompt's words -- Whisper repeating
    its prompt over silence, not a person listing four trades in a row."""
    words = VOCABULARY.get((language or "").split("-")[0].lower())
    if not words:
        return False
    tokens = _tokens(transcript)
    return len(tokens) >= 3 and all(t in words for t in tokens)
