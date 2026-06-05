"""Tests for hq.polsia_bridge — NocoBase sync."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hq.polsia_bridge import (
    NB_URL,
    create_record,
    ensure_platform_connections,
    get_token,
    list_collection,
    sync,
)

# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """AsyncClient with all HTTP methods mocked."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def reset_token():
    """Reset global TOKEN state between tests."""
    import hq.polsia_bridge as pb

    pb.TOKEN = None
    pb.TOKEN_EXPIRES = 0
    yield


# ─── Token tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_token_success(mock_client):
    """get_token returns token from NocoBase auth endpoint."""
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": {"token": "test-token-abc123"}},
    )
    token = await get_token(mock_client)
    assert token == "test-token-abc123"
    assert mock_client.post.called
    call_kwargs = mock_client.post.call_args
    assert NB_URL in str(call_kwargs[0])


@pytest.mark.asyncio
async def test_get_token_caches(mock_client):
    """get_token caches token and doesn't re-auth on second call."""
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": {"token": "cached-token"}},
    )
    token1 = await get_token(mock_client)
    assert token1 == "cached-token"
    assert mock_client.post.call_count == 1

    # Second call should use cache
    mock_client.post.reset_mock()
    token2 = await get_token(mock_client)
    assert token2 == "cached-token"
    assert mock_client.post.call_count == 0  # no auth call


@pytest.mark.asyncio
async def test_get_token_raises_on_failure(mock_client):
    """get_token raises when NocoBase auth fails."""
    mock_client.post.return_value = MagicMock(
        status_code=401,
        raise_for_status=MagicMock(side_effect=httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=MagicMock(status_code=401),
        )),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await get_token(mock_client)


# ─── list_collection tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_collection_empty(mock_client):
    """list_collection returns empty set when no records."""
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": {"token": "tok"}},
    )
    mock_client.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": [], "meta": {"page": 1, "pageSize": 100, "count": 0}},
    )
    result = await list_collection(mock_client, "employees", "name")
    assert result == set()


@pytest.mark.asyncio
async def test_list_collection_returns_names(mock_client):
    """list_collection returns set of field values."""
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": {"token": "tok"}},
    )
    mock_client.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "data": [
                {"name": "Alice", "id": 1},
                {"name": "Bob", "id": 2},
            ],
            "meta": {"page": 1, "pageSize": 100, "count": 2},
        },
    )
    result = await list_collection(mock_client, "employees", "name")
    assert result == {"Alice", "Bob"}


# ─── create_record tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_record_success(mock_client):
    """create_record returns True on 201."""
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": {"token": "tok"}},
    )
    mock_client.post.reset_mock()
    mock_client.post.return_value = MagicMock(status_code=201)
    result = await create_record(mock_client, "employees", {"name": "Test"})
    assert result is True


@pytest.mark.asyncio
async def test_create_record_fails_on_4xx(mock_client):
    """create_record returns False on 4xx."""
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": {"token": "tok"}},
    )
    mock_client.post.reset_mock()
    mock_client.post.return_value = MagicMock(status_code=409, text="Conflict")
    result = await create_record(mock_client, "employees", {"name": "Dup"})
    assert result is False


# ─── ensure_platform_connections tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_platform_connections_seeds_when_empty(mock_client):
    """ensure_platform_connections creates default platforms when none exist."""
    # Return empty list, then token for create
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": {"token": "tok"}},
    )
    mock_client.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": [], "meta": {"page": 1, "pageSize": 100, "count": 0}},
    )
    mock_client.post.reset_mock()
    mock_client.post.return_value = MagicMock(status_code=201)

    await ensure_platform_connections(mock_client)


# ─── sync integration (mocked) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_skips_when_db_missing():
    """sync gracefully skips when DB_PATH doesn't exist."""
    import hq.polsia_bridge as pb

    pb.DB_PATH = "/tmp/nonexistent/db.sqlite"

    result = await sync()
    assert result is None  # returns None on skip


@pytest.mark.asyncio
async def test_sync_with_mocked_db():
    """sync runs through with a real temp SQLite DB."""
    import os
    import tempfile

    import hq.polsia_bridge as pb

    Pf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Pf.name
    Pf.close()

    try:
        # Create a minimal Polsia-like DB with one task
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            await db.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, agent_type TEXT, status TEXT, created_at TEXT)")
            await db.execute("CREATE TABLE external_orders (id INTEGER PRIMARY KEY, title TEXT, platform TEXT, external_id TEXT, status TEXT, budget_min REAL, budget_max REAL, currency TEXT, score REAL, score_reason TEXT, created_at TEXT, provider_notes TEXT, deliverables TEXT, delivery_notes TEXT)")
            await db.execute("INSERT INTO tasks (title, agent_type, status, created_at) VALUES (?, ?, ?, ?)",
                ("Test Task", "orchestrator", "pending", "2026-06-01"),
            )
            await db.commit()

        # Mock NocoBase HTTP
        pb.DB_PATH = db_path
        with patch("hq.polsia_bridge.httpx.AsyncClient") as mock_http:
            client_instance = AsyncMock()
            mock_http.return_value.__aenter__.return_value = client_instance
            client_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"data": {"token": "test"}},
            )
            client_instance.get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"data": [], "meta": {"page": 1, "pageSize": 100, "count": 0}},
            )

            await sync()
            # Should have called NocoBase APIs
            assert client_instance.post.called

    finally:
        os.unlink(db_path)
