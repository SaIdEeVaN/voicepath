"""Environment configuration (PRD section 6.7).

Every provider in this codebase has an ``offline`` implementation, so the whole
pipeline runs end to end with no API keys at all. That is a development and demo
convenience, not a fallback that hides failure: offline providers announce
themselves in every response body (``provider: "offline"``) and the frontend
renders a visible banner. Nothing silently pretends to be a real model.
"""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["groq", "gemini", "offline"]
SpeechProvider = Literal["local", "groq", "offline"]
EmbeddingProvider = Literal["onnx", "local", "hf_api", "offline"]
SearchProvider = Literal["tavily", "offline"]
PlacesProvider = Literal["overpass", "offline"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Core ---------------------------------------------------------------
    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"

    database_url: str | None = Field(
        default=None,
        description="Postgres connection string. Without it the API runs in "
        "memory-only mode and persists nothing.",
    )

    # Comma-separated list; the frontend origin must appear here. 3001/3002 are
    # included because Next.js silently increments the port when 3000 is busy,
    # and the resulting CORS failure looks exactly like a dead backend.
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002"

    # -- Speech (all local; no speech vendor, no key, no per-call cost) -----
    # "groq" runs the same open-weight Whisper on someone else's GPU;
    # "local" runs it here. Measured on a 5.8s clip: 1.1s against 32.5s, which
    # is the difference between a usable screen and one people abandon.
    stt_provider: SpeechProvider = "groq"
    # faster-whisper size when stt_provider=local. "medium" is the balance point
    # on a CPU: "large-v3" was measured 1.6x slower and no better on Tamil.
    stt_model: str = "medium"
    # Model name when stt_provider=groq.
    stt_groq_model: str = "whisper-large-v3"
    stt_device: str = "cpu"
    # int8 quantisation. float16 needs a GPU; float32 doubles memory for no
    # measured accuracy gain at this size.
    stt_compute_type: str = "int8"

    tts_provider: SpeechProvider = "local"
    # Piper voices, one per language. A language with no voice file falls back
    # to the browser rather than failing the request.
    piper_voice_dir: str = "models/piper"
    # Voices to load at startup rather than on the first request that needs
    # one. Each is a 63 MB read, and it otherwise lands in the gap between a
    # person seeing an answer and hearing it -- again after every idle sleep on
    # a tier that sleeps. Comma-separated; empty warms nothing.
    #
    # Defaults to Tamil alone, which is the interface default and the language
    # most of this product's users speak. Warming all three would hold ~190 MB
    # on a 512 MB container.
    tts_warm_languages: str = "ta"

    # -- LLM ----------------------------------------------------------------
    # Groq hosting open-weight models. The weights are open source; the hosting
    # is not, so this is the one component that needs a key and a network.
    llm_provider: LLMProvider = "groq"
    llm_api_key: str | None = None
    # Measured against gpt-oss-120b and gpt-oss-20b on Tamil extraction:
    # fastest of the three, and the only one that caught a skill the person
    # described rather than named ("diagnosing engine problems by sound").
    # Groq rotates its lineup -- if this 404s, list /v1/models and re-pick.
    llm_model: str = "qwen/qwen3.8-27b"
    llm_base_url: str | None = None
    llm_timeout_seconds: float = 120.0
    llm_max_output_tokens: int = 4000
    # Headroom for models that think before answering. Llama on Groq does not,
    # so it is 0 here: every token budgeted is a token the answer can use.
    # Raise it if you point LLM_MODEL at a reasoning model.
    llm_reasoning_headroom: int = 0

    # -- Web search (PRD section 7) ------------------------------------------
    # Finds scheme pages the local corpus does not have. Offline without a key,
    # which means the ingested documents answer and nothing else does.
    search_provider: SearchProvider = "tavily"
    tavily_api_key: str | None = None
    search_timeout_seconds: float = 30.0
    search_result_limit: int = 5
    # A repeated question should not re-bill the API, and a cached answer is
    # what keeps the feature working when the API is down (section 20).
    search_cache_hours: int = 24

    # Tier 1: the domain is the trust signal, so pages from these are usable
    # without review. Everything else is fetched as pending_verification and
    # cannot be answered from until an admin looks at it (section 18).
    trusted_domains: str = (
        "gov.in,nic.in,india.gov.in,myscheme.gov.in,ncs.gov.in,"
        "skillindiadigital.gov.in,eshram.gov.in,pmvishwakarma.gov.in"
    )

    # Trusted, but not worth searching: these serve a JavaScript shell to any
    # crawler, ours and the search provider's alike, so every result slot spent
    # on them comes back as "Something went wrong" and is discarded. They stay
    # in trusted_domains -- a page from one is still Tier 1 if it ever arrives
    # by another route -- but asking for them wastes the query.
    unreadable_domains: str = "myscheme.gov.in"

    # Never searched, never stored, never trusted, whatever their suffix.
    # Public broadcasters' news sites are .gov.in, so a domain-only trust rule
    # made their sports pages Tier 1: a question comparing footballers fetched
    # two match reports and stored them as scheme guidance.
    excluded_domains: str = "ddnews.gov.in,newsonair.gov.in,prasarbharati.gov.in"

    # -- Nearby places (the map) ---------------------------------------------
    # Support offices near a person -- ITIs, employment offices, government
    # offices, banks -- come from OpenStreetMap. Searches around the towns the
    # map knows are answered from a bundled snapshot
    # (app/data/support_places.json, refreshed by
    # app.scripts.fetch_support_places); anything else asks the Overpass API
    # live. No key and no cost. "offline" turns the live lookups off; the
    # snapshot, being local data, still answers what it covers.
    places_provider: PlacesProvider = "overpass"
    # Tried in order. The public instances are volunteer-run and any one of
    # them can be busy, so a second endpoint is the difference between a map
    # with offices on it and one without.
    overpass_urls: str = (
        "https://overpass-api.de/api/interpreter,"
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    )
    places_timeout_seconds: float = 20.0
    # Offices do not move by the hour. A repeated search for the same area is
    # answered from memory rather than asking a volunteer server again.
    places_cache_hours: int = 24

    # -- Embeddings ---------------------------------------------------------
    # "onnx" (2026-11-10, the default) runs multilingual-e5-small inside the
    # API: an int8 ONNX export read by onnxruntime -- which Piper already
    # brings -- and tokenised by sentencepiece. No key, no credits to run out
    # of, about 200 MB of memory. Fetched at build time into
    # embedding_model_dir by scripts/fetch_embedding_model.py.
    #
    # "local" runs the model through sentence-transformers (torch; for
    # development). "hf_api" ran e5-base through the Hugging Face Inference
    # API until its credits ran out on 2026-11-04 and every call came back
    # 402. A different model writes different vectors: switching between them
    # means changing the pgvector columns and re-embedding (db/015).
    embedding_provider: EmbeddingProvider = "onnx"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dimension: int = 384
    embedding_model_dir: str = "models/e5-small"
    embedding_api_timeout: float = 60.0

    # Hugging Face token. Needed by embedding_provider=hf_api.
    hf_token: str | None = None

    # -- Matching (PRD section 8) ---------------------------------------------
    # The weights are per kind since 2026-11-09 -- a job, a course and a scheme
    # do not ask the same things -- and live in services/kinds.WEIGHTS, where
    # tests/test_kinds.py checks each set sums to 1.

    # Below this cosine similarity a normalized skill is not accepted outright
    # and is surfaced to the user for disambiguation instead (PRD section 4.3).
    #
    # Model-specific; re-measured 2026-11-10 for e5-small with
    # app/scripts/measure_embeddings.py over 50 described trades and 12
    # unrelated sentences. 0.84 accepts 28 of the 50 outright, 27 rightly --
    # the share e5-base accepted at 0.82, with one error fewer -- and none of
    # the unrelated sentences (the highest reached 0.809). The candidate
    # threshold filters nothing under either model (no sentence scored below
    # 0.78); the model's disambiguation and the person's own choice do that.
    normalization_accept_threshold: float = 0.84
    normalization_candidate_threshold: float = 0.60
    normalization_candidate_count: int = 3

    match_result_limit: int = 8

    # -- Privacy (PRD section 7) -------------------------------------------
    # No code path keeps a recording (routes/speech.py). This is the window
    # the daily safety net in main.py passes to purge_expired_audio: any clip
    # link older than it, or on a session that never opted in, is cleared.
    audio_retention_days: int = 90

    # -- Rate limiting (PRD section 6.6) -----------------------------------
    rate_limit_enabled: bool = True
    rate_limit_speech_per_minute: int = 12
    rate_limit_assistant_per_minute: int = 20
    rate_limit_default_per_minute: int = 60
    # The shared store for the counters (redis:// or rediss://) -- on Render,
    # the Key Value instance's internal URL. Unset: counted in this process,
    # which is right for one instance and multiplies behind several.
    rate_limit_redis_url: str | None = None

    # -- Admin (PRD section 6.6) -------------------------------------------
    # Bootstrap token, sha256-compared. Used only when admin_users is empty.
    admin_bootstrap_token: str | None = None

    max_audio_bytes: int = 15 * 1024 * 1024

    @model_validator(mode="after")
    def _resolve_providers(self) -> "Settings":
        """Downgrade to offline where credentials are missing, and say so.

        A provider configured but unusable is worse than an honest offline
        mode: it fails at request time, deep in the pipeline, with a vendor
        error the user cannot act on.
        """
        # Speech needs no credential now, only the package and the model
        # files. find_spec rather than import: importing faster-whisper pulls
        # in ctranslate2, which is slow at startup.
        if self.stt_provider == "local":
            if importlib.util.find_spec("faster_whisper") is None:
                object.__setattr__(self, "stt_provider", "offline")
        if self.stt_provider == "groq" and not self.llm_api_key:
            object.__setattr__(self, "stt_provider", "offline")
        if self.tts_provider == "local":
            if importlib.util.find_spec("piper") is None:
                object.__setattr__(self, "tts_provider", "offline")

        if self.llm_provider != "offline" and not self.llm_api_key:
            object.__setattr__(self, "llm_provider", "offline")

        # The on-server model needs its two packages and its two files. Without
        # them it is offline, said at startup, not a 500 on the first request.
        if self.embedding_provider == "onnx":
            folder = Path(self.embedding_model_dir)
            if (
                importlib.util.find_spec("onnxruntime") is None
                or importlib.util.find_spec("sentencepiece") is None
                or not (folder / "model_quantized.onnx").is_file()
                or not (folder / "sentencepiece.bpe.model").is_file()
            ):
                object.__setattr__(self, "embedding_provider", "offline")

        # find_spec rather than import: this runs at startup, and importing
        # sentence-transformers pulls in torch, which is seconds and gigabytes.
        if self.embedding_provider == "local":
            if importlib.util.find_spec("sentence_transformers") is None:
                object.__setattr__(self, "embedding_provider", "offline")

        # A search provider without a key is not a provider.
        if self.search_provider == "tavily" and not self.tavily_api_key:
            object.__setattr__(self, "search_provider", "offline")

        # The hosted embedder is useless without a token, and an embedder that
        # fails at query time is worse than one that says so at startup.
        if self.embedding_provider == "hf_api" and not self.hf_token:
            object.__setattr__(self, "embedding_provider", "offline")

        return self

    @property
    def tts_warm_language_list(self) -> list[str]:
        return [p.strip() for p in self.tts_warm_languages.split(",") if p.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_domain_list(self) -> list[str]:
        return [d.strip().lower() for d in self.trusted_domains.split(",") if d.strip()]

    @property
    def excluded_domain_list(self) -> list[str]:
        return [d.strip().lower() for d in self.excluded_domains.split(",") if d.strip()]

    @property
    def searchable_domain_list(self) -> list[str]:
        """Trusted domains a crawler can actually read."""
        skip = {d.strip().lower() for d in self.unreadable_domains.split(",") if d.strip()}
        return [d for d in self.trusted_domain_list if d not in skip]

    @property
    def overpass_url_list(self) -> list[str]:
        return [u.strip() for u in self.overpass_urls.split(",") if u.strip()]

    @property
    def persistence_enabled(self) -> bool:
        return bool(self.database_url)

    @property
    def degraded_providers(self) -> list[str]:
        """Providers running offline. Surfaced on /health and in responses."""
        out = []
        if self.stt_provider == "offline":
            out.append("stt")
        if self.tts_provider == "offline":
            out.append("tts")
        if self.llm_provider == "offline":
            out.append("llm")
        if self.embedding_provider == "offline":
            out.append("embeddings")
        if self.search_provider == "offline":
            out.append("search")
        if self.places_provider == "offline":
            out.append("places")
        if not self.persistence_enabled:
            out.append("database")
        return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Drop the cache. Tests use this after mutating the environment."""
    get_settings.cache_clear()
    return get_settings()


# Convenience for scripts that run outside the FastAPI lifespan.
def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
