"""HQ API routes — NocoBase is the primary data source, no CACHE."""

from datetime import UTC, datetime

from fastapi import APIRouter

from hq.domains.data import polsia_sync
from hq.nocobase_client import (
    get_employees as _get_employees,
)
from hq.nocobase_client import (
    get_expenses,
    get_lines,
    get_revenue_history,
    get_summary,
    get_tasks,
)
from hq.nocobase_client import (
    get_external_orders as _get_external_orders,
)
from hq.nocobase_client import (
    get_leads as _get_leads,
)

router = APIRouter(prefix="/api/hq", tags=["api"])


async def _empty_if_none(data):
    return data if data is not None else []


@router.get("/summary")
async def summary():
    """Dashboard summary from NocoBase."""
    nb = await get_summary()
    if nb and nb.get("employees", {}).get("total", 0) > 0:
        nb["last_sync"] = None
        return nb
    return {
        "employees": {"total": 0, "active": 0, "status_distribution": {}},
        "lines": [],
        "orders": {"total": 0, "active": 0, "status_distribution": {}},
        "mrr": 0, "customers": 0,
        "leads": {"total": 0, "new": 0},
        "last_sync": None,
        "source": "nocobase",
    }


@router.get("/employees")
async def get_employees():
    data = await _get_employees()
    return {"data": data if data else []}


@router.get("/orders")
async def get_orders(status: str | None = None, platform: str | None = None):
    nb = await get_tasks()
    result = [
        {"title": t.get("title", ""), "status": t.get("status", "pending"),
         "agent_type": t.get("agent_type", ""), "created_at": t.get("created_at", ""),
         "source_id": t.get("source_id"), "platform": "internal"}
        for t in (nb or [])
    ]
    if status:
        result = [o for o in result if o.get("status") == status]
    if platform:
        result = [o for o in result if o.get("platform") == platform]
    return {"data": result}


@router.get("/leads")
async def get_leads(status: str | None = None):
    nb = await _get_leads()
    if nb:
        result = [
            {"id": lead.get("id"), "name": lead.get("name", ""), "email": lead.get("email", ""),
             "company": lead.get("company", ""), "product_interest": lead.get("product_interest", ""),
             "budget_range": lead.get("budget_range", ""), "message": lead.get("message", ""),
             "status": lead.get("status", "new"), "source_page": lead.get("source_page", ""),
             "created_at": lead.get("created_at", "")}
            for lead in nb
        ]
        total = len(result)
        new_count = len([lead for lead in result if lead.get("status") == "new"])
    else:
        result, total, new_count = [], 0, 0
    if status:
        result = [lead for lead in result if lead.get("status") == status]
    return {"data": result, "total": total, "new_count": new_count}


@router.get("/external-orders")
async def get_external_orders(platform: str | None = None, status: str | None = None):
    nb = await _get_external_orders()
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
        result, total = [], 0
    if platform:
        result = [o for o in result if o.get("platform") == platform]
    if status:
        result = [o for o in result if o.get("status") == status]
    return {"data": result, "total": total}


@router.get("/lines")
async def get_lines_endpoint():
    nb = await get_lines()
    return {"data": [
        {"name": item.get("name", item.get("slug", "")), "slug": item.get("slug", ""),
         "status": item.get("status", "unknown"), "monthly_revenue": item.get("monthly_revenue", 0) or 0,
         "customer_count": item.get("customer_count", 0) or 0}
        for item in (nb or [])
    ]}


@router.get("/deployment-orders")
async def get_deployment_orders(status: str | None = None):
    from hq.crossdeploy_client import get_deployment_orders as _fetch_orders

    orders = await _fetch_orders(status)
    return {"data": orders, "total": len(orders)}


@router.get("/deployment-tiers")
async def get_deployment_tiers():
    from hq.crossdeploy_client import get_deployment_tiers

    tiers = await get_deployment_tiers()
    return {"tiers": tiers}


@router.get("/sync")
async def manual_sync():
    await polsia_sync()
    return {"ok": True, "synced_at": datetime.now(UTC).isoformat()}


@router.get("/finances")
async def get_finances():
    expenses = await get_expenses() or []
    revenue = await get_revenue_history() or []
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
        "mrr": sum(r["amount"] for r in revenue[-3:] if revenue) // 3 if revenue else 0,
        "arr": total_revenue,
        "expense_by_category": [{"category": k, "amount": v} for k, v in sorted(expense_by_cat.items(), key=lambda x: -x[1])],
        "revenue_by_month": [{"month": k, "revenue": v} for k, v in sorted(rev_by_month.items())],
    }


@router.get("/reports")
async def get_reports():
    nb_tasks = await get_tasks() or []
    nb_emps = await _get_employees() or []

    orders_data = [
        {"title": t.get("title", ""), "status": t.get("status", "pending"),
         "agent_type": t.get("agent_type", ""), "created_at": t.get("created_at", ""),
         "id": t.get("source_id")}
        for t in nb_tasks
    ]

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
    activity_7d = sum(v for k, v in task_by_day.items()
                     if k >= (datetime.now(UTC).isoformat()[:10] if task_by_day else ""))
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "completion_rate": round(completed / total_tasks * 100, 1) if total_tasks else 0,
        "agent_performance": [{"agent": k, **v} for k, v in sorted(agent_perf.items(), key=lambda x: -x[1]["total"])],
        "task_trend": [{"date": k, "count": v} for k, v in sorted(task_by_day.items())],
        "last_7d_activity": activity_7d,
        "employee_count": len(nb_emps),
    }
