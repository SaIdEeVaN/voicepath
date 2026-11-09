"""A short code on every error the API sends, so the screen can say it in the
reader's language (2026-11-09).

The API's messages are English sentences. A Tamil or Hindi reader used to see
them as they were -- "That session was not found." in the middle of a Tamil
page -- and an error already on screen stayed in English after a language
switch. Now each error response also carries ``code``; the frontend
(``lib/problems.ts``) has the sentence for each code in all three languages
and shows the English ``detail`` only when it has no translation.

The code is looked up from the message, so the forty places that raise an
error stay as they are. tests/test_error_codes.py fails if a message listed
here no longer appears anywhere in the code.
"""

from __future__ import annotations

from typing import Any

from app.services.repository import RETIRED_SESSION_MESSAGE, UNKEYED_SESSION_MESSAGE

BY_MESSAGE: dict[str, str] = {
    "That session was not found.": "session_not_found",
    "Bad session id.": "session_not_found",
    RETIRED_SESSION_MESSAGE: "session_retired",
    UNKEYED_SESSION_MESSAGE: "session_outdated",
    "That scheme was not found.": "scheme_not_found",
    "This scheme has not been matched for that session.": "not_matched",
    "Nothing has been understood for this session yet.": "nothing_understood",
    "There is nothing to read yet.": "nothing_understood",
    "There was nothing to read.": "nothing_to_read",
    "There was no question to answer.": "no_question",
    "The transcript was empty.": "empty_transcript",
    "Nothing was typed.": "nothing_typed",
    "No audio was received.": "no_audio",
    "That recording is too long. Try a shorter one.": "recording_too_long",
    "Only audio recordings can be sent here.": "not_audio",
    "Too many requests. Please wait a moment and try again.": "too_many_requests",
}

# When the message is not one of the above, the status still says something.
BY_STATUS: dict[int, str] = {
    413: "too_large",
    415: "not_audio",
    422: "invalid_input",
    429: "too_many_requests",
    503: "unavailable",
}


def code_for(status_code: int, detail: Any) -> str | None:
    if isinstance(detail, str) and detail in BY_MESSAGE:
        return BY_MESSAGE[detail]
    return BY_STATUS.get(status_code)
