"""Tests for CrossWave HQ Bridge API endpoints.

Uses fixture-based auth_client from conftest.py (no module-level singletons).
"""

import os

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")



# ─── /health (public, no auth) ────────────────────────────────────────────────
class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "CrossWave HQ Bridge"
        assert isinstance(data["services"], int)


# ─── /api/hq/summary ──────────────────────────────────────────────────────────
class TestSummary:
    URL = "/api/hq/summary"

    def test_summary_structure(self, auth_client):
        resp = auth_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        for key in ("employees", "lines", "orders", "mrr", "customers", "leads", "last_sync"):
            assert key in data

    def test_summary_empty_without_nocobase(self, auth_client):
        """NB_DISABLED=true → all counts are 0."""
        resp = auth_client.get(self.URL)
        data = resp.json()
        assert data["employees"]["total"] == 0
        assert data["orders"]["total"] == 0
        assert data["mrr"] == 0


class TestSummaryNocoBase:
    """Tests for the NocoBase-read path (NB_DISABLED=true → empty data)."""

    def test_nocobase_summary_structure(self, auth_client):
        resp = auth_client.get("/api/hq/summary")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("employees", "lines", "orders", "mrr", "source"):
            assert key in data

    def test_nocobase_stats_endpoint(self, auth_client):
        resp = auth_client.get("/api/hq/nocobase/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_nocobase_employees_endpoint(self, auth_client):
        resp = auth_client.get("/api/hq/nocobase/employees")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data

    def test_nocobase_orders_endpoint(self, auth_client):
        resp = auth_client.get("/api/hq/nocobase/orders")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data


# ─── /api/hq/employees ────────────────────────────────────────────────────────
class TestEmployees:
    def test_get_employees(self, auth_client):
        """NB_DISABLED=true → returns empty list."""
        resp = auth_client.get("/api/hq/employees")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["data"], list)

    def test_employee_fields(self, auth_client):
        """Response shape is valid even when empty."""
        resp = auth_client.get("/api/hq/employees")
        data = resp.json()["data"]
        assert isinstance(data, list)


# ─── /api/hq/orders (parametrized filters) ────────────────────────────────────
class TestOrders:
    def test_orders_empty_without_nocobase(self, auth_client):
        """NB_DISABLED=true → all orders endpoints return empty."""
        resp = auth_client.get("/api/hq/orders")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ─── /api/hq/leads (parametrized filters) ─────────────────────────────────────
class TestLeads:
    def test_leads_empty_without_nocobase(self, auth_client):
        """NB_DISABLED=true → leads endpoints return empty."""
        resp = auth_client.get("/api/hq/leads")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0


# ─── /api/hq/external-orders ──────────────────────────────────────────────────
class TestExternalOrders:
    def test_external_orders_empty_without_nocobase(self, auth_client):
        """NB_DISABLED=true → external orders endpoints return empty."""
        resp = auth_client.get("/api/hq/external-orders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_empty_when_no_data(self, auth_client):
        """NB_DISABLED=true → NocoBase returns no data (empty)."""
        resp = auth_client.get("/api/hq/external-orders")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)


# ─── /api/hq/lines ────────────────────────────────────────────────────────────
class TestLines:
    def test_get_lines(self, auth_client):
        resp = auth_client.get("/api/hq/lines")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)




# ─── /api/hq/sync ─────────────────────────────────────────────────────────────
class TestSync:
    def test_manual_sync(self, auth_client):
        resp = auth_client.get("/api/hq/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "synced_at" in data


# ─── /api/hq/finances ─────────────────────────────────────────────────────────
class TestFinances:
    def test_finance_structure(self, auth_client):
        resp = auth_client.get("/api/hq/finances")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("total_revenue", "total_costs", "profit_margin", "mrr", "arr",
                     "expense_by_category", "revenue_by_month"):
            assert key in data

    def test_finance_empty_defaults(self, auth_client):
        """NB_DISABLED=true → NocoBase returns no data from NocoBase."""
        data = auth_client.get("/api/hq/finances").json()
        assert data["total_revenue"] == 0
        assert data["total_costs"] == 0

    def test_expense_categories(self, auth_client):
        cats = auth_client.get("/api/hq/finances").json()["expense_by_category"]
        assert isinstance(cats, list)

    def test_revenue_by_month(self, auth_client):
        revs = auth_client.get("/api/hq/finances").json()["revenue_by_month"]
        assert isinstance(revs, list)


# ─── /api/hq/reports ──────────────────────────────────────────────────────────
class TestReports:
    def test_reports_structure(self, auth_client):
        data = auth_client.get("/api/hq/reports").json()
        for key in ("total_tasks", "completed_tasks", "failed_tasks", "completion_rate",
                     "agent_performance", "task_trend", "employee_count"):
            assert key in data

    def test_reports_empty_defaults(self, auth_client):
        """NB_DISABLED=true → NocoBase returns no data."""
        data = auth_client.get("/api/hq/reports").json()
        assert data["total_tasks"] == 0
        assert data["completion_rate"] == 0.0

    def test_agent_performance(self, auth_client):
        agents = auth_client.get("/api/hq/reports").json()["agent_performance"]
        assert isinstance(agents, list)

    def test_employee_count(self, auth_client):
        assert auth_client.get("/api/hq/reports").json()["employee_count"] == 0


# ─── /api/portal/order/{id} ────────────────────────────────────────────────────
class TestPortalOrder:
    def test_portal_order_404_no_nocobase(self, auth_client):
        """NB_DISABLED=true → portal returns 404 without NocoBase."""
        resp = auth_client.get("/api/portal/order/1")
        assert resp.status_code == 404


# ─── /api/hq/monitor ──────────────────────────────────────────────────────────
class TestMonitor:
    def test_monitor_structure(self, auth_client):
        data = auth_client.get("/api/hq/monitor").json()
        assert "summary" in data
        assert "results" in data
        s = data["summary"]
        for key in ("total", "up", "degraded", "down", "avg_response_time_ms", "all_up", "timestamp"):
            assert key in s

    def test_monitor_results_count(self, auth_client):
        assert len(auth_client.get("/api/hq/monitor").json()["results"]) >= 4

    def test_monitor_result_fields(self, auth_client):
        result = auth_client.get("/api/hq/monitor").json()["results"][0]
        for key in ("service", "status", "http_status", "response_time_ms", "label"):
            assert key in result

    def test_monitor_summary_all_up_type(self, auth_client):
        assert isinstance(auth_client.get("/api/hq/monitor").json()["summary"]["all_up"], bool)


# ─── /api/hq/evolution ────────────────────────────────────────────────────────
class TestEvolution:
    def test_evolution_no_db_graceful(self, auth_client):
        """When POLSIA_DB points to non-existent file, returns graceful error."""
        data = auth_client.get("/api/hq/evolution").json()
        assert "error" in data or "agent_metrics" in data or "suggestions" in data
