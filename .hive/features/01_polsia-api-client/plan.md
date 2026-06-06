# Polsia Fork API Client

## Discovery

### Original Request
- User said "自行推进" (proceed autonomously). Chose Polsia Fork API integration as the most strategic direction based on architecture analysis.

### Research Findings
- **Polsia Fork API**: 29 API v1 routers at `/api/v1/`. Key: agents.py, tasks.py, dashboard.py, health.py, activity.py, leads.py, orders_external.py.
- **Auth model**: Most endpoints need no auth. Only `health.py` `/dashboard/health` and `orders_external.py` require `X-API-Key` header. Default key is `"dev-key"` (`polsia-fork/app/config.py:10`, `polsia-fork/app/core/auth.py:11-24`).
- **Response format**: All endpoints return inline dicts (no Pydantic response models). Only `polsia-fork/app/schemas/auth.py` exists.
- **Current HQ bottleneck**: `hq/domains/data.py:68-226` reads Polsia Fork SQLite directly via `aiosqlite` — works for dev SQLite, breaks with PostgreSQL in production.
- **Pattern reference**: `hq/nocobase_client.py:1-63` — httpx.AsyncClient + global token cache. Tests use CACHE manipulation (`hq/tests/conftest.py:49-127`) + temp SQLite files.

---

## Auth Matrix

| PolsiaClient Method | Polsia Fork Endpoint | X-API-Key Required | Notes |
|---|---|---|---|
| `get_agents()` | `GET /api/v1/agents/monitor` | No | Public read-only status |
| `get_tasks()` | `GET /api/v1/tasks` | No | Public read |
| `get_task(task_id)` | `GET /api/v1/tasks/{id}` | No | Public read |
| `create_task()` | `POST /api/v1/tasks` | No | Public create |
| `get_activity()` | `GET /api/v1/activity` | No | Public read |
| `get_leads()` | `GET /api/v1/leads` | No | Public read |
| `get_dashboard_summary()` | `GET /api/v1/dashboard/summary` | No | Public read |
| `get_health()` | `GET /api/v1/dashboard/health` | **Yes** | Requires X-API-Key |
| `get_external_orders()` | `GET /api/v1/orders/external` | **Yes** | Router-level auth |

All non-auth methods also accept `needs_auth: bool = False` param. Auth methods set `needs_auth=True` and inject `X-API-Key` header.

## Fallback Contract

`polsia_sync_via_api()` replaces SQLite reads with REST API calls. Each data set is independently fetched. Fallback behavior per endpoint:

| Data | Primary (PolsiaClient) | Fallback | Edge case |
|---|---|---|---|
| Agents (`employees`) | `GET /api/v1/agents/monitor` | Empty employees list | API fails mid-response → CACHE retains prior values |
| Tasks (`orders`, `tasks`) | `GET /api/v1/tasks` | Empty lists | Timeout → empty, no CACHE corruption |
| Activity log | `GET /api/v1/activity` | Empty list | 503 → empty, logged |
| Leads | `GET /api/v1/leads` | Empty list | 500 → empty, logged |
| External orders | `GET /api/v1/orders/external` | Skipped gracefully (auth may fail) | Auth failure → skips, doesn't block other data |
| Dashboard summary | `GET /api/v1/dashboard/summary` | Hardcoded defaults ($174 MRR, 4 subs) | 404 → defaults |
| Health | `GET /api/v1/dashboard/health` | `{"overall": "unknown"}` | Auth failure → unknown |
| Expenses | N/A | SQLite fallback | No API endpoint yet |
| Revenue history | N/A | SQLite fallback | No API endpoint yet |
| Proposals | N/A | SQLite fallback | No API endpoint yet |

**Fallback trigger conditions:**
- Network timeout (>5s per call) → log warning, use fallback for that data subset
- HTTP 5xx → log error, use fallback value per table above
- HTTP 401/403 (auth endpoints only) → log warning, skip (not SQLite fallback — auth failures are permanent)
- Partial success: each data set is independently fetched. A failure in `get_external_orders()` does NOT prevent `get_tasks()` from populating CACHE.

