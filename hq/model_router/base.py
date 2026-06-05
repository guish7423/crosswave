"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod

from .models import Capability, ModelProfile, ModelResponse


class ModelProvider(ABC):
    """Every LLM provider must implement this interface."""

    # ── metadata (set by __init_subclass__ or override) ──────────────
    provider_name: str = "unknown"
    capabilities: list[Capability] = []

    # ── abstract properties / methods ─────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name, e.g. \"DeepSeek Chat\"."""

    @abstractmethod
    def get_profile(self) -> ModelProfile:
        """Return a snapshot of this provider's current profile."""

    @abstractmethod
    async def chat(
        self, messages: list[dict], **kwargs: dict
    ) -> ModelResponse:
        """Send a chat completion request and return the response.

        Only the *first* choice is returned (no streaming).
        """

    @abstractmethod
    async def check_health(self) -> bool:
        """Return True if the provider is reachable and authenticated."""
