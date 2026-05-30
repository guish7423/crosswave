"""Tests for Polsia Fork API client (mock fallback)."""

from app.services.polsia_client import PolsiaClient


async def test_mock_fallback_dashboard_summary(monkeypatch):
    monkeypatch.setattr("app.config.settings.polsia_mock", True)
    client = PolsiaClient()
    result = await client.get_dashboard_summary()
    assert isinstance(result, dict)
    assert result["active_agents"] == 10
    assert result["tasks_today_total"] == 24
    assert "mrr_cents" in result


async def test_mock_fallback_agents(monkeypatch):
    monkeypatch.setattr("app.config.settings.polsia_mock", True)
    client = PolsiaClient()
    result = await client.get_agents_status()
    assert isinstance(result, list)
    assert len(result) == 10
    orchestrator = next(a for a in result if a["agent_type"] == "orchestrator")
    assert orchestrator["status"] == "running"


async def test_mock_fallback_activity(monkeypatch):
    monkeypatch.setattr("app.config.settings.polsia_mock", True)
    client = PolsiaClient()
    result = await client.get_activity()
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["agent_type"] is not None


async def test_disconnected_no_mock(monkeypatch):
    monkeypatch.setattr("app.config.settings.polsia_mock", False)
    client = PolsiaClient()
    result = await client.get_dashboard_summary()
    assert isinstance(result, dict)
    assert result.get("status") == "disconnected"


async def test_get_without_client(monkeypatch):
    """When client is None, should fall back to mock or disconnected."""
    monkeypatch.setattr("app.config.settings.polsia_mock", True)
    client = PolsiaClient()
    client._client = None
    result = await client._get("/api/v1/dashboard/summary")
    assert isinstance(result, dict)
