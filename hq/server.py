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

async def polsia_sync():
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
            weekly_report_rows = await db.execute_fetchall(
                "SELECT id, period_start, period_end, summary, created_at, recipient_count "
                "FROM weekly_reports ORDER BY created_at DESC LIMIT 20"
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
        exps.append({"amount": r[0] / 100.0 if r[0] else 0, "category": r[1] or "other", "description": r[2] or "", "date": r[3] or ""})
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
    CACHE["last_sync"] = datetime.now(timezone.utc).isoformat()
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

async def periodic_sync():
    while True:
        await polsia_sync()
        await asyncio.sleep(1800)

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


@app.get("/api/hq/lines")
async def get_lines():
    return {"data": CACHE["lines"]}


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


@app.get("/api/hq/sync")
async def trigger_sync():
    await polsia_sync()
    return {"ok": True, "synced_at": CACHE["last_sync"]}

@app.get("/")
async def dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "dashboard.html"))

@app.get("/dashboard")
async def dashboard_redirect():
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/")

@app.get("/orders")
async def orders_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "orders.html"))

@app.get("/employees")
async def employees_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "employees.html"))

@app.get("/leads")
async def leads_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "leads.html"))

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
    completed = len([o for o in orders if o["status"] in ("done", "completed")])
    failed = len([o for o in orders if o["status"] == "failed"])
    agent_perf = {}
    for o in orders:
        at = o.get("agent_type", "unknown")
        if at not in agent_perf:
            agent_perf[at] = {"done": 0, "failed": 0, "total": 0}
        agent_perf[at]["total"] += 1
        if o["status"] in ("done", "completed"):
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

@app.get("/finances")
async def finances_redirect():
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/finance")

@app.get("/deploy")
async def deploy_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "deploy.html"))

# ─── Public Customer Portal ──────────────────────────────────────────────────
@app.get("/api/portal/order/{order_id}")
async def portal_order(order_id: int):
    """Public endpoint — returns order details for customer portal display."""
    orders = CACHE.get("external_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    stage_order = ["pending", "scanned", "accepted", "in_progress", "deploying", "testing", "completed", "delivered"]
    stage_idx = {"pending": 0, "scanned": 1, "accepted": 2, "in_progress": 3, "deploying": 4, "testing": 5, "completed": 6, "delivered": 7}
    status = order.get("status", "pending")
    progress_idx = stage_idx.get(status, 0)
    deployment_plan = None
    if "deployment_plan" in order:
        try:
            deployment_plan = json.loads(order["deployment_plan"]) if isinstance(order["deployment_plan"], str) else order["deployment_plan"]
        except (json.JSONDecodeError, TypeError):
            deployment_plan = None
    deliverables = order.get("deliverables", [])
    return {
        "id": order["id"],
        "title": order.get("title", "CrossDeploy Project"),
        "status": status,
        "progress_idx": min(progress_idx, len(stage_order) - 1),
        "total_stages": len(stage_order),
        "stages": stage_order,
        "score": order.get("score"),
        "platform": order.get("platform", "direct"),
        "created_at": order.get("created_at", ""),
        "deployment_plan": deployment_plan,
        "deliverables": deliverables,
        "delivery_notes": order.get("delivery_notes", ""),
    }

@app.get("/portal/{order_id}")
async def portal_page(order_id: int):
    return FileResponse(os.path.join(os.path.dirname(__file__), "portal.html"))

# ─── Monitor (守望者) ──────────────────────────────────────────────────────
SERVICES_TO_CHECK = [
    {"name": "polsia-fork", "url": "http://localhost:8001/api/v1/health", "label": "Polsia Fork (AI Agents)"},
    {"name": "crosswave",     "url": "http://localhost:9999/health",           "label": "CrossWave (Website)"},
    {"name": "crossblog",     "url": "http://localhost:8002/health",           "label": "CrossBlog (80 Posts)"},
    {"name": "hq-bridge",     "url": "http://localhost:13001/health",          "label": "CrossWave HQ (Bridge)"},
]


async def _check_svc(name: str, url: str, timeout: int = 5) -> dict:
    import time
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


@app.get("/login")
async def login_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "login.html"))

@app.post("/api/hq/auth")
async def auth_login(request: Request):
    body = await request.json()
    token = body.get("token", "")
    if token == AUTH_TOKEN:
        return {"ok": True, "token": AUTH_TOKEN}
    return JSONResponse(status_code=403, content={"ok": False, "error": "Invalid token"})

