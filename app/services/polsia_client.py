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
        if "proposals/by-token/" in path:
            return {
                "id": 0,
                "status": "sent",
                "proposed_amount": 2500,
                "currency": "USD",
                "content": "## Mock Proposal\n\nThis is a mock proposal for offline development.",
                "created_at": "2026-06-01T12:00:00+00:00",
                "order_id": 0,
                "deliverables": [
                    {"title": "Docker Deployment", "description": "Production-ready Docker container"}
                ],
            }
        return {"status": "disconnected"}

    async def get_dashboard_summary(self) -> dict | list:
        return await self._get("/api/v1/dashboard/summary")

    async def get_agents_status(self) -> dict | list:
        return await self._get("/api/v1/agents/status")

    async def get_activity(self, limit: int = 20) -> dict | list:
        return await self._get(f"/api/v1/activity?limit={limit}")

    async def get_tasks(self, limit: int = 500) -> dict | list:
        return await self._get(f"/api/v1/tasks?limit={limit}")

    async def _post(self, path: str, json_data: dict) -> dict | list:
        if not self._client:
            return {"status": "disconnected", "error": "client not initialized"}
        try:
            r = await self._client.post(path, json=json_data)
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError, Exception) as e:
            if self._mock_disconnected():
                return {"status": "mock", "order_id": 0, "proposal_id": 0, "note": f"mock fallback: {e}"}
            return {"status": "error", "error": str(e)}

    async def submit_quick_quote(self, data: dict) -> dict | list:
        return await self._post("/api/v1/quick-quote", data)

    async def get_proposal_by_token(self, token: str) -> dict | list:
        return await self._get(f"/api/v1/proposals/by-token/{token}")

    async def track_proposal_view(self, token: str) -> dict | list:
        return await self._post(f"/api/v1/proposals/by-token/{token}/track-view", {})

    async def accept_proposal(self, token: str) -> dict | list:
        return await self._post(f"/api/v1/proposals/by-token/{token}/accept", {})

    async def reject_proposal(self, token: str, reason: str = "") -> dict | list:
        return await self._post(f"/api/v1/proposals/by-token/{token}/reject", {"reason": reason})

    async def execute_deploy(self, order_id: int) -> dict | list:
        return await self._post(f"/api/v1/orders/external/{order_id}/execute-deploy", {})

    async def create_product_checkout(self, product_key: str, customer_email: str = "") -> dict | list:
        """Direct product purchase from pricing page Buy Now buttons."""
        return await self._post("/api/v1/create-product-checkout", {
            "product_key": product_key,
            "customer_email": customer_email,
        })

    async def create_checkout(self, order_id: int) -> dict | list:
        return await self._post(f"/api/v1/orders/{order_id}/create-checkout", {})

    async def get_execution_status(self, order_id: int) -> dict | list:
        return await self._get(f"/api/v1/orders/external/{order_id}/execution-status")

    async def get_downloadable_orders(self) -> list:
        return await self._get("/api/v1/orders/external/downloadable")

    async def get_analytics(self) -> dict:
        """Aggregate task data into chart-friendly analytics."""
        tasks = await self.get_tasks()
        if not isinstance(tasks, list):
            return {"status_distribution": [], "agent_breakdown": [], "daily_trend": []}
        from collections import Counter, defaultdict
        status_counter = Counter()
        agent_map = defaultdict(lambda: Counter())
        daily_counter = Counter()
        for t in tasks:
            status = t.get("status", "unknown")
            agent = t.get("agent_type", "unknown")
            status_counter[status] += 1
            agent_map[agent][status] += 1
            created = t.get("created_at", "")
            if created:
                daily_counter[created[:10]] += 1
        return {
            "status_distribution": [
                {"label": s.capitalize(), "value": c} for s, c in sorted(status_counter.items(), key=lambda x: -x[1])
            ],
            "agent_breakdown": [
                {"agent": a, **{s.capitalize(): c for s, c in sorted(stats.items())}}
                for a, stats in sorted(agent_map.items())
            ],
            "daily_trend": [
                {"date": d, "count": c} for d, c in sorted(daily_counter.items())
            ],
        }


# Singleton
polsia_client = PolsiaClient()
