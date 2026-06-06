"""HQ API routes — data endpoints (NocoBase-first, CACHE-fallback)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Query

from hq.domains.data import (
    CACHE,
    polsia_sync,
)

router = APIRouter(prefix="/api/hq", tags=["api"])


# ─── Fallback helpers ─────────────────────────────────────────────────────────

async def _nb_fetch(method_name: str, *args, **kwargs):
    """Try NocoBase read, return None on failure."""
    try:
        from hq.nocobase_client import get_summary, get_employees, get_lines, get_external_orders
        from hq.nocobase_client import get_leads as _get_leads
        from hq.nocobase_client import get_tasks, get_proposals, get_expenses, get_revenue_history
        readers = {
            "summary": get_summary,
            "employees": get_employees,
            "lines": get_lines,
            "external_orders": get_external_orders,
            "leads": _get_leads,
            "tasks": get_tasks,
            "proposals": get_proposals,
            "expenses": get_expenses,
            "revenue_history": get_revenue_history,
        }
        fn = readers.get(method_name)
        if fn:
            return await fn(*args, **kwargs)
        return None
    except Exception:
        return None


async def _nb_available() -> bool:
    """Quick check: NocoBase has employees data."""
    emps = await _nb_fetch("employees")
    return bool(emps and len(emps) > 0)


# ─── CACHE fallback (preserved for when NocoBase is unavailable) ──────────────

def _summary_from_cache() -> dict:
    """Build summary dict from in-memory CACHE (fallback)."""
    emps = CACHE["employees"]
    lines = CACHE["lines"]
    orders = CACHE["orders"]
    active_orders = [o for o in orders if o["status"] in ("pending", "in_progress")]
    total_mrr = sum(item.get("monthly_revenue", 0) for item in lines)
    CACHE["mrr"] = total_mrr
    total_customers = sum(item.get("customer_count", 0) for item in lines)
    leads = CACHE["leads"]
    return {
        "employees": {
            "total": len(emps),
            "active": len([e for e in emps if e.get("status") in ("idle", "running")]),
            "status_distribution": {s: len([e for e in emps if e.get("status") == s]) for s in set(e["status"] for e in emps)},
        },
        "lines": [
            {"name": item["name"], "slug": item.get("slug", ""), "status": item.get("status", "unknown"),
             "health": "healthy" if item.get("status") == "active" else "warning",
             "monthly_revenue": item.get("monthly_revenue", 0),
             "customer_count": item.get("customer_count", 0)}
            for item in lines
        ],
        "orders": {
            "total": len(orders),
            "active": len(active_orders),
            "status_distribution": {s: len([o for o in orders if o["status"] == s]) for s in set(o["status"] for o in orders)},
        },
        "mrr": total_mrr,
        "customers": total_customers,
        "leads": {
            "total": len(leads),
            "new": len([lead for lead in leads if lead.get("status") == "new"]),
        },
        "last_sync": CACHE.get("last_sync"),
        "source": "cache",
    }


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/summary")
async def summary(source: str = Query("auto", description="data source: auto, cache, or nocobase")):
    """Dashboard summary — tries NocoBase first (if 'auto'), falls back to in-memory CACHE."""
    if source != "cache":
        nb = await _nb_fetch("summary")
        if nb and nb.get("employees", {}).get("total", 0) > 0:
            nb["last_sync"] = CACHE.get("last_sync")
            return nb
    return _summary_from_cache()


@router.get("/employees")
async def get_employees():
    nb = await _nb_fetch("employees")
    if nb:
        return {"data": nb}
    return {"data": CACHE["employees"]}


@router.get("/orders")
async def get_orders(status: str | None = None, platform: str | None = None):
    """Orders from NocoBase tasks collection (Polsia Fork tasks)."""
    nb = await _nb_fetch("tasks")
    if nb:
        result = [
            {"title": t.get("title", ""), "status": t.get("status", "pending"),
             "agent_type": t.get("agent_type", ""), "created_at": t.get("created_at", ""),
             "source_id": t.get("source_id"), "platform": "internal"}
            for t in nb
        ]
    else:
        result = list(CACHE["orders"])
    if status:
        result = [o for o in result if o.get("status") == status]
    if platform:
        result = [o for o in result if o.get("platform") == platform]
    return {"data": result}


@router.get("/leads")
async def get_leads(status: str | None = None):
    nb = await _nb_fetch("leads")
    if nb:
        result = [
            {"id": l.get("id"), "name": l.get("name", ""), "email": l.get("email", ""),
             "company": l.get("company", ""), "product_interest": l.get("product_interest", ""),
             "budget_range": l.get("budget_range", ""), "message": l.get("message", ""),
             "status": l.get("status", "new"), "source_page": l.get("source_page", ""),
             "created_at": l.get("created_at", "")}
            for l in nb
        ]
        total = len(result)
        new_count = len([l for l in result if l.get("status") == "new"])
    else:
        result = list(CACHE["leads"])
        total = len(CACHE["leads"])
        new_count = len([lead for lead in CACHE["leads"] if lead.get("status") == "new"])
    if status:
        result = [lead for lead in result if lead.get("status") == status]
    return {"data": result, "total": total, "new_count": new_count}


@router.get("/external-orders")
async def get_external_orders(platform: str | None = None, status: str | None = None):
    nb = await _nb_fetch("external_orders")
    if nb:
        result = [
            {"id": o.get("id"), "title": o.get("title", ""), "platform": o.get("platform", ""),
             "external_id": o.get("external_id", ""), "status": o.get("status", "scanned"),
             "budget_min": o.get("budget_min"), "budget_max": o.get("budget_max"),
             "currency": o.get("currency", "USD"), "score": o.get("score"),
             "score_reason": o.get("score_reason", ""),
             "assigned_agent": o.get("assigned_agent", ""), "created_at": o.get("created_at", ""),
             "deployment_plan": o.get("description", ""),
             "deliverables": o.get("deliverables", []),
             "delivery_notes": o.get("delivery_notes", "")}
            for o in nb
        ]
        total = len(result)
    else:
        result = list(CACHE["external_orders"])
        total = len(CACHE["external_orders"])
    if platform:
        result = [o for o in result if o.get("platform") == platform]
    if status:
        result = [o for o in result if o.get("status") == status]
    return {"data": result, "total": total}


@router.get("/lines")
async def get_lines():
    nb = await _nb_fetch("lines")
    if nb:
        return {"data": [
            {"name": l.get("name", l.get("slug", "")), "slug": l.get("slug", ""),
             "status": l.get("status", "unknown"), "monthly_revenue": l.get("monthly_revenue", 0) or 0,
             "customer_count": l.get("customer_count", 0) or 0}
            for l in nb
        ]}
    return {"data": CACHE["lines"]}


@router.get("/deployment-orders")
async def get_deployment_orders(status: str | None = None):
    """Fetch deployment orders from CrossDeploy service."""
    from hq.crossdeploy_client import get_deployment_orders as _fetch_orders  # noqa: lazy import

    orders = await _fetch_orders(status)
    return {"data": orders, "total": len(orders)}


@router.get("/deployment-tiers")
async def get_deployment_tiers():
    """Fetch available deployment tiers/pricing from CrossDeploy."""
    from hq.crossdeploy_client import get_deployment_tiers  # noqa: lazy import

    tiers = await get_deployment_tiers()
    return {"tiers": tiers}


@router.get("/sync")
async def manual_sync():
    await polsia_sync()
    return {"ok": True, "synced_at": datetime.now(UTC).isoformat()}


@router.get("/finances")
async def get_finances():
    nb_exp = await _nb_fetch("expenses")
    nb_rev = await _nb_fetch("revenue_history")
    expenses = nb_exp if nb_exp else CACHE["expenses"]
    revenue = nb_rev if nb_rev else CACHE["revenue_history"]
    total_costs = sum(e["amount"] for e in expenses)
    total_revenue = sum(r["amount"] for r in revenue)
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
        "mrr": CACHE.get("mrr", sum(r["amount"] for r in revenue[-3:] if revenue) // 3 if revenue else 0),
        "arr": CACHE.get("mrr", 0) * 12,
        "expense_by_category": [{"category": k, "amount": v} for k, v in sorted(expense_by_cat.items(), key=lambda x: -x[1])],
        "revenue_by_month": [{"month": k, "revenue": v} for k, v in sorted(rev_by_month.items())],
    }


@router.get("/reports")
async def get_reports():
    # Tasks from NocoBase
    nb_tasks = await _nb_fetch("tasks")
    if nb_tasks:
        orders_data = [
            {"title": t.get("title", ""), "status": t.get("status", "pending"),
             "agent_type": t.get("agent_type", ""), "created_at": t.get("created_at", ""),
             "id": t.get("source_id")}
            for t in nb_tasks
        ]
    else:
        orders_data = list(CACHE["orders"])
    nb_emps = await _nb_fetch("employees")
    employees_data = nb_emps if nb_emps else CACHE["employees"]

    total_tasks = len(orders_data)
    completed = len([o for o in orders_data if o["status"] == "completed"])
    failed = len([o for o in orders_data if o["status"] == "failed"])
    agent_perf = {}
    for o in orders_data:
        at = o.get("agent_type", "unknown")
        if at not in agent_perf:
            agent_perf[at] = {"done": 0, "failed": 0, "total": 0}
        agent_perf[at]["total"] += 1
        if o["status"] == "completed":
            agent_perf[at]["done"] += 1
        elif o["status"] == "failed":
            agent_perf[at]["failed"] += 1
    task_by_day = {}
    for o in orders_data:
        d = o["created_at"][:10] if o["created_at"] else "unknown"
        task_by_day[d] = task_by_day.get(d, 0) + 1
    activity_7d = sum(v for k, v in task_by_day.items() if k >= (datetime.now(UTC).isoformat()[:10] if task_by_day else ""))
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "completion_rate": round(completed / total_tasks * 100, 1) if total_tasks else 0,
        "agent_performance": [{"agent": k, **v} for k, v in sorted(agent_perf.items(), key=lambda x: -x[1]["total"])],
        "task_trend": [{"date": k, "count": v} for k, v in sorted(task_by_day.items())],
        "last_7d_activity": activity_7d,
        "employee_count": len(employees_data),
    }
