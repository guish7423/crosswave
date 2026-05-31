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
            agents = await db.execute_fetchall(
                "SELECT type, name, role, status, id FROM agents ORDER BY id"
            )
            tasks = await db.execute_fetchall(
                "SELECT title, status, agent_type, created_at, id FROM tasks ORDER BY created_at DESC LIMIT 100"
            )
    except Exception as e:
        print(f"[bridge] DB read error: {e}")
        return

    employees = []
    for row in agents:
        employees.append({
            "name": row[1] or row[0],
            "type": row[3] or "ai",
            "role": row[2] or row[0],
            "status": row[3] or "idle",
            "agent_type": row[0],
            "source_id": row[4],
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
        {"name": "Polsia Fork", "slug": "polsia", "status": "active", "monthly_revenue": 0, "customer_count": 0},
        {"name": "HiveMind", "slug": "hivemind", "status": "development", "monthly_revenue": 0, "customer_count": 0},
    ]
    CACHE["employees"] = employees
    CACHE["lines"] = predef_lines
    CACHE["orders"] = orders
    CACHE["last_sync"] = datetime.now(timezone.utc).isoformat()
    print(f"[bridge] Synced: {len(employees)} employees, {len(orders)} tasks")

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
