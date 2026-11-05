"""VoicePath API.

Run with:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models import schemas
from app.routes import admin, assistant, places, profile, query, schemes, sessions, speech
from app.services import (
    corpus_sync, db, embeddings, llm, ner, ratelimit, repository, stt, tts, websearch,
)
from app.services import schemes as schemes_service
from app.services import taxonomy as taxonomy_service
from app.services import places as places_service
from app import security
from app.security import BodySizeLimitMiddleware, SecurityHeadersMiddleware, SessionKeyMiddleware

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    await db.init_pool()

    # A short bootstrap token can be guessed, lockout or not.
    if settings.admin_bootstrap_token and len(settings.admin_bootstrap_token) < 32:
        logger.warning(
            "ADMIN_BOOTSTRAP_TOKEN is shorter than 32 characters. Use a long random "
            "value (python -c 'import secrets; print(secrets.token_urlsafe(32))')."
        )

    degraded = _degraded(settings)
    if degraded:
        # Loud, once, at startup -- so nobody discovers it from a puzzling
        # response three screens into a demo.
        logger.warning(
            "Running with offline providers for: %s. Responses will say so.",
            ", ".join(degraded),
        )
    logger.info(
        "Providers -- stt=%s tts=%s llm=%s embeddings=%s db=%s",
        settings.stt_provider, settings.tts_provider, settings.llm_provider,
        settings.embedding_provider, "on" if settings.persistence_enabled else "memory",
    )

    # Load the speech voices in the background rather than on the first
    # request that needs one.
    #
    # Not awaited: a 63 MB read would delay the app reporting itself ready,
    # and the point is only to move the read off the path of someone waiting.
    # Whoever speaks first is recording and being transcribed while this runs,
    # so it is usually finished before any audio is asked for -- and if it is
    # not, `synthesize` loads it the old way and nothing breaks.
    #
    # The reference is held because asyncio only keeps a weak one, and a task
    # nobody holds can be collected mid-read.
    warming = asyncio.create_task(_warm_voices(settings))

    # Whatever this release ships that the database lacks: embeddings for new
    # skills, bundled documents not yet in the corpus, document URLs now on
    # record. Background, idempotent, and a no-op once caught up.
    syncing = asyncio.create_task(corpus_sync.catch_up_safely())

    # A configured database that did not answer: keep trying, and switch over
    # once nobody is mid-flow on the in-memory store.
    reconnecting = (
        asyncio.create_task(
            db.reconnect_in_background(
                is_quiet=lambda: repository.memory_quiet(MEMORY_IDLE_BEFORE_SWITCH_SECONDS),
                on_connected=_after_reconnect,
            )
        )
        if db.is_configured() and not db.is_available()
        else None
    )

    # The privacy safety net, daily: no clip link may outlive its window or
    # sit on a session that never opted in. Nothing keeps a recording today;
    # this holds the line if anything ever does.
    purging = asyncio.create_task(purge_audio_daily())

    yield

    warming.cancel()
    syncing.cancel()
    purging.cancel()
    if reconnecting is not None:
        reconnecting.cancel()
    await db.close_pool()


PURGE_INTERVAL_SECONDS = 24 * 60 * 60


async def purge_audio_once() -> int | None:
    """Run db/002's purge_expired_audio once. None when there is no database."""
    if not db.is_available():
        return None
    try:
        cleared = await db.fetchval(
            "select purge_expired_audio($1)", get_settings().audio_retention_days
        )
    except Exception:  # noqa: BLE001 - a missed night is retried tomorrow
        logger.exception("Audio purge failed")
        return None
    if cleared:
        logger.warning("Audio purge cleared %d clip link(s)", cleared)
    return int(cleared or 0)


async def purge_audio_daily(sleep=asyncio.sleep) -> None:
    while True:
        await purge_audio_once()
        await sleep(PURGE_INTERVAL_SECONDS)


# How long the in-memory store must sit unused before the API switches to a
# database that has come back. Nobody is mid-flow after half an hour idle.
MEMORY_IDLE_BEFORE_SWITCH_SECONDS = 30 * 60


