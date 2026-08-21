"""
Flyyy.ai application configuration. Loaded from environment variables / .env.
All secrets are read from env vars and NEVER hardcoded.
"""

import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_list(name: str, default: list[str]) -> list[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [v.strip() for v in val.split(",") if v.strip()]


class Settings:
    """Central application settings."""

    APP_NAME: str = os.getenv("APP_NAME", "Flyyy.ai - SaaS AI Governance")
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["development", "production"] = os.getenv(
        "ENVIRONMENT", "development"
    )

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./flyyy.db"
    )

    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "CHANGE_ME_admin_2025")
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "dev-secret-key-please-change-in-production"
    )
    TOKEN_EXPIRE_MINUTES: int = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))

    BACKEND_CORS_ORIGINS: list[str] = _get_list(
        "BACKEND_CORS_ORIGINS", ["http://localhost:5173"]
    )

    SEED_DEMO_DATA: bool = _get_bool("SEED_DEMO_DATA", True)
    CREATE_TABLES_ON_STARTUP: bool = os.getenv("ENVIRONMENT", "development") != "production"

    SFDC_ENABLED: bool = _get_bool("SFDC_ENABLED", False)
    SFDC_DOMAIN: str | None = os.getenv("SFDC_DOMAIN")
    SFDC_CLIENT_ID: str | None = os.getenv("SFDC_CLIENT_ID")
    SFDC_CLIENT_SECRET: str | None = os.getenv("SFDC_CLIENT_SECRET")
    SFDC_API_VERSION: str = os.getenv("SFDC_API_VERSION", "62.0")
    SFDC_OTEL_SESSION_IDS: str | None = os.getenv("SFDC_OTEL_SESSION_IDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
