"""Test configuration for HQ Bridge API tests."""

import os
import sys
from pathlib import Path

# Point POLSIA_DB to non-existent file so startup sync doesn't error
os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")
# Set auth token for tests
os.environ.setdefault("HQ_AUTH_TOKEN", "test-hq-token")

# Ensure hq/ is on sys.path so `from server import app` works
_hq_dir = str(Path(__file__).resolve().parent.parent)
if _hq_dir not in sys.path:
    sys.path.insert(0, _hq_dir)

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

# Must import AFTER env/path setup
from server import app, CACHE

_raw_client = TestClient(app)
_AUTH = os.environ["HQ_AUTH_TOKEN"]

class _AuthClient:
    """Wrapper that adds X-HQ-Token to all requests except public endpoints."""
    def get(self, url, **kw):
        kw.setdefault("headers", {})["X-HQ-Token"] = _AUTH
        return _raw_client.get(url, **kw)
    def post(self, url, **kw):
        kw.setdefault("headers", {})["X-HQ-Token"] = _AUTH
        return _raw_client.post(url, **kw)
    def put(self, url, **kw):
        kw.setdefault("headers", {})["X-HQ-Token"] = _AUTH
        return _raw_client.put(url, **kw)
    def patch(self, url, **kw):
        kw.setdefault("headers", {})["X-HQ-Token"] = _AUTH
        return _raw_client.patch(url, **kw)
    def delete(self, url, **kw):
        kw.setdefault("headers", {})["X-HQ-Token"] = _AUTH
        return _raw_client.delete(url, **kw)

client = _AuthClient()


@pytest.fixture(autouse=True)
def reset_cache():
    """Populate CACHE with representative test data before each test."""
    CACHE["employees"] = [
        {"name": "Orchestrator", "type": "ai", "role": "orchestrator", "status": "idle",
         "agent_type": "orchestrator"},
        {"name": "Social Media", "type": "ai", "role": "social_media", "status": "running",
         "agent_type": "social_media"},
        {"name": "Finance Agent", "type": "ai", "role": "finance_agent", "status": "error",
         "agent_type": "finance_agent"},
    ]
    CACHE["lines"] = [
        {"name": "CrossBridge", "slug": "crossbridge", "status": "active",
         "monthly_revenue": 0, "customer_count": 0},
        {"name": "Polsia Fork", "slug": "polsia", "status": "active",
         "monthly_revenue": 174, "customer_count": 4},
        {"name": "HiveMind", "slug": "hivemind", "status": "development",
         "monthly_revenue": 0, "customer_count": 0},
    ]
    CACHE["orders"] = [
        {"title": "Agent Cycle 1", "status": "completed", "agent_type": "orchestrator",
         "created_at": "2026-05-28T10:00:00", "source_id": 1, "platform": "internal"},
        {"title": "Social Post", "status": "pending", "agent_type": "social_media",
         "created_at": "2026-05-29T14:00:00", "source_id": 2, "platform": "internal"},
        {"title": "Finance Report", "status": "failed", "agent_type": "finance_agent",
         "created_at": "2026-05-30T08:00:00", "source_id": 3, "platform": "internal"},
    ]
    CACHE["leads"] = [
        {"id": 1, "name": "Alice", "email": "alice@test.com", "company": "TestCorp",
         "product_interest": "crossbridge", "budget_range": "149", "message": "Interested",
         "status": "new", "source_page": "pricing", "created_at": "2026-05-30T10:00:00"},
        {"id": 2, "name": "Bob", "email": "bob@test.com", "company": "BizInc",
         "product_interest": "crossdeploy", "budget_range": "2000", "message": "Need deploy",
         "status": "contacted", "source_page": "deploy", "created_at": "2026-05-29T10:00:00"},
    ]
    CACHE["external_orders"] = [
        {"id": 1, "title": "Build API Gateway", "platform": "upwork",
         "external_id": "up_001", "status": "scanned", "budget_min": 500, "budget_max": 1000,
         "currency": "USD", "score": 8, "score_reason": "good match", "assigned_agent": "",
         "created_at": "2026-05-30T12:00:00"},
        {"id": 2, "title": "Docker Setup", "platform": "fiverr",
         "external_id": "fv_001", "status": "accepted", "budget_min": 200, "budget_max": 300,
         "currency": "USD", "score": 6, "score_reason": "deploy match", "assigned_agent": "deploy_agent",
         "created_at": "2026-05-29T12:00:00"},
    ]
    CACHE["expenses"] = [
        {"amount": 200.0, "category": "hosting", "description": "Server", "date": "2026-05-01"},
        {"amount": 150.0, "category": "ai", "description": "API credits", "date": "2026-05-01"},
        {"amount": 50.0, "category": "tools", "description": "SaaS", "date": "2026-05-01"},
    ]
    CACHE["revenue_history"] = [
        {"date": "2026-05-01", "amount": 150.0, "source": "subscription"},
        {"date": "2026-06-01", "amount": 174.0, "source": "subscription"},
    ]
    CACHE["last_sync"] = "2026-06-01T00:00:00+00:00"
    CACHE["mrr"] = 174
    yield
    # Clear after test so tests don't leak state
    keys = list(CACHE.keys())
    for k in keys:
        if k != "last_sync":
            CACHE[k] = [] if isinstance(CACHE[k], list) else CACHE[k]
