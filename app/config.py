"""CrossWave — centralized configuration."""

from dataclasses import dataclass, field
from os import environ


@dataclass
class Settings:
    polsia_base_url: str = field(
        default_factory=lambda: environ.get(
            "POLSIA_BASE_URL", "http://localhost:8000"
        )
    )
    polsia_api_key: str = field(
        default_factory=lambda: environ.get("POLSIA_API_KEY", "dev-key")
    )
    proxy_timeout: int = 5
    debug: bool = field(
        default_factory=lambda: environ.get("DEBUG", "true").lower() == "true"
    )
    polsia_mock: bool = field(
        default_factory=lambda: environ.get("POLSIA_MOCK", "true").lower() == "true"
    )

    # ── LLM Provider Abstraction (Phase 3) ──────────────────────────
    llm_api_key: str = field(
        default_factory=lambda: environ.get("LLM_API_KEY", "")
    )
    deepseek_api_key: str = field(
        default_factory=lambda: environ.get("DEEPSEEK_API_KEY", "")
    )
    openai_base_url: str = field(
        default_factory=lambda: environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
    )
    llm_provider_mock: bool = field(
        default_factory=lambda: environ.get("LLM_PROVIDER_MOCK", "true").lower()
        == "true"
    )


settings = Settings()
