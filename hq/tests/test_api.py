"""Tests for CrossWave HQ Bridge API endpoints.

Uses fixture-based auth_client from conftest.py (no module-level singletons).
"""

import os

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")

import pytest
from conftest import CACHE  # type: ignore[import]


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
    def test_summary_structure(self, auth_client):
        resp = auth_client.get("/api/hq/summary")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("employees", "lines", "orders", "mrr", "customers", "leads", "last_sync"):
            assert key in data

    def test_summary_employee_counts(self, auth_client):
        resp = auth_client.get("/api/hq/summary")
        data = resp.json()
        assert data["employees"]["total"] == 3
        assert data["employees"]["status_distribution"]["idle"] == 1
        assert data["employees"]["status_distribution"]["running"] == 1
        assert data["employees"]["status_distribution"]["error"] == 1

    def test_summary_orders(self, auth_client):
        resp = auth_client.get("/api/hq/summary")
        data = resp.json()
        assert data["orders"]["total"] == 3
        assert data["orders"]["active"] == 1
        assert data["orders"]["status_distribution"]["completed"] == 1

    def test_summary_mrr(self, auth_client):
        resp = auth_client.get("/api/hq/summary")
        data = resp.json()
        assert data["mrr"] == 174
        assert data["customers"] == 4

    def test_summary_leads(self, auth_client):
        resp = auth_client.get("/api/hq/summary")
        data = resp.json()
        assert data["leads"]["total"] == 2
        assert data["leads"]["new"] == 1

    def test_summary_lines_health(self, auth_client):
        resp = auth_client.get("/api/hq/summary")
        data = resp.json()
        lines = data["lines"]
        assert len(lines) == 3
        active = [l for l in lines if l["health"] == "healthy"]
        dev = [l for l in lines if l["health"] == "warning"]
        assert len(active) == 2
        assert len(dev) == 1


# ─── /api/hq/employees ────────────────────────────────────────────────────────
class TestEmployees:
    def test_get_employees(self, auth_client):
        resp = auth_client.get("/api/hq/employees")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3
        names = [e["name"] for e in data["data"]]
        assert "Orchestrator" in names
        assert "Social Media" in names

    def test_employee_fields(self, auth_client):
        resp = auth_client.get("/api/hq/employees")
        emp = resp.json()["data"][0]
        for key in ("name", "type", "role", "status", "agent_type"):
            assert key in emp