**CACHE state guarantee:** `polsia_sync_via_api()` only writes to CACHE after successful API response for each data subset. If API is completely unreachable, CACHE is NOT cleared — prior data remains. This prevents the dashboard from going blank during transient outages.

---

## Non-Goals (What we're NOT building)
- NOT replacing the NocoBase sync bridge (`hq/polsia_bridge.py`)
- NOT building bidirectional sync — read-heavy initially, with task creation
- NOT modifying Polsia Fork's API — consuming existing endpoints only
- NOT adding Pydantic models to Polsia Fork — types stay in HQ client
- NOT implementing WebSocket/SSE streaming from Polsia Fork
- NOT replacing `polsia_sync()` entirely — create client first, then gradually migrate

---

## Design Summary

Create `PolsiaClient` in `hq/polsia_client.py` — an `httpx.AsyncClient`-based REST API client for Polsia Fork. Unlike the current SQLite-direct approach, this works with any database backend (SQLite, PostgreSQL) that Polsia Fork uses.

Auth is simpler than NocoBase's JWT: static `X-API-Key` header. Fallback is built-in: API-first, SQLite-second in `polsia_sync()`.

Key methods map 1:1 to Polsia Fork endpoints. Response data stays as plain dicts (matching Polsia Fork's inline serialization).

For tests: `AsyncMock`-based mock client via an opt-in conftest fixture.

---

## Tasks

### 1. Create PolsiaClient class with tests

**Depends on**: none

**Files:**
- Create: `hq/polsia_client.py` — the API client class
- Create: `hq/tests/test_polsia_client.py` — 13 tests

**What to do**:

- Step 1: Create `hq/tests/test_polsia_client.py` with 13 tests

  ```python
  """Tests for hq/polsia_client.py."""
  import os
  import pytest
  from unittest.mock import AsyncMock, patch

  # ── GET /agents/monitor ──────────────────────────────────────────

  @pytest.mark.asyncio
  async def test_get_agents_returns_dict():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = {"agents": [{"agent_type": "orchestrator", "status": "idle"}]}
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp):
          result = await client.get_agents()
          assert result == {"agents": [{"agent_type": "orchestrator", "status": "idle"}]}

  # ── GET /tasks ───────────────────────────────────────────────────

  @pytest.mark.asyncio
  async def test_get_tasks_returns_list():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = [{"id": 1, "title": "T1", "status": "pending"}]
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
          result = await client.get_tasks()
          assert result[0]["title"] == "T1"
          assert "params" in mock_get.call_args[1]

  @pytest.mark.asyncio
  async def test_get_tasks_with_filters():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = []
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
          await client.get_tasks(status="pending", agent_type="orchestrator", limit=200)
          params = mock_get.call_args[1].get("params", {})
          assert params.get("status") == "pending"
          assert params.get("agent_type") == "orchestrator"
          assert params.get("limit") == 200

  # ── GET /activity ────────────────────────────────────────────────

  @pytest.mark.asyncio
  async def test_get_activity():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = [{"id": 1, "action": "test", "level": "info"}]
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
          result = await client.get_activity(limit=50)
          assert result[0]["action"] == "test"
          assert mock_get.call_args[1]["params"]["limit"] == 50

  # ── GET /leads ───────────────────────────────────────────────────

  @pytest.mark.asyncio
  async def test_get_leads():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = {"total": 2, "data": [{"id": 1, "name": "Alice"}]}
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
          result = await client.get_leads(status="new")
          assert result["total"] == 2
          assert mock_get.call_args[1]["params"]["status"] == "new"

  # ── GET /orders/external (auth) ──────────────────────────────────

  @pytest.mark.asyncio
  async def test_get_external_orders_sends_api_key():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = {"data": [], "total": 0}
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
          await client.get_external_orders()
          headers = mock_get.call_args[1].get("headers", {})
          assert headers.get("X-API-Key") == "test-key"

  # ── GET /dashboard/summary ───────────────────────────────────────

  @pytest.mark.asyncio
  async def test_get_dashboard_summary():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = {"total_revenue": 1000.0}
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp):
          result = await client.get_dashboard_summary()
          assert result["total_revenue"] == 1000.0

  # ── GET /dashboard/health (auth) ─────────────────────────────────

  @pytest.mark.asyncio
  async def test_get_health_sends_api_key():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = {"overall": "healthy"}
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
          result = await client.get_health()
          assert result["overall"] == "healthy"
          headers = mock_get.call_args[1].get("headers", {})
          assert headers.get("X-API-Key") == "test-key"

  # ── POST /tasks (create) ─────────────────────────────────────────

  @pytest.mark.asyncio
  async def test_create_task():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 201
      mock_resp.json.return_value = {"id": 1, "title": "Test", "agent_type": "orchestrator", "status": "pending"}
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
          result = await client.create_task(title="Test", agent_type="orchestrator")
          assert result["id"] == 1
          data = mock_post.call_args[1].get("data", {})
          assert data["title"] == "Test"
          assert data["agent_type"] == "orchestrator"

  @pytest.mark.asyncio
  async def test_create_task_defaults():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 201
      mock_resp.json.return_value = {"id": 2, "title": "Default", "agent_type": "social", "status": "pending"}
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
          await client.create_task("Default", "social")
          data = mock_post.call_args[1]["data"]
          assert data["priority"] == 3
          assert data["source"] == "api"

  # ── Error handling ───────────────────────────────────────────────

  @pytest.mark.asyncio
  async def test_client_raises_on_http_error():
      from hq.polsia_client import PolsiaClient, PolsiaConnectionError
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 503
      mock_resp.raise_for_status.side_effect = Exception("503 Service Unavailable")
      with patch.object(client._client, "get", return_value=mock_resp):
          with pytest.raises(PolsiaConnectionError):
              await client.get_agents()

  @pytest.mark.asyncio
  async def test_client_handles_empty_response():
      from hq.polsia_client import PolsiaClient
      client = PolsiaClient(base_url="http://test", api_key="test-key")
      mock_resp = AsyncMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = []
      mock_resp.raise_for_status.return_value = None
      with patch.object(client._client, "get", return_value=mock_resp):
          result = await client.get_tasks()
          assert result == []

  # ── Env configuration ────────────────────────────────────────────

  @pytest.mark.asyncio
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
  ```

- Step 2: Run test file to confirm ImportError
  ```
  uv run pytest hq/tests/test_polsia_client.py -v --tb=short
  ```
  Expected: ImportError — "No module named hq.polsia_client"

- Step 3: Create `hq/polsia_client.py` with the PolsiaClient class:

  ```python
  """httpx-based REST API client for the Polsia Fork agent platform.

  Connects to Polsia Fork FastAPI backend at POLSIA_BASE_URL (default http://localhost:8001).
  Uses static X-API-Key auth for protected endpoints.

  Usage:
      client = PolsiaClient()
      agents = await client.get_agents()
      tasks = await client.get_tasks(status="pending")
  """
  import os
  from typing import Any

  import httpx

  DEFAULT_BASE_URL = os.environ.get("POLSIA_BASE_URL", "http://localhost:8001")
  DEFAULT_API_KEY = os.environ.get("POLSIA_API_KEY", "dev-key")


  class PolsiaConnectionError(Exception):
      """Raised when a Polsia Fork API call fails."""


  class PolsiaClient:
      """REST client for Polsia Fork API v1."""

      def __init__(
          self,
          base_url: str | None = None,
          api_key: str | None = None,
          timeout: float = 10.0,
      ):
          self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
          self.api_key = api_key or DEFAULT_API_KEY
          self._timeout = timeout
          self._client: httpx.AsyncClient | None = None

      @property
      def client(self) -> httpx.AsyncClient:
          if self._client is None:
              self._client = httpx.AsyncClient(timeout=self._timeout)
          return self._client

      async def close(self) -> None:
          if self._client:
              await self._client.aclose()
              self._client = None

      async def _request(
          self,
          method: str,
          path: str,
          *,
          needs_auth: bool = False,
          params: dict[str, Any] | None = None,
          data: dict[str, Any] | None = None,
      ) -> Any:
          url = f"{self.base_url}/api/v1{path}"
          headers = {}
          if needs_auth:
              headers["X-API-Key"] = self.api_key
          try:
              r = await self.client.request(
                  method, url, headers=headers, params=params, json=data
              )
              r.raise_for_status()
              return r.json()
          except Exception as exc:
              raise PolsiaConnectionError(
                  f"{method} {url} failed: {exc}"
              ) from exc

      # ── Agents ──────────────────────────────────────────────────

      async def get_agents(self) -> dict[str, Any]:
          """GET /api/v1/agents/monitor — agent status + latest runs."""
          return await self._request("GET", "/agents/monitor")

      # ── Tasks ───────────────────────────────────────────────────

      async def get_tasks(
          self,
          status: str | None = None,
          agent_type: str | None = None,
          limit: int = 100,
      ) -> list[dict[str, Any]]:
          """GET /api/v1/tasks — list tasks with optional filters."""
          params: dict[str, Any] = {"limit": min(limit, 500)}
          if status:
              params["status"] = status
          if agent_type:
              params["agent_type"] = agent_type
          return await self._request("GET", "/tasks", params=params)

      async def get_task(self, task_id: int) -> dict[str, Any]:
          """GET /api/v1/tasks/{task_id} — single task detail."""
          return await self._request("GET", f"/tasks/{task_id}")

      async def create_task(
          self,
          title: str,
          agent_type: str,
          description: str | None = None,
          priority: int = 3,
          source: str = "api",
      ) -> dict[str, Any]:
          """POST /api/v1/tasks — create a new agent task."""
          data: dict[str, Any] = {
              "title": title,
              "agent_type": agent_type,
              "priority": priority,
              "source": source,
          }
          if description is not None:
              data["description"] = description
          return await self._request("POST", "/tasks", data=data)

      # ── Activity ────────────────────────────────────────────────

      async def get_activity(self, limit: int = 50) -> list[dict[str, Any]]:
          """GET /api/v1/activity — recent activity log entries."""
          return await self._request(
              "GET", "/activity", params={"limit": min(limit, 200)}
          )

      # ── Leads ───────────────────────────────────────────────────

      async def get_leads(
          self, status: str | None = None, limit: int = 100
      ) -> dict[str, Any]:
          """GET /api/v1/leads — list leads with optional status filter."""
          params: dict[str, Any] = {"limit": min(limit, 500)}
          if status:
              params["status"] = status
          return await self._request("GET", "/leads", params=params)

      # ── External Orders (auth) ──────────────────────────────────

      async def get_external_orders(
          self, platform: str | None = None, status: str | None = None, limit: int = 50
      ) -> dict[str, Any]:
          """GET /api/v1/orders/external — requires X-API-Key."""
          params: dict[str, Any] = {"limit": min(limit, 200)}
          if platform:
              params["platform"] = platform
          if status:
              params["status"] = status
          return await self._request(
              "GET", "/orders/external", needs_auth=True, params=params
          )

      # ── Dashboard ───────────────────────────────────────────────

      async def get_dashboard_summary(self) -> dict[str, Any]:
          """GET /api/v1/dashboard/summary — aggregate metrics."""
          return await self._request("GET", "/dashboard/summary")

      async def get_health(self) -> dict[str, Any]:
          """GET /api/v1/dashboard/health — requires X-API-Key."""
          return await self._request(
              "GET", "/dashboard/health", needs_auth=True
          )


  def get_polsia_client() -> PolsiaClient:
      """Shortcut: create a PolsiaClient from env defaults."""
      return PolsiaClient()
  ```

- Step 4: Create `PolsiaConnectionError` import in `__init__.py`
  ```bash
  # Check if hq/polsia_client.py symbols need to be importable
  ```

- Step 5: Run tests (should pass now)
  ```bash
  uv run pytest hq/tests/test_polsia_client.py -v --tb=short
  ```
  Expected: 13/13 PASS

- Step 6: Run lint
  ```bash
  uv run ruff check hq/polsia_client.py hq/tests/test_polsia_client.py
  ```
  Expected: No errors

**Must NOT do**:
- Don't add PolsiaClient as a dependency in `hq/__init__.py` — let consumers import directly
- Don't use a shared httpx client across all calls (fresh client per call like nocobase_client.py)
- Don't implement WebSocket/SSE streaming (out of scope)

**References**:
- `hq/nocobase_client.py:1-63` — Existing httpx.AsyncClient pattern with global token cache
- `polsia-fork/app/api/v1/agents.py:21-189` — Agent monitor endpoint
- `polsia-fork/app/api/v1/tasks.py:21-128` — Tasks endpoint with filters
- `polsia-fork/app/config.py:10` — Default API key "dev-key"

**Verify**:
- [ ] Run: `uv run pytest hq/tests/test_polsia_client.py -v --tb=short` → 13 PASS
- [ ] Run: `uv run ruff check hq/polsia_client.py hq/tests/test_polsia_client.py` → No errors

### 2. Integrate PolsiaClient into data.py sync

**Depends on**: 1

**Files:**
- Modify: `hq/domains/data.py:68-226` — Add `polsia_sync_via_api()` function
- Modify: `hq/domains/data.py:68` — Update `polsia_sync()` entry point

**What to do**:

- Step 1: Read `hq/domains/data.py` fully

- Step 2: Add import at top of data.py (after existing imports):
  ```python
  from hq.polsia_client import PolsiaClient, PolsiaConnectionError
  ```

- Step 3: Add `polsia_sync_via_api()` function before existing `polsia_sync()`:
  ```python
  async def polsia_sync_via_api() -> bool:
      """Pull data from Polsia Fork REST API into CACHE.

      Returns True if API was reachable (even partial success).
      Falls back gracefully per endpoint — never raises.
      """
      try:
          client = PolsiaClient()
      except Exception as e:
          print(f"[bridge] PolsiaClient init failed: {e}")
          return False

      # Agents — try API, fallback to empty list (not SQLite)
      try:
          monitor = await client.get_agents()
          agents_raw = monitor.get("agents", [])
          employees = [
              {
                  "name": a.get("agent_type", "").replace("_", " ").title(),
                  "type": "ai",
                  "role": a.get("agent_type", "agent"),
                  "status": a.get("status", "idle"),
                  "agent_type": a.get("agent_type", ""),
              }
              for a in agents_raw
          ]
          # Ensure known agents are present even if API returns partial list
          known = ["orchestrator", "social_media", "customer_support", "competitor_research",
                    "business_planning", "code_generation", "deployment",
                    "finance_agent", "email_outreach", "ads_management"]
          existing = set(a.get("agent_type") for a in agents_raw)
          for ka in known:
              if ka not in existing:
                  employees.append({
                      "name": ka.replace("_", " ").title(),
                      "type": "ai",
                      "role": ka.replace("_", " ").title(),
                      "status": "idle",
                      "agent_type": ka,
                  })
          CACHE["employees"] = employees
      except PolsiaConnectionError:
          print("[bridge] Agents API unavailable, keeping prior CACHE")
          employees = CACHE.get("employees", [])

      # Tasks — try API
      try:
          tasks_data = await client.get_tasks(limit=200)
          CACHE["orders"] = [
              {
                  "title": t.get("title", ""),
                  "status": t.get("status", "pending"),
                  "agent_type": t.get("agent_type", ""),
                  "created_at": t.get("created_at", ""),
                  "source_id": t.get("id"),
                  "platform": "internal",
              }
              for t in tasks_data
          ]
          CACHE["tasks"] = [
              {
                  "id": t.get("id"),
                  "title": t.get("title", ""),
                  "description": t.get("description", ""),
                  "agent_type": t.get("agent_type", ""),
                  "priority": t.get("priority", 3),
                  "status": t.get("status", "pending"),
                  "source": t.get("source", ""),
                  "scheduled_date": t.get("scheduled_date", ""),
                  "result_summary": t.get("result_summary", ""),
                  "error_message": t.get("error_message", ""),
                  "metadata_json": t.get("metadata_json", ""),
                  "created_at": t.get("created_at", ""),
                  "updated_at": t.get("updated_at", ""),
              }
              for t in tasks_data
          ]
      except PolsiaConnectionError:
          print("[bridge] Tasks API unavailable, keeping prior CACHE")

      # Activity log
      activity = []
      try:
          activity = await client.get_activity(limit=200)
          CACHE["activity_log"] = activity
      except PolsiaConnectionError:
          print("[bridge] Activity API unavailable")

      # Leads
      try:
          leads_resp = await client.get_leads(limit=100)
          leads_data = leads_resp.get("data", [])
          CACHE["leads"] = [
              {
                  "id": l.get("id"),
                  "name": l.get("name", ""),
                  "email": l.get("email", ""),
                  "company": l.get("company", ""),
                  "product_interest": l.get("product_interest", ""),
                  "budget_range": l.get("budget_range", ""),
                  "message": l.get("message", ""),
                  "status": l.get("status", "new"),
                  "source_page": l.get("source_page", ""),
                  "created_at": l.get("created_at", ""),
              }
              for l in leads_data
          ]
      except PolsiaConnectionError:
          print("[bridge] Leads API unavailable, keeping prior CACHE")

      # External orders — try API but don't fail if auth fails
      try:
          orders_resp = await client.get_external_orders(limit=100)
          ext_orders_data = orders_resp.get("data", [])
          CACHE["external_orders"] = [
              {
                  "id": o.get("id"),
                  "title": o.get("title", ""),
                  "platform": o.get("platform", ""),
                  "external_id": o.get("external_id", ""),
                  "status": o.get("status", "scanned"),
                  "budget_min": o.get("budget_min"),
                  "budget_max": o.get("budget_max"),
                  "currency": o.get("currency", "USD"),
                  "score": o.get("score"),
                  "score_reason": o.get("score_reason", ""),
                  "assigned_agent": o.get("assigned_agent", ""),
                  "created_at": o.get("created_at", ""),
                  "deployment_plan": o.get("deployment_plan", ""),
                  "deliverables": o.get("deliverables", []),
                  "delivery_notes": o.get("delivery_notes", ""),
              }
              for o in ext_orders_data
          ]
      except PolsiaConnectionError:
          print("[bridge] External orders API unavailable, skipping")

      # Dashboard summary — for MRR/subscriber defaults
      try:
          summary = await client.get_dashboard_summary()
      except PolsiaConnectionError:
          summary = {}

      mrr_val = summary.get("total_revenue", summary.get("mrr", 174))
      subscribers = summary.get("active_subscribers", 4)

      # Business lines
      CACHE["lines"] = [
          {"name": "CrossBridge", "slug": "crossbridge", "status": "active", "monthly_revenue": 0, "customer_count": 0},
          {"name": "CrossBlog", "slug": "crossblog", "status": "active", "monthly_revenue": 0, "customer_count": 0},
          {"name": "CrossDeploy", "slug": "crossdeploy", "status": "active", "monthly_revenue": 0, "customer_count": 0},
          {"name": "Polsia Fork", "slug": "polsia", "status": "active", "monthly_revenue": mrr_val, "customer_count": subscribers},
          {"name": "HiveMind", "slug": "hivemind", "status": "development", "monthly_revenue": 0, "customer_count": 0},
      ]

      CACHE["last_sync"] = datetime.now(UTC).isoformat()

      print(f"[bridge] API sync: {len(CACHE['employees'])} employees, {len(CACHE['orders'])} orders, "
            f"{len(CACHE.get('leads', []))} leads, {len(CACHE.get('activity_log', []))} activity entries")
      return True
  ```

- Step 4: Modify the existing `polsia_sync()` function to try API first:
  ```python
  async def polsia_sync():
      """Pull data from Polsia Fork into CACHE. Tries API first, falls back to SQLite."""
      # Try API first
      if await polsia_sync_via_api():
          # API succeeded — still try NocoBase sync at the end
          await _try_nocobase_sync()
          return
      print("[bridge] API unavailable, falling back to SQLite sync")
  ```
  Then keep the rest of the existing `polsia_sync()` as the fallback.

  Also refactor the NocoBase sync try block at the end of the existing fallback into a helper:

  ```python
  async def _try_nocobase_sync():
      """Attempt to sync to NocoBase (best-effort)."""
      try:
          from hq.polsia_bridge import sync as nocobase_sync
          await nocobase_sync()
          print("[bridge] NocoBase sync completed")
      except Exception as nbe:
          print(f"[bridge] NocoBase sync skipped: {nbe}")
  ```

  And replace the inline try block at end of fallback with `await _try_nocobase_sync()`.

- Step 5: Run existing tests to verify no regression
  ```
  uv run pytest hq/tests/ -v --tb=short -x
  ```
  Expected: All existing tests PASS (API client fails → SQLite fallback)

- Step 6: Run lint
  ```
  uv run ruff check hq/domains/data.py
  ```
  Expected: No errors

**Must NOT do**:
- Don't remove the existing SQLite sync code — it's the fallback
- Don't change the CACHE dict structure
- Don't add new dependencies to `pyproject.toml` (httpx is already there)
- Don't modify `periodic_sync()` — it calls `polsia_sync()` which now tries API first

**References**:
- `hq/domains/data.py:68-226` — Existing `polsia_sync()` SQLite-based implementation
- `hq/domains/data.py:22-43` — CACHE dict structure
- `hq/domains/data.py:237-241` — `periodic_sync()` background loop

**Verify**:
- [ ] Run: `uv run pytest hq/tests/test_polsia_client.py -v --tb=short` → Still 13 PASS
- [ ] Run: `uv run pytest hq/tests/ -v --tb=short -x` → All existing tests PASS (API unreachable → SQLite fallback)
- [ ] Run: `uv run ruff check hq/domains/data.py` → No errors

### 3. Add PolsiaClient mock fixture for tests

**Depends on**: 2

**Files:**
- Modify: `hq/tests/conftest.py` — Add opt-in mock fixture
- Modify: `hq/tests/test_polsia_client.py` — Add 1 extra test

**What to do**:

- Step 1: Read `hq/tests/conftest.py` fully

- Step 2: Add opt-in mock fixture after the `reset_cache` fixture (before file end):
  ```python
  @pytest.fixture
  def mock_polsia_client():
      """Opt-in fixture providing a mock PolsiaClient with realistic test data.

      Usage:
          async def test_foo(mock_polsia_client):
              from hq.domains.data import polsia_sync_via_api
              result = await polsia_sync_via_api()
              assert result is True
      """
      from unittest.mock import AsyncMock, patch

      mock = AsyncMock()
      mock.get_agents.return_value = {
          "agents": [
              {"agent_type": "orchestrator", "status": "idle"},
              {"agent_type": "social_media", "status": "running"},
              {"agent_type": "finance_agent", "status": "error"},
          ]
      }
      mock.get_tasks.return_value = [
          {"id": 1, "title": "Weekly report", "agent_type": "orchestrator", "status": "completed",
           "priority": 2, "source": "schedule", "created_at": "2026-06-01T00:00:00"},
          {"id": 2, "title": "Scrape competitors", "agent_type": "competitor_research", "status": "in_progress",
           "priority": 3, "source": "api", "created_at": "2026-06-05T00:00:00"},
      ]
      mock.get_activity.return_value = [
          {"id": 1, "agent_type": "orchestrator", "action": "completed task", "summary": "Weekly report done",
           "level": "info", "created_at": "2026-06-05T10:00:00"},
      ]
      mock.get_leads.return_value = {
          "total": 2,
          "data": [
              {"id": 1, "name": "Alice", "email": "alice@test.com", "company": "Acme",
               "product_interest": "CrossBridge", "status": "new", "created_at": "2026-06-01T00:00:00"},
              {"id": 2, "name": "Bob", "email": "bob@test.com", "company": "BobCo",
               "product_interest": "CrossDeploy", "status": "contacted", "created_at": "2026-06-03T00:00:00"},
          ]
      }
      mock.get_external_orders.return_value = {
          "data": [
              {"id": 1, "title": "Build landing page", "platform": "Upwork", "status": "scanned",
               "budget_min": 500, "budget_max": 1000, "currency": "USD", "score": 8},
          ],
          "total": 1,
      }
      mock.get_dashboard_summary.return_value = {
          "total_revenue": 1000.0,
          "active_subscribers": 10,
          "mrr": 174.0,
      }
      mock.get_health.return_value = {
          "overall": "healthy",
          "checks": {"agents": {"status": "healthy", "running": 5, "total": 10}},
      }

      with patch("hq.domains.data.PolsiaClient", return_value=mock):
          yield mock
  ```

- Step 3: Add integration test to `hq/tests/test_polsia_client.py`:
  ```python
  @pytest.mark.asyncio
  async def test_polsia_sync_via_api_with_mock(mock_polsia_client):
      """Verify that polsia_sync_via_api works with the mock client."""
      from hq.domains.data import polsia_sync_via_api, CACHE
      # Reset CACHE to clean state
      CACHE.clear()
      CACHE.update({k: [] for k in ["employees", "lines", "orders", "leads",
                                      "external_orders", "expenses", "revenue_history",
                                      "tasks", "activity_log"]})
      CACHE["last_sync"] = None

      result = await polsia_sync_via_api()
      assert result is True
      assert len(CACHE["employees"]) >= 3
      assert len(CACHE["tasks"]) == 2
      assert CACHE["last_sync"] is not None
  ```

- Step 4: Run tests
  ```
  uv run pytest hq/tests/test_polsia_client.py -v --tb=short
  ```
  Expected: 14/14 passed (13 original + 1 new)

- Step 5: Run full test suite to confirm no regression
  ```
  uv run pytest hq/tests/ -v --tb=short -x
  ```
  Expected: All existing tests PASS

- Step 6: Run lint
  ```
  uv run ruff check hq/tests/
  ```
  Expected: No errors

**Must NOT do**:
- Don't make the mock fixture autouse — must be opt-in
- Don't modify `reset_cache` autouse fixture
- Don't remove existing fixture patterns

**References**:
- `hq/tests/conftest.py:12-30` — Existing fixture patterns (app, client, auth_headers, etc.)
- `hq/tests/conftest.py:49-127` — Existing `reset_cache` autouse fixture data structure
- `hq/domains/data.py:22-43` — CACHE dict keys

**Verify**:
- [ ] Run: `uv run pytest hq/tests/test_polsia_client.py -v --tb=short` → 14 PASS
- [ ] Run: `uv run pytest hq/tests/ -v --tb=short -x` → All PASS (no regression)
- [ ] Run: `uv run ruff check hq/tests/` → No errors

### 4. Final verification

**Depends on**: 3

**Files:**
- All touched files

**What to do**:

- Step 1: Run full test suite (fast mode, no coverage)
  ```
  uv run pytest -n auto -q --tb=short
  ```
  Expected: All tests PASS, no regressions

- Step 2: Run ruff check on all touched files
  ```
  uv run ruff check hq/polsia_client.py hq/tests/test_polsia_client.py hq/domains/data.py hq/tests/conftest.py
  ```
  Expected: No errors

- Step 3: Run typecheck
  ```
  uv run mypy hq/polsia_client.py --ignore-missing-imports
  ```
  Expected: No type errors (or acceptable type annotation issues)

- Step 4: Save learnings via agentmemory

**Must NOT do**:
- Don't run integration tests that require external services (Docker, Polsia Fork)
- Don't deploy to production
- Don't modify files outside the scope of this feature

**Verify**:
- [ ] Run: `uv run pytest -n auto -q --tb=short` → All PASS
- [ ] Run: `uv run ruff check hq/polsia_client.py hq/tests/test_polsia_client.py hq/domains/data.py hq/tests/conftest.py` → No errors
