# CrossWave Multi-Product Architecture — Architecture Decision Record

> Version: 1.1 | Date: 2026-06-05
> Based on research of SoundCloud BFF, Nx monorepo, Veld Systems, Ginilab, and 10+ production SaaS architectures.
> Status: v0.7.0 — 198 tests passing, SSE real-time, NocoBase PostgreSQL live

---

## 1. Current State Assessment

CrossWave has 6 product surfaces, each at a different stage:

| Product | Stage | Deployment | Current Backend |
|---------|-------|-----------|-----------------|
| 🌉 **CrossBridge** | ✅ Live on Railway | Railway | Flask (monolith) |
| 📝 **CrossBlog** | ✅ Code ready | Not deployed | FastAPI (monolith) |
| 🏢 **Polsia Fork** | ✅ Complete | Not deployed | FastAPI + Celery |
| 📊 **CrossWave HQ** | ✅ v0.7.0 | Not deployed | FastAPI + HTMX (11 domain modules, SSE, NocoBase) |
| 🚀 **CrossDeploy** | ✅ Service ready | Static pages | Static (part of HQ) |
| 🐝 **HiveMind** | ✅ Complete | Tauri v2 desktop | Rust + React |

**Key insight**: All products share the same customer org. A user of CrossBridge will also use CrossBlog, CrossDeploy, and HiveMind. **Shared identity and data isolation are critical from day one.**

---

## 2. Architecture Decision: Per-Product BFFs

### Decision

```
                        ┌──────────────────────┐
                        │   Cloudflare CDN       │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │   API Gateway          │
                        │   (Auth validation,    │
                        │    Rate limiting,       │
                        │    Routing)             │
                        └──────┬──────┬─────────┘
                               │      │
              ┌────────────────┼──────┼───────────────────┐
              │                │      │                   │
     ┌────────▼───┐   ┌───────▼──┐ ┌─▼────────┐  ┌──────▼──────┐
     │CrossBridge  │   │CrossBlog │ │CrossDeploy│  │  HiveMind   │
     │   BFF       │   │   BFF    │ │   BFF     │  │    BFF      │
     └──────┬──────┘   └────┬─────┘ └─────┬─────┘  └──────┬──────┘
            │               │             │               │
            └───────────────┼─────────────┼───────────────┘
                            │             │
                   ┌────────▼─────────────▼──────────┐
                   │      Shared Domain Services      │
                   │   (Auth, Users, Payments,        │
                   │    Notifications, Feature Flags) │
                   └────────────────┬─────────────────┘
                                    │
                   ┌────────────────▼─────────────────┐
                   │     Data Layer (PostgreSQL)       │
                   │  common.* │ crossbridge.* │ ...   │
                   └──────────────────────────────────┘
```

### Rationale

| Decision | Rationale | Source |
|----------|-----------|--------|
| One BFF per product | Each product has different data needs, latency profiles, evolution pace | SoundCloud production experience |
| BFFs are thin (aggregation only) | No business logic in BFFs — prevents 3x bug syndrome | Veld Systems, Ginilab |
| Business logic in shared domain services | Single source of truth, testable independently | Domain-driven design |
| BFFs owned by product teams | Avoid recreating the shared-API bottleneck | SoundCloud post-mortem |

### Rules

1. **Each BFF is owned by the product team** that ships the client
2. **BFFs contain NO business logic** — only aggregation, reshaping, auth validation
3. **Business logic lives in shared domain services**
4. **Shared BFF framework library** — extract only when 3+ BFFs need it (rule of three)

---

## 3. Shared Identity & Authentication

### Decision: Single centralized auth service

Every CrossWave product shares one auth service:

```
JWT Claims: { userId, orgId, appId, entitlements: [...] }
```

| Claim | Purpose |
|-------|---------|
| `orgId` | Cross-product organization identity |
| `appId` | Current product (`crossbridge`, `crossblog`, `crossdeploy`, etc.) |
| `entitlements` | What products/features the org has access to |

### Auth Service Responsibility

- **User registration/login** (email + password, OAuth)
- **Organization management** (members, roles)
- **Product entitlements** (which products the org can use)
- **JWT issuance and validation** (HS256/RS256)
- **API key management** (for programmatic access)

### Recommendation: Supabase Auth (or Clerk)

Both support:
- Railway deployment (CrossBridge is already on Railway)
- Custom JWT claims
- Organization/team management
- OAuth providers (Google, GitHub)

### Anti-patterns to avoid

