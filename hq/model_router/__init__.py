"""Model Router — LLM Provider Abstraction Layer (Phase 3).

Exports:
  - ProviderRegistry     — register providers, select by capability
  - get_registry()       — singleton factory
  - AGENT_CAPABILITY_MAP — agent type → capability mapping
"""

import os
from typing import Optional

from .base import ModelProvider
from .models import Capability, ModelProfile, ModelResponse

# ─── Agent → Capability mapping ──────────────────────────────────────────

AGENT_CAPABILITY_MAP: dict[str, Capability] = {
    "orchestrator": "analysis",
    "social_media": "content_gen",
    "competitor_research": "analysis",
    "business_planning": "analysis",
    "code_generation": "code",
    "finance": "analysis",
    "email_outreach": "content_gen",
    "customer_support": "conversation",
    "ads_management": "content_gen",
    "deployment": "code",
    "order_scanner": "classification",
    "lead_nurturing": "conversation",
    "market_intel": "analysis",
    "evolution": "analysis",
    "monitor": "classification",
}


def resolve_capability(agent_type: str) -> Optional[Capability]:
    """Return the capability for a given agent type, or None."""
    return AGENT_CAPABILITY_MAP.get(agent_type)


# ─── Registry ────────────────────────────────────────────────────────────


class ProviderRegistry:
    """Holds all registered providers and routes by capability."""

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    # ── registration ────────────────────────────────────────────────

    def register(self, provider: ModelProvider) -> None:
        """Register a provider under its ``provider_name``."""
        self._providers[provider.provider_name] = provider

    # ── queries ─────────────────────────────────────────────────────

    def get_all_profiles(self) -> list[ModelProfile]:
        return [p.get_profile() for p in self._providers.values()]

    def get_available_profiles(self) -> list[ModelProfile]:
        return [p for p in self.get_all_profiles() if p.available]

    def get_profile(self, name: str) -> Optional[ModelProfile]:
        for p in self._providers.values():
            if p.name == name:
                return p.get_profile()
        return None

    # ── routing ─────────────────────────────────────────────────────

    def select_model(self, agent_type: str) -> Optional[ModelProvider]:
        """Return the best available provider for *agent_type*.

        Selection algorithm:
          1. Resolve agent_type → capability via AGENT_CAPABILITY_MAP
          2. Filter providers that support that capability AND are available
          3. Sort by ``priority`` (ascending, lower = better)
          4. Return the first match, or *any* available provider as fallback
        """
        cap = resolve_capability(agent_type)
        candidates: list[ModelProvider] = []
        fallback: list[ModelProvider] = []

        for p in self._providers.values():
            prof = p.get_profile()
            if not prof.available:
                continue
            if cap and cap in prof.capabilities:
                candidates.append(p)
            fallback.append(p)

        candidates.sort(key=lambda p: p.get_profile().priority)
        if candidates:
            return candidates[0]
        fallback.sort(key=lambda p: p.get_profile().priority)
        return fallback[0] if fallback else None

    async def chat(
        self, agent_type: str, messages: list[dict], **kwargs
    ) -> ModelResponse:
        """Route a chat request to the best provider for *agent_type*."""
        provider = self.select_model(agent_type)
        if provider is None:
            return ModelResponse(
                content="No available model provider.",
                model="none",
                provider="none",
            )
        return await provider.chat(messages, **kwargs)

    def __len__(self) -> int:
        return len(self._providers)


# ─── Singleton factory ───────────────────────────────────────────────────

_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    """Return the singleton registry, building it on first call."""
    global _registry
    if _registry is not None:
        return _registry

    _registry = ProviderRegistry()

    # Lazy-import providers here so the package can be imported without
    # depending on httpx / env vars at module level.
    from .providers import DeepSeekProvider, MockProvider, OpenAIChatProvider  # noqa: PLC0415

    _registry.register(MockProvider())

    if os.environ.get("LLM_API_KEY"):
        _registry.register(OpenAIChatProvider())

    if os.environ.get("DEEPSEEK_API_KEY"):
        _registry.register(DeepSeekProvider())

    return _registry
