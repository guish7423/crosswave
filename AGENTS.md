# AGENTS.md — CrossWave

## What this project is

CrossWave is an AI Globalization Stack — a FastAPI app (port 9999) with mounted sub-apps for HQ admin, BFFs, and shared services, all sitting in front of a Polsia Fork agent engine. Serves as the company's AI OS / neural center.

**Single FastAPI app** (`app/main.py:create_app()`) with HQ mounted at `/hq`, product BFFs at `/bridge`, `/blog`, `/deploy`. All behind one port.

## Product line

| Product | Role |
|---------|------|
| CrossBridge | AI translation SaaS (live on Railway) |
| CrossBlog | SEO blog engine (ai-blog-engine/ submodule) |
| CrossDeploy | Deployment service (products/deploy/) |
| Polsia Fork | 10-agent backend platform (polsia-fork/ submodule) |

## Key commands

```bash
uv sync --all-extras
uv run pytest tests/ hq/tests/ -q
uv run ruff check app/ hq/ scripts/
uv run uvicorn app.main:app --reload          # unified app on :9999
docker compose up -d                          # full stack
```

## Architecture — AI OS 4 Layers

### Layer 1: Data (Phase A)
- **NocoBase** (PostgreSQL) is the sole data store — CACHE was removed in Step 5.
- `hq/polsia_bridge.py` syncs Polsia Fork data to NocoBase collections.
- `hq/nocobase_client.py` reads from NocoBase for all HQ endpoints.

### Layer 2: Plugin Registry (Phase B)
- `hq/plugin_registry/` — `CrossWavePlugin` base class, `PluginRegistry` singleton.
- 5 products auto-register on startup: CrossBridge, CrossBlog, CrossDeploy, Polsia, NocoBase.
- 60s health-check loop. REST API at `/api/hq/plugins`.

### Layer 3: Event Bus (Phase C)
- `hq/event_bus/` — `EventBus` singleton, pub/sub with SSE stream.
- Plugin lifecycle events auto-published. SSE at `/api/hq/events`.

### Layer 4: MCP Standard (Phase D)
- `hq/mcp_server.py` — 10 MCP tools on SSE transport at `/api/hq/mcp/`.
- Tools: plugin CRUD, event publish, system status, NocoBase queries.

### Workflow Engine
- `hq/workflows/` — Trigger→condition→action patterns. Sync-complete→refresh-health built-in.
- REST API at `/api/hq/workflows`.

### Shared Auth
- `app/core/auth/` — JWT (HS256) with `create_token`/`verify_token`, `require_jwt`/`optional_jwt` Dependencies.
- Login at `/api/auth/login`, verify at `/api/auth/verify`.

### Monorepo
- `packages/crosswave-core/`, `packages/crosswave-auth/` with editable installs.

## Routes

| Prefix | App | Auth |
|--------|-----|------|
| `/` | Main website (page_routes, proxy_routes, blog_proxy, mcp_routes) | None |
| `/hq/` | HQ admin (dashboard, employees, orders, plugins, events, workflows) | Session cookie or X-HQ-Token |
| `/api/auth/` | Shared JWT auth | None (login) / Bearer (verify) |
| `/api/gateway/` | Health aggregator | None |
| `/bridge/` | CrossBridge BFF | JWT |
| `/blog/` | CrossBlog BFF | JWT |
| `/deploy/` | CrossDeploy BFF | JWT |

## Auth
- HQ: `require_session()` checks cookie → falls back to `require_token()` (X-HQ-Token header).
- BFFs: `require_jwt()` expects `Authorization: Bearer <token>`.
- Token from `.env` (`HQ_AUTH_TOKEN`) or auto-generated (prints warning).

## Testing

- Dependencies: `uv sync --all-extras` (includes pytest, etc.).
- `reset_cache` fixture **removed** in Step 5 — NocoBase is the sole data source.
- NB_DISABLED=true in tests → NocoBase unavailable → routes return empty data.
- Core tests: `tests/`, HQ tests: `hq/tests/`.
- Coverage: `fail_under = 60`, source: `["app", "hq", "packages"]`.

## Files/dirs

| Path | What |
|------|------|
| `app/main.py` | Application factory, mounts HQ+BFFs |
| `app/config.py` | Pydantic settings |
| `hq/server.py` | HQ bridge sub-app factory |
| `hq/domains/` | HQ routes (api_routes, page_routes, monitor_routes, etc.) |
| `hq/plugin_registry/` | Plugin system (contract + registry + routes) |
| `hq/event_bus/` | Event bus (bus + models + routes) |
| `hq/workflows/` | Workflow engine |
| `hq/mcp_server.py` | MCP tools |
| `packages/` | Monorepo shared packages |
| `docs/` | Design docs (auth-design, plugin-sdk, ARCHITECTURE) |
| `.github/workflows/ci.yml` | GitHub Actions (lint→test→build) |
