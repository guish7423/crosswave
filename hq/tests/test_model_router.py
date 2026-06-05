"""Tests for the model_router package (Phase 3)."""

import os
from unittest.mock import patch

import pytest

from hq.model_router import AGENT_CAPABILITY_MAP, ProviderRegistry, get_registry, resolve_capability

# ══════════════════════════════════════════════════════════════════════════
# 1. Agent → Capability mapping
# ══════════════════════════════════════════════════════════════════════════


class TestAgentCapabilityMap:
    def test_known_agents_have_capabilities(self):
        """Every agent type in the map should have a valid capability."""
        valid_caps = {
            "analysis",
            "content_gen",
            "code",
            "classification",
            "summarization",
            "conversation",
        }
        for agent, cap in AGENT_CAPABILITY_MAP.items():
            assert cap in valid_caps, f"{agent} -> {cap} is not valid"

    def test_resolve_capability_found(self):
        assert resolve_capability("code_generation") == "code"
        assert resolve_capability("social_media") == "content_gen"

    def test_resolve_capability_none(self):
        assert resolve_capability("nonexistent_agent") is None

    def test_map_is_not_empty(self):
        assert len(AGENT_CAPABILITY_MAP) > 0


# ══════════════════════════════════════════════════════════════════════════
# 2. MockProvider
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_provider():
    from hq.model_router.providers import MockProvider

    return MockProvider()


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_all_capabilities(self, mock_provider):
        """Every capability should return a non-empty response."""
        for cap in (
            "analysis",
            "content_gen",
            "code",
            "classification",
            "summarization",
            "conversation",
        ):
            resp = await mock_provider.chat(
                [{"role": "user", "content": f"test {cap}"}]
            )
            assert resp.content, f"empty response for {cap}"
            assert resp.provider == "mock"

    @pytest.mark.asyncio
    async def test_always_available(self, mock_provider):
        profile = mock_provider.get_profile()
        assert profile.available is True

    @pytest.mark.asyncio
    async def test_health(self, mock_provider):
        assert await mock_provider.check_health() is True

    def test_profile_structure(self, mock_provider):
        profile = mock_provider.get_profile()
        assert profile.name == "Mock Provider"
        assert profile.provider == "mock"
        assert profile.priority == 100


# ══════════════════════════════════════════════════════════════════════════
# 3. ProviderRegistry
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def fresh_registry():
    """A registry with ONLY MockProvider registered."""
    from hq.model_router.providers import MockProvider

    reg = ProviderRegistry()
    reg.register(MockProvider())
    return reg


class TestProviderRegistry:
    def test_register_and_profiles(self, fresh_registry):
        assert len(fresh_registry) == 1
        profiles = fresh_registry.get_all_profiles()
        assert len(profiles) == 1
        assert profiles[0].provider == "mock"

    def test_get_available_profiles(self, fresh_registry):
        avail = fresh_registry.get_available_profiles()
        assert len(avail) == 1
        assert avail[0].available is True

    def test_get_profile_by_name(self, fresh_registry):
        prof = fresh_registry.get_profile("Mock Provider")
        assert prof is not None
        assert prof.provider == "mock"
        # Non-existent
        assert fresh_registry.get_profile("Nope") is None

    def test_select_model_for_each_agent(self, fresh_registry):
        for agent in AGENT_CAPABILITY_MAP:
            provider = fresh_registry.select_model(agent)
            assert provider is not None, f"No provider for {agent}"
            assert provider.get_profile().available is True

    def test_select_model_unknown_agent(self, fresh_registry):
        # Should fall back to any available provider
        provider = fresh_registry.select_model("does_not_exist")
        assert provider is not None

    @pytest.mark.asyncio
    async def test_chat_returns_response(self, fresh_registry):
        resp = await fresh_registry.chat(
            "code_generation",
            [{"role": "user", "content": "test"}],
        )
        assert resp.content
        assert resp.provider == "mock"
        assert resp.model == "mock-v1"

    @pytest.mark.asyncio
    async def test_chat_with_unknown_agent(self, fresh_registry):
        resp = await fresh_registry.chat(
            "unknown_agent",
            [{"role": "user", "content": "test"}],
        )
        # Falls back to mock
        assert resp.content
        assert resp.provider == "mock"

    def test_double_register(self, fresh_registry):
        from hq.model_router.providers import MockProvider

        fresh_registry.register(MockProvider())
        # Should not duplicate since keyed by provider_name
        assert len(fresh_registry) == 1


# ══════════════════════════════════════════════════════════════════════════
# 4. Singleton factory (get_registry)
# ══════════════════════════════════════════════════════════════════════════


class TestGetRegistry:
    def test_returns_registry(self):
        reg = get_registry()
        assert isinstance(reg, ProviderRegistry)
        assert len(reg) >= 1  # at least MockProvider

    def test_singleton(self):
        assert get_registry() is get_registry()


# ══════════════════════════════════════════════════════════════════════════
# 5. Mock-flag awareness
# ══════════════════════════════════════════════════════════════════════════


class TestMockFlag:
    def test_mock_prefixes_real_provider(self):
        """When LLM_PROVIDER_MOCK=true even with a real key, provider shows unavailable."""
        from hq.model_router.providers import OpenAIChatProvider

        # Set key AND mock flag
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test123", "LLM_PROVIDER_MOCK": "true"}):
            p = OpenAIChatProvider()
            prof = p.get_profile()
            assert prof.available is False, "should be unavailable in mock mode"
            assert prof.key_preview != ""


