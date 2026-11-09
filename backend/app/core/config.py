from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str = "sqlite:///./urbix.db"
    urbix_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openaq_api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    urbix_env: str = "development"
    urbix_refresh_hours: float = 0
    urbix_bootstrap_on_start: bool = False

    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")


settings = Settings()
os.environ.setdefault("DATABASE_URL", settings.database_url)
if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
if settings.openaq_api_key:
    os.environ.setdefault("OPENAQ_API_KEY", settings.openaq_api_key)
