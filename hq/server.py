<<<<<<< HEAD
import os, json, asyncio, httpx, uvicorn, secrets, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timezone

# ─── Simple Auth (Token-based) ─────────────────────────────────────────────
AUTH_TOKEN = os.environ.get("HQ_AUTH_TOKEN", "")
if not AUTH_TOKEN:
    AUTH_TOKEN = secrets.token_urlsafe(24)
    print(f"[hq] ⚠ No HQ_AUTH_TOKEN set — generated: {AUTH_TOKEN}")

async def require_token(request: Request):
    """Reject requests missing X-HQ-Token header. Skip public paths."""
    public_paths = ("/health", "/login", "/api/hq/auth", "/api/portal/", "/portal/", "/static")
    if request.url.path.startswith("/api/portal/") or request.url.path.startswith("/portal/") or request.url.path in ("/health", "/login") or request.url.path.startswith("/api/hq/auth") or request.url.path.startswith("/static"):
        return True
    token = request.headers.get("X-HQ-Token", "")
    if token == AUTH_TOKEN:
        return True
    raise HTTPException(status_code=401, detail="Unauthorized — provide X-HQ-Token header")

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Start background sync on startup."""
    asyncio.create_task(periodic_sync())
    yield

app = FastAPI(title="CrossWave HQ Bridge", dependencies=[Depends(require_token)], lifespan=app_lifespan)
app.mount("/static", StaticFiles(directory=os.path.dirname(__file__)), name="hq_static")

DB_PATH = os.environ.get("POLSIA_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "polsia-fork", "polsia.db"))
CROSSBRIDGE_DB = os.environ.get("CROSSBRIDGE_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "ai-content-bridge", "content_bridge.db"))
POLSIA_PORT = int(os.environ.get("POLSIA_PORT", "8001"))
HQ_URL = os.environ.get("HQ_URL", "http://localhost:13000/api")
HQ_TOKEN = os.environ.get("HQ_TOKEN", "")

CACHE = {"employees": [], "lines": [], "orders": [], "leads": [], "external_orders": [], "proposals": [], "expenses": [], "revenue_history": [], "last_sync": None, "tasks": []}
=======
import os
import json
import asyncio
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timezone

app = FastAPI(title="CrossWave HQ Bridge")

DB_PATH = os.environ.get("POLSIA_DB", os.path.expanduser("~/.opencode-workspace/projects/polsia-fork/polsia.db"))
HQ_URL = os.environ.get("HQ_URL", "http://localhost:13000/api")
HQ_TOKEN = os.environ.get("HQ_TOKEN", "")

CACHE = {"employees": [], "lines": [], "orders": [], "expenses": [], "revenue_history": [], "last_sync": None}

async def polsia_sync():
    if not os.path.exists(DB_PATH):
        print(f"[bridge] Polsia DB not found at {DB_PATH}")
        return
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
<<<<<<< HEAD
            agent_types = await db.execute_fetchall(
                "SELECT DISTINCT agent_type FROM tasks ORDER BY agent_type"
=======
            agents = await db.execute_fetchall(
                "SELECT type, name, role, status, id FROM agents ORDER BY id"
>>>>>>> feature/hq-p2
            )
            tasks = await db.execute_fetchall(
                "SELECT title, status, agent_type, created_at, id FROM tasks ORDER BY created_at DESC LIMIT 100"
            )
<<<<<<< HEAD
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
            weekly_report_rows = await db.execute_fetchall(
                "SELECT id, period_start, period_end, summary, created_at, recipient_count "
                "FROM weekly_reports ORDER BY created_at DESC LIMIT 20"
            )
=======
>>>>>>> feature/hq-p2
    except Exception as e:
        print(f"[bridge] DB read error: {e}")
        return

    employees = []
<<<<<<< HEAD
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
=======
    for row in agents:
        employees.append({
            "name": row[1] or row[0],
            "type": row[3] or "ai",
            "role": row[2] or row[0],
            "status": row[3] or "idle",
            "agent_type": row[0],
            "source_id": row[4],
        })
>>>>>>> feature/hq-p2
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
    try:
        expense_rows = await db.execute_fetchall(
            "SELECT amount, category, description, date FROM expenses ORDER BY date"
        )
        CACHE["expenses"] = [
            {"amount": r[0], "category": r[1] or "other", "description": r[2] or "", "date": r[3] or ""}
            for r in expense_rows
        ]
    except Exception:
        CACHE["expenses"] = []
    try:
        rev_rows = await db.execute_fetchall(
            "SELECT date, amount, source FROM finance_records ORDER BY date"
        )
        CACHE["revenue_history"] = [
            {"date": r[0] or "", "amount": r[1] or 0, "source": r[2] or "unknown"}
            for r in rev_rows
        ]
    except Exception:
        CACHE["revenue_history"] = []
    predef_lines = [
        {"name": "CrossBridge", "slug": "crossbridge", "status": "active", "monthly_revenue": 0, "customer_count": 0},
        {"name": "CrossBlog", "slug": "crossblog", "status": "active", "monthly_revenue": 0, "customer_count": 0},
        {"name": "CrossDeploy", "slug": "crossdeploy", "status": "active", "monthly_revenue": 0, "customer_count": 0},
<<<<<<< HEAD
        {"name": "Polsia Fork", "slug": "polsia", "status": "active", "monthly_revenue": mrr_dollars, "customer_count": subscribers},
=======
        {"name": "Polsia Fork", "slug": "polsia", "status": "active", "monthly_revenue": 0, "customer_count": 0},
>>>>>>> feature/hq-p2
        {"name": "HiveMind", "slug": "hivemind", "status": "development", "monthly_revenue": 0, "customer_count": 0},
    ]
    CACHE["employees"] = employees
    CACHE["lines"] = predef_lines
    CACHE["orders"] = orders
    CACHE["last_sync"] = datetime.now(timezone.utc).isoformat()
<<<<<<< HEAD
    leads = []
    for row in lead_rows:
        leads.append({"id": row[0], "name": row[1] or "", "email": row[2] or "", "company": row[3] or "", "product_interest": row[4] or "", "budget_range": row[5] or "", "message": row[6] or "", "status": row[7] or "new", "source_page": row[8] or "", "created_at": row[9] or ""})
    CACHE["leads"] = leads
    ext_orders = []
    for row in ext_order_rows:
        provider_notes_raw = row[12] if len(row) > 12 else None
        deliverables_raw = row[13] if len(row) > 13 else None
        delivery_notes_raw = row[14] if len(row) > 14 else None
        ext_orders.append({"id": row[0], "title": row[1] or "", "platform": row[2] or "", "external_id": row[3] or "", "status": row[4] or "scanned", "budget_min": row[5], "budget_max": row[6], "currency": row[7] or "USD", "score": row[8], "score_reason": row[9] or "", "assigned_agent": row[10] or "", "created_at": row[11] or "", "deployment_plan": provider_notes_raw, "deliverables": json.loads(deliverables_raw) if isinstance(deliverables_raw, str) else (deliverables_raw or []), "delivery_notes": delivery_notes_raw or ""})
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
    # Activity log (for notifications, nurture tracking, timeline)
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
    # Weekly reports
    try:
        CACHE["weekly_reports"] = [
            {"id": r[0], "period_start": r[1], "period_end": r[2],
             "summary": r[3], "created_at": r[4], "recipient_count": r[5]}
            for r in weekly_report_rows
        ]
    except Exception:
        CACHE["weekly_reports"] = []
    print(f"[bridge] Synced: {len(employees)} employees, {len(orders)} tasks, {len(leads)} leads, {len(ext_orders)} ext orders, {len(exps)} expenses, {len(revs)} rev months, {len(full_tasks)} full tasks")

    # ── Optional: sync to NocoBase ─────────────────────────────
    try:
        from hq.polsia_bridge import sync as nocobase_sync
        await nocobase_sync()
        print("[bridge] NocoBase sync completed")
    except Exception as nbe:
        print(f"[bridge] NocoBase sync skipped: {nbe}")
=======
    print(f"[bridge] Synced: {len(employees)} employees, {len(orders)} tasks")
>>>>>>> feature/hq-p2

async def periodic_sync():
    while True:
        await polsia_sync()
        await asyncio.sleep(1800)

<<<<<<< HEAD
=======
@app.on_event("startup")
async def startup():
    asyncio.create_task(periodic_sync())

>>>>>>> feature/hq-p2
@app.get("/api/hq/summary")
async def summary():
    emps = CACHE["employees"]
    lines = CACHE["lines"]
    orders = CACHE["orders"]
    active_orders = [o for o in orders if o["status"] in ("pending", "in_progress")]
    total_mrr = sum(l.get("monthly_revenue", 0) for l in lines)
    CACHE["mrr"] = total_mrr
    total_customers = sum(l.get("customer_count", 0) for l in lines)
    status_counts = {}
    for e in emps:
        s = e.get("status", "idle")
        status_counts[s] = status_counts.get(s, 0) + 1
    order_status = {}
    for o in orders:
        s = o.get("status", "pending")
        order_status[s] = order_status.get(s, 0) + 1
    lines_health = []
    for l in lines:
        h = "healthy" if l["status"] == "active" else "warning" if l["status"] == "development" else "critical"
        lines_health.append({"name": l["name"], "slug": l["slug"], "status": l["status"], "health": h, "revenue": l.get("monthly_revenue", 0), "customers": l.get("customer_count", 0)})
    return {
        "employees": {"total": len(emps), "status_distribution": status_counts},
        "lines": lines_health,
        "orders": {"total": len(orders), "active": len(active_orders), "status_distribution": order_status},
        "mrr": total_mrr,
        "customers": total_customers,
<<<<<<< HEAD
        "leads": {"total": len(CACHE["leads"]), "new": len([l for l in CACHE["leads"] if l["status"] == "new"])},
        "proposals": {p["status"]: len([x for x in CACHE.get("proposals", []) if x["status"] == p["status"]]) for p in [{"status":s} for s in ("draft","sent","replied","negotiating","won","lost")]},
        "last_sync": CACHE["last_sync"],
        "crossbridge": await get_crossbridge_summary(),
    }

@app.get("/crossbridge")
async def crossbridge_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "crossbridge.html"))

@app.get("/api/hq/crossbridge")
async def get_crossbridge():
    return await get_crossbridge_summary()

async def get_crossbridge_summary():
    """Read CrossBridge SQLite for user/conversion stats."""
    if not os.path.exists(CROSSBRIDGE_DB):
        return {"status": "unavailable", "db_path": CROSSBRIDGE_DB}
    try:
        import aiosqlite
        async with aiosqlite.connect(CROSSBRIDGE_DB) as db:
            users = await db.execute_fetchall(
                "SELECT id, email, plan, monthly_usage, is_active, created_at FROM users ORDER BY created_at DESC"
            )
            conv = await db.execute_fetchall(
                "SELECT COUNT(*) as cnt, MAX(created_at) as last FROM conversions"
            )
            daily_conv = await db.execute_fetchall(
                "SELECT date(created_at) as d, COUNT(*) as c FROM conversions GROUP BY d ORDER BY d"
            )
        total_users = len(users)
        active_users = sum(1 for u in users if u[4] == 1)
        total_conversions = conv[0][0] if conv else 0
        last_conversion = conv[0][1] if conv and conv[0][1] else None
        plan_dist = {}
        user_list = []
        for u in users:
            p = u[2] or "free"
            plan_dist[p] = plan_dist.get(p, 0) + 1
            user_list.append({
                "id": u[0], "email": u[1], "plan": p,
                "monthly_usage": u[3], "is_active": bool(u[4]),
                "created_at": u[5],
            })
        daily_conversions = [{"date": r[0], "count": r[1]} for r in daily_conv]
        return {
            "status": "available",
            "total_users": total_users,
            "active_users": active_users,
            "total_conversions": total_conversions,
            "last_conversion": last_conversion,
            "plan_distribution": plan_dist,
            "users": user_list,
            "daily_conversions": daily_conversions,
            "db_path": CROSSBRIDGE_DB,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

=======
        "last_sync": CACHE["last_sync"],
    }

>>>>>>> feature/hq-p2
@app.get("/api/hq/employees")
async def get_employees():
    return {"data": CACHE["employees"]}

@app.get("/api/hq/orders")
async def get_orders(platform: str = "", status: str = ""):
    items = CACHE["orders"]
    if platform:
        items = [o for o in items if o.get("platform") == platform]
    if status:
        items = [o for o in items if o.get("status") == status]
    return {"data": items}

<<<<<<< HEAD
@app.get("/api/hq/leads")
async def get_leads(status: str = ""):
    items = CACHE["leads"]
    if status:
        items = [l for l in items if l.get("status") == status]
    return {"data": items, "total": len(items), "new_count": len([l for l in items if l.get("status") == "new"])}

@app.get("/api/hq/external-orders")
async def get_external_orders(platform: str = "", status: str = ""):
    items = CACHE.get("external_orders", [])
    if platform:
        items = [o for o in items if o.get("platform") == platform]
    if status:
        items = [o for o in items if o.get("status") == status]
    return {"data": items, "total": len(items)}


@app.get("/api/hq/proposals")
async def get_proposals(status: str = ""):
    items = CACHE.get("proposals", [])
    if status:
        items = [p for p in items if p.get("status") == status]
    return {"data": items, "total": len(items)}


@app.get("/proposals")
async def proposals_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "proposals.html"))


=======
>>>>>>> feature/hq-p2
@app.get("/api/hq/lines")
async def get_lines():
    return {"data": CACHE["lines"]}

<<<<<<< HEAD

@app.get("/api/hq/quick-quote-analytics")
async def quick_quote_analytics():
    """Aggregate Quick Quote pipeline: website leads → orders → proposals."""
    leads = CACHE.get("leads", [])
    ext_orders = CACHE.get("external_orders", [])
    proposals = CACHE.get("proposals", [])

    # Quick-quote leads: created via /request-quote (product_interest contains Quick Quote)
    qq_leads = [l for l in leads if "Quick Quote" in (l.get("product_interest") or "")]
    qq_orders = [o for o in ext_orders if o.get("platform") == "internal" and "Quick Quote" in (o.get("title") or "")]
    qq_order_ids = {o["id"] for o in qq_orders}
    qq_proposals = [p for p in proposals if p.get("order_id") in qq_order_ids]

    total_leads = len(qq_leads)
    total_orders = len(qq_orders)
    total_proposals = len(qq_proposals)
    sent = len([p for p in qq_proposals if p.get("status") == "sent"])
    won = len([p for p in qq_proposals if p.get("status") == "won"])
    lost = len([p for p in qq_proposals if p.get("status") == "lost"])

    # Revenue from won proposals
    total_revenue = sum(p.get("proposed_amount", 0) or 0 for p in qq_proposals if p.get("status") == "won")

    # Monthly trend
    monthly = {}
    for l in qq_leads:
        created = l.get("created_at", "")[:7]
        monthly[created] = monthly.get(created, {"leads": 0, "orders": 0, "revenue": 0})
        monthly[created]["leads"] += 1
    for o in qq_orders:
        created = o.get("created_at", "")[:7]
        if created not in monthly:
            monthly[created] = {"leads": 0, "orders": 0, "revenue": 0}
        monthly[created]["orders"] += 1
    for p in qq_proposals:
        if p.get("status") == "won":
            created = p.get("created_at", "")[:7]
            if created in monthly:
                monthly[created]["revenue"] += p.get("proposed_amount", 0) or 0

    trend = [{"month": k, **v} for k, v in sorted(monthly.items())]

    return {
        "summary": {
            "total_leads": total_leads,
            "total_orders": total_orders,
            "total_proposals": total_proposals,
            "sent": sent,
            "won": won,
            "lost": lost,
            "total_revenue": total_revenue,
        },
        "funnel": {
            "lead_to_order_pct": round(total_orders / total_leads * 100, 1) if total_leads else 0,
            "order_to_proposal_pct": round(total_proposals / total_orders * 100, 1) if total_orders else 0,
            "proposal_to_sent_pct": round(sent / total_proposals * 100, 1) if total_proposals else 0,
            "proposal_to_won_pct": round(won / total_proposals * 100, 1) if total_proposals else 0,
        },
        "trend": trend,
    }


@app.get("/quick-quote")
async def quick_quote_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "quick-quote.html"))

@app.post("/api/hq/proxy/patch")
async def proxy_patch(request: Request):
    """Proxy PATCH requests to Polsia Fork API (for status updates)."""
    body = await request.json()
    path = body.get("path", "")
    params = body.get("params", {})
    url = f"http://127.0.0.1:{POLSIA_PORT}/api/v1{path}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(url, params=params, headers={"X-API-Key": "dev-key"})
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        raise HTTPException(502, f"Polsia proxy failed: {e}")


=======
>>>>>>> feature/hq-p2
@app.get("/api/hq/sync")
async def trigger_sync():
    await polsia_sync()
    return {"ok": True, "synced_at": CACHE["last_sync"]}

@app.get("/")
async def dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "dashboard.html"))

<<<<<<< HEAD
@app.get("/dashboard")
async def dashboard_redirect():
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/")

=======
>>>>>>> feature/hq-p2
@app.get("/orders")
async def orders_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "orders.html"))

@app.get("/employees")
async def employees_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "employees.html"))

@app.get("/api/hq/finances")
async def get_finances():
    expenses = CACHE["expenses"]
    revenue = CACHE["revenue_history"]
    total_revenue = sum(r["amount"] for r in revenue) if revenue else 0
    total_costs = sum(e["amount"] for e in expenses) if expenses else 0
    profit_margin = round((total_revenue - total_costs) / total_revenue * 100, 1) if total_revenue else 0
    expense_by_cat = {}
    for e in expenses:
        cat = e["category"]
        expense_by_cat[cat] = expense_by_cat.get(cat, 0) + e["amount"]
    rev_by_month = {}
    for r in revenue:
        d = r["date"][:7] if r["date"] else "unknown"
        rev_by_month[d] = rev_by_month.get(d, 0) + r["amount"]
    return {
        "total_revenue": total_revenue,
        "total_costs": total_costs,
        "profit_margin": profit_margin,
        "mrr": CACHE["mrr"] if "mrr" in CACHE else sum(r["amount"] for r in revenue[-3:] if revenue) // 3 if revenue else 0,
        "arr": CACHE["mrr"] * 12 if "mrr" in CACHE else 0,
        "expense_by_category": [{"category": k, "amount": v} for k, v in sorted(expense_by_cat.items(), key=lambda x: -x[1])],
        "revenue_by_month": [{"month": k, "revenue": v} for k, v in sorted(rev_by_month.items())],
    }

@app.get("/api/hq/reports")
async def get_reports():
    orders = CACHE["orders"]
    employees = CACHE["employees"]
    total_tasks = len(orders)
    completed = len([o for o in orders if o["status"] == "done"])
    failed = len([o for o in orders if o["status"] == "failed"])
    agent_perf = {}
    for o in orders:
        at = o.get("agent_type", "unknown")
        if at not in agent_perf:
            agent_perf[at] = {"done": 0, "failed": 0, "total": 0}
        agent_perf[at]["total"] += 1
        if o["status"] == "done":
            agent_perf[at]["done"] += 1
        elif o["status"] == "failed":
            agent_perf[at]["failed"] += 1
    task_by_day = {}
    for o in orders:
        d = o["created_at"][:10] if o["created_at"] else "unknown"
        task_by_day[d] = task_by_day.get(d, 0) + 1
    activity_7d = sum(v for k, v in task_by_day.items() if k >= (datetime.now(timezone.utc).isoformat()[:10] if task_by_day else ""))
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "completion_rate": round(completed / total_tasks * 100, 1) if total_tasks else 0,
        "agent_performance": [{"agent": k, **v} for k, v in sorted(agent_perf.items(), key=lambda x: -x[1]["total"])],
        "task_trend": [{"date": k, "count": v} for k, v in sorted(task_by_day.items())],
        "last_7d_activity": activity_7d,
        "employee_count": len(employees),
    }

@app.get("/finance")
async def finance_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "finances.html"))

@app.get("/reports")
async def reports_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "reports.html"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=13001)
