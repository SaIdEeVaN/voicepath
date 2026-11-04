"""Security hardening added 2026-11-04, one class per finding.

Each test is the attack the review found, run against the fix.
"""

from __future__ import annotations

import socket
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app import security
from app.config import reload_settings
from app.main import app
from app.services import ratelimit, websearch


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHeaders:
    def test_every_response_carries_them(self, client):
        response = client.get("/health")
        for name in ("content-security-policy", "x-content-type-options", "x-frame-options",
                     "referrer-policy", "strict-transport-security", "permissions-policy"):
            assert name in response.headers, name
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    def test_nothing_personal_is_cached(self, client):
        session = client.post(
            "/api/speech/client-transcript",
            json={"transcript": "I do welding.", "language_detected": "en"},
        ).json()["session_id"]
        response = client.get(f"/api/sessions/{session}")
        assert response.headers["cache-control"] == "no-store"

    def test_errors_carry_them_too(self, client):
        assert "x-frame-options" in client.get("/api/schemes/999999").headers

    def test_cors_admits_only_the_headers_the_frontend_sends(self, client):
        preflight = client.options(
            "/api/assistant/query",
            headers={"Origin": "http://localhost:3000",
                     "Access-Control-Request-Method": "POST",
                     "Access-Control-Request-Headers": "x-evil-header"},
        )
        assert preflight.status_code == 400

    def test_a_foreign_origin_gets_no_cors_grant(self, client):
        response = client.get("/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in response.headers


class TestDocs:
    def test_on_locally(self, monkeypatch):
        monkeypatch.delenv("RENDER", raising=False)
        assert security.docs_enabled("development")

    def test_off_on_render_and_in_production(self, monkeypatch):
        monkeypatch.delenv("RENDER", raising=False)
        assert not security.docs_enabled("production")
        monkeypatch.setenv("RENDER", "true")
        assert not security.docs_enabled("development")


class TestBodySize:
    def test_a_huge_json_body_is_refused_before_it_is_read(self, client):
        response = client.post(
            "/api/query/understand",
            content=b'{"text":"' + b"a" * (security.DEFAULT_MAX_BODY_BYTES + 10) + b'"}',
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 413
        assert "x-content-type-options" in response.headers

    def test_a_chunked_body_with_no_length_is_counted(self, client):
        def chunks():
            for _ in range(40):
                yield b"x" * 10_000

        response = client.post(
            "/api/query/understand", content=chunks(),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 413

    def test_audio_gets_its_own_larger_limit(self):
        middleware = security.BodySizeLimitMiddleware(app=None, max_audio_bytes=15_000_000)
        assert middleware.limit_for("/api/speech/transcribe") > 15_000_000
        assert middleware.limit_for("/api/assistant/query") == security.DEFAULT_MAX_BODY_BYTES

    def test_only_audio_is_accepted_as_a_recording(self, client):
        response = client.post(
            "/api/speech/transcribe",
            files={"file": ("x.html", b"<script>", "text/html")},
        )
        assert response.status_code == 415

    def test_an_overlong_text_field_is_refused(self, client):
        response = client.post("/api/query/understand", json={"text": "a" * 20001})
        assert response.status_code == 422


@pytest.fixture
def limits_on(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_ASSISTANT_PER_MINUTE", "3")
    reload_settings()
    ratelimit.reset()
    yield
    reload_settings()
    ratelimit.reset()


class TestRateLimits:
    def ask(self, client, session: str | None = None):
        headers = {"X-VoicePath-Session": session} if session else {}
        return client.post("/api/assistant/query",
                           json={"question_text": "how much does it pay?"}, headers=headers)

    def test_a_fresh_session_header_no_longer_resets_the_limit(self, client, limits_on):
        codes = [self.ask(client, str(uuid.uuid4())).status_code for _ in range(20)]
        # Per address: 3 x 4 = 12, whatever the session header says.
        assert codes.count(429) == 20 - 3 * ratelimit.PER_ADDRESS_MULTIPLIER

    def test_one_session_keeps_its_own_limit(self, client, limits_on):
        session = str(uuid.uuid4())
        codes = [self.ask(client, session).status_code for _ in range(5)]
        assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]

    def test_a_malformed_session_header_is_ignored_not_trusted(self, client, limits_on):
        codes = [self.ask(client, f"junk-{i}").status_code for i in range(14)]
        assert codes.count(429) == 14 - 3 * ratelimit.PER_ADDRESS_MULTIPLIER

    def test_there_is_a_ceiling_for_everyone_together(self, limits_on):
        assert ratelimit.GLOBAL_MULTIPLIER > ratelimit.PER_ADDRESS_MULTIPLIER


class TestAdminGuessing:
    def test_wrong_tokens_lock_the_address_out(self, client):
        ratelimit.reset()
        headers = {"Authorization": "Bearer wrong-token"}
        codes = [client.get("/api/admin/schemes", headers=headers).status_code
                 for _ in range(ratelimit.ADMIN_FAILURES_PER_ADDRESS + 2)]
        assert codes[: ratelimit.ADMIN_FAILURES_PER_ADDRESS] == [403] * ratelimit.ADMIN_FAILURES_PER_ADDRESS
        assert codes[-1] == 429
        # Locked out even with the right token, until the window passes.
        right = {"Authorization": "Bearer test-bootstrap-token-not-a-real-one"}
        assert client.get("/api/admin/schemes", headers=right).status_code == 429
        ratelimit.reset()
        assert client.get("/api/admin/schemes", headers=right).status_code == 200

    def test_a_missing_token_is_not_counted_as_a_guess(self, client):
        ratelimit.reset()
        for _ in range(ratelimit.ADMIN_FAILURES_PER_ADDRESS + 2):
            assert client.get("/api/admin/schemes").status_code == 401
        ratelimit.reset()


@pytest.fixture
def resolves_to(monkeypatch):
    table: dict[str, str] = {}

    def fake(host, port, *args, **kwargs):
        if host not in table:
            raise socket.gaierror("unknown host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (table[host], port))]

    monkeypatch.setattr(websearch.socket, "getaddrinfo", fake)
    return table


class TestPageFetching:
    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/", "http://localhost/", "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/", "http://[::1]/", "file:///etc/passwd", "ftp://pib.gov.in/x",
        "http://user:pass@pib.gov.in/", "http://pib.gov.in:8080/",
    ])
    async def test_internal_and_odd_addresses_are_refused(self, url, resolves_to):
        resolves_to.update({"localhost": "127.0.0.1", "pib.gov.in": "164.100.117.97"})
        with pytest.raises(websearch.SearchUnavailable):
            await websearch.ensure_public_url(url)

    async def test_a_name_that_resolves_inside_is_refused(self, resolves_to):
        resolves_to["innocent.gov.in"] = "192.168.1.10"
        with pytest.raises(websearch.SearchUnavailable):
            await websearch.ensure_public_url("https://innocent.gov.in/scheme")

    async def test_a_redirect_into_the_network_is_not_followed(self, resolves_to, monkeypatch):
        resolves_to.update({"pib.gov.in": "164.100.117.97", "metadata.internal": "169.254.169.254"})
        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            return httpx.Response(302, headers={"location": "http://metadata.internal/secrets"})

        real = httpx.AsyncClient
        monkeypatch.setattr(websearch.httpx, "AsyncClient",
                            lambda *a, **k: real(*a, transport=httpx.MockTransport(handler), **k))
        with pytest.raises(websearch.SearchUnavailable):
            await websearch.fetch_page("https://pib.gov.in/release")
        assert requested == ["https://pib.gov.in/release"]

    async def test_a_page_too_large_is_not_read_whole(self, resolves_to, monkeypatch):
        resolves_to["pib.gov.in"] = "164.100.117.97"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"<p>" + b"a" * (websearch.MAX_PAGE_BYTES + 1))

        real = httpx.AsyncClient
        monkeypatch.setattr(websearch.httpx, "AsyncClient",
                            lambda *a, **k: real(*a, transport=httpx.MockTransport(handler), **k))
        with pytest.raises(websearch.SearchUnavailable):
            await websearch.fetch_page("https://pib.gov.in/release")

    async def test_a_public_page_is_still_read(self, resolves_to, monkeypatch):
        resolves_to["pib.gov.in"] = "164.100.117.97"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, html="<html><body><p>PMEGP gives a margin money subsidy "
                                            "to new micro enterprises.</p></body></html>")

        real = httpx.AsyncClient
        monkeypatch.setattr(websearch.httpx, "AsyncClient",
                            lambda *a, **k: real(*a, transport=httpx.MockTransport(handler), **k))
        assert "margin money" in await websearch.fetch_page("https://pib.gov.in/release")
