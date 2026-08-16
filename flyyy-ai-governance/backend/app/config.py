"""
Flyyy.ai - SaaS AI Discovery & Monitoring Platform
Application configuration loaded from environment variables / .env file.
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
    """Central application settings.

    All secrets are read from environment variables and NEVER hardcoded.
    Copy `.env.example` to `.env` and fill in the placeholders before running
    against a real SaaS tenant.
    """

    # ---- Core ----
    APP_NAME: str = os.getenv("APP_NAME", "Flyyy.ai - SaaS AI Governance")
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["development", "production"] = os.getenv(
        "ENVIRONMENT", "development"
    )

    # ---- Database ----
    # Default to a local SQLite file so the app runs out-of-the-box.
    # For production, set a PostgreSQL URL, e.g.:
    #   DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/flyyy
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./flyyy.db"
    )

    # ---- Security ----
    # Used for the simple admin login protecting mutation endpoints.
    # REPLACE these placeholders before any real deployment.
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "CHANGE_ME_admin_2025")
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "dev-secret-key-please-change-in-production"
    )
    TOKEN_EXPIRE_MINUTES: int = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))

    # ---- CORS ----
    # Comma-separated list of allowed frontend origins.
    # In development this is the Vite dev server. In production set it to your
    # deployed frontend origin. Never combine a wildcard with credentials.
    BACKEND_CORS_ORIGINS: list[str] = _get_list(
        "BACKEND_CORS_ORIGINS", ["http://localhost:5173"]
    )

    # ---- Demo data ----
    # When true (default in development), the app seeds realistic simulated data
    # on startup so the full workflow is demonstrable without SaaS credentials.
    SEED_DEMO_DATA: bool = _get_bool("SEED_DEMO_DATA", True)

    # In production, table creation is performed by Alembic migrations, not by
    # the application startup. This flag is auto-derived: it is ONLY true when
    # ENVIRONMENT is not "production".
    CREATE_TABLES_ON_STARTUP: bool = os.getenv("ENVIRONMENT", "development") != "production"

    # ---- Microsoft 365 connector (PLACEHOLDERS - fill after app registration) ----
    # Create an Azure AD app registration with the required Graph / Management
    # Activity API permissions, then provide these values.
    MS365_TENANT_ID: str | None = os.getenv("MS365_TENANT_ID")
    MS365_CLIENT_ID: str | None = os.getenv("MS365_CLIENT_ID")
    MS365_CLIENT_SECRET: str | None = os.getenv("MS365_CLIENT_SECRET")
    # Optional: separate credentials for the Office 365 Management Activity API.
    MS365_MANAGEMENT_API_CLIENT_ID: str | None = os.getenv(
        "MS365_MANAGEMENT_API_CLIENT_ID"
    )
    MS365_MANAGEMENT_API_CLIENT_SECRET: str | None = os.getenv(
        "MS365_MANAGEMENT_API_CLIENT_SECRET"
    )
    # Whether to attempt a real connection. If False (or creds missing), the
    # Microsoft 365 connector reports itself as NOT_CONFIGURED and the system
    # transparently falls back to the demo connector for a runnable experience.
    MS365_ENABLED: bool = _get_bool("MS365_ENABLED", False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
