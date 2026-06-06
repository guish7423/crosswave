# PROJECT_STATUS.md — CrossWave v0.8.0 (Polsia API Client)

Last updated: 2026-06-06

## Current Phase: Feature Complete ✅

### Feature: Polsia Fork API Client (v0.8.0)

| Task | Description | Status |
|------|-------------|--------|
| 1 | PolsiaClient class (9 API methods) + 13 unit tests | ✅ |
| 2 | Integrate into data.py sync (API-first with SQLite fallback) | ✅ |
| 3 | Mock fixture + integration test | ✅ |
| 4 | Final verification (lint + test + typecheck) | ✅ |
| **Feature** | **Polsia Fork API Client** | **✅ COMPLETE** |

### Key Deliverables

| File | What |
|------|------|
| `hq/polsia_client.py` | PolsiaClient class — 9 API methods via httpx.AsyncClient, X-API-Key auth, env config |
| `hq/domains/data.py` | `polsia_sync_via_api()` — API-first sync; `_try_nocobase_sync()` helper; graceful SQLite fallback |
| `hq/tests/test_polsia_client.py` | 14 tests (13 unit + 1 integration with mock) |
| `hq/tests/conftest.py` | `mock_polsia_client` opt-in fixture (7 endpoints) |

### Architecture (v0.8.0)

```
hq/
├── server.py                    # 11 domain module factory
├── domains/
│   ├── data.py                  # CACHE + Polsia sync (API-first, SQLite fallback)
│   ├── middleware.py            # Auth + lifespan
│   └── ... (11 domain modules)
├── polsia_client.py             # ← Polsia Fork REST API client (NEW)
├── nocobase_client.py           # NocoBase REST client
├── polsia_bridge.py             # Sync Polsia→NocoBase
├── tests/ (85+ tests)
└── ...
```

Sync architecture: `polsia_sync()` → tries `polsia_sync_via_api()` (REST) → on fail falls back to direct SQLite read. NocoBase bridge triggered after successful API sync.

### Test Matrix

| Suite | Count | Status |
|-------|-------|--------|
| Core (tests/) | 85 | ✅ |
| HQ API + Pages | 55 | ✅ |
| Polsia Client | 14 | **✅ NEW** |
| Polsia Bridge | 10 | ✅ |
| Weekly Report | 6 | ✅ |
| Scheduler | 5 | ✅ |
| Auth | 7 | ✅ |
| Stripe | 2 | ✅ |
| Model Router | 23 + 2 skip | ✅ |
| Other HQ | 9 | ✅ |
| **Total** | **216** | **✅ (2 skip)** |

### 产品线状态

| 产品 | 部署 | 支付 | 备注 |
|------|------|------|------|
| CrossBridge | ✅ Railway | 🔲 | Live |
| CrossBlog | railway.toml 就绪 | 🔲 | Docker 已验证 |
| CrossDeploy | ❌ | 🔲 | v0.1.0 |
| CrossWave HQ | ❌ | N/A | 本地运行 |
| Polsia Fork | ❌ | N/A | submodule |

### Next Steps (User Action Required)
1. Configure `.env` secrets (Stripe, Sentry, Admin password)
2. Deploy CrossBlog: `railway up` or GitHub integration
3. Deploy Polsia Fork to Railway
4. Buy domain + run `scripts/setup-ssl.sh`
5. `docker compose up -d` on VPS
