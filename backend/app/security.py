"""HTTP-level protections for the API, applied to every request.

Added 2026-11-04 after a security review of the deployed service. Each piece
answers something that review found; none of it changes what an endpoint does.

* **Security headers** on every response. The API serves JSON to a frontend
  on another origin, so it should never be framed, sniffed into HTML, or
  cached by anything between it and the person -- sessions carry what someone
  said about their work.
* **A ceiling on request bodies.** Starlette reads a body into memory before a
  route sees it, and the audio route used to read the whole upload before
  checking its size, so one large request could take a 512 MB instance down.
  A body over the limit is refused as it streams in -- from its declared
  length when it has one, by counting when it does not.
* **API docs off in production.** ``/docs`` listed every route, admin ones
  included, to anyone. Locally they stay, because that is where they help.

Written as plain ASGI middleware rather than ``BaseHTTPMiddleware`` so a body
is counted as it arrives instead of after it has been read.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# JSON bodies. The largest legitimate one is an admin scheme edit or a typed
# transcript (capped at 20,000 characters by its schema): a few tens of KB.
DEFAULT_MAX_BODY_BYTES = 256 * 1024
# Multipart audio carries some form overhead on top of the audio itself.
_MULTIPART_OVERHEAD = 64 * 1024

# Paths whose bodies are recorded audio. Everything else is JSON.
AUDIO_PATHS = ("/api/speech/transcribe",)

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    # JSON is never a document to render, so nothing may load or frame it.
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"strict-transport-security", b"max-age=63072000; includeSubDomains"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
)

# The docs pages load Swagger's script and styles from a CDN; the JSON
# policy above would blank them. They exist only outside production.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def docs_enabled(app_env: str) -> bool:
    """Interactive API docs: on locally, off on Render or in production."""
    if os.environ.get("RENDER"):  # Render sets RENDER=true on every service.
        return False
    return app_env != "production"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        docs = scope.get("path", "").startswith(_DOCS_PATHS)

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                present = {name.lower() for name, _ in headers}
                for name, value in SECURITY_HEADERS:
                    if docs and name == b"content-security-policy":
                        continue
                    if name not in present:
                        headers.append((name, value))
                # Nothing here is meant to be cached by a browser or a proxy:
                # sessions hold what a person said about themselves.
                if b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, with_headers)


class BodySizeLimitMiddleware:
    """Refuse a request body over its route's limit, without buffering it."""

    def __init__(self, app: ASGIApp, *, max_audio_bytes: int,
                 max_body_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_audio_bytes = max_audio_bytes + _MULTIPART_OVERHEAD
        self.max_body_bytes = max_body_bytes

    def limit_for(self, path: str) -> int:
        return self.max_audio_bytes if path.startswith(AUDIO_PATHS) else self.max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope.get("path", ""))

        declared = next(
            (v for k, v in scope.get("headers") or [] if k.lower() == b"content-length"),
            None,
        )
        if declared is not None:
            try:
                too_big = int(declared) > limit
            except ValueError:
                too_big = True
            if too_big:
                await _refuse(send, limit)
                return

        received = 0
        refused = False

        async def counting_receive() -> Message:
            nonlocal received, refused
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body") or b"")
                if received > limit:
                    refused = True
                    raise _BodyTooLarge
            return message

        answered = False

        async def guarded_send(message: Message) -> None:
            # The route or the framework may catch the overflow as a parsing
            # error and answer 400 on its own. Once the limit was crossed, the
            # answer is 413 whatever the app tried to send.
            nonlocal answered
            if refused:
                if not answered:
                    answered = True
                    await _refuse(send, limit)
                return
            answered = answered or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except _BodyTooLarge:
            if not answered:
                await _refuse(send, limit)
        except Exception:
            if refused and not answered:
                await _refuse(send, limit)
            elif not refused:
                raise
        else:
            if refused and not answered:
                await _refuse(send, limit)


class _BodyTooLarge(Exception):
    pass


async def _refuse(send: Send, limit: int) -> None:
    body = (
        b'{"detail":"The request is too large. The limit is '
        + str(limit // 1024).encode()
        + b' KB."}'
    )
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"connection", b"close"),
        ],
    })
    await send({"type": "http.response.body", "body": body})