# ══════════════════════════════════════════════════════════════════════════
# 6. Error handling & retry (integration)
# ══════════════════════════════════════════════════════════════════════════


class TestProviderErrorHandling:
    """Test error handling in real providers (skipped without API keys)."""

    @pytest.mark.asyncio
    async def test_openai_fallback_on_mock(self):
        """OpenAI provider falls back to Mock when LLM_PROVIDER_MOCK=true."""
        from hq.model_router.providers import OpenAIChatProvider

        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test", "LLM_PROVIDER_MOCK": "true"}):
            p = OpenAIChatProvider()
            resp = await p.chat([{"role": "user", "content": "hi"}])
            assert resp.provider == "mock"
            assert resp.error is None

    @pytest.mark.asyncio
    async def test_openai_returns_error_on_bad_key(self):
        """OpenAI provider returns error ModelResponse (not raise) with bad key."""
        from hq.model_router.providers import OpenAIChatProvider

        with patch.dict(os.environ, {
            "LLM_API_KEY": "sk-bad-key-xxx",
            "LLM_PROVIDER_MOCK": "false",
            "OPENAI_BASE_URL": "https://api.openai.com/v1",
        }):
            p = OpenAIChatProvider()
            resp = await p.chat([{"role": "user", "content": "hi"}])
            # Should get an error response, not crash
            assert resp.error is not None
            assert "Provider error" in resp.content or resp.error

    @pytest.mark.asyncio
    async def test_deepseek_returns_error_on_bad_key(self):
        """DeepSeek provider returns error ModelResponse (not raise) with bad key."""
        from hq.model_router.providers import DeepSeekProvider

        with patch.dict(os.environ, {
            "DEEPSEEK_API_KEY": "sk-bad-key-xxx",
            "LLM_PROVIDER_MOCK": "false",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
        }):
            p = DeepSeekProvider()
            resp = await p.chat([{"role": "user", "content": "hi"}])
            assert resp.error is not None
            assert "Provider error" in resp.content or resp.error

    @pytest.mark.asyncio
    async def test_provider_timeout_handled_gracefully(self):
        """Provider returns timeout error, not crash, on unreachable URL."""
        from hq.model_router.providers import OpenAIChatProvider

        with patch.dict(os.environ, {
            "LLM_API_KEY": "sk-test",
            "LLM_PROVIDER_MOCK": "false",
            "OPENAI_BASE_URL": "http://192.0.2.1:9999/v1",  # TEST-NET, unreachable
        }):
            p = OpenAIChatProvider()
            import httpx
            # Force a small timeout so test doesn't take forever
            resp = await p.chat(
                [{"role": "user", "content": "hi"}],
                timeout=1,
            )
            assert resp.error is not None
            assert resp.provider == "openai"


# ══════════════════════════════════════════════════════════════════════════
# 7. Real API connectivity (skipped without env keys)
# ══════════════════════════════════════════════════════════════════════════

REAL_OPENAI_KEY = os.environ.get("LLM_API_KEY", "")
REAL_DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


@pytest.mark.skipif(not REAL_OPENAI_KEY, reason="LLM_API_KEY not set")
class TestOpenAIIntegration:
    """Tests that hit the real OpenAI API.  Run with: LLM_API_KEY=... pytest ..."""

    @pytest.mark.asyncio
    async def test_openai_chat_real(self):
        from hq.model_router.providers import OpenAIChatProvider

        with patch.dict(os.environ, {
            "LLM_API_KEY": REAL_OPENAI_KEY,
            "LLM_PROVIDER_MOCK": "false",
        }):
            p = OpenAIChatProvider()
            resp = await p.chat([
                {"role": "user", "content": "Say exactly: HELLO_FROM_CROSSWAVE"},
            ])
            assert resp.error is None, f"API error: {resp.error}"
            assert resp.provider == "openai"
            assert "HELLO_FROM_CROSSWAVE" in resp.content

    @pytest.mark.asyncio
    async def test_openai_health_check(self):
        from hq.model_router.providers import OpenAIChatProvider

        with patch.dict(os.environ, {
            "LLM_API_KEY": REAL_OPENAI_KEY,
            "LLM_PROVIDER_MOCK": "false",
        }):
            p = OpenAIChatProvider()
            healthy = await p.check_health()
            assert healthy is True


@pytest.mark.skipif(not REAL_DEEPSEEK_KEY, reason="DEEPSEEK_API_KEY not set")
class TestDeepSeekIntegration:
    """Tests that hit the real DeepSeek API.  Run with: DEEPSEEK_API_KEY=... pytest ..."""

    @pytest.mark.asyncio
    async def test_deepseek_chat_real(self):
        from hq.model_router.providers import DeepSeekProvider

        with patch.dict(os.environ, {
            "DEEPSEEK_API_KEY": REAL_DEEPSEEK_KEY,
            "LLM_PROVIDER_MOCK": "false",
        }):
            p = DeepSeekProvider()
            resp = await p.chat([
                {"role": "user", "content": "Say exactly: HELLO_FROM_CROSSWAVE"},
            ])
            assert resp.error is None, f"API error: {resp.error}"
            assert resp.provider == "deepseek"
            assert "HELLO_FROM_CROSSWAVE" in resp.content

    @pytest.mark.asyncio
    async def test_deepseek_health_check(self):
        from hq.model_router.providers import DeepSeekProvider

        with patch.dict(os.environ, {
            "DEEPSEEK_API_KEY": REAL_DEEPSEEK_KEY,
            "LLM_PROVIDER_MOCK": "false",
        }):
            p = DeepSeekProvider()
            healthy = await p.check_health()
            assert healthy is True