- ❌ Per-product auth services — users with multiple products become separate accounts
- ❌ Hardcoded entitlements — must be database-driven, not in code
- ❌ Stripe-coupled auth — entitlements should survive payment provider changes

---

## 4. Data Architecture

### Decision: Shared-schema with app_id isolation

```
common/                      # Cross-product shared data
  users
  organizations
  memberships
  product_entitlements

crossbridge/                 # CrossBridge specific
  translation_projects
  translation_jobs
  ...

crossblog/                   # CrossBlog specific
  posts
  categories
  ...

crossdeploy/                 # CrossDeploy specific
  deployments
  services
  ...

hivemind/                    # HiveMind specific
  sync_entries
  ...

billing/                     # Cross-product billing
  subscriptions
  invoices
  usage_records
```

### Data Rules

1. Every table includes `org_id` (UUID, not null, indexed)
2. Every cross-product query includes `WHERE org_id = ?`
3. Indexes include `org_id` as leading column
4. Unique constraints include `org_id`
5. Product schemas reference `common.*` but **never** reference each other
6. Use **PostgreSQL schemas** for logical isolation

### Escape Hatch

When a customer outgrows shared schema → route to a dedicated schema or DB at the connection-pool level, **not by changing application code**.

---

## 5. Monorepo Strategy

### Decision: Nx monorepo (TypeScript + Python polyglot)

CrossWave should be a **single Nx monorepo** with the following structure:

```
crosswave/
├── apps/                     # Application runtime wiring
│   ├── hq/                   # CrossWave HQ - Next.js dashboard
│   ├── api-gateway/          # Hono routing layer
│   ├── bridge-api/           # CrossBridge backend
│   ├── blog-api/             # CrossBlog backend
│   ├── deploy-api/           # CrossDeploy backend
│   └── polsia-api/           # Polsia Fork backend
│
├── bffs/                     # Per-product BFFs
│   ├── bridge-bff/
│   ├── blog-bff/
│   ├── deploy-bff/
│   ├── hivemind-bff/
│   ├── polsia-bff/
│   └── hq-bff/               # Admin BFF (aggregates across products)
│
├── packages/                  # Shared libraries
│   ├── core/                 # Auth, DB client, logging, HTTP
│   ├── validators/           # Zod schemas (shared API contracts)
│   ├── database/             # Prisma/Drizzle schema + migrations
│   ├── auth/                 # Shared auth middleware
│   ├── ui/                   # Shared design system
│   ├── billing/              # Entitlement checks, Stripe
│   └── config/               # Environment, feature flags
│
├── tooling/
│   ├── eslint/
│   ├── typescript/
│   └── prettier/
├── nx.json
└── pnpm-workspace.yaml
```

### Why Nx over alternatives

| Feature | Nx | Turborepo | Lerna |
|---------|----|-----------|-------|
| Polyglot support (TS + Python + Go) | ✅ | ❌ | ❌ |
| Module boundary enforcement | ✅ | ❌ | ❌ |
| Affected-based CI | ✅ | ✅ | ❌ |
| Custom executors | ✅ | ❌ | ❌ |
| Dependency graph visualization | ✅ | ✅ | ❌ |

### Monorepo Rules

1. **Products are modules. Apps are just runtimes** — `packages/products/` contains business logic, `apps/` contains runtime wiring
2. **Enforce communication through APIs, even internally** — never import directly from another product's package
3. **Keep BFFs thin** — aggregation only, no business logic
4. **Limit shared code aggressively** — extract only after 3+ consumers

---

## 6. Service-to-Service Communication

| Pattern | When | Tool |
|---------|------|------|
| **Synchronous** (BFF → domain service) | Request-response, read-heavy | Internal REST/gRPC over private network |
| **Async** (event-driven) | Cross-product notifications, billing events | BullMQ/Redis (lightweight) |
| **Shared DB** | Co-located services (monorepo) | Prisma/Drizzle with schema-based isolation |

### Railway Deployment Notes

Railway supports private networking between services in the same project:
- `mysql.railway.internal` for DB connections
- `redis.railway.internal` for async queues
- Services communicate via internal hostnames (not public URLs)

---

## 7. API Versioning

For CrossWave's current stage:

1. **URL-based versioning**: `/api/v1/products/bridge/translate`
2. **BFF versioning separate from domain services**
3. **Support N-2** (current + 2 previous versions) for mobile/HiveMind desktop
4. **OpenAPI schemas** as single source of truth
5. **Feature-flag new fields** — enable only when client version supports them

---

## 8. Entitlement-Based Billing

Instead of checking Stripe subscriptions directly:

