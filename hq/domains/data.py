"""Shared state and sync logic for HQ Bridge server."""

import asyncio
import json
import os
import secrets
import time
from datetime import UTC, datetime

import httpx

from hq.polsia_client import PolsiaClient, PolsiaConnectionError

# ─── Auth ─────────────────────────────────────────────────────────────────────
AUTH_TOKEN = os.environ.get("HQ_AUTH_TOKEN", "")
if not AUTH_TOKEN:
    AUTH_TOKEN = secrets.token_urlsafe(24)
    print(f"[hq] ⚠ No HQ_AUTH_TOKEN set — generated: {AUTH_TOKEN}")

# ─── Paths & Config ───────────────────────────────────────────────────────────
_HQ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_HQ_DIR)

DB_PATH = os.environ.get("POLSIA_DB", os.path.join(_PROJECT_ROOT, "polsia-fork", "polsia.db"))
CROSSBRIDGE_DB = os.environ.get(
    "CROSSBRIDGE_DB",
    os.path.join(_PROJECT_ROOT, "ai-content-bridge", "content_bridge.db"),
)
POLSIA_PORT = int(os.environ.get("POLSIA_PORT", "8001"))
HQ_URL = os.environ.get("HQ_URL", "http://localhost:13000/api")
HQ_TOKEN = os.environ.get("HQ_TOKEN", "")

# ─── Shared Cache ─────────────────────────────────────────────────────────────
CACHE: dict = {
    "employees": [],
    "lines": [],
    "orders": [],
    "leads": [],
    "external_orders": [],
    "proposals": [],
    "expenses": [],
    "revenue_history": [],
    "last_sync": None,
    "tasks": [],
}

# ─── Service Monitor ──────────────────────────────────────────────────────────
SERVICES_TO_CHECK = [
    {"name": "polsia-fork", "url": "http://localhost:8001/api/v1/health", "label": "Polsia Fork (AI Agents)"},
    {"name": "crosswave",   "url": "http://localhost:9999/health",        "label": "CrossWave (Website)"},
    {"name": "crossblog",   "url": "http://localhost:8002/health",        "label": "CrossBlog (80 Posts)"},
    {"name": "hq-bridge",   "url": "http://localhost:13001/health",       "label": "CrossWave HQ (Bridge)"},
]


async def _check_svc(name: str, url: str, timeout: int = 5) -> dict:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers={"User-Agent": "CrossWave-Monitor/1.0"})
        ms = int((time.monotonic() - start) * 1000)
        return {"service": name, "status": "up" if resp.is_success else "degraded",
                "http_status": resp.status_code, "response_time_ms": ms, "error": ""}
    except Exception as e:
        ms = int((time.monotonic() - start) * 1000)
        return {"service": name, "status": "down", "http_status": 0,
                "response_time_ms": ms, "error": str(e)[:120]}


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
                "id": lead.get("id"),
                "name": lead.get("name", ""),
                "email": lead.get("email", ""),
                "company": lead.get("company", ""),
                "product_interest": lead.get("product_interest", ""),
                "budget_range": lead.get("budget_range", ""),
                "message": lead.get("message", ""),
                "status": lead.get("status", "new"),
                "source_page": lead.get("source_page", ""),
                "created_at": lead.get("created_at", ""),
            }
            for lead in leads_data
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


