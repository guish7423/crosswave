# Task: 04-final-verification

## Feature: polsia-api-client

## Dependencies

- **3. add-polsiaclient-mock-fixture-for-tests** (03-add-polsiaclient-mock-fixture-for-tests)

## Plan Section

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
- 03-add-polsiaclient-mock-fixture-for-tests: 添加 opt-in `mock_polsia_client` fixture 到 hq/tests/conftest.py（patch PolsiaClient 路径），添加集成测试 `test_polsia_sync_via_api_with_mock` 到 test_polsia_client.py。验证: 14/14 PASSS, 131 PASS/2 SKIP HQ 全套, ruff 0 新错。
