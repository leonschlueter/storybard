from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/storybard"
    ALLOWED_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
