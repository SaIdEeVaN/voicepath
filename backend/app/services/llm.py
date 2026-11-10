"""LLM access for extraction, normalization assist, explanation and Q&A.

One ``complete_json`` / ``complete_text`` surface over four providers. The
callers in ``extraction.py``, ``normalization.py``, ``explanation.py`` and
``assistant.py`` never see provider differences.

Providers, in the order the PRD prefers them:

``groq``     Groq-hosted open-weight models (Llama, Gemma, gpt-oss).
``gemini``   Gemini free tier.
``offline``  No network. Raises ``LLMUnavailable``; each caller has a
             deterministic non-LLM path and labels its output accordingly.

The offline provider deliberately does not fake model output. Inventing a
plausible extraction would violate the one rule the PRD marks non-negotiable
(section 4.2): never assert something the user did not say.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """No LLM is configured, or the configured one could not be reached."""

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        # The outage reason (see _outage_reason), when the provider refused.
        self.reason = reason


class LLMResponseError(RuntimeError):
    """The model replied, but not with what was asked for."""


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def is_available() -> bool:
    return get_settings().llm_provider != "offline"


def provider_name() -> str:
    return get_settings().llm_provider


# ---------------------------------------------------------------------------
# Whether the configured model is actually answering
# ---------------------------------------------------------------------------
#
# ``is_available()`` says a model is configured, which is not the same as
# answering. On 2026-09-12 Groq's daily allowance (200,000 tokens) ran out:
# every extraction, explanation and answer fell back to its rule-based path,
# and /health went on reporting `llm: groq` with nothing degraded, so the
# interface told nobody why the answers had become thinner.
#
# So the last real outage is remembered -- a rate limit, a spent quota, a
# rejected key, a model Groq has retired, a server error, no connection --
# with how long it should hold: Groq's own retry-after when it gives one,
# five minutes otherwise. Any answer clears it at once. A 400 is a problem
# with one request, not with the service, and is not recorded.
#
# Per process, like the rate limiter: two workers can disagree for a few
# minutes, which is the right way to be wrong.

_DEFAULT_HOLD_SECONDS = 300.0
_MAX_HOLD_SECONDS = 24 * 3600.0

# Patched by tests; nothing else should need to.
_clock = time.time


@dataclass
class _Failure:
    reason: str
    since: float
    until: float


# Per model since 2026-11-10: Groq counts its allowance per model, so the main
# model's spent day says nothing about the fallback's.
_failures: dict[str, _Failure] = {}


def models() -> list[str]:
    """The models to try, in order: the main one, then the fallback if any."""
    settings = get_settings()
    chain = [settings.llm_model]
    fallback = (settings.llm_fallback_model or "").strip()
    if settings.llm_provider == "groq" and fallback and fallback != settings.llm_model:
        chain.append(fallback)
    return chain


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=UTC).isoformat(timespec="seconds")


def _active(model: str) -> _Failure | None:
    failure = _failures.get(model)
    if failure is None or _clock() >= failure.until:
        return None
    return failure


def recent_failure() -> dict[str, str] | None:
    """The outage in force, or None while any configured model should answer.

    When every model is out, the main model's reason, and the earliest time
    one of them should be back -- which is what the interface tells people.
    """
    chain = models()
    active = [_active(m) for m in chain]
    if any(f is None for f in active):
        return None
    main = active[0]
    return {
        "reason": main.reason,
        "since": _iso(min(f.since for f in active)),
        "until": _iso(min(f.until for f in active)),
    }


def status() -> dict[str, str]:
    """What /health reports about the model: configured, and answering?"""
    if not is_available():
        return {"status": "offline"}
    failure = recent_failure()
    if failure is not None:
        return {
            "status": failure["reason"],
            "since": failure["since"],
            "until": failure["until"],
        }
    chain = models()
    main = _active(chain[0])
    if main is not None and len(chain) > 1:
        # Answering, on the fallback: worth saying, not a degradation.
        return {
            "status": "ok",
            "model": chain[1],
            "main_model": main.reason,
            "main_back": _iso(main.until),
        }
    return {"status": "ok"}


def reset_status() -> None:
    _failures.clear()


def _note_failure(reason: str, *, model: str | None = None, retry_after: float | None = None) -> None:
    model = model or get_settings().llm_model
    now = _clock()
    hold = retry_after if retry_after and retry_after > 0 else _DEFAULT_HOLD_SECONDS
    hold = min(hold, _MAX_HOLD_SECONDS)
    # An outage that is still going keeps the time it started.
    current = _active(model)
    since = current.since if current is not None else now
    _failures[model] = _Failure(reason=reason, since=since, until=now + hold)
    logger.warning("LLM %s marked unavailable: %s for %.0fs", model, reason, hold)


def _note_success(model: str | None = None) -> None:
    model = model or get_settings().llm_model
    failure = _failures.pop(model, None)
    if failure is not None:
        logger.info("LLM %s answering again after %s", model, failure.reason)


_TRY_AGAIN = re.compile(
    r"try again in\s+(?:(?P<h>\d+)h)?\s*(?:(?P<m>\d+)m)?\s*(?:(?P<s>[\d.]+)s)?",
    re.IGNORECASE,
)


def _retry_after(headers: Any, body: str) -> float | None:
    """Seconds until the provider says to try again, if it said."""
    header = headers.get("retry-after") if headers is not None else None
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    found = _TRY_AGAIN.search(body or "")
    if found and any(found.group(k) for k in ("h", "m", "s")):
        return (
            int(found.group("h") or 0) * 3600
            + int(found.group("m") or 0) * 60
            + float(found.group("s") or 0)
        )
    return None


def _outage_reason(status_code: int, body: str) -> str | None:
    """Why a refused request means the service is not answering, if it does."""
    if status_code == 429:
        lowered = (body or "").lower()
        if "per day" in lowered or "(tpd)" in lowered or "(rpd)" in lowered:
            return "daily_limit"
        if "quota" in lowered:
            return "quota"
        return "rate_limited"
    if status_code in (401, 403):
        return "rejected"
    if status_code == 404:
        return "model_missing"
    if status_code >= 500:
        return "server_error"
    return None


def _endpoint(settings: Any) -> tuple[str, dict[str, str], str]:
    """Return (url, headers, style) for the configured provider."""
    provider = settings.llm_provider
    key = settings.llm_api_key or ""

    if provider == "groq":
        base = settings.llm_base_url or "https://api.groq.com/openai"
        return (
            f"{base.rstrip('/')}/v1/chat/completions",
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            "openai",
        )
    if provider == "gemini":
        base = settings.llm_base_url or "https://generativelanguage.googleapis.com"
        model = settings.llm_model or "gemini-2.0-flash"
        return (
            f"{base.rstrip('/')}/v1beta/models/{model}:generateContent",
            {"Content-Type": "application/json", "x-goog-api-key": key},
            "gemini",
        )
    raise LLMUnavailable(f"Unsupported LLM provider: {provider}")


# Refusals after which the fallback is worth trying: about this model's
# allowance or this model. A rejected key or no connection would fail the
# same way for any model on the same key and host, so they are not retried.
_FALL_OVER = {"daily_limit", "quota", "rate_limited", "model_missing", "server_error"}


async def complete_text(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    """Ask the main model; if it is not answering, the fallback (Groq only).

    A model already known to be out is skipped while another is not, so a
    spent day costs one refused request, not one per question.
    """
    settings = get_settings()
    if settings.llm_provider == "offline":
        raise LLMUnavailable("No LLM configured (LLM_PROVIDER=offline)")

    chain = models()
    if any(_active(m) is None for m in chain):
        chain = [m for m in chain if _active(m) is None]
    last: LLMUnavailable | None = None
    for position, model in enumerate(chain):
        try:
            return await _complete_with(
                model, system, user, temperature=temperature, max_tokens=max_tokens
            )
        except LLMUnavailable as exc:
            last = exc
            if exc.reason not in _FALL_OVER or position == len(chain) - 1:
                raise
            logger.warning("%s is not answering (%s); trying %s", model, exc.reason,
                           chain[position + 1])
    assert last is not None  # the loop either returned or raised
    raise last


async def _complete_with(
    model: str,
    system: str,
    user: str,
    *,
    temperature: float,
    max_tokens: int | None,
) -> str:
    settings = get_settings()
    url, headers, style = _endpoint(settings)
    fallback = model != settings.llm_model
    # max_tokens is the length of the answer the caller wants; the headroom
    # covers the model's own reasoning, which is invisible to the caller and
    # is charged against the same budget.
    headroom = (
        settings.llm_fallback_reasoning_headroom if fallback else settings.llm_reasoning_headroom
    )
    limit = (max_tokens or settings.llm_max_output_tokens) + headroom

    if style == "openai":
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": limit,
        }
        if fallback and settings.llm_fallback_reasoning_effort:
            payload["reasoning_effort"] = settings.llm_fallback_reasoning_effort
    else:  # gemini
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": limit,
            },
        }

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        _note_failure("unreachable", model=model)
        raise LLMUnavailable(
            f"{settings.llm_provider} request failed: {exc}", reason="unreachable"
        ) from exc

    if response.status_code >= 400:
        reason = _outage_reason(response.status_code, response.text)
        if reason is not None:
            _note_failure(
                reason, model=model, retry_after=_retry_after(response.headers, response.text)
            )
        # Body may carry the reason (bad key, quota); keep it short in the log.
        raise LLMUnavailable(
            f"{settings.llm_provider} returned {response.status_code}: "
            f"{response.text[:300]}",
            reason=reason,
        )

    # It answered. Whether the answer is usable is a separate question, about
    # this request rather than the service.
    _note_success(model)

    data = response.json()
    try:
        if style == "openai":
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            if content.strip():
                return content

            # Reasoning models spend the budget on a
            # `reasoning_content` field and return content: null when they run
            # out before answering. That is a budget problem with a specific
            # fix, so say so rather than surfacing "empty response".
            if choice.get("finish_reason") == "length":
                raise LLMResponseError(
                    f"{model} ran out of output tokens before "
                    f"answering (LLM_MAX_OUTPUT_TOKENS={limit}). Reasoning "
                    "models need considerably more headroom than the answer "
                    "itself; raise the limit."
                )
            raise LLMResponseError(f"{model} returned no content")

        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except LLMResponseError:
        raise
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMResponseError(
            f"Unexpected {settings.llm_provider} response shape: {str(data)[:300]}"
        ) from exc


async def complete_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.1,
    max_tokens: int | None = None,
    retries: int = 1,
) -> Any:
    """Ask for JSON and return parsed JSON.

    Models wrap JSON in prose or fences often enough that a tolerant parse is
    worth having; a retry with a blunter instruction covers the rest.
    """
    attempt = 0
    last_error: Exception | None = None
    prompt = user

    while attempt <= retries:
        raw = await complete_text(
            system, prompt, temperature=temperature, max_tokens=max_tokens
        )
        try:
            return parse_json_response(raw)
        except LLMResponseError as exc:
            last_error = exc
            logger.warning("LLM returned unparseable JSON (attempt %d)", attempt + 1)
            prompt = (
                f"{user}\n\n"
                "Your previous reply was not valid JSON. Reply with the JSON "
                "object only. No explanation, no code fence, no leading text."
            )
            attempt += 1

    raise LLMResponseError(f"Model did not return valid JSON: {last_error}")


def parse_json_response(raw: str) -> Any:
    """Pull a JSON value out of a model reply.

    Tries, in order: the whole string; a fenced block; the widest brace- or
    bracket-delimited span.
    """
    text = (raw or "").strip()
    if not text:
        raise LLMResponseError("Empty response")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = _JSON_BLOCK.search(text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise LLMResponseError(f"No JSON found in: {text[:200]}")
