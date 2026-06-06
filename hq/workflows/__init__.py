"""CrossWave Workflow Engine — event-driven cross-product automation."""

from __future__ import annotations


class Workflow:
    """A single workflow: trigger → condition → action."""

    def __init__(self, name: str, description: str = "", event_type: str = "*"):
        self.name = name
        self.description = description
        self.event_type = event_type

    async def condition(self, event: dict) -> bool:
        return True

    async def action(self, event: dict) -> None:
        pass

    async def handle_event(self, event: dict) -> None:
        if await self.condition(event):
            await self.action(event)


class WorkflowEngine:
    """Manages registered workflows."""

    def __init__(self):
        self.workflows: list[Workflow] = []

    def register(self, wf: Workflow) -> None:
        self.workflows.append(wf)
