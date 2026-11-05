"""Rate limiting for public routes, and the admin-token lockout (PRD section 6.6).

Fixed-window counters. Until 2026-11-05 they lived in this process, so behind
more than one instance every limit multiplied by the instance count. Now they
live in a shared store -- a Redis-compatible Render Key Value instance, set by
``RATE_LIMIT_REDIS_URL`` -- so every instance counts against the same numbers.

If the store cannot be reached the limiter falls back to counting in this
process, and stops asking the store for ``STORE_RETRY_SECONDS`` so an outage
costs one short timeout rather than one per request. Falling back is the safe
direction: a request is never refused because the counter is unreachable,
and the per-process limits still hold. ``/health`` says which store is in use.

The keys are hashed before they are stored, so an IP address or a session id
is never kept in the clear -- here or in the shared store.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
MAX_TRACKED_KEYS = 20_000

# Every key in the shared store starts with this, so the instance could be
# shared with something else without collisions.
KEY_PREFIX = "vp:rl:"
# Budget for one round trip to the store. It sits in the same Render region as
# the API, where a round trip is about a millisecond.
STORE_TIMEOUT_SECONDS = 0.5
# After a failed round trip, how long to count in-process before trying again.
STORE_RETRY_SECONDS = 30.0


@dataclass
class _Counter:
    window_start: float
    count: int


_counters: "OrderedDict[str, _Counter]" = OrderedDict()


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


# ---------------------------------------------------------------------------
# The shared store
# ---------------------------------------------------------------------------

_client: Any = None
_client_url: str | None = None
# An asyncio client belongs to the loop that made it. One loop in production;
# tests start a fresh one per client, so a change of loop means a new client.
_client_loop: asyncio.AbstractEventLoop | None = None
# Monotonic time before which the store is not asked; 0 when it is healthy.
_store_down_until = 0.0
_store_error: str | None = None


def _store():
    """The shared store's client, or None when unset or resting after a failure."""
    global _client, _client_url, _client_loop
    url = get_settings().rate_limit_redis_url
    if not url:
        return None
    if time.monotonic() < _store_down_until:
        return None
    loop = asyncio.get_running_loop()
    if _client is None or _client_url != url or _client_loop is not loop:
        import redis.asyncio as redis  # imported only when a store is configured

        _client = redis.Redis.from_url(
            url,
            socket_timeout=STORE_TIMEOUT_SECONDS,
            socket_connect_timeout=STORE_TIMEOUT_SECONDS,
            health_check_interval=30,
        )
        _client_url = url
        _client_loop = loop
    return _client


def _store_failed(exc: BaseException) -> None:
    global _store_down_until, _store_error
    first = _store_error is None
    _store_down_until = time.monotonic() + STORE_RETRY_SECONDS
    _store_error = type(exc).__name__
    # Once per outage, not once per request. The message can carry the host,
    # so it goes to the log only, never to /health.
    if first:
        logger.warning(
            "Rate-limit store unreachable (%s: %s); counting in this process for now",
            type(exc).__name__, exc,
        )


def _store_ok() -> None:
    global _store_down_until, _store_error
    if _store_error is not None:
        logger.info("Rate-limit store reachable again")
    _store_down_until = 0.0
    _store_error = None


def status_report() -> dict[str, str]:
    """For /health: where the counters live, and why if not where configured."""
    if not get_settings().rate_limit_redis_url:
        return {"store": "process"}
    if _store_error is not None:
        return {"store": "process", "reason": f"shared store unreachable ({_store_error})"}
    return {"store": "shared"}


