## Type: golden_rule
**Rule**: When connecting an existing data pipeline (sync/read) to a new event system, use the "fire-and-forget" pattern — wrap event publishing in a try/except that silently catches failures. The event bus should never block the primary data flow.
**Files**: hq/polsia_bridge.py:291, hq/nocobase_client.py:160
**Rationale**: An event bus is a non-critical side-effect. If it fails (not installed, broken, not imported), the core data sync/read must still succeed.

## Type: learning
**Learning**: CrossWave AI OS now has 4 complete layers: NocoBase data layer (Phase A), Plugin Registry (Phase B), Event Bus (Phase C), MCP tools (Phase D). Event stream connected to real product data flows (polsia_bridge sync + nocobase_client reads). Dashboard shows plugin status and event stream. v0.9.3.
