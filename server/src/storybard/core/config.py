from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/storybard"
    DB_AUTOCREATE: bool = True

    # LM Studio's local server, OpenAI-compatible API.
    LM_STUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LLM_MODEL_DEFAULT: str = "google/gemma-4-e4b"
    # Used only for the chain's judgment-heavy nodes (chain/graph.py's CREATIVE_NODE_TYPES
    # — opportunity_spotting, plan_synthesis, world_update). Confirmed live: the default
    # small model stayed conservative on "should something be created here" even with
    # perfect context; a bigger model reliably acts on the same information. Routing only
    # those three nodes through it keeps most of the chain fast.
    LLM_MODEL_CREATIVE: str = "qwen/qwen3.8-27b"
    LM_STUDIO_EMBED_MODEL: str = "text-embedding-nomic-embed-text-v1.5"

    LOG_LEVEL: str = "INFO"

    # Deterministic guardrails on world-mutating ops — never trusted to the LLM. Real
    # per-campaign hot-swappable Settings is Phase 5; these are tunable env-level defaults
    # for now. See spec.md "Narrative momentum: Thread, Clock, Hook".
    MAX_MAJOR_THREADS: int = 3
    MAX_MINOR_THREADS_PER_PARENT: int = 5


settings = Settings()
