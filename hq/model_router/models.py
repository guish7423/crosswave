"""Pydantic models for provider configs, profiles, and responses."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Capability = Literal[
    "analysis",
    "content_gen",
    "code",
    "classification",
    "summarization",
    "conversation",
]


class ProviderConfig(BaseModel):
    """Configuration for a provider instance."""

    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: str = "gpt-4o"
    priority: int = 10  # lower = higher priority when selecting
    capabilities: list[Capability] = Field(default_factory=list)
    available: bool = True


class ModelProfile(BaseModel):
    """Read-only profile returned to the frontend."""

    name: str
    model: str
    provider: str
    capabilities: list[Capability] = Field(default_factory=list)
    priority: int
    available: bool
    key_preview: str = ""
    base_url: Optional[str] = None
    env: Optional[str] = None  # env var name for the API key


class ModelResponse(BaseModel):
    """Standardised chat response wrapper."""

    content: str
    model: str
    provider: str
    error: Optional[str] = None  # error detail if the request failed