async def polsia_sync():
    """Pull data from Polsia Fork into CACHE. Tries API first, falls back to SQLite."""
    # Try API first
    if await polsia_sync_via_api():
        # API succeeded — still try NocoBase sync at the end
        await _try_nocobase_sync()
        return
    print("[bridge] API unavailable, falling back to SQLite sync")
    if not os.path.exists(DB_PATH):
        print(f"[bridge] Polsia DB not found at {DB_PATH}")
        return
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            agent_types = await db.execute_fetchall(
                "SELECT DISTINCT agent_type FROM tasks ORDER BY agent_type"
            )
            tasks = await db.execute_fetchall(
                "SELECT title, status, agent_type, created_at, id FROM tasks ORDER BY created_at DESC LIMIT 100"
            )
            expense_rows = await db.execute_fetchall(
                "SELECT amount_cents, category, description, date FROM expense_records ORDER BY date"
            )
            rev_rows = await db.execute_fetchall(
                "SELECT snapshot_date, mrr_cents, active_subscribers FROM revenue_snapshots ORDER BY snapshot_date"
            )
            ext_order_rows = await db.execute_fetchall(
                "SELECT id, title, platform, external_id, status, budget_min, budget_max, currency, score, score_reason, assigned_agent, created_at, provider_notes, deliverables, delivery_notes FROM external_orders ORDER BY created_at DESC LIMIT 100"
            )
            lead_rows = await db.execute_fetchall(
                "SELECT id, name, email, company, product_interest, budget_range, message, status, source_page, created_at FROM leads ORDER BY created_at DESC LIMIT 100"
            )
            proposal_rows = await db.execute_fetchall(
                "SELECT id, order_id, status, proposed_amount, currency, content, summary, proposal_metadata, created_at, updated_at FROM proposals ORDER BY created_at DESC LIMIT 100"
            )
            task_rows = await db.execute_fetchall(
                "SELECT id, title, description, agent_type, priority, status, source, scheduled_date, result_summary, error_message, metadata_json, created_at, updated_at FROM tasks ORDER BY created_at DESC LIMIT 200"
            )
    except Exception as e:
        print(f"[bridge] DB read error: {e}")
        return

    employees = []
    for row in agent_types:
        employees.append({
            "name": row[0].replace("_", " ").title() if row[0] else "Agent",
            "type": "ai",
            "role": row[0] or "agent",
            "status": "idle",
            "agent_type": row[0],
        })
    employee_types = set(e["agent_type"] for e in employees)
    known_agents = ["orchestrator", "social_media", "customer_support", "competitor_research",
                     "business_planning", "content_writer", "code_generation", "deployment",
                     "finance_agent", "email_outreach", "ads_management"]
    for ka in known_agents:
        if ka not in employee_types:
            employees.append({
                "name": ka.replace("_", " ").title(),
                "type": "ai",
                "role": ka.replace("_", " ").title(),
                "status": "idle",
                "agent_type": ka,
            })
    orders = []
    for row in tasks:
        orders.append({
            "title": row[0] or "",
            "status": row[1] or "pending",
            "agent_type": row[2] or "",
            "created_at": row[3] or "",
            "source_id": row[4],
            "platform": "internal",
        })
    exps = []
    for r in expense_rows:
        exps.append({"amount": r[0] / 100.0 if r[0] else 0, "category": r[1] or "other",
                      "description": r[2] or "", "date": r[3] or ""})
    CACHE["expenses"] = exps
    revs = []
    mrr_val = 0
    sub_val = 0
    for r in rev_rows:
        revs.append({"date": r[0] or "", "amount": r[1] / 100.0 if r[1] else 0, "source": "subscription"})
    CACHE["revenue_history"] = revs
    if rev_rows:
        latest = rev_rows[-1]
        mrr_val = (latest[1] or 0) / 100.0
        sub_val = latest[2] or 0
    mrr_dollars = mrr_val or 174
    subscribers = sub_val or 4
    predef_lines = [
        {"name": "CrossBridge", "slug": "crossbridge", "status": "active", "monthly_revenue": 0, "customer_count": 0},
        {"name": "CrossBlog", "slug": "crossblog", "status": "active", "monthly_revenue": 0, "customer_count": 0},
        {"name": "CrossDeploy", "slug": "crossdeploy", "status": "active", "monthly_revenue": 0, "customer_count": 0},
        {"name": "Polsia Fork", "slug": "polsia", "status": "active", "monthly_revenue": mrr_dollars, "customer_count": subscribers},
        {"name": "HiveMind", "slug": "hivemind", "status": "development", "monthly_revenue": 0, "customer_count": 0},
    ]
    CACHE["employees"] = employees
    CACHE["lines"] = predef_lines
    CACHE["orders"] = orders
    CACHE["last_sync"] = datetime.now(UTC).isoformat()
    leads = []
    for row in lead_rows:
        leads.append({"id": row[0], "name": row[1] or "", "email": row[2] or "",
                       "company": row[3] or "", "product_interest": row[4] or "",
                       "budget_range": row[5] or "", "message": row[6] or "",
                       "status": row[7] or "new", "source_page": row[8] or "",
                       "created_at": row[9] or ""})
    CACHE["leads"] = leads
    ext_orders = []
    for row in ext_order_rows:
        provider_notes_raw = row[12] if len(row) > 12 else None
        deliverables_raw = row[13] if len(row) > 13 else None
        delivery_notes_raw = row[14] if len(row) > 14 else None
        ext_orders.append({
            "id": row[0], "title": row[1] or "", "platform": row[2] or "",
            "external_id": row[3] or "", "status": row[4] or "scanned",
            "budget_min": row[5], "budget_max": row[6], "currency": row[7] or "USD",
            "score": row[8], "score_reason": row[9] or "", "assigned_agent": row[10] or "",
            "created_at": row[11] or "",
            "deployment_plan": provider_notes_raw,
            "deliverables": json.loads(deliverables_raw) if isinstance(deliverables_raw, str) else (deliverables_raw or []),
            "delivery_notes": delivery_notes_raw or "",
        })
    CACHE["external_orders"] = ext_orders
    proposals = []
    for row in proposal_rows:
        meta_raw = row[7] if len(row) > 7 else None
        proposals.append({
            "id": row[0], "order_id": row[1],
            "status": row[2] or "draft",
            "proposed_amount": row[3],
            "currency": row[4] or "USD",
            "content": row[5] or "",
            "summary": row[6] or "",
            "proposal_metadata": json.loads(meta_raw) if isinstance(meta_raw, str) else (meta_raw or {}),
            "created_at": row[8] or "",
            "updated_at": row[9] or "",
        })
    CACHE["proposals"] = proposals
    full_tasks = []
    for r in task_rows:
        full_tasks.append({
            "id": r[0], "title": r[1] or "", "description": r[2] or "",
            "agent_type": r[3] or "", "priority": r[4] or 3,
            "status": r[5] or "pending", "source": r[6] or "",
            "scheduled_date": r[7] or "", "result_summary": r[8] or "",
            "error_message": r[9] or "", "metadata_json": r[10] or "",
            "created_at": r[11] or "", "updated_at": r[12] or "",
        })
    CACHE["tasks"] = full_tasks
    try:
        activity_rows = await db.execute_fetchall(
            "SELECT agent_type, action, summary, level, created_at, id FROM activity_log ORDER BY created_at DESC LIMIT 200"
        )
        CACHE["activity_log"] = [
            {"agent_type": r[0], "action": r[1], "summary": r[2],
             "level": r[3] or "info", "created_at": r[4] or "", "id": r[5]}
            for r in activity_rows
        ]
    except Exception as al_err:
        print(f"[bridge] activity_log sync error: {al_err}")
        CACHE["activity_log"] = []
    print(f"[bridge] Synced: {len(employees)} employees, {len(orders)} tasks, {len(leads)} leads, {len(ext_orders)} ext orders, {len(exps)} expenses, {len(revs)} rev months, {len(full_tasks)} full tasks")

    # ── Optional: sync to NocoBase ─────────────────────────────
    await _try_nocobase_sync()


async def _try_nocobase_sync():
    """Attempt to sync to NocoBase (best-effort)."""
    try:
        from hq.polsia_bridge import sync as nocobase_sync
        await nocobase_sync()
        print("[bridge] NocoBase sync completed")
    except Exception as nbe:
        print(f"[bridge] NocoBase sync skipped: {nbe}")


async def periodic_sync():
    """Background sync every 30 minutes."""
    while True:
        await polsia_sync()
        await asyncio.sleep(1800)
