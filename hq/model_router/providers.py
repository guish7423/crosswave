"""Concrete LLM provider implementations: Mock, OpenAI-compatible, DeepSeek."""

import asyncio
import os
from typing import Optional

import httpx

from .base import ModelProvider
from .models import Capability, ModelProfile, ModelResponse

# ─── Retry helper ──────────────────────────────────────────────────────────

MAX_RETRIES = 3
RETRY_BACKOFF = 1.5  # multiplicative backoff: 1s → 1.5s → 2.25s
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


async def _chat_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    json_body: dict,
) -> httpx.Response:
    """POST with exponential backoff on retryable errors."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.post(url, headers=headers, json=json_body)
            if resp.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF ** (attempt - 1)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF ** (attempt - 1)
                await asyncio.sleep(wait)
                continue
            raise
        except httpx.HTTPStatusError:
            raise
    raise last_exc or httpx.HTTPError("request failed after retries")

# ─── Mock canned responses per capability ────────────────────────────────

MOCK_RESPONSES: dict[str, str] = {
    "analysis": "📊 Analysis result: Based on the data, the optimal strategy is "
    "to focus on high-margin services and automate routine tasks. "
    "Projected 23% efficiency gain.",
    "content_gen": "✍️ Generated content: Here is a draft tailored to your brand "
    "voice. It covers key messaging points with a compelling call-to-action.",
    "code": "💻 Here's the implementation:\n\n```python\ndef solution():\n    "
    "return {\"status\": \"implemented\", \"confidence\": 0.95}\n```",
    "classification": "🎯 Classification result: Category A (confidence: 0.92)\n"
    "Reasoning: Matches known pattern for high-value opportunities.",
    "summarization": "📋 Summary: The key points are (1) revenue grew 18% QoQ, "
    "(2) customer acquisition cost dropped 12%, (3) expansion into "
    "APAC market shows strong early signals.",
    "conversation": "💬 I'd be happy to help with that! Here's what I "
    "recommend based on the available data…",
}

# ─── MockProvider ─────────────────────────────────────────────────────────


class MockProvider(ModelProvider):
    """Returns canned responses.  Always available, no API key needed."""

    provider_name = "mock"
    capabilities: list[Capability] = [
        "analysis",
        "content_gen",
        "code",
        "classification",
        "summarization",
        "conversation",
    ]

    @property
    def name(self) -> str:
        return "Mock Provider"

    def get_profile(self) -> ModelProfile:
        return ModelProfile(
            name=self.name,
            model="mock-v1",
            provider=self.provider_name,
            capabilities=list(self.capabilities),
            priority=100,  # lowest priority — only used when real providers absent
            available=True,
            key_preview="mock-key",
            base_url=None,
            env=None,
        )

    async def chat(
        self, messages: list[dict], **kwargs: dict
    ) -> ModelResponse:
        # Inspect the last user message for a capability hint
        cap = "conversation"
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                content: str = msg.get("content", "")
                for c in self.capabilities:
                    if c in content.lower():
                        cap = c
                        break
                break
        text = MOCK_RESPONSES.get(cap, MOCK_RESPONSES["conversation"])
        return ModelResponse(
            content=text,
            model="mock-v1",
            provider=self.provider_name,
        )

    async def check_health(self) -> bool:
        return True


# ─── API key helper ──────────────────────────────────────────────────────


def _is_mock_forced() -> bool:
    """Respect LLM_PROVIDER_MOCK env var."""
    return os.environ.get("LLM_PROVIDER_MOCK", "true").lower() == "true"


def _preview_key(key: str) -> str:
    k = key.strip()
    if len(k) <= 8:
        return k[:2] + "…" + k[-2:] if len(k) > 4 else k
    return k[:6] + "…" + k[-4:]


def _detect_env(env_var: str) -> Optional[str]:
    val = os.environ.get(env_var, "")
    return env_var if val.strip() else None


# ─── OpenAI-compatible provider ──────────────────────────────────────────


class OpenAIChatProvider(ModelProvider):
    """OpenAI-compatible chat API (also works with any OpenAI-format proxy)."""

    provider_name = "openai"
    capabilities: list[Capability] = [
        "analysis",
        "content_gen",
        "code",
        "summarization",
        "conversation",
    ]

    def __init__(self) -> None:
        self._api_key = os.environ.get("LLM_API_KEY", "")
        self._base_url = os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._priority = 10

    @property
    def name(self) -> str:
        return "OpenAI Chat"

    def get_profile(self) -> ModelProfile:
        key = self._api_key or ""
        return ModelProfile(
            name=self.name,
            model=self._model,
            provider=self.provider_name,
            capabilities=list(self.capabilities),
            priority=self._priority,
            available=bool(key) and not _is_mock_forced(),
            key_preview=_preview_key(key) if key else "",
            base_url=self._base_url,
            env="LLM_API_KEY",
        )

    async def chat(
        self, messages: list[dict], **kwargs: dict
    ) -> ModelResponse:
        if _is_mock_forced() or not self._api_key:
            return await MockProvider().chat(messages, **kwargs)
        timeout_s: float = float(kwargs.pop("timeout", 30))  # type: ignore[arg-type]
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            try:
                resp = await _chat_with_retry(
                    client,
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json_body={
                        "model": kwargs.get("model", self._model),
                        "messages": messages,
                        **kwargs,
                    },
                )
                data = resp.json()
                choice = data["choices"][0]
                content = choice["message"]["content"] or ""
                return ModelResponse(
                    content=content,
                    model=data.get("model", self._model),
                    provider=self.provider_name,
                )
            except httpx.HTTPStatusError as e:
                detail = ""
                try:
                    detail = e.response.text[:200]
                except Exception:
                    pass
                return ModelResponse(
                    content=f"⚠️ Provider error ({e.response.status_code}): {detail}",
                    model=self._model,
                    provider=self.provider_name,
                    error=f"HTTP {e.response.status_code}",
                )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                return ModelResponse(
                    content=f"⚠️ Provider unreachable after {MAX_RETRIES} retries: {type(e).__name__}",
                    model=self._model,
                    provider=self.provider_name,
                    error="connection_error",
                )

    async def check_health(self) -> bool:
        if not self._api_key or _is_mock_forced():
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False


# ─── DeepSeek provider ───────────────────────────────────────────────────


class DeepSeekProvider(ModelProvider):
    """DeepSeek chat (OpenAI-compatible format)."""

    provider_name = "deepseek"
    capabilities: list[Capability] = [
        "analysis",
        "code",
        "classification",
        "summarization",
        "conversation",
    ]

    def __init__(self) -> None:
        self._api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self._base_url = os.environ.get(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        ).rstrip("/")
        self._model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        self._priority = 20

    @property
    def name(self) -> str:
        return "DeepSeek Chat"

    def get_profile(self) -> ModelProfile:
        key = self._api_key or ""
        return ModelProfile(
            name=self.name,
            model=self._model,
            provider=self.provider_name,
            capabilities=list(self.capabilities),
            priority=self._priority,
            available=bool(key) and not _is_mock_forced(),
            key_preview=_preview_key(key) if key else "",
            base_url=self._base_url,
            env="DEEPSEEK_API_KEY",
        )

    async def chat(
        self, messages: list[dict], **kwargs: dict
    ) -> ModelResponse:
        if _is_mock_forced() or not self._api_key:
            return await MockProvider().chat(messages, **kwargs)
        timeout_s: float = float(kwargs.pop("timeout", 30))  # type: ignore[arg-type]
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            try:
                resp = await _chat_with_retry(
                    client,
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json_body={
                        "model": kwargs.get("model", self._model),
                        "messages": messages,
                        **kwargs,
                    },
                )
                data = resp.json()
                choice = data["choices"][0]
                content = choice["message"]["content"] or ""
                return ModelResponse(
                    content=content,
                    model=data.get("model", self._model),
                    provider=self.provider_name,
                )
            except httpx.HTTPStatusError as e:
                detail = ""
                try:
                    detail = e.response.text[:200]
                except Exception:
                    pass
                return ModelResponse(
                    content=f"⚠️ Provider error ({e.response.status_code}): {detail}",
                    model=self._model,
                    provider=self.provider_name,
                    error=f"HTTP {e.response.status_code}",
                )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                return ModelResponse(
                    content=f"⚠️ Provider unreachable after {MAX_RETRIES} retries: {type(e).__name__}",
                    model=self._model,
                    provider=self.provider_name,
                    error="connection_error",
                )

    async def check_health(self) -> bool:
        if not self._api_key or _is_mock_forced():
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False
