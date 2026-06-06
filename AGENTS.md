# AGENTS.md — CrossWave

## What this project is

CrossWave is an AI Globalization Stack — a FastAPI BFF/website layer (port 9999) + HQ admin bridge (port 13001) that sits in front of a Polsia Fork agent engine. All products serve Chinese entrepreneurs expanding globally.

**Two FastAPI apps, one Docker container.** Both run via `docker-start.sh` as separate uvicorn processes inside the same container (ports 9999 and 13001).

## Product line (at a glance)

| Product | Role |
|---------|------|
| CrossBridge | AI translation SaaS (live on Railway) |
| CrossBlog | SEO blog engine (ai-blog-engine/ submodule) |
| CrossDeploy | Deployment service (products/deploy/) |
| Polsia Fork | 10-agent backend platform (polsia-fork/ submodule) |

## Key commands

```bash
# Install dependencies (uv — not pip)
uv sync --frozen --no-dev

# Lint
uv run ruff check app/ hq/ scripts/

# Type check
uv run mypy app/ hq/

# Run all tests (parallel)
uv run pytest -n auto -q --cov=app --cov=hq --cov-report=term-missing --tb=short

# Run only core tests
uv run pytest tests/ -q

# Run only HQ tests
uv run pytest hq/tests/ -q

# Run single test file
uv run pytest tests/test_routes.py -q -x

# Local dev (main app only)
uv run uvicorn app.main:app --reload

# Local dev (HQ bridge only)
uv run uvicorn hq.server:app --host 0.0.0.0 --port 13001 --reload

# Full Docker stack
docker compose up -d

# Docker with hot-reload mounts
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

## Architecture

### Main app (`app/`)
- FastAPI application factory in `app/main.py`
- Routes split into domain modules in `app/domains/`: page_routes, proxy_routes, blog_proxy, mcp_routes
- Polsia client (`app/services/polsia_client.py`) proxies requests to the Polsia Fork backend
- MCP protocol (JSON-RPC 2.0 over SSE) at `/mcp/sse` and `/mcp/message`
- Settings via pydantic-settings (`app/config.py`) — reads `.env` file, fail-fast on validation

### HQ bridge (`hq/`)
- Separate FastAPI app in `hq/server.py` with 11 domain modules
- **Auth**: All HQ routes (except `/health`, `/login`, `/portal/*`, `/static`, `/api/hq/auth`, `/api/hq/models`) require `X-HQ-Token` header. Session cookie fallback via `itsdangerous`.
- **Shared state**: `hq/domains/data.py` contains a `CACHE` dict — this is the HQ's "database" (not persisted). Syncs from Polsia Fork's SQLite DB every 30 minutes.
- Auth token auto-generated if `HQ_AUTH_TOKEN` env var is not set (prints to stdout on first boot).

### Products (`products/`)
- CrossBridge: standalone Flask app, live on Railway
- CrossBlog: `ai-blog-engine/` submodule, FastAPI, Docker
- CrossDeploy: `products/deploy/`, Docker

## Testing quirks

- **`tests/test_routes.py`** uses a **module-level** `TestClient(app)` — not a fixture. All other test files use fixtures.
- **HQ tests** (`hq/tests/`) use `conftest.py` which sets `POLSIA_DB=/tmp/crosswave-test-polsia.db` and `HQ_AUTH_TOKEN=test-hq-token`. Fixtures: `app`, `client`, `auth_headers`, `auth_client`, `reset_cache`.
- `reset_cache` autouse fixture populates `CACHE` with test data before each test and clears after.
- `pytest.ini` has `asyncio_mode = auto`, testpaths = `tests hq/tests`, addopts = `--tb=short -q`.
- Coverage minimum: 60% (`fail_under = 60`).
- CI runs `pytest -n auto` (parallel) with coverage. CI does NOT install dev dependencies (`--no-dev`).

## Framework/toolchain quirks

- **Package manager**: `uv` (not pip). Lockfile: `uv.lock`. Dependencies split: `pyproject.toml` has base + dev extras, `requirements.txt` has a subset for Docker (minimal).
- **Python**: 3.11+ required.
- **Linter**: ruff, line-length=100, all rules except E501 (`ignore = ["E501"]`).
- **Type checker**: mypy, non-strict (`strict = false`, `ignore_missing_imports = true`).
- **Docker base**: `python:3.12-slim`, non-root user `crosswave`, multi-stage in docker-start.sh.
- **LLMs**: Only DeepSeek-compatible API endpoints (httpx async). Use `POLSIA_MOCK=true` or `LLM_PROVIDER_MOCK=true` to stub LLM calls.

## Files/dirs an agent must know

| Path | What |
|------|------|
| `pyproject.toml` | Project metadata, deps, lint, test, coverage config |
| `app/main.py` | Application factory, route registration |
| `app/config.py` | Pydantic settings (reads `.env`) |
| `hq/server.py` | HQ bridge factory |
| `hq/domains/data.py` | `CACHE` dict, Polsia sync, service monitor |
| `hq/domains/middleware.py` | `require_token` auth dependency |
| `docker-start.sh` | Boots both apps in one container |
| `docker-compose.yml` | Full production stack (10+ services) |
| `crossblog.railway.toml` | CrossBlog Railway deploy config (port 8000) |
| `railway.toml` | Main app Railway deploy config (port 9999) |
| `CROSSWAVE_OPS.md` | Operations manual (deploy, maintain, recover) |
| `COMPANY_STRATEGY.md` | Product strategy, pricing, positioning |
| `polsia-fork/CLAUDE.md` | Agent platform instructions |

## Known issues (preserve)

- CrossBridge DB path hardcodes `../ai-content-bridge/content_bridge.db` — this is a sibling directory, not a submodule.
- `hq/domains/data.py` generates a random `AUTH_TOKEN` if `HQ_AUTH_TOKEN` is unset (warning printed). In production, always set this explicitly.