```
entitlements
  org_id
  product (app_id)
  feature (e.g., "unlimited_translations", "custom_domain")
  is_active
  expires_at
```

**Flow**: Stripe webhook → update entitlements → code checks entitlements only.

**Benefits**:
- Decouples pricing from deployment
- Restructure plans without code changes
- Bundle products or offer cross-product discounts
- Survives payment provider migration

---

## 9. Phase-In Roadmap

### Phase 0: Now (已完成 ✅)
- ✅ Shared auth path: JWT with `orgId` + `appId`
- ✅ Refactored HQ to domain-driven (`app/domains/`, `hq/domains/`)
- ✅ NocoBase running with data sync pipeline
- ✅ 163 tests passing with 80%+ coverage
- ✅ Docker/nginx/CI/docker-compose infrastructure

### Phase 1: Foundation (Week 1-2)
| Action | Effort | Priority |
|--------|--------|----------|
| Set up Supabase Auth (or Clerk) | 1-2d | 🔴 Critical |
| Define shared Zod/OpenAPI schemas | 0.5d | 🔴 Critical |
| Scaffold Nx monorepo structure | 1d | 🔴 Critical |
| Move CrossBridge to `apps/bridge-api` + `bffs/bridge-bff` | 2-3d | 🔴 Critical |
| Add `org_id` + `app_id` to JWT | 0.5d | 🔴 Critical |

### Phase 2: Data Architecture (Week 2-4)
| Action | Effort | Priority |
|--------|--------|----------|
| Extract `common` PostgreSQL schema | 1-2d | 🟡 High |
| Set up shared Prisma/Drizzle client | 1d | 🟡 High |
| Migrate CACHE dict to SQLite/SQLAlchemy | 2d | 🟡 High |
| Add `org_id` to all tables | 1d | 🟡 High |

### Phase 3: BFF Rollout (Week 3-6)
| Action | Effort | Priority |
|--------|--------|----------|
| Build HQ BFF (aggregates across products) | 2-3d | 🟡 High |
| Build Bridge BFF | 1-2d | 🟡 High |
| Add entitlements table, decouple billing | 1-2d | 🟡 High |

### Phase 4: Infrastructure (Week 6-10)
| Action | Effort | Priority |
|--------|--------|----------|
| Set up affected-based CI (Nx + GitHub Actions) | 1-2d | 🟢 Medium |
| Add Pact contract tests per BFF | 2d | 🟢 Medium |
| Deploy Polsia Fork to Railway | 1d | 🟢 Medium |
| Deploy CrossBlog to Railway | 0.5d | 🟢 Medium |
| Production PostgreSQL (Neon/Supabase) | 1d | 🟢 Medium |
| Production Redis (Upstash/Railway) | 0.5d | 🟢 Medium |

### Phase 5: Operations (Week 8-12)
| Action | Effort | Priority |
|--------|--------|----------|
| Domain DNS + SSL (crosswave.app) | 0.5d | 🟢 Medium |
| Monitoring (Healthchecks.io / Sentry) | 0.5d | 🟢 Medium |
| Stripe production keys + webhooks | 1d | 🟢 Medium |
| LLM API Keys for production | 0.5d | 🟢 Medium |
| PM2/systemd for production services | 0.5d | 🟢 Medium |

---

## 10. Anti-Pattern Reference

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| One BFF for all products | Recreates the shared-API bottleneck; different products diverge in data needs |
| Business logic in BFF | Once in 3 BFFs, same bug lives in 3 places — extract to domain service |
| Skipping API contracts in monorepo | "It's in the same repo" leads to silent drift — always use schemas |
| DB-per-product from day one | Massive operational overhead before you need it — start shared-schema |
| Auth service per product | Users with multiple products become separate accounts — reconcile nightmare |
| Per-product CI pipelines | Drift silently — one unified monorepo CI is simpler |
| Stripe-coupled billing | Changing payment provider requires code changes — use entitlements abstraction |

---

## 11. Key Recommendations

1. **Do the shared auth + monorepo BEFORE deploying more products** — this is the critical inflection point
2. **Start with 2-3 BFFs** — HQ BFF (admin dashboard) + Bridge BFF (translation SaaS) + Blog BFF (content)
3. **Use `org_id` on every table from day one** — even if single-tenant now, it prevents painful migration later
4. **Extract shared BFF framework library only after 3+ BFFs** — rule of three prevents premature abstraction
5. **Feature-flag new API fields** — BFF changes must be backward-compatible with all supported client versions

---

*This document is the authoritative architecture reference for CrossWave. Update it before making significant architectural changes.*
