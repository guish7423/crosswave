"""httpx-based REST API client for the Polsia Fork agent platform.

Connects to Polsia Fork FastAPI backend at POLSIA_BASE_URL (default http://localhost:8001).
Uses static X-API-Key auth for protected endpoints.

Usage:
    client = PolsiaClient()
    agents = await client.get_agents()
    tasks = await client.get_tasks(status="pending")
"""
import os
from typing import Any

import httpx


class PolsiaConnectionError(Exception):
    """Raised when a Polsia Fork API call fails."""


class PolsiaClient:
    """REST client for Polsia Fork API v1."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
    ):
        self.base_url = (base_url or os.environ.get("POLSIA_BASE_URL", "http://localhost:8001")).rstrip("/")
        self.api_key = api_key or os.environ.get("POLSIA_API_KEY", "dev-key")
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        needs_auth: bool = False,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/api/v1{path}"
        headers = {}
        if needs_auth:
            headers["X-API-Key"] = self.api_key
        try:
            r = await self._client.request(
                method, url, headers=headers, params=params, json=data
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            raise PolsiaConnectionError(
                f"{method} {url} failed: {exc}"
            ) from exc

    # ── Agents ──────────────────────────────────────────────────

    async def get_agents(self) -> dict[str, Any]:
        """GET /api/v1/agents/monitor — agent status + latest runs."""
        return await self._request("GET", "/agents/monitor")

    # ── Tasks ───────────────────────────────────────────────────

    async def get_tasks(
        self,
        status: str | None = None,
        agent_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """GET /api/v1/tasks — list tasks with optional filters."""
        params: dict[str, Any] = {"limit": min(limit, 500)}
        if status:
            params["status"] = status
        if agent_type:
            params["agent_type"] = agent_type
        return await self._request("GET", "/tasks", params=params)

    async def get_task(self, task_id: int) -> dict[str, Any]:
        """GET /api/v1/tasks/{task_id} — single task detail."""
        return await self._request("GET", f"/tasks/{task_id}")

    async def create_task(
        self,
        title: str,
        agent_type: str,
        description: str | None = None,
        priority: int = 3,
        source: str = "api",
    ) -> dict[str, Any]:
        """POST /api/v1/tasks — create a new agent task."""
        data: dict[str, Any] = {
            "title": title,
            "agent_type": agent_type,
            "priority": priority,
            "source": source,
        }
        if description is not None:
            data["description"] = description
        return await self._request("POST", "/tasks", data=data)

    # ── Activity ────────────────────────────────────────────────

    async def get_activity(self, limit: int = 50) -> list[dict[str, Any]]:
        """GET /api/v1/activity — recent activity log entries."""
        return await self._request(
            "GET", "/activity", params={"limit": min(limit, 200)}
        )

    # ── Leads ───────────────────────────────────────────────────

    async def get_leads(
        self, status: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        """GET /api/v1/leads — list leads with optional status filter."""
        params: dict[str, Any] = {"limit": min(limit, 500)}
        if status:
            params["status"] = status
        return await self._request("GET", "/leads", params=params)

    # ── External Orders (auth) ──────────────────────────────────

    async def get_external_orders(
        self, platform: str | None = None, status: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        """GET /api/v1/orders/external — requires X-API-Key."""
        params: dict[str, Any] = {"limit": min(limit, 200)}
        if platform:
            params["platform"] = platform
        if status:
            params["status"] = status
        return await self._request(
            "GET", "/orders/external", needs_auth=True, params=params
        )

    # ── Dashboard ───────────────────────────────────────────────

    async def get_dashboard_summary(self) -> dict[str, Any]:
        """GET /api/v1/dashboard/summary — aggregate metrics."""
        return await self._request("GET", "/dashboard/summary")

    async def get_health(self) -> dict[str, Any]:
        """GET /api/v1/dashboard/health — requires X-API-Key."""
        return await self._request(
            "GET", "/dashboard/health", needs_auth=True
        )


def get_polsia_client() -> PolsiaClient:
    """Shortcut: create a PolsiaClient from env defaults."""
    return PolsiaClient()
