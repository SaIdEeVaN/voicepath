"""/health says when the model is configured but not answering.

On 2026-09-12 Groq's daily allowance ran out. Every extraction, explanation
and answer fell back to its rule-based path, and /health went on reporting
`llm: groq` with nothing degraded -- so the interface told nobody why the
answers had become thinner. These tests hold the fix: a refusal that means
the service is not answering is remembered for as long as the provider says
it will last, reported, and forgotten at the next answer.
"""

from __future__ import annotations

import httpx
import pytest

from app.config import reload_settings
from app.main import health
from app.services import llm

DAILY_LIMIT_BODY = (
    '{"error":{"message":"Rate limit reached for model `qwen/qwen3.8-27b` in '
    "organization `org_x` service tier `on_demand` on tokens per day (TPD): "
    "Limit 200000, Used 199527, Requested 1234. Please try again in 7m12.5s. "
    'Need more tokens?","type":"tokens","code":"rate_limit_exceeded"}}'
)
OK_BODY = {"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}]}


@pytest.fixture
def groq(monkeypatch):
    """A configured Groq whose replies the test decides."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    reload_settings()

    replies: list = []
    real = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(llm.httpx, "AsyncClient", client)
    yield replies
    reload_settings()


@pytest.fixture
def clock(monkeypatch):
    now = [1_800_000_000.0]
    monkeypatch.setattr(llm, "_clock", lambda: now[0])
    return now


async def _call():
    return await llm.complete_text("system", "user")


async def _fails(replies, reply):
    replies.append(reply)
    with pytest.raises(llm.LLMUnavailable):
        await _call()


class TestWhatCountsAsNotAnswering:
    async def test_the_daily_limit_holds_for_as_long_as_groq_says(self, groq, clock):
        await _fails(
            groq,
            httpx.Response(429, text=DAILY_LIMIT_BODY, headers={"retry-after": "433"}),
        )
        failure = llm.recent_failure()
        assert failure["reason"] == "daily_limit"

        clock[0] += 432
        assert llm.recent_failure() is not None
        clock[0] += 2
        assert llm.recent_failure() is None

    async def test_without_a_header_the_message_gives_the_wait(self, groq, clock):
        await _fails(groq, httpx.Response(429, text=DAILY_LIMIT_BODY))
        clock[0] += 432
        assert llm.recent_failure() is not None
        clock[0] += 1
        assert llm.recent_failure() is None

    async def test_a_per_minute_limit_is_a_rate_limit(self, groq, clock):
        await _fails(groq, httpx.Response(429, text='{"error":{"message":"slow down"}}'))
        assert llm.recent_failure()["reason"] == "rate_limited"
        clock[0] += llm._DEFAULT_HOLD_SECONDS + 1
        assert llm.recent_failure() is None

    @pytest.mark.parametrize(
        ("status", "reason"),
        [(401, "rejected"), (403, "rejected"), (404, "model_missing"),
         (500, "server_error"), (503, "server_error")],
    )
    async def test_the_service_level_refusals(self, groq, clock, status, reason):
        await _fails(groq, httpx.Response(status, text="no"))
        assert llm.recent_failure()["reason"] == reason

    async def test_no_connection_is_unreachable(self, groq, clock):
        await _fails(groq, httpx.ConnectError("refused"))
        assert llm.recent_failure()["reason"] == "unreachable"

    async def test_a_bad_request_is_about_the_request_not_the_service(self, groq, clock):
        await _fails(groq, httpx.Response(400, text='{"error":"context too long"}'))
        assert llm.recent_failure() is None

    async def test_a_wait_of_days_is_capped_at_one(self, groq, clock):
        await _fails(groq, httpx.Response(429, text="x", headers={"retry-after": "999999"}))
        clock[0] += 24 * 3600 + 1
        assert llm.recent_failure() is None


class TestRecovery:
    async def test_the_next_answer_clears_it(self, groq, clock):
        await _fails(groq, httpx.Response(429, text=DAILY_LIMIT_BODY))
        groq.append(httpx.Response(200, json=OK_BODY))
        assert await _call() == "hello"
        assert llm.recent_failure() is None

    async def test_a_continuing_outage_keeps_the_time_it_started(self, groq, clock):
        await _fails(groq, httpx.Response(503, text="down"))
        started = llm.recent_failure()["since"]
        clock[0] += 60
        await _fails(groq, httpx.Response(503, text="down"))
        assert llm.recent_failure()["since"] == started


class TestHealth:
    async def test_it_reports_the_model_as_degraded_and_why(self, groq, clock):
        await _fails(
            groq,
            httpx.Response(429, text=DAILY_LIMIT_BODY, headers={"retry-after": "600"}),
        )
        report = await health()
        assert report.status == "degraded"
        assert "llm" in report.degraded
        assert report.llm["status"] == "daily_limit"
        assert report.llm["until"] > report.llm["since"]

    async def test_a_model_that_is_answering_is_ok(self, groq, clock):
        groq.append(httpx.Response(200, json=OK_BODY))
        await _call()
        report = await health()
        assert report.llm == {"status": "ok"}
        assert "llm" not in report.degraded

    async def test_it_recovers_on_its_own_when_the_wait_is_over(self, groq, clock):
        await _fails(groq, httpx.Response(429, text="x", headers={"retry-after": "30"}))
        clock[0] += 31
        report = await health()
        assert report.llm == {"status": "ok"}
        assert "llm" not in report.degraded

    async def test_offline_by_configuration_says_offline(self):
        report = await health()
        assert report.llm == {"status": "offline"}
        assert "llm" in report.degraded