async def _after_reconnect() -> None:
    """Hand over from the in-memory store to the database that came back."""
    retired = repository.retire_memory_sessions()
    # Built from the bundled catalogue while the database was away; the
    # database's rows (and ids) are the ones to use now.
    taxonomy_service.reset_memory_cache()
    schemes_service.reset_memory_cache()
    logger.warning(
        "Switched to the database; %d session(s) from the outage were not saved", retired
    )
    await corpus_sync.catch_up_safely()


def _degraded(settings) -> list[str]:
    """Providers running offline, including a database that would not answer.

    Settings can only see whether DATABASE_URL is set. Whether the database
    behind it actually connected is known only after startup tried it -- and
    a configured database that did not answer is the more important of the
    two to report, because everything looks configured.
    """
    degraded = list(settings.degraded_providers)
    if db.unreachable() is not None and "database" not in degraded:
        degraded.append("database")
    # Configured but not answering: rate-limited, out of quota, or down.
    if llm.recent_failure() is not None and "llm" not in degraded:
        degraded.append("llm")
    if embeddings.recent_failure() is not None and "embeddings" not in degraded:
        degraded.append("embeddings")
    return degraded


async def _warm_voices(settings) -> None:
    languages = settings.tts_warm_language_list
    if not languages:
        return
    try:
        loaded = await tts.warm(languages)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - never worth failing startup for
        logger.warning("Voice warming failed (%s); voices load on first use", exc)
        return
    if loaded:
        logger.info("Speech voices ready: %s", ", ".join(loaded))


_settings = get_settings()
_docs = security.docs_enabled(_settings.app_env)

app = FastAPI(
    # Off on Render and in production: they listed every route, admin ones
    # included, to anyone. Local development keeps them.
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
    title="VoicePath API",
    description=(
        "Voice-first skill discovery and scheme matching for PM-AJAY "
        "beneficiaries. Extraction never invents; matching is deterministic; "
        "explanations describe a ranking they cannot change."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    # Only the headers the frontend sends; "*" admitted anything.
    allow_headers=[
        "Content-Type", "Authorization", "X-VoicePath-Session", "X-VoicePath-Session-Key",
    ],
    max_age=600,
)
# Added last so they run first: a body over its limit is refused before CORS
# or a route sees it, and every response, refusals included, carries the
# security headers.
app.add_middleware(SessionKeyMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_audio_bytes=_settings.max_audio_bytes)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(speech.router)
app.include_router(profile.router)
app.include_router(query.router)
app.include_router(schemes.router)
app.include_router(assistant.router)
app.include_router(sessions.router)
app.include_router(places.router)
app.include_router(admin.router)


@app.exception_handler(repository.SessionAccessDenied)
async def session_denied_handler(
    request: Request, exc: repository.SessionAccessDenied
) -> JSONResponse:
    """A session asked for without its key: as if it did not exist (404), or,
    for one from before keys existed, a plain "start again" (410)."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Turn a service-layer ValueError into a 400 rather than a 500.

    The services raise ValueError for "you asked for something impossible",
    which is a client problem, not a server fault.
    """
    logger.info("Bad request at %s: %s", request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", response_model=schemas.HealthResponse, tags=["meta"])
async def health() -> schemas.HealthResponse:
    settings = get_settings()
    database = await db.healthcheck()
    degraded = _degraded(settings)
    return schemas.HealthResponse(
        status="degraded" if degraded else "ok",
        providers={
            "stt": stt.provider_name(),
            "tts": tts.provider_name(),
            "llm": llm.provider_name(),
            "embeddings": embeddings.provider_name(),
            "ner": ner.provider_name(),
            "search": websearch.provider_name(),
            "places": places_service.provider_name(),
        },
        degraded=degraded,
        database=database,
        llm=llm.status(),
        embeddings=embeddings.status(),
        rate_limits=ratelimit.status_report(),
    )


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "VoicePath API",
        "docs": "/docs",
        "health": "/health",
    }
