"""Tests for CrossWave HQ Bridge API endpoints.

Covers all 13 API endpoints:
  /health, /api/hq/summary, /api/hq/employees, /api/hq/orders,
  /api/hq/leads, /api/hq/external-orders, /api/hq/lines, /api/hq/sync,
  /api/hq/finances, /api/hq/reports, /api/portal/order/{id},
  /api/hq/monitor, /api/hq/evolution
"""

import os
from pathlib import Path

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")

import pytest
from fastapi.testclient import TestClient

from conftest import client, CACHE


# ─── /health ───────────────────────────────────────────────────────────────────
class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "CrossWave HQ Bridge"
        assert isinstance(data["services"], int)


# ─── /api/hq/summary ──────────────────────────────────────────────────────────
class TestSummary:
    def test_summary_structure(self):
        resp = client.get("/api/hq/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "employees" in data
        assert "lines" in data
        assert "orders" in data
        assert "mrr" in data
        assert "customers" in data
        assert "leads" in data
        assert "last_sync" in data

    def test_summary_employee_counts(self):
        resp = client.get("/api/hq/summary")
        data = resp.json()
        assert data["employees"]["total"] == 3
        assert data["employees"]["status_distribution"]["idle"] == 1
        assert data["employees"]["status_distribution"]["running"] == 1
        assert data["employees"]["status_distribution"]["error"] == 1

    def test_summary_orders(self):
        resp = client.get("/api/hq/summary")
        data = resp.json()
        assert data["orders"]["total"] == 3
        assert data["orders"]["active"] == 1  # only "pending" is active
        assert data["orders"]["status_distribution"]["completed"] == 1

    def test_summary_mrr(self):
        resp = client.get("/api/hq/summary")
        data = resp.json()
        assert data["mrr"] == 174
        assert data["customers"] == 4

    def test_summary_leads(self):
        resp = client.get("/api/hq/summary")
        data = resp.json()
        assert data["leads"]["total"] == 2
        assert data["leads"]["new"] == 1

    def test_summary_lines_health(self):
        resp = client.get("/api/hq/summary")
        data = resp.json()
        lines = data["lines"]
        assert len(lines) == 3
        active = [l for l in lines if l["health"] == "healthy"]
        dev = [l for l in lines if l["health"] == "warning"]
        assert len(active) == 2
        assert len(dev) == 1


# ─── /api/hq/employees ────────────────────────────────────────────────────────
class TestEmployees:
    def test_get_employees(self):
        resp = client.get("/api/hq/employees")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3
        names = [e["name"] for e in data["data"]]
        assert "Orchestrator" in names
        assert "Social Media" in names

    def test_employee_fields(self):
        resp = client.get("/api/hq/employees")
        emp = resp.json()["data"][0]
        assert "name" in emp
        assert "type" in emp
        assert "role" in emp
        assert "status" in emp
        assert "agent_type" in emp


# ─── /api/hq/orders ───────────────────────────────────────────────────────────
class TestOrders:
    def test_get_all_orders(self):
        resp = client.get("/api/hq/orders")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3

    def test_filter_by_status(self):
        resp = client.get("/api/hq/orders?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "completed"

    def test_filter_by_platform(self):
        resp = client.get("/api/hq/orders?platform=internal")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3

    def test_filter_empty_result(self):
        resp = client.get("/api/hq/orders?platform=upwork")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ─── /api/hq/leads ────────────────────────────────────────────────────────────
class TestLeads:
    def test_get_all_leads(self):
        resp = client.get("/api/hq/leads")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["total"] == 2
        assert data["new_count"] == 1

    def test_leads_filter_by_status(self):
        resp = client.get("/api/hq/leads?status=new")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "new"

    def test_leads_filter_empty(self):
        resp = client.get("/api/hq/leads?status=won")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ─── /api/hq/external-orders ──────────────────────────────────────────────────
class TestExternalOrders:
    def test_get_all_external_orders(self):
        resp = client.get("/api/hq/external-orders")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["total"] == 2

    def test_filter_by_platform(self):
        resp = client.get("/api/hq/external-orders?platform=upwork")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["platform"] == "upwork"

    def test_filter_by_status(self):
        resp = client.get("/api/hq/external-orders?status=accepted")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "accepted"

    def test_external_order_fields(self):
        resp = client.get("/api/hq/external-orders")
        order = resp.json()["data"][0]
        assert "id" in order
        assert "title" in order
        assert "platform" in order
        assert "status" in order
        assert "score" in order
        assert "created_at" in order

    def test_empty_when_no_data(self):
        # Temporarily clear external_orders
        CACHE["external_orders"] = []
        resp = client.get("/api/hq/external-orders")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        # Restore for other tests
        CACHE["external_orders"] = [
            {"id": 1, "title": "X", "platform": "upwork",
             "external_id": "up_001", "status": "scanned", "budget_min": 500, "budget_max": 1000,
             "currency": "USD", "score": 8, "score_reason": "good", "assigned_agent": "",
             "created_at": "2026-05-30T12:00:00"},
        ]


# ─── /api/hq/lines ────────────────────────────────────────────────────────────
class TestLines:
    def test_get_lines(self):
        resp = client.get("/api/hq/lines")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3
        slugs = [l["slug"] for l in data["data"]]
        assert "crossbridge" in slugs
        assert "polsia" in slugs

    def test_line_revenue(self):
        resp = client.get("/api/hq/lines")
        polsia = next(l for l in resp.json()["data"] if l["slug"] == "polsia")
        assert polsia["monthly_revenue"] == 174


# ─── /api/hq/sync ─────────────────────────────────────────────────────────────
class TestSync:
    def test_manual_sync(self):
        resp = client.get("/api/hq/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "synced_at" in data


# ─── /api/hq/finances ─────────────────────────────────────────────────────────
class TestFinances:
    def test_finance_structure(self):
        resp = client.get("/api/hq/finances")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_revenue" in data
        assert "total_costs" in data
        assert "profit_margin" in data
        assert "mrr" in data
        assert "arr" in data
        assert "expense_by_category" in data
        assert "revenue_by_month" in data

    def test_finance_values(self):
        resp = client.get("/api/hq/finances")
        data = resp.json()
        assert data["total_revenue"] == 324.0  # 150 + 174
        assert data["total_costs"] == 400.0  # 200 + 150 + 50
        assert data["mrr"] == 174
        assert data["arr"] == 174 * 12
        # Profit margin: (324-400)/324 = -23.5% (negative)
        assert isinstance(data["profit_margin"], float)

    def test_expense_categories(self):
        resp = client.get("/api/hq/finances")
        cats = resp.json()["expense_by_category"]
        assert len(cats) == 3
        # Sorted by amount descending: hosting(200) > ai(150) > tools(50)
        assert cats[0]["category"] == "hosting"
        assert cats[0]["amount"] == 200.0

    def test_revenue_by_month(self):
        resp = client.get("/api/hq/finances")
        revs = resp.json()["revenue_by_month"]
        assert len(revs) == 2  # May & June
        assert revs[0]["month"] == "2026-05"
        assert revs[1]["month"] == "2026-06"


# ─── /api/hq/reports ──────────────────────────────────────────────────────────
class TestReports:
    def test_reports_structure(self):
        resp = client.get("/api/hq/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tasks" in data
        assert "completed_tasks" in data
        assert "failed_tasks" in data
        assert "completion_rate" in data
        assert "agent_performance" in data
        assert "task_trend" in data
        assert "employee_count" in data

    def test_reports_counts(self):
        resp = client.get("/api/hq/reports")
        data = resp.json()
        assert data["total_tasks"] == 3
        assert data["completed_tasks"] == 1
        assert data["failed_tasks"] == 1
        assert data["completion_rate"] == pytest.approx(33.3, rel=0.5)

    def test_agent_performance(self):
        resp = client.get("/api/hq/reports")
        agents = resp.json()["agent_performance"]
        assert len(agents) == 3
        # orchestrator has 1 completed, social_media 1 pending, finance_agent 1 failed
        orch = next(a for a in agents if a["agent"] == "orchestrator")
        assert orch["done"] == 1

    def test_employee_count(self):
        resp = client.get("/api/hq/reports")
        assert resp.json()["employee_count"] == 3


# ─── /api/portal/order/{id} ────────────────────────────────────────────────────
class TestPortalOrder:
    def test_get_portal_order(self):
        resp = client.get("/api/portal/order/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["status"] == "scanned"
        assert "progress_idx" in data
        assert "total_stages" in data
        assert "stages" in data
        assert data["score"] == 8

    def test_portal_order_404(self):
        resp = client.get("/api/portal/order/999")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_portal_order_stages(self):
        resp = client.get("/api/portal/order/1")
        data = resp.json()
        assert data["total_stages"] == 8
        assert data["stages"] == [
            "pending", "scanned", "accepted", "in_progress",
            "deploying", "testing", "completed", "delivered"
        ]

    def test_portal_order_accepted(self):
        resp = client.get("/api/portal/order/2")
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["progress_idx"] == 2  # index of "accepted" in stages

    def test_portal_order_no_deployment_plan(self):
        resp = client.get("/api/portal/order/1")
        data = resp.json()
        assert "deployment_plan" in data
        assert data["deployment_plan"] is None


# ─── /api/hq/monitor ──────────────────────────────────────────────────────────
class TestMonitor:
    def test_monitor_structure(self):
        resp = client.get("/api/hq/monitor")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "results" in data
        s = data["summary"]
        assert "total" in s
        assert "up" in s
        assert "degraded" in s
        assert "down" in s
        assert "avg_response_time_ms" in s
        assert "all_up" in s
        assert "timestamp" in s

    def test_monitor_results_count(self):
        resp = client.get("/api/hq/monitor")
        assert len(resp.json()["results"]) >= 4

    def test_monitor_result_fields(self):
        resp = client.get("/api/hq/monitor")
        result = resp.json()["results"][0]
        assert "service" in result
        assert "status" in result
        assert "http_status" in result
        assert "response_time_ms" in result
        assert "label" in result

    def test_monitor_summary_all_up_not_guaranteed(self):
        """All_up may be false if services are down in test env; just verify type."""
        resp = client.get("/api/hq/monitor")
        assert isinstance(resp.json()["summary"]["all_up"], bool)


# ─── /api/hq/evolution ────────────────────────────────────────────────────────
class TestEvolution:
    def test_evolution_no_db_graceful(self):
        """When POLSIA_DB points to non-existent file, evolution returns graceful error."""
        resp = client.get("/api/hq/evolution")
        assert resp.status_code == 200
        data = resp.json()
        # Our test env has POLSIA_DB = /tmp/crosswave-test-polsia.db which doesn't exist
        assert "error" in data or "agent_metrics" in data or "suggestions" in data
