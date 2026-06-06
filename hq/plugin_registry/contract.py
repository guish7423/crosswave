"""CrossWavePlugin contract — abstract base for all product plugins."""

from __future__ import annotations

from .models import PluginInfo, PluginRegisterRequest, PluginStatus


class CrossWavePlugin:
    """Base class for all CrossWave plugins/products.

    Subclasses define:
    - Plugin metadata (name, version, capabilities)
    - Lifecycle hooks (on_register, on_unregister, health_check)
    - Optional routes, MCP tools, event handlers
    """

    name: str = ""
    description: str = ""
    version: str = "0.1.0"
    base_url: str | None = None
    capabilities: list[str] = []
    metadata: dict[str, str] = {}

    def to_register_request(self) -> PluginRegisterRequest:
        return PluginRegisterRequest(
            name=self.name,
            description=self.description,
            version=self.version,
            base_url=self.base_url,
            capabilities=self.capabilities,
            metadata=self.metadata,
        )

    @property
    def info(self) -> PluginInfo | None:
        return None

    @info.setter
    def info(self, value: PluginInfo | None) -> None:
        self._info = value

    async def on_register(self) -> None:
        """Called after the plugin is registered in the registry."""

    async def on_unregister(self) -> None:
        """Called before the plugin is unregistered."""

    async def on_heartbeat(self) -> None:
        """Called during health check cycle. Override to implement custom health logic."""

    async def health_check(self) -> PluginStatus:
        """Override to implement custom health checking.

        By default, does an HTTP GET to {base_url}/health.
        """
        info = getattr(self, "_info", None)
        if info is None or not info.base_url:
            return PluginStatus.UNKNOWN
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{info.base_url.rstrip('/')}/health")
            if resp.status_code < 500:
                return PluginStatus.ONLINE
            return PluginStatus.DEGRADED
        except Exception:
            return PluginStatus.OFFLINE
