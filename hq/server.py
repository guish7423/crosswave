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
app.mount("/static", StaticFiles(directory=os.path.dirname(__file__)), name="hq_static")

DB_PATH = os.environ.get("POLSIA_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "polsia-fork", "polsia.db"))
HQ_URL = os.environ.get("HQ_URL", "http://localhost:13000/api")
HQ_TOKEN = os.environ.get("HQ_TOKEN", "")

CACHE = {"employees": [], "lines": [], "orders": [], "leads": [], "external_orders": [], "expenses": [], "revenue_history": [], "last_sync": None}

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
                "SELECT id, title, platform, external_id, status, budget_min, budget_max, currency, score, score_reason, assigned_agent, created_at FROM external_orders ORDER BY created_at DESC LIMIT 100"
            )
            lead_rows = await db.execute_fetchall(
                "SELECT id, name, email, company, product_interest, budget_range, message, status, source_page, created_at FROM leads ORDER BY created_at DESC LIMIT 100"
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
        ext_orders.append({"id": row[0], "title": row[1] or "", "platform": row[2] or "", "external_id": row[3] or "", "status": row[4] or "scanned", "budget_min": row[5], "budget_max": row[6], "currency": row[7] or "USD", "score": row[8], "score_reason": row[9] or "", "assigned_agent": row[10] or "", "created_at": row[11] or ""})
    CACHE["external_orders"] = ext_orders
    print(f"[bridge] Synced: {len(employees)} employees, {len(orders)} tasks, {len(leads)} leads, {len(ext_orders)} ext orders, {len(exps)} expenses, {len(revs)} rev months")

async def periodic_sync():
    while True:
        await polsia_sync()
        await asyncio.sleep(1800)

@app.on_event("startup")
async def startup():
    asyncio.create_task(periodic_sync())

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
        "last_sync": CACHE["last_sync"],
    }

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


@app.get("/api/hq/lines")
async def get_lines():
    return {"data": CACHE["lines"]}

@app.get("/api/hq/sync")
async def trigger_sync():
    await polsia_sync()
    return {"ok": True, "synced_at": CACHE["last_sync"]}

@app.get("/")
async def dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "dashboard.html"))

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

@app.get("/reports")
async def reports_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "reports.html"))

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=13001)
