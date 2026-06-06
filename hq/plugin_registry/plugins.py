"""Concrete CrossWavePlugin implementations for all products."""

from __future__ import annotations

from app.config import settings

from .contract import CrossWavePlugin


class CrossBridgePlugin(CrossWavePlugin):
    name = "CrossBridge"
    description = "AI translation SaaS — core product"
    version = "0.1.0"
    base_url = "https://crossbridge.example.com"
    capabilities = ["translation", "api", "nlp"]
    metadata = {"product_line": "localization", "live": "true"}


class CrossBlogPlugin(CrossWavePlugin):
    name = "CrossBlog"
    description = "SEO blog engine — content generation & publishing"
    version = "0.1.0"
    capabilities = ["content", "seo", "blog"]
    metadata = {"product_line": "marketing", "live": "true"}

    @property
    def base_url(self) -> str | None:
        return settings.crossblog_url


class CrossDeployPlugin(CrossWavePlugin):
    name = "CrossDeploy"
    description = "Deployment service — one-click deploy infrastructure"
    version = "0.1.0"
    base_url = "http://localhost:8002"
    capabilities = ["deployment", "infra", "devops"]
    metadata = {"product_line": "infrastructure"}


class PolsiaForkPlugin(CrossWavePlugin):
    name = "Polsia Fork"
    description = "10-agent backend platform — AI agent orchestration engine"
    version = "0.1.0"
    capabilities = ["agents", "orchestration", "llm", "async_tasks"]
    metadata = {"product_line": "platform", "engine": "polsia"}

    @property
    def base_url(self) -> str | None:
        return settings.polsia_base_url


class NocoBasePlugin(CrossWavePlugin):
    name = "NocoBase"
    description = "Low-code data platform — unified data layer & CMS"
    version = "0.1.0"
    base_url = "http://localhost:13000"
    capabilities = ["database", "cms", "nocobase", "api"]
    metadata = {"product_line": "platform", "engine": "database"}


ALL_PRODUCT_PLUGINS: list[CrossWavePlugin] = [
    CrossBridgePlugin(),
    CrossBlogPlugin(),
    CrossDeployPlugin(),
    PolsiaForkPlugin(),
    NocoBasePlugin(),
]
