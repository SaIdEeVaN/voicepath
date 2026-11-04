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
import re
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
    _admin_failures.clear()


# Three limits, all of which must hold. Until 2026-11-04 there was one, keyed
# on the X-VoicePath-Session header when present -- a value the client
# chooses. Sending a fresh random one with every request reset the limit every
# time, so nothing stood between a script and the Groq allowance.
#
# * Per session -- only a well-formed UUID counts, and it is the fair key
#   behind shared mobile NAT, where many people arrive from one address.
# * Per address -- a few sessions' worth, so minting session ids from one
#   machine buys little.
# * Per route, for everyone together -- the ceiling nothing can get round,
#   because the address can be forged too (it comes from X-Forwarded-For).
#   Sized well above real use; it exists to bound the cost of abuse.
PER_ADDRESS_MULTIPLIER = 4
GLOBAL_MULTIPLIER = 25

_SESSION_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _hashed(identity: str) -> str:
    return hashlib.blake2b(identity.encode("utf-8"), digest_size=16).hexdigest()


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _keys(request: Request, bucket: str, limit: int) -> list[tuple[str, int]]:
    keys = [
        (f"{bucket}:ip:{_hashed(client_address(request))}", limit * PER_ADDRESS_MULTIPLIER),
        (f"{bucket}:all", limit * GLOBAL_MULTIPLIER),
    ]
    session_id = (request.headers.get("x-voicepath-session") or "").strip()
    if _SESSION_ID.match(session_id):
        keys.insert(0, (f"{bucket}:s:{_hashed(session_id.lower())}", limit))
    return keys


def _hit(key: str, limit: int, now: float) -> int | None:
    """Count one request against a key; the seconds to wait if over the limit."""
    counter = _counters.get(key)
    if counter is None or now - counter.window_start >= WINDOW_SECONDS:
        _counters[key] = _Counter(window_start=now, count=1)
        _counters.move_to_end(key)
        while len(_counters) > MAX_TRACKED_KEYS:
            _counters.popitem(last=False)
        return None
    counter.count += 1
    if counter.count > limit:
        return int(WINDOW_SECONDS - (now - counter.window_start)) + 1
    return None


def check(request: Request, bucket: str, limit: int) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled or limit <= 0:
        return

    now = time.monotonic()
    waits = [w for key, cap in _keys(request, bucket, limit)
             if (w := _hit(key, cap, now)) is not None]
    if waits:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(max(waits))},
        )


# ---------------------------------------------------------------------------
# Admin token guessing
# ---------------------------------------------------------------------------
# A wrong admin token used to cost nothing, so a token could be guessed at
# the speed of the network. Failures are counted per address and in total;
# past either limit, admin routes answer 429 without checking anything, until
# the window passes. A correct token is never counted.

ADMIN_FAILURE_WINDOW_SECONDS = 15 * 60
ADMIN_FAILURES_PER_ADDRESS = 10
ADMIN_FAILURES_TOTAL = 100

_admin_failures: OrderedDict[str, _Counter] = OrderedDict()


def _admin_keys(request: Request) -> list[tuple[str, int]]:
    return [
        (f"ip:{_hashed(client_address(request))}", ADMIN_FAILURES_PER_ADDRESS),
        ("all", ADMIN_FAILURES_TOTAL),
    ]


def admin_locked_out(request: Request) -> int | None:
    """Seconds until admin attempts are accepted again, or None."""
    now = time.monotonic()
    for key, cap in _admin_keys(request):
        counter = _admin_failures.get(key)
        if counter is None or now - counter.window_start >= ADMIN_FAILURE_WINDOW_SECONDS:
            continue
        if counter.count >= cap:
            return int(ADMIN_FAILURE_WINDOW_SECONDS - (now - counter.window_start)) + 1
    return None


def record_admin_failure(request: Request) -> None:
    now = time.monotonic()
    for key, _cap in _admin_keys(request):
        counter = _admin_failures.get(key)
        if counter is None or now - counter.window_start >= ADMIN_FAILURE_WINDOW_SECONDS:
            _admin_failures[key] = _Counter(window_start=now, count=1)
            _admin_failures.move_to_end(key)
            while len(_admin_failures) > MAX_TRACKED_KEYS:
                _admin_failures.popitem(last=False)
        else:
            counter.count += 1


def speech_limit(request: Request) -> None:
    check(request, "speech", get_settings().rate_limit_speech_per_minute)


def assistant_limit(request: Request) -> None:
    check(request, "assistant", get_settings().rate_limit_assistant_per_minute)


def default_limit(request: Request) -> None:
    check(request, "default", get_settings().rate_limit_default_per_minute)
