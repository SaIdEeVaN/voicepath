"""A second Groq model answers when the first has spent its day (2026-11-10).

Groq counts its allowance per model -- the refusal names the model -- so on the
same key a second model still has its own. These hold when the fallback is
tried and when it is not, that a spent model is not asked again until it is
due back, and what /health says meanwhile.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import reload_settings
from app.services import llm

MAIN, FALLBACK = "qwen/qwen3.8-27b", "openai/gpt-oss-120b"


def refusal(model: str) -> httpx.Response:
    return httpx.Response(
        429,
        headers={"retry-after": "3600"},
        text=('{"error":{"message":"Rate limit reached for model `' + model + '` in '
              "organization `org_x` service tier `on_demand` on tokens per day (TPD): "
              'Limit 200000, Used 199999, Requested 900. Please try again in 1h0m0s."}}'),
    )


def answer(text: str = "hello") -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text},
                                                  "finish_reason": "stop"}]})


@pytest.fixture
def groq(monkeypatch):
    """Groq with the fallback on; replies are scripted per model asked for."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    monkeypatch.setenv("LLM_MODEL", MAIN)
    monkeypatch.setenv("LLM_FALLBACK_MODEL", FALLBACK)
    reload_settings()

    replies: dict[str, list] = {MAIN: [], FALLBACK: []}
    asked: list[dict] = []
    real = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        asked.append(body)
        reply = replies[body["model"]].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(llm.httpx, "AsyncClient", client)
    yield replies, asked
    reload_settings()


@pytest.fixture
def clock(monkeypatch):
    now = [1_800_000_000.0]
    monkeypatch.setattr(llm, "_clock", lambda: now[0])
    return now


async def ask():
    return await llm.complete_text("system", "user")


class TestFallingOver:
    async def test_a_spent_day_is_answered_by_the_fallback(self, groq, clock):
        replies, asked = groq
        replies[MAIN].append(refusal(MAIN))
        replies[FALLBACK].append(answer("from the fallback"))
        assert await ask() == "from the fallback"
        assert [a["model"] for a in asked] == [MAIN, FALLBACK]

    async def test_the_fallback_is_asked_to_keep_its_reasoning_short(self, groq, clock):
        replies, asked = groq
        replies[MAIN].append(refusal(MAIN))
        replies[FALLBACK].append(answer())
        await ask()
        main, fallback = asked
        assert "reasoning_effort" not in main
        assert fallback["reasoning_effort"] == "low"
        # and is given room for it on top of the answer
        assert fallback["max_tokens"] == main["max_tokens"] + 1000

    async def test_the_spent_model_is_not_asked_again_until_it_is_due(self, groq, clock):
        replies, asked = groq
        replies[MAIN].append(refusal(MAIN))
        replies[FALLBACK] += [answer("one"), answer("two")]
        await ask()
        assert await ask() == "two"
        assert [a["model"] for a in asked] == [MAIN, FALLBACK, FALLBACK]

        clock[0] += 3601  # Groq said an hour
        replies[MAIN].append(answer("main again"))
        assert await ask() == "main again"

    @pytest.mark.parametrize("status, body", [
        (404, '{"error":{"message":"The model `qwen/qwen3.8-27b` does not exist"}}'),
        (503, "service unavailable"),
    ])
    async def test_a_retired_model_or_a_server_error_falls_over_too(self, groq, clock,
                                                                    status, body):
        replies, _ = groq
        replies[MAIN].append(httpx.Response(status, text=body))
        replies[FALLBACK].append(answer("still here"))
        assert await ask() == "still here"


class TestNotFallingOver:
    async def test_a_rejected_key_is_not_tried_on_another_model(self, groq, clock):
        replies, asked = groq
        replies[MAIN].append(httpx.Response(401, text="invalid api key"))
        with pytest.raises(llm.LLMUnavailable):
            await ask()
        assert [a["model"] for a in asked] == [MAIN]

    async def test_no_connection_is_not_retried_either(self, groq, clock):
        replies, asked = groq
        replies[MAIN].append(httpx.ConnectError("no route"))
        with pytest.raises(llm.LLMUnavailable):
            await ask()
        assert [a["model"] for a in asked] == [MAIN]

    async def test_a_bad_reply_is_about_the_request_not_the_model(self, groq, clock):
        replies, asked = groq
        replies[MAIN].append(httpx.Response(200, json={"choices": [
            {"message": {"content": ""}, "finish_reason": "stop"}]}))
        with pytest.raises(llm.LLMResponseError):
            await ask()
        assert [a["model"] for a in asked] == [MAIN]

    async def test_off_when_empty(self, groq, clock, monkeypatch):
        replies, asked = groq
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "")
        reload_settings()
        replies[MAIN].append(refusal(MAIN))
        with pytest.raises(llm.LLMUnavailable):
            await ask()
        assert [a["model"] for a in asked] == [MAIN]

    def test_only_on_groq(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", FALLBACK)
        reload_settings()
        assert llm.models() == [llm.get_settings().llm_model]
        reload_settings()


class TestWhatHealthSays:
    async def test_answering_on_the_fallback_is_ok_and_says_so(self, groq, clock):
        replies, _ = groq
        replies[MAIN].append(refusal(MAIN))
        replies[FALLBACK].append(answer())
        await ask()
        status = llm.status()
        assert status["status"] == "ok"
        assert status["model"] == FALLBACK and status["main_model"] == "daily_limit"
        assert llm.recent_failure() is None  # not degraded: answers are still real

    async def test_both_spent_is_degraded_until_the_first_is_back(self, groq, clock):
        replies, _ = groq
        replies[MAIN].append(refusal(MAIN))
        replies[FALLBACK].append(refusal(FALLBACK))
        with pytest.raises(llm.LLMUnavailable):
            await ask()
        failure = llm.recent_failure()
        assert failure["reason"] == "daily_limit"
        assert llm.status()["status"] == "daily_limit"

    def test_the_default_is_a_production_model_on_the_same_key(self):
        from app.config import Settings

        assert Settings.model_fields["llm_fallback_model"].default == FALLBACK
        assert Settings.model_fields["llm_model"].default != FALLBACK
