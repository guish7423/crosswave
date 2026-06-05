"""Tests for FastAPI routes — page routes + proxy endpoints.

Parametrized to reduce boilerplate for repetitive patterns.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ══════════════════════════════════════════════════════════════
# Page routes (parametrized)
# ══════════════════════════════════════════════════════════════

import pytest


@pytest.mark.parametrize("path,keyword", [
    ("/", "CrossWave"),
    ("/dashboard", "Dashboard"),
    ("/agents", "Agent"),
    ("/deploy", "Deploy"),
    ("/request-quote", "Quote"),
], ids=["landing", "dashboard", "agents", "deploy", "request-quote"])
def test_page_routes(path: str, keyword: str):
    """All page routes return 200 + expected keyword in content."""
    resp = client.get(path)
    assert resp.status_code == 200
    assert keyword.encode() in resp.content or keyword.lower().encode() in resp.content


def test_robots_txt():
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert b"Allow:" in resp.content


def test_quote_view_not_found():
    """Invalid token shows error state (not 404)."""
    resp = client.get("/quote/nonexistent-token-12345")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "not found" in content.lower() or "error" in content.lower() or "Proposal" in content


def test_quote_view_mock():
    """Mock proposal renders proposal page (polsia mock mode on by default)."""
    resp = client.get("/quote/mock-token-001")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# Proxy GET routes — paramtrized for 5 identical HTMX endpoints
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("endpoint", [
    "/api/v1/_proxy/agents/status",
    "/api/v1/_proxy/dashboard/summary",
    "/api/v1/_proxy/dashboard/task-summary",
    "/api/v1/_proxy/agents/rows",
    "/api/v1/_proxy/activity",
], ids=["agents_status", "dashboard_summary", "task_summary", "agent_rows", "activity"])
def test_proxy_html_endpoints(endpoint: str):
    """All HTMX proxy endpoints return 200 + text/html."""
    resp = client.get(endpoint)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_proxy_analytics():
    """Analytics endpoint returns JSON with chart data."""
    resp = client.get("/api/v1/_proxy/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "status_distribution" in data
    assert "agent_breakdown" in data
    assert "daily_trend" in data


def test_proxy_blog_latest():
    """Blog proxy returns JSON with posts list (empty when CrossBlog down)."""
    resp = client.get("/api/v1/_proxy/blog/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert "posts" in data
    assert isinstance(data["posts"], list)


def test_proxy_execution_status_not_found():
    """Execution status for nonexistent order returns error/mock."""
    resp = client.get("/api/v1/_proxy/execution-status/99999")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


# ══════════════════════════════════════════════════════════════
# Proxy POST routes
# ══════════════════════════════════════════════════════════════

def test_proxy_submit_quote():
    """Submit Quick Quote form data via proxy."""
    resp = client.post(
        "/api/v1/_proxy/submit-quote",
        json={"name": "Test User", "email": "test@example.com",
              "company": "TestCorp", "project_description": "Test project",
              "budget_range": "2000-5000", "preferred_tier": "standard"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Returns mock fallback or disconnected state
    assert isinstance(data, dict)


def test_proxy_submit_quote_invalid():
    """Submit quote with missing required fields returns fallback."""
    resp = client.post(
        "/api/v1/_proxy/submit-quote",
        json={"name": "", "email": ""},
    )
    # The proxy forwards to Polsia which validates — but TestClient may send anyway
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_proxy_track_view():
    """Track a proposal view via proxy."""
    resp = client.post("/api/v1/_proxy/track-view/test-token")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_proxy_accept_proposal():
    """Accept a proposal via proxy (mock fallback)."""
    resp = client.post("/api/v1/_proxy/accept-proposal/test-token")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_proxy_reject_proposal():
    """Reject a proposal via proxy (mock fallback)."""
    resp = client.post(
        "/api/v1/_proxy/reject-proposal/test-token",
        json={"reason": "Budget too high"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_proxy_create_checkout():
    """Create Stripe Checkout session for an order (mock fallback)."""
    resp = client.post("/api/v1/_proxy/create-checkout/1")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_proxy_product_checkout():
    """Direct product checkout (Buy Now from pricing page)."""
    resp = client.post(
        "/api/v1/_proxy/product-checkout",
        json={"product_key": "crossdeploy-basic", "customer_email": "buyer@example.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_proxy_execute_deploy():
    """Execute deployment for an order (mock fallback)."""
    resp = client.post("/api/v1/_proxy/execute-deploy/1")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


# ══════════════════════════════════════════════════════════════
# Health endpoint
# ══════════════════════════════════════════════════════════════

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "CrossWave"


def test_static_files():
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
