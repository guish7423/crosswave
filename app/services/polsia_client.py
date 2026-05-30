"""Polsia Fork API client — server-side proxy with mock fallback."""

import httpx

from app.config import settings

MOCK_AGENTS = [
    {"agent_type": "orchestrator", "name": "Orchestrator", "status": "running", "last_run": "2m ago"},
    {"agent_type": "business_planning", "name": "Business Planning", "status": "idle", "last_run": "1h ago"},
    {"agent_type": "competitor_research", "name": "Competitor Research", "status": "idle", "last_run": "2h ago"},
    {"agent_type": "social_media", "name": "Social Media", "status": "done", "last_run": "30m ago"},
    {"agent_type": "email_outreach", "name": "Email Outreach", "status": "idle", "last_run": "3h ago"},
    {"agent_type": "customer_support", "name": "Customer Support", "status": "running", "last_run": "5m ago"},
    {"agent_type": "ads_management", "name": "Ads Management", "status": "idle", "last_run": "4h ago"},
    {"agent_type": "code_generation", "name": "Code Generation", "status": "done", "last_run": "15m ago"},
    {"agent_type": "finance", "name": "Finance", "status": "done", "last_run": "10m ago"},
    {"agent_type": "deployment", "name": "Deployment", "status": "idle", "last_run": "6h ago"},
]

MOCK_ACTIVITY = [
    {"agent_type": "orchestrator", "action": "plan", "summary": "Planned 8 tasks for today", "created_at": "2026-05-30T09:30:00"},
    {"agent_type": "orchestrator", "action": "assign", "summary": "Assigned competitor analysis to Research Agent", "created_at": "2026-05-30T09:28:00"},
    {"agent_type": "social_media", "action": "publish", "summary": "Posted to X: AI Market Trends 2026", "created_at": "2026-05-30T09:15:00"},
    {"agent_type": "customer_support", "action": "resolve", "summary": "Answered ticket #1423: API integration question", "created_at": "2026-05-30T09:10:00"},
    {"agent_type": "code_generation", "action": "commit", "summary": "Pushed fix for billing calculation bug", "created_at": "2026-05-30T08:55:00"},
    {"agent_type": "deployment", "action": "deploy", "summary": "Deployed v1.2.3 to staging", "created_at": "2026-05-30T08:45:00"},
    {"agent_type": "finance", "action": "report", "summary": "Generated weekly revenue report", "created_at": "2026-05-30T08:30:00"},
    {"agent_type": "email_outreach", "action": "send", "summary": "Sent 45 cold emails to leads", "created_at": "2026-05-30T08:00:00"},
    {"agent_type": "competitor_research", "action": "scan", "summary": "Detected price drop by Competitor X", "created_at": "2026-05-30T07:30:00"},
    {"agent_type": "ads_management", "action": "optimize", "summary": "Ad spend adjusted: +15% ROI on Google Ads", "created_at": "2026-05-30T07:00:00"},
]


class PolsiaClient:
    """HTTP client for Polsia Fork API with mock fallback."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._started = False

    async def start(self):
        self._started = True
        try:
            self._client = httpx.AsyncClient(
                base_url=settings.polsia_base_url,
                timeout=settings.proxy_timeout,
                headers={"X-API-Key": settings.polsia_api_key},
            )
        except Exception:
            self._client = None

    async def stop(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        self._started = False

    def _mock_disconnected(self) -> bool:
        """Return True when we should return mock data instead of error."""
        return settings.polsia_mock

    async def _get(self, path: str) -> dict | list:
        if not self._client:
            return self._mock_fallback(path)
        try:
            r = await self._client.get(path)
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError, Exception):
            return self._mock_fallback(path)

    def _mock_fallback(self, path: str) -> dict | list:
        """Return mock data when Polsia Fork is unreachable and mock mode is on."""
        if not self._mock_disconnected():
            return {"status": "disconnected"}
        if "dashboard/summary" in path:
            return {
                "active_agents": 10,
                "tasks_today_total": 24,
                "tasks_today_pending": 8,
                "tasks_today_completed": 14,
                "tasks_today_failed": 2,
                "recent_activity_count": 47,
                "total_expenses_cents": 125000,
                "mrr_cents": 1900,
                "arr_cents": 22800,
                "active_subscribers": 3,
            }
        if "agents" in path:
            return MOCK_AGENTS
        if "activity" in path:
            return MOCK_ACTIVITY
        return {"status": "disconnected"}

    async def get_dashboard_summary(self) -> dict | list:
        return await self._get("/api/v1/dashboard/summary")

    async def get_agents_status(self) -> dict | list:
        return await self._get("/api/v1/agents/status")

    async def get_activity(self, limit: int = 20) -> dict | list:
        return await self._get(f"/api/v1/dashboard/activity?limit={limit}")


# Singleton
polsia_client = PolsiaClient()
