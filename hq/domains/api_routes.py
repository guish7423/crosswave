"""HQ API routes — data endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Query

from hq.domains.data import (
    CACHE,
    polsia_sync,
)

router = APIRouter(prefix="/api/hq", tags=["api"])


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


@router.get("/summary")
async def summary(source: str = Query("auto", description="data source: auto, cache, or nocobase")):
    """Dashboard summary — tries NocoBase first (if 'auto'), falls back to in-memory CACHE."""
    if source != "cache":
        try:
            from hq.nocobase_client import get_summary  # noqa: lazy import
            nb = await get_summary()
            if nb.get("employees", {}).get("total", 0) > 0:
                # NocoBase has data — use it, but fill gaps from CACHE
                nb["leads"] = _summary_from_cache().get("leads", {"total": 0, "new": 0})
                nb["last_sync"] = CACHE.get("last_sync")
                return nb
        except Exception:
            pass  # fall through to CACHE
    return _summary_from_cache()


@router.get("/employees")
async def get_employees():
    return {"data": CACHE["employees"]}


@router.get("/orders")
async def get_orders(status: str | None = None, platform: str | None = None):
    result = CACHE["orders"]
    if status:
        result = [o for o in result if o.get("status") == status]
    if platform:
        result = [o for o in result if o.get("platform") == platform]
    return {"data": result}


@router.get("/leads")
async def get_leads(status: str | None = None):
    result = CACHE["leads"]
    if status:
        result = [lead for lead in result if lead.get("status") == status]
    return {"data": result, "total": len(CACHE["leads"]), "new_count": len([lead for lead in CACHE["leads"] if lead.get("status") == "new"])}


@router.get("/external-orders")
async def get_external_orders(platform: str | None = None, status: str | None = None):
    result = CACHE["external_orders"]
    if platform:
        result = [o for o in result if o.get("platform") == platform]
    if status:
        result = [o for o in result if o.get("status") == status]
    return {"data": result, "total": len(CACHE["external_orders"])}


@router.get("/lines")
async def get_lines():
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
    expenses = CACHE["expenses"]
    revenue = CACHE["revenue_history"]
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
    orders = CACHE["orders"]
    employees = CACHE["employees"]
    total_tasks = len(orders)
    completed = len([o for o in orders if o["status"] == "completed"])
    failed = len([o for o in orders if o["status"] == "failed"])
    agent_perf = {}
    for o in orders:
        at = o.get("agent_type", "unknown")
        if at not in agent_perf:
            agent_perf[at] = {"done": 0, "failed": 0, "total": 0}
        agent_perf[at]["total"] += 1
        if o["status"] == "completed":
            agent_perf[at]["done"] += 1
        elif o["status"] == "failed":
            agent_perf[at]["failed"] += 1
    task_by_day = {}
    for o in orders:
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
        "employee_count": len(employees),
    }
