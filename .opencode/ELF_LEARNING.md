# ELF Learning: Phase A — NocoBase-First Data Layer

## Type: learning
**Pattern**: CACHE→NocoBase migration of HQ data layer
**Key decisions**:
- NocoBase-first, CACHE-fallback strategy (safe migration pattern)
- NB_DISABLED env var for test isolation
- polsia_bridge sync expanded to 5 new collections (leads/tasks/proposals/expenses/revenue_snapshots)
- nocobase_client mirrors CACHE shape for seamless fallback

## Type: golden_rule
**Rule**: When migrating from in-memory CACHE to database, use "new-first, old-fallback" pattern — not "old-first, new-fallback". This surfaces DB issues immediately while keeping the system running.
**File**: hq/domains/api_routes.py, hq/domains/monitor_routes.py, hq/nocobase_client.py
