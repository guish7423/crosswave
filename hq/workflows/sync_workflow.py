"""Workflow: when NocoBase sync completes, refresh plugin health checks."""

from __future__ import annotations

from hq.plugin_registry import get_registry
from hq.workflows import Workflow


class SyncCompleteRefreshWorkflow(Workflow):
    """After every NocoBase sync, trigger plugin health checks."""

    def __init__(self):
        super().__init__(
            name="sync-refresh-health",
            description="Refresh plugin health checks after NocoBase sync",
        )

    async def condition(self, event: dict) -> bool:
        return event.get("type") == "sync.complete"

    async def action(self, event: dict) -> None:
        registry = get_registry()
        await registry.check_all_health()


WORKFLOWS: list[Workflow] = [
    SyncCompleteRefreshWorkflow(),
]
