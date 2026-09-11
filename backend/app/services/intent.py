"""What was this person doing when they said that? (PRD section 6.)

One sentence can be two things at once, and the pipeline behind it forks. "I
repair two-wheelers" is work to extract skills from. "Who is eligible for
PM-AJAY?" is a question for the guidelines. "I do welding, is there a scheme for
that?" is both, and answering only half of it is the failure this module exists
to prevent.

This step decides; it never answers. Skills still come from ``extraction``,
which verifies every quote against the transcript, and answers still come from
``scheme_qa``, which cites a passage or refuses. Nothing here can assert
anything about a person -- the worst a wrong classification does is route to a
step that then finds nothing, which is recoverable. That is deliberate: a
classifier is the wrong place to put a guarantee.

Offline, the heuristic below is honest about being coarse. It reads question
marks and question words, and first-person work phrasing, in the three
languages. It will miss an indirect question. That is a recall limit, and the
caller treats it as one.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.prompts import INTENT_SYSTEM, INTENT_USER_TEMPLATE
from app.services import llm

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryIntent:
    """What the person was doing, and the question if they asked one."""

    describes_work: bool
    asks_question: bool
    # Their words, in their language. Never a rephrasing, and never a statement
    # turned into a question -- the retrieval step searches with this verbatim.
    question: str | None
    provider: str

    @property
    def is_empty(self) -> bool:
        """Neither. Noise, a greeting, or a fragment."""
        return not self.describes_work and not self.asks_question


# Question markers across the three languages. Devanagari and Tamil question
# words are listed rather than transliterated, because the transcript keeps the
# script it was spoken in.
_QUESTION_MARKS = re.compile(r"[?？]")
_QUESTION_WORDS = (
    # English
    "who", "what", "when", "where", "why", "how", "which", "can i", "am i",
    "do i", "is there", "are there", "tell me about", "eligible",
    # Hindi
    "क्या", "कौन", "कब", "कहाँ", "कहां", "क्यों", "कैसे", "कितना", "बताइए",
    # Tamil
    "என்ன", "யார்", "எப்போது", "எங்கே", "ஏன்", "எப்படி", "எவ்வளவு", "சொல்லுங்கள்",
    "இருக்கா", "உண்டா",
)
# First-person work phrasing. Deliberately narrow: a false "describes work"
# sends extraction looking for a skill nobody mentioned.
_WORK_MARKERS = (
    "i work", "i repair", "i fix", "i know", "i do", "i have been", "i worked",
    "my work", "i am a", "i can",
    "करता हूँ", "करता हूं", "काम", "जानता", "मुझे आता",
    "செய்வேன்", "செஞ்சேன்", "தெரியும்", "வேலை", "பாத்தேன்", "பண்ணுவேன்",
)


def _heuristic(text: str) -> QueryIntent:
    lowered = text.lower()
    asks = bool(_QUESTION_MARKS.search(text)) or any(
        word in lowered for word in _QUESTION_WORDS
    )
    describes = any(marker in lowered for marker in _WORK_MARKERS)
    return QueryIntent(
        describes_work=describes,
        asks_question=asks,
        # The whole utterance, since a heuristic cannot reliably find where the
        # question starts. Retrieval copes with the extra words; a wrong slice
        # would search for something the person did not ask.
        question=text.strip() if asks else None,
        provider="offline",
    )


async def classify(text: str) -> QueryIntent:
    """Decide what to do with an utterance.

    Falls back to the heuristic whenever the model is unavailable or answers in
    a shape that cannot be trusted. A coarse route is recoverable; a confident
    wrong one is not.
    """
    clean = (text or "").strip()
    if not clean:
        return QueryIntent(False, False, None, "offline")

    if not llm.is_available():
        return _heuristic(clean)

    try:
        payload = await llm.complete_json(
            INTENT_SYSTEM,
            INTENT_USER_TEMPLATE.format(text=clean),
            temperature=0.0,
            max_tokens=200,
        )
    except (llm.LLMUnavailable, llm.LLMResponseError) as exc:
        logger.warning("Intent classification unavailable (%s); using heuristics", exc)
        return _heuristic(clean)

    if not isinstance(payload, dict):
        return _heuristic(clean)

    describes = bool(payload.get("describes_work"))
    asks = bool(payload.get("asks_question"))

    question = payload.get("question")
    question = question.strip() if isinstance(question, str) else None
    if question and question not in clean:
        # The model was asked to copy their words. Anything else is a
        # rephrasing, and searching with a rephrasing means answering a
        # question the person did not ask. Keep the route, drop the slice.
        logger.info("Intent returned a question not present in the text; using the whole utterance")
        question = clean
    if asks and not question:
        question = clean

    if not describes and not asks:
        # The model found neither. The heuristic is cheap and sometimes sees a
        # marker the model talked itself out of, so give it the last word.
        fallback = _heuristic(clean)
        if not fallback.is_empty:
            return fallback

    return QueryIntent(
        describes_work=describes,
        asks_question=asks,
        question=question if asks else None,
        provider=llm.provider_name(),
    )
