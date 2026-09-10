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
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """No LLM is configured, or the configured one could not be reached."""


class LLMResponseError(RuntimeError):
    """The model replied, but not with what was asked for."""


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def is_available() -> bool:
    return get_settings().llm_provider != "offline"


def provider_name() -> str:
    return get_settings().llm_provider


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


async def complete_text(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    settings = get_settings()
    if settings.llm_provider == "offline":
        raise LLMUnavailable("No LLM configured (LLM_PROVIDER=offline)")

    url, headers, style = _endpoint(settings)
    # max_tokens is the length of the answer the caller wants; the headroom
    # covers the model's own reasoning, which is invisible to the caller and
    # is charged against the same budget.
    limit = (max_tokens or settings.llm_max_output_tokens) + settings.llm_reasoning_headroom

    if style == "openai":
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": limit,
        }
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
        raise LLMUnavailable(f"{settings.llm_provider} request failed: {exc}") from exc

    if response.status_code >= 400:
        # Body may carry the reason (bad key, quota); keep it short in the log.
        raise LLMUnavailable(
            f"{settings.llm_provider} returned {response.status_code}: "
            f"{response.text[:300]}"
        )

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
                    f"{settings.llm_model} ran out of output tokens before "
                    f"answering (LLM_MAX_OUTPUT_TOKENS={limit}). Reasoning "
                    "models need considerably more headroom than the answer "
                    "itself; raise the limit."
                )
            raise LLMResponseError(f"{settings.llm_model} returned no content")

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
