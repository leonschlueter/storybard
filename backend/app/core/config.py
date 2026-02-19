from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/storybard"
    DB_AUTOCREATE: bool = True

    OLLAMA_BASE_URL: str = "http://localhost:11434"

    LLM_MODEL_DEFAULT: str = "mistral"
    LLM_MODEL_INTENT: str | None = None
    LLM_MODEL_CHECK: str | None = None
    LLM_MODEL_KNOWLEDGE: str | None = None
    LLM_MODEL_GM: str | None = None
    LLM_MODEL_NARRATOR: str | None = None
    LLM_MODEL_MEMORY: str | None = None
    LLM_MODEL_THREAD: str | None = None
    LLM_MODEL_SEEDER: str | None = None

    LOG_LEVEL: str = "INFO"

    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_SERVICE_NAME: str = "storybard-engine"

    def model_for(self, role: str) -> str:
        role_map = {
            "intent": self.LLM_MODEL_INTENT,
            "check": self.LLM_MODEL_CHECK,
            "knowledge": self.LLM_MODEL_KNOWLEDGE,
            "gm": self.LLM_MODEL_GM,
            "narrator": self.LLM_MODEL_NARRATOR,
            "memory": self.LLM_MODEL_MEMORY,
            "thread": self.LLM_MODEL_THREAD,
            "seeder": self.LLM_MODEL_SEEDER,
        }
        return role_map.get(role) or self.LLM_MODEL_DEFAULT


settings = Settings()
