"""Plugin Registry — in-memory service registry for CrossWave products."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .models import PluginInfo, PluginRegisterRequest, PluginStatus

import httpx


class PluginRegistry:
    """Central registry for all CrossWave plugins/products.

    Maintains an in-memory dict of registered plugins with heartbeat
    tracking and periodic health checking.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, PluginInfo] = {}

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, req: PluginRegisterRequest) -> PluginInfo:
        now = datetime.now(timezone.utc).isoformat()
        plugin_id = req.metadata.get("id", uuid.uuid4().hex[:12])
        info = PluginInfo(
            id=plugin_id,
            name=req.name,
            description=req.description,
            version=req.version,
            base_url=req.base_url,
            status=PluginStatus.UNKNOWN,
            capabilities=req.capabilities,
            registered_at=now,
            metadata=req.metadata,
        )
        self._plugins[plugin_id] = info
        return info

    def unregister(self, plugin_id: str) -> bool:
        return self._plugins.pop(plugin_id, None) is not None

    # ── Queries ───────────────────────────────────────────────────────────

    def get(self, plugin_id: str) -> PluginInfo | None:
        return self._plugins.get(plugin_id)

    def list(self) -> list[PluginInfo]:
        return list(self._plugins.values())

    def get_by_capability(self, capability: str) -> list[PluginInfo]:
        return [p for p in self._plugins.values() if capability in p.capabilities]

    # ── Heartbeat ─────────────────────────────────────────────────────────

    def heartbeat(self, plugin_id: str) -> PluginInfo | None:
        info = self._plugins.get(plugin_id)
        if info is not None:
            info.touch()
        return info

    # ── Health check ──────────────────────────────────────────────────────

    async def check_plugin_health(self, plugin_id: str) -> None:
        info = self._plugins.get(plugin_id)
        if info is None or not info.base_url:
            return
        try:
            health_url = f"{info.base_url.rstrip('/')}/health"
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(health_url)
            if resp.status_code < 500:
                info.touch()
            else:
                info.status = PluginStatus.DEGRADED
        except Exception:
            info.status = PluginStatus.OFFLINE

    async def check_all_health(self) -> list[dict]:
        import asyncio

        for info in self._plugins.values():
            if info.base_url:
                info.status = PluginStatus.UNKNOWN

        tasks = [self.check_plugin_health(pid) for pid in self._plugins]
        await asyncio.gather(*tasks)

        return [
            {"id": p.id, "name": p.name, "status": p.status.value}
            for p in self._plugins.values()
        ]

    def __len__(self) -> int:
        return len(self._plugins)


# ── Singleton ─────────────────────────────────────────────────────────────

_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry
