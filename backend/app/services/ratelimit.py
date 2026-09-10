"""Per-session / per-IP rate limiting for public routes (PRD section 6.6).

A fixed-window counter held in this process. That is the right size for a
single-instance MVP and honest about its limits: behind more than one worker the
effective limit multiplies by the worker count. For a multi-instance deployment,
move the counter to Redis -- the interface here does not change.

The keys are hashed before they are stored, so an IP address is not sitting in
memory in the clear for the lifetime of the window.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.config import get_settings

WINDOW_SECONDS = 60
MAX_TRACKED_KEYS = 20_000


@dataclass
class _Counter:
    window_start: float
    count: int


_counters: "OrderedDict[str, _Counter]" = OrderedDict()


def reset() -> None:
    _counters.clear()


def _client_key(request: Request, bucket: str) -> str:
    # A session id is the better key: it survives shared NAT, and it is what a
    # rate limit is actually about here. IP is the fallback.
    session_id = request.headers.get("x-voicepath-session")
    identity = session_id or (request.client.host if request.client else "unknown")
    digest = hashlib.blake2b(identity.encode("utf-8"), digest_size=16).hexdigest()
    return f"{bucket}:{digest}"


def check(request: Request, bucket: str, limit: int) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled or limit <= 0:
        return

    key = _client_key(request, bucket)
    now = time.monotonic()
    counter = _counters.get(key)

    if counter is None or now - counter.window_start >= WINDOW_SECONDS:
        _counters[key] = _Counter(window_start=now, count=1)
        _counters.move_to_end(key)
        while len(_counters) > MAX_TRACKED_KEYS:
            _counters.popitem(last=False)
        return

    counter.count += 1
    if counter.count > limit:
        retry_after = int(WINDOW_SECONDS - (now - counter.window_start)) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(retry_after)},
        )


def speech_limit(request: Request) -> None:
    check(request, "speech", get_settings().rate_limit_speech_per_minute)


def assistant_limit(request: Request) -> None:
    check(request, "assistant", get_settings().rate_limit_assistant_per_minute)


def default_limit(request: Request) -> None:
    check(request, "default", get_settings().rate_limit_default_per_minute)
