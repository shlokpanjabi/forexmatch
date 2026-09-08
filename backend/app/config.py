"""Application configuration.

Everything that varies between environments lives here and is read from the
environment (or ``backend/.env``). Two rules matter:

1. No secret ever has a usable default.
2. AWS credentials are never read from settings — Bedrock resolves them through
   the standard boto3 credential chain, so this process only needs to know the
   region and the model id.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Runtime configuration, loaded once and cached."""

    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # `model_` is a legitimate prefix for us (model_provider); stop pydantic
        # from treating those fields as protected namespace collisions.
        protected_namespaces=(),
    )

    # --- Application --------------------------------------------------------
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # --- Database -----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://localhost:5432/forexmatch"

    # --- Bedrock / model ----------------------------------------------------
    # "mock" runs the agent against a deterministic offline model so the whole
    # pipeline is exercisable without AWS access.
    model_provider: Literal["bedrock", "mock"] = "bedrock"
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-6"
    bedrock_max_tokens: int = 4096
    bedrock_temperature: float = 0.3
    #: Bedrock exposes Converse and ConverseStream as separately gated
    #: operations — an account can be cleared for one and not the other. Set
    #: false to fall back to the non-streaming Converse API.
    bedrock_streaming: bool = True

    # --- FX -----------------------------------------------------------------
    fx_provider: Literal["frankfurter", "exchangerate_host", "static"] = "frankfurter"
    fx_api_key: str | None = None
    fx_cache_ttl_seconds: int = 3600

    # --- Research -----------------------------------------------------------
    research_provider: Literal["bedrock", "none"] = "bedrock"
    research_max_results: int = 5

    # --- Admin --------------------------------------------------------------
    admin_secret: str | None = None

    # --- Optional integrations ---------------------------------------------
    posthog_api_key: str | None = None
    posthog_host: str = "https://eu.i.posthog.com"
    sentry_dsn: str | None = None

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        """Fail loudly rather than blocking the event loop on a sync driver."""
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL using the asyncpg driver, "
                f"e.g. postgresql+asyncpg://localhost:5432/forexmatch (got: {value.split('://')[0]}://…)"
            )
        return value

    @property
    def sync_database_url(self) -> str:
        """Alembic runs migrations synchronously via psycopg."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def analytics_enabled(self) -> bool:
        return bool(self.posthog_api_key)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings_field_names = set(Settings.model_fields)
__all__ = ["Settings", "get_settings", "BACKEND_ROOT", "REPO_ROOT"]