async def _shared_hits(keys: list[tuple[str, int]], window: int) -> list[tuple[int, int]] | None:
    """Count one request against each key in the store, in one round trip.

    Returns ``(count, seconds_left_in_window)`` per key, or None if the store
    is unavailable -- the caller then counts in-process instead.
    """
    client = _store()
    if client is None:
        return None
    now = time.time()
    index = int(now // window)
    left = int(window - (now - index * window)) + 1
    try:
        async with client.pipeline(transaction=False) as pipe:
            for key, _cap in keys:
                name = f"{KEY_PREFIX}{key}:{index}"
                pipe.incr(name)
                # Twice the window: long enough to outlive it, short enough
                # that nothing accumulates.
                pipe.expire(name, window * 2, nx=True)
            replies = await asyncio.wait_for(
                pipe.execute(), timeout=STORE_TIMEOUT_SECONDS * 2
            )
    except Exception as exc:  # noqa: BLE001 - any store failure means "count locally"
        _store_failed(exc)
        return None
    _store_ok()
    return [(int(replies[i * 2]), left) for i in range(len(keys))]


# ---------------------------------------------------------------------------
# Request limits
# ---------------------------------------------------------------------------


def _hit(key: str, limit: int, now: float) -> int | None:
    """Count one request in-process; the seconds to wait if over the limit."""
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


async def check(request: Request, bucket: str, limit: int) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled or limit <= 0:
        return

    keys = _keys(request, bucket, limit)
    shared = await _shared_hits(keys, WINDOW_SECONDS)
    if shared is not None:
        waits = [left for (count, left), (_key, cap) in zip(shared, keys) if count > cap]
    else:
        now = time.monotonic()
        waits = [w for key, cap in keys if (w := _hit(key, cap, now)) is not None]
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
# the window passes. A correct token is never counted. Shared across
# instances like the request limits, so a guesser cannot spread attempts
# over them.

ADMIN_FAILURE_WINDOW_SECONDS = 15 * 60
ADMIN_FAILURES_PER_ADDRESS = 10
ADMIN_FAILURES_TOTAL = 100

_admin_failures: OrderedDict[str, _Counter] = OrderedDict()


def _admin_keys(request: Request) -> list[tuple[str, int]]:
    return [
        (f"admin:ip:{_hashed(client_address(request))}", ADMIN_FAILURES_PER_ADDRESS),
        ("admin:all", ADMIN_FAILURES_TOTAL),
    ]


async def _shared_admin_counts(keys: list[tuple[str, int]]) -> list[tuple[int, int]] | None:
    client = _store()
    if client is None:
        return None
    window = ADMIN_FAILURE_WINDOW_SECONDS
    now = time.time()
    index = int(now // window)
    left = int(window - (now - index * window)) + 1
    try:
        values = await asyncio.wait_for(
            client.mget([f"{KEY_PREFIX}{key}:{index}" for key, _cap in keys]),
            timeout=STORE_TIMEOUT_SECONDS * 2,
        )
    except Exception as exc:  # noqa: BLE001
        _store_failed(exc)
        return None
    _store_ok()
    return [(int(v or 0), left) for v in values]


async def admin_locked_out(request: Request) -> int | None:
    """Seconds until admin attempts are accepted again, or None."""
    keys = _admin_keys(request)
    shared = await _shared_admin_counts(keys)
    if shared is not None:
        for (count, left), (_key, cap) in zip(shared, keys):
            if count >= cap:
                return left
        return None

    now = time.monotonic()
    for key, cap in keys:
        counter = _admin_failures.get(key)
        if counter is None or now - counter.window_start >= ADMIN_FAILURE_WINDOW_SECONDS:
            continue
        if counter.count >= cap:
            return int(ADMIN_FAILURE_WINDOW_SECONDS - (now - counter.window_start)) + 1
    return None


async def record_admin_failure(request: Request) -> None:
    keys = _admin_keys(request)
    if await _shared_hits(keys, ADMIN_FAILURE_WINDOW_SECONDS) is not None:
        return

    now = time.monotonic()
    for key, _cap in keys:
        counter = _admin_failures.get(key)
        if counter is None or now - counter.window_start >= ADMIN_FAILURE_WINDOW_SECONDS:
            _admin_failures[key] = _Counter(window_start=now, count=1)
            _admin_failures.move_to_end(key)
            while len(_admin_failures) > MAX_TRACKED_KEYS:
                _admin_failures.popitem(last=False)
        else:
            counter.count += 1


# ---------------------------------------------------------------------------
# Route dependencies
# ---------------------------------------------------------------------------


async def speech_limit(request: Request) -> None:
    await check(request, "speech", get_settings().rate_limit_speech_per_minute)


async def assistant_limit(request: Request) -> None:
    await check(request, "assistant", get_settings().rate_limit_assistant_per_minute)


async def default_limit(request: Request) -> None:
    await check(request, "default", get_settings().rate_limit_default_per_minute)


def reset() -> None:
    """Tests: forget every in-process counter and any store outage."""
    global _client, _client_url, _client_loop
    _counters.clear()
    _admin_failures.clear()
    _store_ok()
    _client = None
    _client_url = None
    _client_loop = None
