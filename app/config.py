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


settings = Settings()
