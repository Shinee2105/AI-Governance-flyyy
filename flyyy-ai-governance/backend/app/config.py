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
    # the application startup. Auto-create is ONLY true in development.
    CREATE_TABLES_ON_STARTUP: bool = os.getenv("ENVIRONMENT", "development") != "production"

    # ---- Salesforce connector (OPTIONAL - fill to discover REAL evidence) ----
    # 1. Enable External Client Apps in your Salesforce org.
    # 2. Create an External Client App (Connected App) with OAuth 2.0 enabled.
    # 3. Use the Client Credentials grant type, assign scopes (api, etc.),
    #    and set the Run-As integration user.
    # 4. Provide the domain, client ID, and client secret below, then set
    #    SFDC_ENABLED=true.
    # 5. (Monitoring) For Agentforce session traces, obtain session IDs from the
    #    Session Trace UI in Salesforce and set SFDC_OTEL_SESSION_IDS.
    SFDC_ENABLED: bool = _get_bool("SFDC_ENABLED", False)
    SFDC_DOMAIN: str | None = os.getenv("SFDC_DOMAIN")
    SFDC_CLIENT_ID: str | None = os.getenv("SFDC_CLIENT_ID")
    SFDC_CLIENT_SECRET: str | None = os.getenv("SFDC_CLIENT_SECRET")
    SFDC_API_VERSION: str = os.getenv("SFDC_API_VERSION", "62.0")
    # Comma-separated list of Agentforce session IDs for OTel trace retrieval.
    # Obtain from the Salesforce Session Trace UI / Data Explorer.
    SFDC_OTEL_SESSION_IDS: str | None = os.getenv("SFDC_OTEL_SESSION_IDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
