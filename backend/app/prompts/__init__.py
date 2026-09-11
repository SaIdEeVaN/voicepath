"""Prompt text, kept out of service code so it can be reviewed on its own.

PRD section 6.4 makes two boundaries reviewable: the extraction layer must never
invent data, and the explanation layer must never re-rank. Both boundaries live
here as much as they live in code, so any change to these strings is a change
that needs the same review as a change to ``matching.py``.
"""

from app.prompts.text import (
    ASSISTANT_SYSTEM,
    ASSISTANT_USER_TEMPLATE,
    DISAMBIGUATION_SYSTEM,
    DISAMBIGUATION_USER_TEMPLATE,
    EXPLANATION_SYSTEM,
    EXPLANATION_USER_TEMPLATE,
    EXTRACTION_SYSTEM,
    EXTRACTION_USER_TEMPLATE,
    INTENT_SYSTEM,
    INTENT_USER_TEMPLATE,
)

__all__ = [
    "ASSISTANT_SYSTEM",
    "ASSISTANT_USER_TEMPLATE",
    "DISAMBIGUATION_SYSTEM",
    "DISAMBIGUATION_USER_TEMPLATE",
    "EXPLANATION_SYSTEM",
    "EXPLANATION_USER_TEMPLATE",
    "EXTRACTION_SYSTEM",
    "EXTRACTION_USER_TEMPLATE",
    "INTENT_SYSTEM",
    "INTENT_USER_TEMPLATE",
]
