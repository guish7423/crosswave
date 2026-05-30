"""Tests for FastAPI routes."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_landing_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"CrossWave" in resp.content


def test_dashboard_page():
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Dashboard" in resp.content or b"CrossWave" in resp.content


def test_agents_page():
    resp = client.get("/agents")
    assert resp.status_code == 200
    assert b"Agent" in resp.content or b"CrossWave" in resp.content


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "CrossWave"


def test_static_files():
    resp = client.get("/static/style.css")
    assert resp.status_code == 200


def test_proxy_agents_status():
    """HTMX partial returns HTML, not JSON."""
    resp = client.get("/api/v1/_proxy/agents/status")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_proxy_dashboard_summary():
    """HTMX partial returns HTML."""
    resp = client.get("/api/v1/_proxy/dashboard/summary")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_proxy_task_summary():
    resp = client.get("/api/v1/_proxy/dashboard/task-summary")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_proxy_agent_rows():
    resp = client.get("/api/v1/_proxy/agents/rows")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_proxy_activity():
    resp = client.get("/api/v1/_proxy/activity")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
