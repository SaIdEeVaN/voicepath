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
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["groq", "gemini", "offline"]
SpeechProvider = Literal["local", "groq", "offline"]
EmbeddingProvider = Literal["local", "hf_api", "offline"]
NERProvider = Literal["local", "offline"]
SearchProvider = Literal["tavily", "offline"]


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

    # -- Entity tagging (PER/ORG/LOC; never skills -- see services/ner.py) ---
    ner_provider: NERProvider = "local"
    ner_model: str = "ai4bharat/IndicNER"

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

    # -- Embeddings ---------------------------------------------------------
    # "hf_api" runs the same model as "local" through the Hugging Face
    # Inference API, so vectors already in Postgres stay valid. It exists so a
    # deployment can drop torch (~530MB), which is what puts the container
    # inside a free tier's memory limit.
    embedding_provider: EmbeddingProvider = "local"
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dimension: int = 768
    embedding_api_timeout: float = 60.0

    # Hugging Face token. Needed by embedding_provider=hf_api, and by the
    # gated ai4bharat/IndicNER repo.
    hf_token: str | None = None

    # -- Matching (PRD section 8; weights are tunable per section 4.4) -------
    weight_skill: float = 0.50
    weight_experience: float = 0.25
    weight_eligibility: float = 0.15
    weight_location: float = 0.10

    # Below this cosine similarity a normalized skill is not accepted outright
    # and is surfaced to the user for disambiguation instead (PRD section 4.3).
    normalization_accept_threshold: float = 0.82
    normalization_candidate_threshold: float = 0.60
    normalization_candidate_count: int = 3

    match_result_limit: int = 8

    # -- Privacy (PRD section 7) -------------------------------------------
    # Hard off-switch. When false, no code path can persist audio, whatever
    # the request asks for.
    allow_audio_retention: bool = True
    audio_retention_days: int = 90

    # -- Rate limiting (PRD section 6.6) -----------------------------------
    rate_limit_enabled: bool = True
    rate_limit_speech_per_minute: int = 12
    rate_limit_assistant_per_minute: int = 20
    rate_limit_default_per_minute: int = 60

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

        # find_spec rather than import: this runs at startup, and importing
        # sentence-transformers pulls in torch, which is seconds and gigabytes.
        if self.embedding_provider == "local":
            if importlib.util.find_spec("sentence_transformers") is None:
                object.__setattr__(self, "embedding_provider", "offline")

        # A search provider without a key is not a provider.
        if self.search_provider == "tavily" and not self.tavily_api_key:
            object.__setattr__(self, "search_provider", "offline")

        if self.ner_provider == "local":
            if importlib.util.find_spec("transformers") is None:
                object.__setattr__(self, "ner_provider", "offline")

        # The hosted embedder is useless without a token, and an embedder that
        # fails at query time is worse than one that says so at startup.
        if self.embedding_provider == "hf_api" and not self.hf_token:
            object.__setattr__(self, "embedding_provider", "offline")

        total = (
            self.weight_skill
            + self.weight_experience
            + self.weight_eligibility
            + self.weight_location
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Matching weights must sum to 1.0, got {total:.4f}. "
                "See PRD section 8."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_domain_list(self) -> list[str]:
        return [d.strip().lower() for d in self.trusted_domains.split(",") if d.strip()]

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
        if self.ner_provider == "offline":
            out.append("ner")
        if self.search_provider == "offline":
            out.append("search")
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
