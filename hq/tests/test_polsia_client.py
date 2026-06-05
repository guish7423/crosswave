"""Tests for hq/polsia_client.py."""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio


def _make_client(base_url: str = "http://test", api_key: str = "test-key"):
    """Helper: create a PolsiaClient with test credentials."""
    from hq.polsia_client import PolsiaClient
    return PolsiaClient(base_url=base_url, api_key=api_key)


def _mock_resp(status_code: int = 200, json_data=None):
    """Build a mock httpx.Response (json/raise_for_status are sync)."""
    m = MagicMock()
    m.status_code = status_code
    if json_data is not None:
        m.json.return_value = json_data
    m.raise_for_status.return_value = None
    return m


# ── GET /agents/monitor ──────────────────────────────────────────


async def test_get_agents_returns_dict():
    client = _make_client()
    resp = _mock_resp(json_data={"agents": [{"agent_type": "orchestrator", "status": "idle"}]})
    client._client.request = AsyncMock(return_value=resp)
    result = await client.get_agents()
    assert result == {"agents": [{"agent_type": "orchestrator", "status": "idle"}]}


# ── GET /tasks ───────────────────────────────────────────────────


async def test_get_tasks_returns_list():
    client = _make_client()
    resp = _mock_resp(json_data=[{"id": 1, "title": "T1", "status": "pending"}])
    client._client.request = AsyncMock(return_value=resp)
    result = await client.get_tasks()
    assert result[0]["title"] == "T1"


async def test_get_tasks_with_filters():
    client = _make_client()
    resp = _mock_resp(json_data=[])
    client._client.request = AsyncMock(return_value=resp)
    await client.get_tasks(status="pending", agent_type="orchestrator", limit=200)
    call_kwargs = client._client.request.call_args[1]
    assert call_kwargs["params"]["status"] == "pending"
    assert call_kwargs["params"]["agent_type"] == "orchestrator"
    assert call_kwargs["params"]["limit"] == 200


# ── GET /activity ────────────────────────────────────────────────


async def test_get_activity():
    client = _make_client()
    resp = _mock_resp(json_data=[{"id": 1, "action": "test", "level": "info"}])
    client._client.request = AsyncMock(return_value=resp)
    await client.get_activity(limit=50)
    assert client._client.request.call_args[1]["params"]["limit"] == 50


# ── GET /leads ───────────────────────────────────────────────────


async def test_get_leads():
    client = _make_client()
    resp = _mock_resp(json_data={"total": 2, "data": [{"id": 1, "name": "Alice"}]})
    client._client.request = AsyncMock(return_value=resp)
    await client.get_leads(status="new")
    assert client._client.request.call_args[1]["params"]["status"] == "new"


# ── GET /orders/external (auth) ──────────────────────────────────


async def test_get_external_orders_sends_api_key():
    client = _make_client()
    resp = _mock_resp(json_data={"data": [], "total": 0})
    client._client.request = AsyncMock(return_value=resp)
    await client.get_external_orders()
    headers = client._client.request.call_args[1].get("headers", {})
    assert headers.get("X-API-Key") == "test-key"


# ── GET /dashboard/summary ───────────────────────────────────────


async def test_get_dashboard_summary():
    client = _make_client()
    resp = _mock_resp(json_data={"total_revenue": 1000.0})
    client._client.request = AsyncMock(return_value=resp)
    result = await client.get_dashboard_summary()
    assert result["total_revenue"] == 1000.0


# ── GET /dashboard/health (auth) ─────────────────────────────────


async def test_get_health_sends_api_key():
    client = _make_client()
    resp = _mock_resp(json_data={"overall": "healthy"})
    client._client.request = AsyncMock(return_value=resp)
    result = await client.get_health()
    assert result["overall"] == "healthy"
    headers = client._client.request.call_args[1].get("headers", {})
    assert headers.get("X-API-Key") == "test-key"


# ── POST /tasks (create) ─────────────────────────────────────────


async def test_create_task():
    client = _make_client()
    resp = _mock_resp(status_code=201, json_data={"id": 1, "title": "Test", "agent_type": "orchestrator", "status": "pending"})
    client._client.request = AsyncMock(return_value=resp)
    result = await client.create_task(title="Test", agent_type="orchestrator")
    assert result["id"] == 1
    data = client._client.request.call_args[1].get("json", {})
    assert data["title"] == "Test"
    assert data["agent_type"] == "orchestrator"


async def test_create_task_defaults():
    client = _make_client()
    resp = _mock_resp(status_code=201, json_data={"id": 2, "title": "Default", "agent_type": "social", "status": "pending"})
    client._client.request = AsyncMock(return_value=resp)
    await client.create_task("Default", "social")
    data = client._client.request.call_args[1]["json"]
    assert data["priority"] == 3
    assert data["source"] == "api"


# ── Error handling ───────────────────────────────────────────────


async def test_client_raises_on_http_error():
    from hq.polsia_client import PolsiaConnectionError
    client = _make_client()
    resp = _mock_resp(status_code=503)
    resp.raise_for_status.side_effect = Exception("503 Service Unavailable")
    client._client.request = AsyncMock(return_value=resp)
    with pytest.raises(PolsiaConnectionError):
        await client.get_agents()


async def test_client_handles_empty_response():
    client = _make_client()
    resp = _mock_resp(json_data=[])
    client._client.request = AsyncMock(return_value=resp)
    result = await client.get_tasks()
    assert result == []


# ── Env configuration ────────────────────────────────────────────


async def test_client_reads_env():
    os.environ["POLSIA_BASE_URL"] = "http://env-test:8001"
    os.environ["POLSIA_API_KEY"] = "env-key"
    try:
        from hq.polsia_client import PolsiaClient
        client = PolsiaClient()
        assert client.base_url == "http://env-test:8001"
        assert client.api_key == "env-key"
    finally:
        del os.environ["POLSIA_BASE_URL"]
        del os.environ["POLSIA_API_KEY"]
