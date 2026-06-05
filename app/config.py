"""CrossWave — Pydantic v2 Settings (fail-fast on env validation)."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Environment ────────────────────────────────────────────────────
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    proxy_timeout: int = 5

    # ── Polsia Fork ────────────────────────────────────────────────────
    polsia_base_url: str = "http://localhost:8000"
    polsia_api_key: str = "dev-key"
    polsia_mock: bool = True

    # ── LLM Providers ──────────────────────────────────────────────────
    llm_api_key: str | None = Field(default=None, repr=False)
    deepseek_api_key: str | None = Field(default=None, repr=False)
    openai_base_url: str = "https://api.openai.com/v1"
    llm_provider_mock: bool = True

    # ── Sentry ─────────────────────────────────────────────────────────
    sentry_dsn: str | None = Field(default=None, repr=False)

    # ── Admin Login ────────────────────────────────────────────────────
    secret_key: str = "dev-secret"  # noqa: S105
    admin_username: str = "admin"
    admin_password_hash: str = ""

    # ── CrossBlog ──────────────────────────────────────────────────────
    crossblog_url: str = "http://127.0.0.1:8001"

    # ── Stripe ─────────────────────────────────────────────────────────
    stripe_secret_key: str | None = Field(default=None, repr=False)
    stripe_webhook_secret: str | None = Field(default=None, repr=False)
    stripe_price_ids: dict[str, str] = {}  # e.g. {"crossbridge_starter": "price_xxx"}

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v: object) -> bool:
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)

    @field_validator("polsia_mock", "llm_provider_mock", mode="before")
    @classmethod
    def parse_bool(cls, v: object) -> bool:
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)


settings = Settings()