@app.get("/health")
async def hq_health():
    return {"status": "ok", "app": "CrossWave HQ Bridge", "services": len(SERVICES_TO_CHECK)}


@app.get("/api/hq/monitor")
async def get_monitor():
    import asyncio
    tasks = [_check_svc(s["name"], s["url"]) for s in SERVICES_TO_CHECK]
    results = await asyncio.gather(*tasks)
    up = sum(1 for r in results if r["status"] == "up")
    degraded = sum(1 for r in results if r["status"] == "degraded")
    down = sum(1 for r in results if r["status"] == "down")
    valid_ms = [r["response_time_ms"] for r in results if r["response_time_ms"] > 0]
    avg_ms = round(sum(valid_ms) / len(valid_ms)) if valid_ms else 0
    return {
        "summary": {
            "total": len(results), "up": up, "degraded": degraded, "down": down,
            "avg_response_time_ms": avg_ms, "all_up": up == len(results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "results": [{**r, "label": next((s["label"] for s in SERVICES_TO_CHECK if s["name"] == r["service"]), r["service"])} for r in results],
    }


@app.get("/monitor")
async def monitor_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "monitor.html"))


# ─── Evolution Office (进化办) ──────────────────────────────────────────────
@app.get("/api/hq/evolution")
async def get_evolution():
    """Return evolution analysis from Polsia DB.

    Reads activity_log and task data to produce agent performance metrics.
    """
    if not os.path.exists(DB_PATH):
        return {
            "error": "Polsia DB not found — run Polsia Fork first",
            "agent_metrics": [],
            "suggestions": ["启动 Polsia Fork 后再查看进化分析"],
            "total_activities": 0,
        }
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            # Activity log counts per agent_type
            act_rows = await db.execute_fetchall(
                "SELECT agent_type, level, COUNT(*) as cnt FROM activity_log "
                "WHERE created_at >= datetime('now', '-7 days') "
                "GROUP BY agent_type, level ORDER BY agent_type"
            )
            # Task counts per agent_type
            task_rows = await db.execute_fetchall(
                "SELECT agent_type, status, COUNT(*) as cnt FROM tasks "
                "WHERE created_at >= datetime('now', '-7 days') "
                "GROUP BY agent_type, status ORDER BY agent_type"
            )
            # Total counts
            total_activities = (await db.execute_fetchall(
                "SELECT COUNT(*) FROM activity_log WHERE created_at >= datetime('now', '-7 days')"
            ))[0][0] or 0
            total_tasks = (await db.execute_fetchall(
                "SELECT COUNT(*) FROM tasks WHERE created_at >= datetime('now', '-7 days')"
            ))[0][0] or 0
    except Exception as e:
        return {"error": f"DB read error: {e}", "agent_metrics": [], "suggestions": []}

    # Build per-agent metrics
    agent_data = {}
    for row in act_rows:
        at = row[0] or "unknown"
        level = row[1] or "info"
        cnt = row[2] or 0
        if at not in agent_data:
            agent_data[at] = {"agent_type": at, "total": 0, "errors": 0, "warnings": 0}
        agent_data[at]["total"] += cnt
        if level == "error":
            agent_data[at]["errors"] += cnt
        elif level == "warning":
            agent_data[at]["warnings"] += cnt

    # Merge task data
    for row in task_rows:
        at = row[0] or "unknown"
        status = row[1] or "pending"
        cnt = row[2] or 0
        if at not in agent_data:
            agent_data[at] = {"agent_type": at, "total": 0, "errors": 0, "warnings": 0}
        agent_data[at]["total"] += cnt
        if status == "failed":
            agent_data[at]["errors"] += cnt

    metrics = []
    suggestions = []
    for at, d in sorted(agent_data.items()):
        success_rate = round((d["total"] - d["errors"]) / d["total"] * 100, 1) if d["total"] else 100.0
        d["success_rate"] = success_rate
        metrics.append(d)
        if d["errors"] > 0 and d["total"] >= 3:
            suggestions.append(
                f"{at}: 成功率 {success_rate}% ({d['errors']}/{d['total']} 错误)"
            )

    if not suggestions:
        suggestions.append("所有 Agent 运行正常，无需优化")

    return {
        "agent_metrics": metrics,
        "suggestions": suggestions,
        "total_activities": total_activities,
        "total_tasks": total_tasks,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/evolution")
async def evolution_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "evolution.html"))

