"""VoicePath API.

Run with:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models import schemas
from app.routes import admin, assistant, schemes, profile, sessions, speech
from app.services import db, embeddings, llm, ner, stt, tts

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

    degraded = settings.degraded_providers
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
    yield
    await db.close_pool()


app = FastAPI(
    title="VoicePath API",
    description=(
        "Voice-first skill discovery and scheme matching for PM-AJAY "
        "beneficiaries. Extraction never invents; matching is deterministic; "
        "explanations describe a ranking they cannot change."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

_settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(speech.router)
app.include_router(profile.router)
app.include_router(schemes.router)
app.include_router(assistant.router)
app.include_router(sessions.router)
app.include_router(admin.router)


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
    degraded = settings.degraded_providers
    return schemas.HealthResponse(
        status="degraded" if degraded else "ok",
        providers={
            "stt": stt.provider_name(),
            "tts": tts.provider_name(),
            "llm": llm.provider_name(),
            "embeddings": embeddings.provider_name(),
            "ner": ner.provider_name(),
        },
        degraded=degraded,
        database=database,
    )


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "VoicePath API",
        "docs": "/docs",
        "health": "/health",
    }
