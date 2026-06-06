# Task: 02-integrate-polsiaclient-into-datapy-sync

## Feature: polsia-api-client

## Dependencies

- **1. create-polsiaclient-class-with-tests** (01-create-polsiaclient-class-with-tests)

## Plan Section

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