# ─── Weekly Reports (周报) ────────────────────────────────────────────────────
@app.get("/api/hq/weekly-reports")
async def hq_weekly_reports():
    """Return cached weekly reports."""
    return {"data": CACHE.get("weekly_reports", [])}

@app.get("/api/hq/report/{report_id}")
async def hq_report_detail(report_id: int):
    """Return full report with HTML content."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            rows = await db.execute_fetchall(
                "SELECT id, period_start, period_end, summary, html_content, created_at, recipient_count "
                "FROM weekly_reports WHERE id = ?",
                (report_id,)
            )
            if not rows:
                raise HTTPException(status_code=404, detail="Report not found")
            r = rows[0]
            return {
                "id": r[0], "period_start": r[1], "period_end": r[2],
                "summary": r[3], "html_content": r[4], "created_at": r[5],
                "recipient_count": r[6],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports")
async def reports_page():
    """Weekly reports listing page."""
    return FileResponse(os.path.join(os.path.dirname(__file__), "reports.html"))

@app.get("/report/{report_id}")
async def report_detail_page(report_id: int):
    """Single report detail page."""
    return FileResponse(os.path.join(os.path.dirname(__file__), "report_detail.html"))

# ─── Timeline (统一时间线) ──────────────────────────────────────────────────
@app.get("/api/hq/timeline")
async def get_timeline(limit: int = 50, offset: int = 0):
    """Unified chronological event feed across all modules."""
    events = []
    # Activities from activity_log
    if os.path.exists(DB_PATH):
        try:
            import aiosqlite
            async with aiosqlite.connect(DB_PATH) as db:
                act_rows = await db.execute_fetchall(
                    "SELECT agent_type, level, message, created_at FROM activity_log "
                    "ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
                )
                for row in act_rows:
                    events.append({
                        "type": "activity",
                        "source": row[0] or "system",
                        "level": row[1] or "info",
                        "title": (row[2] or "")[:100],
                        "time": row[3] or "",
                    })
                lead_rows = await db.execute_fetchall(
                    "SELECT name, email, product_interest, status, created_at FROM leads "
                    "ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
                )
                for row in lead_rows:
                    events.append({
                        "type": "lead",
                        "source": "sales",
                        "level": "info",
                        "title": f"New lead: {row[0] or 'Unknown'} ({row[1] or ''}) — {row[2] or ''}",
                        "time": row[4] or "",
                    })
                ext_rows = await db.execute_fetchall(
                    "SELECT title, platform, status, score, created_at FROM external_orders "
                    "ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
                )
                for row in ext_rows:
                    score_str = f" Score:{row[3]}" if row[3] else ""
                    events.append({
                        "type": "order",
                        "source": row[1] or "external",
                        "level": "info",
                        "title": f"Order {row[2]}: {row[0] or 'Untitled'}{score_str}",
                        "time": row[4] or "",
                    })
        except Exception:
            pass
    events.sort(key=lambda e: e.get("time", ""), reverse=True)
    return {"data": events[:limit], "total": len(events)}


# ─── Agent Control Center ───────────────────────────────────────────────────
@app.get("/api/hq/agents")
async def get_agents():
    """List all 16 agents with status from Polsia Fork."""
    polsia_url = "http://localhost:8001/api/v1/agents"
    trigger_url = "http://localhost:8001/api/v1/agents/status"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(polsia_url, headers={"X-API-Key": "dev-key"})
            agents = resp.json() if resp.is_success else []
            status_resp = await client.get(trigger_url, headers={"X-API-Key": "dev-key"})
            status_map = status_resp.json() if status_resp.is_success else {}
    except Exception:
        agents = []
        status_map = {}
    all_types = ["orchestrator", "social_media", "customer_support", "competitor_research",
                 "business_planning", "code_generation", "deployment", "finance",
                 "email_outreach", "ads_management", "order_scanner", "order_fulfiller",
                 "lead_nurturing", "deploy_agent", "monitor", "evolution"]
    names = {"orchestrator": "Orchestrator", "social_media": "Social Media",
             "customer_support": "Customer Support", "competitor_research": "Competitor Research",
             "business_planning": "Business Planning", "code_generation": "Code Generation",
             "deployment": "Deployment", "finance": "Finance", "email_outreach": "Email Outreach",
             "ads_management": "Ads Management", "order_scanner": "Order Scanner",
             "order_fulfiller": "Order Fulfiller", "lead_nurturing": "Lead Nurturing",
             "deploy_agent": "Deploy Agent", "monitor": "Monitor (守望者)", "evolution": "Evolution (进化办)"}
    emojis = {"orchestrator": "🧠", "social_media": "📱", "customer_support": "💬",
              "competitor_research": "🔍", "business_planning": "📊", "code_generation": "💻",
              "deployment": "🚀", "finance": "💰", "email_outreach": "📧", "ads_management": "📢",
              "order_scanner": "🔎", "order_fulfiller": "✅", "lead_nurturing": "🌱",
              "deploy_agent": "⚙️", "monitor": "👁️", "evolution": "🧬"}
    agent_map = {a.get("agent_type", ""): a for a in agents if isinstance(a, dict)}
    result = []
    for at in all_types:
        existing = agent_map.get(at, {})
        result.append({
            "agent_type": at,
            "name": names.get(at, at.replace("_", " ").title()),
            "emoji": emojis.get(at, "🤖"),
            "status": existing.get("status", "idle") if isinstance(existing, dict) else "idle",
            "last_run": existing.get("last_run") if isinstance(existing, dict) else None,
        })
    return {"data": result, "total": len(result)}


@app.post("/api/hq/agents/{agent_type}/trigger")
async def trigger_agent(agent_type: str):
    """Trigger an agent via Polsia Fork API."""
    polsia_url = f"http://localhost:8001/api/v1/agents/{agent_type}/trigger"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(polsia_url, headers={"X-API-Key": "dev-key"})
            if resp.is_success:
                return {"ok": True, "message": f"{agent_type} triggered"}
            return JSONResponse(status_code=resp.status_code, content={"ok": False, "error": resp.text})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polsia unreachable: {e}")


# ─── Global Search ──────────────────────────────────────────────────────────
@app.get("/api/hq/search")
async def global_search(q: str = ""):
    """Search across all HQ modules."""
    if not q or len(q) < 2:
        return {"data": []}
    ql = q.lower()
    results = []
    # Leads
    for l in CACHE["leads"]:
        if ql in l.get("name", "").lower() or ql in l.get("email", "").lower() or ql in l.get("company", "").lower():
            results.append({"module": "leads", "label": f"Lead: {l['name']} ({l['email']})",
                            "url": "/leads", "status": l.get("status", "")})
    # Orders
    for o in CACHE["orders"]:
        if ql in o.get("title", "").lower() or ql in o.get("agent_type", "").lower():
            results.append({"module": "orders", "label": f"Task: {o['title'][:60]}",
                            "url": "/orders", "status": o.get("status", "")})
    # External orders
    for o in CACHE.get("external_orders", []):
        if ql in o.get("title", "").lower() or ql in o.get("platform", "").lower():
            results.append({"module": "external_orders", "label": f"Order: {o['title'][:60]} ({o.get('platform','')})",
                            "url": "/orders", "status": o.get("status", "")})
    # Customers (leads)
    for l in CACHE["leads"]:
        if ql in l.get("name", "").lower() or ql in l.get("email", "").lower() or ql in l.get("company", "").lower():
            results.append({"module": "customers", "label": f"Customer: {l['name']} ({l.get('company','')})",
                            "url": f"/customer/{l['id']}", "status": l.get("status", "")})
    # Employees
    for e in CACHE["employees"]:
        if ql in e.get("name", "").lower() or ql in e.get("role", "").lower():
            results.append({"module": "employees", "label": f"Employee: {e['name']} — {e.get('role','')}",
                            "url": "/employees", "status": e.get("status", "")})
    # Proposals
    for p in CACHE.get("proposals", []):
        if ql in str(p.get("summary", "")).lower() or ql in str(p.get("status", "")).lower():
            results.append({"module": "proposals", "label": f"Proposal #{p['id']}: {p.get('summary','')[:60]}",
                            "url": "/proposals", "status": p.get("status", "")})
    return {"data": results[:20], "total": len(results)}


# ─── Analytics ──────────────────────────────────────────────────────────────
@app.get("/api/hq/analytics/revenue-trend")
async def revenue_trend():
    """Revenue history with linear regression projection (next 30 days)."""
    rev = CACHE["revenue_history"]
    if not rev:
        return {"history": [], "projection": [], "summary": {"current_mrr": 0, "next_month_projection": 0, "growth_rate": 0}}
    points = [(i, r["amount"]) for i, r in enumerate(rev)]
    n = len(points)
    if n < 2:
        return {"history": rev, "projection": [], "summary": {"current_mrr": rev[-1]["amount"], "next_month_projection": rev[-1]["amount"], "growth_rate": 0}}
    sum_x = sum(i for i, _ in points)
    sum_y = sum(v for _, v in points)
    sum_xy = sum(i * v for i, v in points)
    sum_xx = sum(i * i for i, _ in points)
    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
    intercept = (sum_y - slope * sum_x) / n
    projection = []
    for i in range(n, n + 30):
        projection.append({"day": i - n + 1, "projected_mrr": round(slope * i + intercept, 2)})
    current_mrr = rev[-1]["amount"]
    next_mrr = round(slope * (n + 29) + intercept, 2)
    growth_rate = round((next_mrr - current_mrr) / current_mrr * 100, 1) if current_mrr > 0 else 0
    return {
        "history": [{"date": r["date"], "amount": r["amount"]} for r in rev],
        "projection": projection,
        "summary": {"current_mrr": current_mrr, "next_month_projection": next_mrr, "growth_rate": growth_rate, "slope_per_day": round(slope, 2)},
    }

@app.get("/api/hq/analytics/lead-funnel")
async def lead_funnel():
    """Lead status distribution + conversion rates."""
    leads = CACHE["leads"]
    total = len(leads)
    stages = {"new": 0, "contacted": 0, "qualified": 0, "proposal": 0, "negotiation": 0, "won": 0, "lost": 0}
    for l in leads:
        s = l.get("status", "new")
        if s in stages:
            stages[s] += 1
    won_stages = stages["won"] + stages["lost"]
    conversion_rate = round(stages["won"] / total * 100, 1) if total > 0 else 0
    return {
        "total": total,
        "stages": stages,
        "conversion_rate": conversion_rate,
        "won": stages["won"],
        "lost": stages["lost"],
    }

@app.get("/api/hq/analytics/agent-performance")
async def agent_performance():
    """Per-agent metrics from tasks and activity log."""
    orders = CACHE["orders"]
    if not orders:
        return {"agents": [], "summary": {"total_agents": 0, "avg_success_rate": 0}}
    agent_stats = {}
    for o in orders:
        atype = o.get("agent_type", "unknown")
        if atype not in agent_stats:
            agent_stats[atype] = {"total": 0, "completed": 0, "failed": 0, "pending": 0}
        agent_stats[atype]["total"] += 1
        s = o.get("status", "pending")
        if s in ("done", "completed"):
            agent_stats[atype]["completed"] += 1
        elif s == "failed":
            agent_stats[atype]["failed"] += 1
        else:
            agent_stats[atype]["pending"] += 1
    agents = []
    for aname, stats in sorted(agent_stats.items()):
        rate = round(stats["completed"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
        agents.append({
            "name": aname.replace("_", " ").title(),
            "agent_type": aname,
            "total": stats["total"],
            "completed": stats["completed"],
            "failed": stats["failed"],
            "pending": stats["pending"],
            "success_rate": rate,
        })
    avg_rate = round(sum(a["success_rate"] for a in agents) / len(agents), 1) if agents else 0
    return {"agents": agents, "summary": {"total_agents": len(agents), "avg_success_rate": avg_rate}}

# ─── Notifications ──────────────────────────────────────────────────────────
@app.get("/api/hq/notifications")
async def get_notifications():
    """Count new/unread items across modules."""
    new_leads = len([l for l in CACHE["leads"] if l.get("status") == "new"])
    pending_orders = len([o for o in CACHE.get("external_orders", []) if o.get("status") in ("pending", "scanned")])
    active_internal = len([o for o in CACHE["orders"] if o.get("status") in ("pending", "in_progress")])
    draft_proposals = len([p for p in CACHE.get("proposals", []) if p.get("status") in ("draft", "sent")])
    nurture_followups = len([a for a in CACHE.get("activity_log", [])
                             if a.get("agent_type") == "proposal_nurture"
                             and a.get("action") == "proposal_needs_followup"])
    return {
        "new_leads": new_leads,
        "pending_external_orders": pending_orders,
        "active_tasks": active_internal,
        "draft_proposals": draft_proposals,
        "nurture_followups": nurture_followups,
        "total": new_leads + pending_orders + active_internal + draft_proposals + nurture_followups,
    }


# ─── CRM (Customer Relationship Management) ─────────────────────────────────

@app.get("/api/hq/customers")
async def get_customers(q: str = "", status: str = ""):
    """Unified customer view: leads + linked orders."""
    leads = CACHE["leads"]
    orders = CACHE.get("external_orders", [])
    customers = []
    for l in leads:
        lid = l.get("id", 0)
        lname = l.get("name", "Unknown")
        lemail = l.get("email", "")
        customer_orders = [o for o in orders if
                           lname.lower() in o.get("title", "").lower() or
                           lemail.lower() in o.get("title", "").lower()]
        total_value = sum((o.get("budget_min", 0) or 0) + (o.get("budget_max", 0) or 0) for o in customer_orders) // 2
        customers.append({
            "id": lid, "name": lname, "email": lemail,
            "company": l.get("company", ""), "phone": l.get("phone", ""),
            "product_interest": l.get("product_interest", ""),
            "lead_status": l.get("status", "new"),
            "created_at": l.get("created_at", ""),
            "order_count": len(customer_orders),
            "total_order_value": total_value,
            "last_contact": max([o.get("created_at", "") for o in customer_orders] + [l.get("created_at", "")]),
        })
    if status:
        customers = [c for c in customers if c["lead_status"] == status]
    if q:
        ql = q.lower()
        customers = [c for c in customers if ql in c["name"].lower() or ql in c["email"].lower() or ql in c["company"].lower()]
    customers.sort(key=lambda c: c.get("last_contact", ""), reverse=True)
    total_v = sum(c["total_order_value"] for c in customers)
    return {"data": customers, "total": len(customers),
            "summary": {"total_customers": len(customers), "total_leads": len(leads),
                        "total_order_value": total_v, "avg_order_value": round(total_v / len(customers), 2) if customers else 0}}


@app.get("/api/hq/customers/{customer_id}")
async def get_customer_detail(customer_id: int):
    """Detailed customer view with orders and activity timeline."""
    leads = CACHE["leads"]
    orders = CACHE.get("external_orders", [])
    l = next((x for x in leads if x.get("id") == customer_id), None)
    if not l:
        raise HTTPException(status_code=404, detail="Customer not found")
    lname = l.get("name", "Unknown")
    lemail = l.get("email", "")
    customer_orders = [o for o in orders if lname.lower() in o.get("title", "").lower() or lemail.lower() in o.get("title", "").lower()]
    timeline = []
    for o in customer_orders:
        timeline.append({"type": "order", "title": f"Order {o['status']}: {o['title']}",
                         "time": o.get("created_at", ""), "detail": f"{o.get('platform','')} | Score: {o.get('score','N/A')}"})
    timeline.append({"type": "lead", "title": f"Lead created ({l.get('product_interest','')})",
                     "time": l.get("created_at", ""), "detail": f"Status: {l.get('status','new')}"})
    timeline.sort(key=lambda e: e.get("time", ""), reverse=True)
    return {"customer": {"id": l.get("id"), "name": lname, "email": lemail, "company": l.get("company",""),
                         "phone": l.get("phone",""), "product_interest": l.get("product_interest",""),
                         "lead_status": l.get("status","new"), "source_url": l.get("source_url",""),
                         "created_at": l.get("created_at","")},
            "orders": customer_orders, "timeline": timeline}


# ─── New HTML Pages ─────────────────────────────────────────────────────────
@app.get("/timeline")
async def timeline_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "timeline.html"))

@app.get("/agents")
async def agents_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "agents.html"))

@app.get("/analytics")
async def analytics_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "analytics.html"))

@app.get("/customers")
async def customers_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "customers.html"))

@app.get("/customer/{customer_id}")
async def customer_detail_page(customer_id: int):
    return FileResponse(os.path.join(os.path.dirname(__file__), "customer_detail.html"))

# ─── Market Intelligence Briefing ────────────────────────────────────────────

BRIEFINGS_DIR = os.environ.get(
    "BRIEFINGS_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "polsia-fork", "data",
    ),
)

@app.get("/api/hq/briefings")
async def get_briefings(limit: int = 10):
    """Return recent market intelligence briefings."""
    import json
    path = os.path.join(BRIEFINGS_DIR, "briefings.json")
    if not os.path.exists(path):
        return {"briefings": []}
    with open(path) as f:
        data = json.load(f)
    return {"briefings": data[:limit]}

@app.get("/briefing")
async def briefing_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "briefing.html"))

# ─── Model Routing Gateway ────────────────────────────────────────────────────

MODEL_PROFILES = [
    {"name":"DeepSeek V4 Flash","env":"DEEPSEEK_API_KEY","base_url":"https://api.deepseek.com/v1","model":"deepseek-chat","capabilities":["analysis","content_gen","classification","summarization","conversation"],"priority":1},
    {"name":"DeepSeek V4 Flash (via LLM_API_KEY)","env":"LLM_API_KEY","base_url":"https://api.deepseek.com/v1","model":"deepseek-chat","capabilities":["analysis","content_gen","classification","summarization","conversation"],"priority":2},
    {"name":"Volc Engine Doubao-pro","env":"VOLC_ENGINE_API_KEY","base_url":"https://ark.cn-beijing.volces.com/api/v3","model":"doubao-pro-32k","capabilities":["content_gen","analysis","summarization","conversation"],"priority":3},
    {"name":"Volc Engine Doubao-lite","env":"VOLC_ENGINE_API_KEY","base_url":"https://ark.cn-beijing.volces.com/api/v3","model":"doubao-lite-32k","capabilities":["classification","summarization"],"priority":4},
    {"name":"Mock (no API key)","env":"","base_url":"","model":"mock","capabilities":["analysis","content_gen","code","classification","summarization","conversation"],"priority":99},
]

AGENT_MODEL_MAP = {
    "orchestrator":"analysis","social_media":"content_gen","competitor_research":"analysis",
    "business_planning":"analysis","deployment":"code","finance":"analysis",
    "ads_management":"analysis","email_outreach":"conversation","code_generation":"code",
    "customer_support":"conversation","order_scanner":"classification","order_fulfiller":"analysis",
    "lead_nurturing":"conversation","deploy_agent":"code","monitor":"analysis",
    "evolution":"analysis","market_intel":"summarization",
}

@app.get("/api/hq/models")
async def hq_models():
    """Return model profiles with live availability status."""
    import os
    result = []
    for p in MODEL_PROFILES:
        key = os.environ.get(p["env"], "") if p["env"] else "mock"
        result.append({
            **p,
            "available": bool(key),
            "key_preview": key[:8] + "…" if key and key != "mock" else ("mock" if not p["env"] else "❌"),
        })
    return {"profiles": result, "agent_mapping": AGENT_MODEL_MAP}

@app.get("/models")
async def models_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "model_router.html"))


@app.get("/sandbox")
async def sandbox_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "sandbox.html"))


# ─── Sandbox API ────────────────────────────────────────────────────────────


@app.get("/api/hq/sandbox")
async def hq_sandbox_summary():
    """Sandbox dashboard data — read Polsia SQLite sandbox state."""
    import json
    import os as _os
    sandbox_dir = _os.path.join(_os.path.dirname(DB_PATH), ".sandbox")
    pending_file = _os.path.join(sandbox_dir, "pending_actions.json")
    rejected_file = _os.path.join(sandbox_dir, "rejected_actions.json")

    def _load(p: str) -> list:
        if not _os.path.exists(p):
            return []
        try:
            with open(p) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    pending = _load(pending_file)
    rejected = _load(rejected_file)
    pending_active = [a for a in pending if a["status"] == "pending"]

    # Enrich with Polsia sandbox summary
    polsia_url = f"http://127.0.0.1:{POLSIA_PORT}/api/v1/sandbox/summary"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(polsia_url)
            polsia_data = r.json()
    except Exception:
        polsia_data = {"sandbox_enabled": False}

    return {
        "sandbox_enabled": polsia_data.get("sandbox_enabled", True),
        "pending_count": len(pending_active),
        "total_pending": len(pending),
        "approved_count": sum(1 for a in pending if a["status"] == "approved"),
        "rejected_count": len(rejected),
        "pending_actions": pending_active,
        "recent_actions": pending[:10] if pending else [],
    }


@app.get("/api/hq/sandbox/pending")
async def hq_sandbox_pending():
    """Proxy: get all pending actions from Polsia sandbox."""
    polsia_url = f"http://127.0.0.1:{POLSIA_PORT}/api/v1/sandbox/pending"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(polsia_url)
            return r.json()
    except Exception as e:
        return {"error": str(e), "actions": []}


@app.post("/api/hq/sandbox/pending/{action_id}/approve")
async def hq_sandbox_approve(action_id: int):
    """Proxy: approve a pending action."""
    polsia_url = f"http://127.0.0.1:{POLSIA_PORT}/api/v1/sandbox/pending/{action_id}/approve"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(polsia_url)
            return r.json()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/hq/sandbox/pending/{action_id}/reject")
async def hq_sandbox_reject(action_id: int, reason: str = ""):
    """Proxy: reject a pending action."""
    polsia_url = f"http://127.0.0.1:{POLSIA_PORT}/api/v1/sandbox/pending/{action_id}/reject"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(polsia_url, params={"reason": reason})
            return r.json()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/hq/sandbox/cleanup")
async def hq_sandbox_cleanup(hours: int = 72):
    """Proxy: cleanup expired pending actions."""
    polsia_url = f"http://127.0.0.1:{POLSIA_PORT}/api/v1/sandbox/cleanup"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(polsia_url, params={"hours": hours})
            return r.json()
    except Exception as e:
        return {"error": str(e)}


# ─── Deploy Execution (部署执行) ──────────────────────────────────────────────
@app.post("/api/hq/orders/{order_id}/execute-deploy")
async def hq_execute_deploy(order_id: int):
    """Proxy: trigger deployment execution for an order."""
    polsia_url = f"http://127.0.0.1:{POLSIA_PORT}/api/v1/orders/external/{order_id}/execute-deploy"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(polsia_url, headers={"X-API-Key": "dev-key"})
            return r.json()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/hq/orders/{order_id}/execution-status")
async def hq_execution_status(order_id: int):
    """Proxy: get deployment execution status."""
    polsia_url = f"http://127.0.0.1:{POLSIA_PORT}/api/v1/orders/external/{order_id}/execution-status"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(polsia_url, headers={"X-API-Key": "dev-key"})
            return r.json()
    except Exception as e:
        return {"error": str(e)}


# ─── Task Board (任务管理) ──────────────────────────────────────────────────
@app.get("/api/hq/tasks")
async def get_tasks(status: str = "", agent: str = "", search: str = ""):
    """Return tasks from Polsia DB with optional filters."""
    if not os.path.exists(DB_PATH):
        return {"tasks": [], "total": 0, "filtered": 0}
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            import json
            rows = await db.execute_fetchall(
                "SELECT id, title, description, status, priority, agent_type, "
                "created_at, updated_at, assigned_to, result, metadata_json, "
                "due_date, parent_task_id FROM tasks ORDER BY created_at DESC"
            )
            tasks = []
            for r in rows:
                t = {
                    "id": r[0], "title": r[1], "description": r[2],
                    "status": r[3], "priority": r[4], "agent_type": r[5],
                    "created_at": r[6], "updated_at": r[7],
                    "assigned_to": r[8], "result": r[9],
                    "metadata": json.loads(r[10]) if r[10] else {},
                    "due_date": r[11], "parent_task_id": r[12],
                }
                tasks.append(t)
        total = len(tasks)
        # Apply filters
        if status:
            statuses = [s.strip() for s in status.split(",")]
            tasks = [t for t in tasks if t["status"] in statuses]
        if agent:
            agents = [a.strip() for a in agent.split(",")]
            tasks = [t for t in tasks if t["agent_type"] in agents]
        if search:
            sl = search.lower()
            tasks = [t for t in tasks if
                     sl in (t["title"] or "").lower() or
                     sl in (t["description"] or "").lower()]
        return {"tasks": tasks, "total": total, "filtered": len(tasks)}
    except Exception as e:
        return {"error": str(e), "tasks": [], "total": 0, "filtered": 0}


@app.get("/api/hq/tasks/summary")
async def get_tasks_summary():
    """Return task summary (counts per status, per agent)."""
    if not os.path.exists(DB_PATH):
        return {"by_status": {}, "by_agent": {}, "total": 0}
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            status_rows = await db.execute_fetchall(
                "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
            )
            agent_rows = await db.execute_fetchall(
                "SELECT agent_type, status, COUNT(*) as cnt FROM tasks "
                "GROUP BY agent_type, status ORDER BY agent_type"
            )
        by_status = {r[0]: r[1] for r in status_rows}
        by_agent = {}
        for r in agent_rows:
            a = r[0] or "unknown"
            if a not in by_agent:
                by_agent[a] = {"completed": 0, "pending": 0, "failed": 0,
                                "in_progress": 0, "cancelled": 0,
                                "blocked": 0, "paused": 0, "in_review": 0}
            s = r[1] or "pending"
            by_agent[a][s] = by_agent[a].get(s, 0) + r[2]
        return {"by_status": by_status, "by_agent": by_agent, "total": sum(by_status.values())}
    except Exception as e:
        return {"error": str(e), "by_status": {}, "by_agent": {}, "total": 0}


@app.get("/task-board")
async def task_board_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "task_board.html"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=13001)
