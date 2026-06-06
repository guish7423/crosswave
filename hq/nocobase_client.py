"""
NocoBase REST API client for CrossWave HQ.

Queries synced business data from NocoBase (PostgreSQL) for dashboard display.
Sync happens via polsia_bridge.py (write path); this client is the read path.
"""
import os
import time

import httpx

NB_URL = os.environ.get("HQ_URL", "http://localhost:13000/api")
NB_EMAIL = os.environ.get("NB_EMAIL", "admin@nocobase.com")
NB_PASSWORD = os.environ.get("NB_PASSWORD", "CrossWave@2026")
_NB_DISABLED = os.environ.get("NB_DISABLED", "").lower() in ("1", "true", "yes")

_token: str | None = None
_token_expires: float = 0


async def get_token(client: httpx.AsyncClient) -> str:
    global _token, _token_expires
    if _token and time.time() < _token_expires:
        return _token
    r = await client.post(
        f"{NB_URL}/auth:signIn",
        json={"email": NB_EMAIL, "password": NB_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    _token = data["data"]["token"]
    _token_expires = time.time() + 3300  # 55 min (tokens last 1hr)
    assert _token is not None
    return _token


async def list_all(collection: str, page_size: int = 100) -> list[dict]:
    """Fetch all records from a NocoBase collection."""
    if _NB_DISABLED:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        token = await get_token(client)
        items = []
        page = 1
        while True:
            r = await client.get(
                f"{NB_URL}/{collection}:list",
                params={"page": page, "pageSize": page_size},
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code == 404:
                return []  # collection doesn't exist yet
            r.raise_for_status()
            data = r.json()
            batch = data.get("data", [])
            items.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return items


async def get_stats() -> dict:
    """Get summary counts from all synced NocoBase collections."""
    if _NB_DISABLED:
        return {"status": "disabled", "employees": 0, "business_lines": 0, "external_orders": 0}
    employees = await list_all("employees")
    lines = await list_all("business_lines")
    orders = await list_all("external_orders")

    return {
        "employees": len(employees),
        "business_lines": len(lines),
        "external_orders": len(orders),
        "status": "connected",
    }


async def get_summary() -> dict:
    """Rich summary matching /api/hq/summary shape, sourced from NocoBase."""
    if _NB_DISABLED:
        return {"source": "disabled"}
    employees = await list_all("employees")
    lines = await list_all("business_lines")
    ext_orders = await list_all("external_orders")
    tasks_raw = await list_all("tasks")
    leads_raw = await list_all("leads")

    # Employee stats
    emp_statuses: dict[str, int] = {}
    for e in employees:
        s = e.get("status", "idle")
        emp_statuses[s] = emp_statuses.get(s, 0) + 1

    # Line stats
    total_mrr = sum(line.get("monthly_revenue", 0) or 0 for line in lines)
    total_customers = sum(line.get("customer_count", 0) or 0 for line in lines)
    line_summaries = []
    for line in lines:
        line_summaries.append({
            "name": line.get("name", line.get("slug", "unknown")),
            "slug": line.get("slug", ""),
            "status": line.get("status", "unknown"),
            "health": "healthy" if line.get("status") == "active" else "warning",
            "monthly_revenue": line.get("monthly_revenue", 0) or 0,
            "customer_count": line.get("customer_count", 0) or 0,
        })

    # Order stats (from tasks + external_orders)
    active_orders = [o for o in ext_orders if o.get("status") in ("pending", "in_progress")]
    order_statuses: dict[str, int] = {}
    for o in ext_orders:
        s = o.get("status", "pending")
        order_statuses[s] = order_statuses.get(s, 0) + 1

    # Task stats
    task_statuses: dict[str, int] = {}
    for t in tasks_raw:
        s = t.get("status", "pending")
        task_statuses[s] = task_statuses.get(s, 0) + 1

    # Lead stats
    lead_statuses: dict[str, int] = {}
    for l in leads_raw:
        s = l.get("status", "new")
        lead_statuses[s] = lead_statuses.get(s, 0) + 1

    return {
        "employees": {
            "total": len(employees),
            "active": len([e for e in employees if e.get("status") in ("idle", "running")]),
            "status_distribution": emp_statuses,
        },
        "lines": line_summaries,
        "orders": {
            "total": len(ext_orders),
            "active": len(active_orders),
            "status_distribution": order_statuses,
        },
        "tasks": {
            "total": len(tasks_raw),
            "status_distribution": task_statuses,
        },
        "mrr": total_mrr,
        "customers": total_customers,
        "leads": {
            "total": len(leads_raw),
            "new": lead_statuses.get("new", 0),
        },
        "last_sync": None,
        "source": "nocobase",
    }


# ─── Domain-specific readers ──────────────────────────────────────────────────

async def get_employees() -> list[dict]:
    return await list_all("employees")


async def get_lines() -> list[dict]:
    return await list_all("business_lines")


async def get_external_orders() -> list[dict]:
    return await list_all("external_orders")


async def get_leads() -> list[dict]:
    return await list_all("leads")


async def get_tasks() -> list[dict]:
    return await list_all("tasks")


async def get_proposals() -> list[dict]:
    return await list_all("proposals")


async def get_expenses() -> list[dict]:
    rows = await list_all("expenses")
    return [
        {"amount": r.get("amount_cents", 0) / 100.0 if r.get("amount_cents") else 0,
         "category": r.get("category", "other"),
         "description": r.get("description", ""),
         "date": r.get("date", "")}
        for r in rows
    ]


async def get_revenue_history() -> list[dict]:
    rows = await list_all("revenue_snapshots")
    return [
        {"date": r.get("snapshot_date", ""),
         "amount": (r.get("mrr_cents", 0) or 0) / 100.0,
         "source": "subscription"}
        for r in rows
    ]
