# Task: 03-add-polsiaclient-mock-fixture-for-tests

## Feature: polsia-api-client

## Dependencies

- **2. integrate-polsiaclient-into-datapy-sync** (02-integrate-polsiaclient-into-datapy-sync)

## Plan Section

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

## Task Type

modification

## Context

## learnings

# Polsia Fork API Client - Research Learnings

## Polsia Fork API Facts
- 29 routers at `/api/v1/`, most without X-API-Key auth
- All responses are inline dicts (no Pydantic response models)
- Only `health.py` and `orders_external.py` require `X-API-Key`
- Default API key: `"dev-key"` (from Settings)
- Configurable via env: `API_KEY`, `LLM_API_BASE_URL`

## Key Endpoints Needed
| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/agents/monitor` | Agent statuses |
| `GET /api/v1/agents/runs` | Run history |
| `GET /api/v1/tasks` | Task list (with status/agent_type filters) |
| `POST /api/v1/tasks` | Create task |
| `GET /api/v1/dashboard/summary` | Dashboard aggregation |
| `GET /api/v1/activity` | Activity log |
| `GET /api/v1/leads` | Leads list |
| `GET /api/v1/orders/external` | External orders (requires API key) |
| `GET /api/v1/dashboard/health` | Health check (requires API key) |

## Current HQ Integration (to replace)
- `hq/domains/data.py:68-226` (`polsia_sync()`) reads Polsia Fork SQLite directly via aiosqlite
- 8 SQL queries against tables: tasks, expense_records, revenue_snapshots, external_orders, leads, proposals, activity_log
- CACHE dict populated from raw SQL results

## Existing Client Patterns
- `hq/nocobase_client.py` - httpx.AsyncClient with global token cache (55min TTL)
- `hq/polsia_bridge.py` - NocoBase write client, separate global TOKEN
- Tests use CACHE manipulation + temp SQLite files

## Key Difference from NocoBase
- NocoBase uses Bearer JWT tokens
- Polsia Fork uses X-API-Key header
- Simpler: static API key, no token refresh needed


## Completed Tasks

- 01-create-polsiaclient-class-with-tests: Created hq/polsia_client.py (PolsiaClient class with 9 endpoints) and hq/tests/test_polsia_client.py (13 tests). Implementation: httpx-based REST client for Polsia Fork API v1 with X-API-Key auth, env-configurable defaults, and exception wrapping. Tests use MagicMock for sync httpx.Response behavior, covering all endpoints, auth headers, filters, error handling, empty responses, and env configuration. 13/13 tests passing, ruff clean.
- 02-integrate-polsiaclient-into-datapy-sync: 集成 PolsiaClient 到 hq/domains/data.py: (1) 添加 `polsia_sync_via_api()` — 通过 REST API 填充 CACHE (PolsiaClient 9个端点，按 endpoint 独立 try/except 优雅降级); (2) 修改 `polsia_sync()` — API 优先，失败后回退到原有的 SQLite 同步; (3) 提取 `_try_nocobase_sync()` 辅助函数; (4) 修复 E741 (l→lead)。验证: 130 PASS/2 SKIP, ruff 零错误。