# ─── /api/hq/orders (parametrized filters) ────────────────────────────────────
class TestOrders:
    @pytest.mark.parametrize("query,expected_count,expected_status", [
        ("", 3, None),
        ("?status=completed", 1, "completed"),
        ("?platform=internal", 3, None),
        ("?platform=upwork", 0, None),
    ], ids=["all", "filter_completed", "filter_internal", "filter_none"])
    def test_orders(self, auth_client, query, expected_count, expected_status):
        resp = auth_client.get(f"/api/hq/orders{query}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == expected_count
        if expected_status and data:
            assert data[0]["status"] == expected_status


# ─── /api/hq/leads (parametrized filters) ─────────────────────────────────────
class TestLeads:
    @pytest.mark.parametrize("query,expected_count,expected_status", [
        ("", 2, None),
        ("?status=new", 1, "new"),
        ("?status=won", 0, None),
    ], ids=["all", "filter_new", "filter_none"])
    def test_leads(self, auth_client, query, expected_count, expected_status):
        resp = auth_client.get(f"/api/hq/leads{query}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == expected_count
        if expected_status and data:
            assert data[0]["status"] == expected_status


# ─── /api/hq/external-orders ──────────────────────────────────────────────────
class TestExternalOrders:
    @pytest.mark.parametrize("query,expected_count", [
        ("", 2),
        ("?platform=upwork", 1),
        ("?status=accepted", 1),
    ], ids=["all", "filter_platform", "filter_status"])
    def test_external_orders(self, auth_client, query, expected_count):
        resp = auth_client.get(f"/api/hq/external-orders{query}")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == expected_count

    def test_external_order_fields(self, auth_client):
        resp = auth_client.get("/api/hq/external-orders")
        order = resp.json()["data"][0]
        for key in ("id", "title", "platform", "status", "score", "created_at"):
            assert key in order

    def test_empty_when_no_data(self, auth_client):
        CACHE["external_orders"] = []
        resp = auth_client.get("/api/hq/external-orders")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        CACHE["external_orders"] = [
            {"id": 1, "title": "X", "platform": "upwork",
             "external_id": "up_001", "status": "scanned", "budget_min": 500, "budget_max": 1000,
             "currency": "USD", "score": 8, "score_reason": "good", "assigned_agent": "",
             "created_at": "2026-05-30T12:00:00"},
        ]


# ─── /api/hq/lines ────────────────────────────────────────────────────────────
class TestLines:
    def test_get_lines(self, auth_client):
        resp = auth_client.get("/api/hq/lines")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3
        slugs = [l["slug"] for l in data["data"]]
        assert "crossbridge" in slugs
        assert "polsia" in slugs

    def test_line_revenue(self, auth_client):
        resp = auth_client.get("/api/hq/lines")
        polsia = next(l for l in resp.json()["data"] if l["slug"] == "polsia")
        assert polsia["monthly_revenue"] == 174


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

    def test_finance_values(self, auth_client):
        data = auth_client.get("/api/hq/finances").json()
        assert data["total_revenue"] == 324.0
        assert data["total_costs"] == 400.0
        assert data["mrr"] == 174
        assert data["arr"] == 174 * 12
        assert isinstance(data["profit_margin"], float)

    def test_expense_categories(self, auth_client):
        cats = auth_client.get("/api/hq/finances").json()["expense_by_category"]
        assert len(cats) == 3
        assert cats[0]["category"] == "hosting"
        assert cats[0]["amount"] == 200.0

    def test_revenue_by_month(self, auth_client):
        revs = auth_client.get("/api/hq/finances").json()["revenue_by_month"]
        assert len(revs) == 2
        assert revs[0]["month"] == "2026-05"
        assert revs[1]["month"] == "2026-06"


# ─── /api/hq/reports ──────────────────────────────────────────────────────────
class TestReports:
    def test_reports_structure(self, auth_client):
        data = auth_client.get("/api/hq/reports").json()
        for key in ("total_tasks", "completed_tasks", "failed_tasks", "completion_rate",
                     "agent_performance", "task_trend", "employee_count"):
            assert key in data

    def test_reports_counts(self, auth_client):
        data = auth_client.get("/api/hq/reports").json()
        assert data["total_tasks"] == 3
        assert data["completed_tasks"] == 1
        assert data["failed_tasks"] == 1
        assert data["completion_rate"] == pytest.approx(33.3, rel=0.5)

    def test_agent_performance(self, auth_client):
        agents = auth_client.get("/api/hq/reports").json()["agent_performance"]
        assert len(agents) == 3
        orch = next(a for a in agents if a["agent"] == "orchestrator")
        assert orch["done"] == 1

    def test_employee_count(self, auth_client):
        assert auth_client.get("/api/hq/reports").json()["employee_count"] == 3


# ─── /api/portal/order/{id} ────────────────────────────────────────────────────
class TestPortalOrder:
    def test_get_portal_order(self, auth_client):
        data = auth_client.get("/api/portal/order/1").json()
        assert data["id"] == 1
        assert data["status"] == "scanned"
        assert data["score"] == 8

    def test_portal_order_404(self, auth_client):
        resp = auth_client.get("/api/portal/order/999")
        assert resp.status_code == 404

    def test_portal_order_stages(self, auth_client):
        data = auth_client.get("/api/portal/order/1").json()
        assert data["total_stages"] == 8
        assert data["stages"] == [
            "pending", "scanned", "accepted", "in_progress",
            "deploying", "testing", "completed", "delivered"
        ]

    def test_portal_order_accepted(self, auth_client):
        data = auth_client.get("/api/portal/order/2").json()
        assert data["status"] == "accepted"
        assert data["progress_idx"] == 2

    def test_portal_order_no_deployment_plan(self, auth_client):
        assert auth_client.get("/api/portal/order/1").json()["deployment_plan"] is None


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
