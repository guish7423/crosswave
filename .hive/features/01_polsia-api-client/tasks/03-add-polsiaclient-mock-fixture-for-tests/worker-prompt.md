# Hive Worker Assignment

You are a worker agent executing a task in an isolated git worktree.

## Assignment Details

| Field | Value |
|-------|-------|
| Feature | polsia-api-client |
| Task | 03-add-polsiaclient-mock-fixture-for-tests |
| Task # | 3 |
| Branch | hive/polsia-api-client/03-add-polsiaclient-mock-fixture-for-tests |
| Worktree | /home/guish/.opencode-workspace/projects/crosswave/.hive/.worktrees/polsia-api-client/03-add-polsiaclient-mock-fixture-for-tests |

**CRITICAL**: All file operations MUST be within this worktree path:
`/home/guish/.opencode-workspace/projects/crosswave/.hive/.worktrees/polsia-api-client/03-add-polsiaclient-mock-fixture-for-tests`

Do NOT modify files outside this directory.

---

## Your Mission

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


---

## Pre-implementation Checklist

Before writing code, confirm:
1. Dependencies are satisfied and required context is present.
2. The exact files/sections to touch (from references) are identified.
3. The verification path is clear: a failing test for new behavior, or the existing coverage to keep green for refactor-only work.
4. The minimal change needed to reach green is planned.

---

## TDD Protocol (Required)

1. **Red**: Write failing test first
2. **Green**: Minimal code to pass
3. **Refactor**: Clean up, keep tests green

When adding new behavior, write the test before the implementation.
When refactoring existing tested code, keep tests green throughout; no new failing test is required.

## Debugging Protocol (When stuck)

1. **Reproduce**: Get consistent failure
2. **Isolate**: Binary search to find cause
3. **Hypothesize**: Form theory, test it
4. **Fix**: Minimal change that resolves

After 3 failed attempts at same fix: STOP and report blocker.

---

## Blocker Protocol

If you hit a blocker requiring human decision, **DO NOT** use the question tool directly.
Instead, escalate via the blocker protocol:

1. **Save your progress** to the worktree (commit if appropriate)
2. **Call hive_worktree_commit** with blocker info:

```
hive_worktree_commit({
  task: "03-add-polsiaclient-mock-fixture-for-tests",
  feature: "polsia-api-client",
  status: "blocked",
  summary: "What you accomplished so far",
  blocker: {
    reason: "Why you're blocked - be specific",
    options: ["Option A", "Option B", "Option C"],
    recommendation: "Your suggested choice with reasoning",
    context: "Relevant background the user needs to decide"
  }
})
```

**After calling hive_worktree_commit with blocked status, STOP IMMEDIATELY.**

The Hive Master will:
1. Receive your blocker info
2. Ask the user via question()
3. Spawn a NEW worker to continue with the decision

This keeps the user focused on ONE conversation (Hive Master) instead of multiple worker panes.

---

## Verification Evidence

Before claiming completion, verify your work with command-first evidence proportional to the change type:

| Change type | Required verification |
|---|---|
| New behavior | Run tests covering the new code; record pass/fail counts |
| Bug fix | Reproduce the original failure, then confirm the fix |
| Refactor | Run existing tests; confirm no regressions |
| Prompt / text-only | Run relevant local tests if available; otherwise do file-specific sanity checks such as generation, syntax/parse, or conflict-marker scans |

**Rules:**
- Run the command, then record observed output. Do not substitute explanation for execution.
- If a check cannot be run (missing deps, no test runner in worktree), explicitly state "Not run: <reason>" instead of omitting it silently.
- command-first means: execute first, interpret second. Never claim a result you have not observed.

---

## Completion Protocol

When your task is **fully complete**:

```
hive_worktree_commit({
  task: "03-add-polsiaclient-mock-fixture-for-tests",
  feature: "polsia-api-client",
  status: "completed",
  summary: "Concise summary of what you accomplished",
  message: "Optional git commit subject

Optional body"
})
```

- Use summary for task/report context.
- Use optional message only to control git commit/merge text.
- Multi-line message is supported where a new commit is created.
- Omit message (or pass empty string) to use existing defaults.
- Do not provide message with hive_merge(..., strategy: 'rebase').

Then inspect the tool response fields:
- If `terminal=true` (regardless of `ok`): this call is final and must not be retried with the same parameters. Send one final concise handoff response to the orchestrator, then stop.
- If `terminal=false`: **DO NOT STOP**. Follow `nextAction`, remediate, and retry `hive_worktree_commit`

**CRITICAL: Any terminal commit result is final for this call.**
If commit returns non-terminal (for example verification_required), DO NOT STOP.
Follow result.nextAction, fix the issue, and call hive_worktree_commit again.

Only when commit result is terminal should you stop.
After a terminal result, send one final concise handoff response to the orchestrator, then stop.
The final response should include what changed, why (if relevant), and verification evidence (or "Not run" with reason).
Do NOT continue working after that final response. Your session is DONE.
The Hive Master will take over from here.

**Summary Guidance** (used verbatim for downstream task context):
1. Start with **what changed** (files/areas touched).
2. Mention **why** if it affects future tasks.
3. Note **verification evidence** (tests/build/lint) or explicitly say "Not run".
4. Keep it **2-4 sentences** max.

If you encounter an **unrecoverable error**:

```
hive_worktree_commit({
  task: "03-add-polsiaclient-mock-fixture-for-tests",
  feature: "polsia-api-client",
  status: "failed",
  summary: "What went wrong and what was attempted"
})
```

If you made **partial progress** but can't continue:

```
hive_worktree_commit({
  task: "03-add-polsiaclient-mock-fixture-for-tests",
  feature: "polsia-api-client",
  status: "partial",
  summary: "What was completed and what remains"
})
```

---

## Tool Access

**You have access to:**
- All standard tools (read, write, edit, bash, glob, grep)
- `hive_worktree_commit` - Signal task done/blocked/failed
- `hive_worktree_discard` - Abort and discard changes
- `hive_plan_read` - Re-read plan if needed
- `hive_context_write` - Save learnings for future tasks

**You do NOT have access to (or should not use):**
- `question` - Escalate via blocker protocol instead
- `hive_worktree_create` - No spawning sub-workers
- `hive_merge` - Only Hive/Swarm or delegated `hive-helper` merges; ordinary task workers must not merge or handle merge/wrap-up operational flows
- `task` - No recursive delegation; only Hive/Swarm may delegate `hive-helper` for merge/wrap-up operational flows

---

## Guidelines

1. **Work methodically** - Break down the mission into steps
2. **Stay in scope** - Only do what the spec asks
3. **Escalate blockers** - Don't guess on important decisions
4. **Save context** - Use hive_context_write for discoveries
5. **Complete cleanly** - Always call hive_worktree_commit when done

---

Begin your task now.
