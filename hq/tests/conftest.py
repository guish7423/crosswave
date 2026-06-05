"""Test configuration for HQ Bridge API tests.

Provides proper pytest fixtures (not module-level singletons) for
clean test isolation.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")
os.environ.setdefault("HQ_AUTH_TOKEN", "test-hq-token")

_root_dir = str(Path(__file__).resolve().parent.parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

_hq_dir = str(Path(__file__).resolve().parent.parent)
if _hq_dir not in sys.path:
    sys.path.insert(0, _hq_dir)


import pytest
from fastapi.testclient import TestClient
from server import CACHE, create_app


@pytest.fixture
def app():
    """Fresh app instance per test (no lifecycle or shared state leaks)."""
    return create_app()


@pytest.fixture
def client(app):
    """TestClient wrapping a fresh app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    """Auth headers for HQ API endpoints."""
    return {"X-HQ-Token": os.environ["HQ_AUTH_TOKEN"]}


@pytest.fixture
def auth_client(client, auth_headers):
    """TestClient subclass that auto-adds X-HQ-Token."""
    orig_get = client.get
    orig_post = client.post
    orig_put = client.put

    def _get(url, **kw):
        kw.setdefault("headers", {}).update(auth_headers)
        return orig_get(url, **kw)

    def _post(url, **kw):
        kw.setdefault("headers", {}).update(auth_headers)
        return orig_post(url, **kw)

    def _put(url, **kw):
        kw.setdefault("headers", {}).update(auth_headers)
        return orig_put(url, **kw)

    client.get = _get
    client.post = _post
    client.put = _put
    return client


@pytest.fixture(autouse=True)
def reset_cache():
    """Populate CACHE with test data before each test, clear after."""
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
    for k in list(CACHE.keys()):
        if k != "last_sync":
            CACHE[k] = [] if isinstance(CACHE[k], list) else CACHE[k]
