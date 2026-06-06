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
    employees = await list_all("employees")
    lines = await list_all("business_lines")
    orders = await list_all("external_orders")

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

    # Order stats
    active_orders = [o for o in orders if o.get("status") in ("pending", "in_progress")]
    order_statuses: dict[str, int] = {}
    for o in orders:
        s = o.get("status", "pending")
        order_statuses[s] = order_statuses.get(s, 0) + 1

    return {
        "employees": {
            "total": len(employees),
            "active": len([e for e in employees if e.get("status") in ("idle", "running")]),
            "status_distribution": emp_statuses,
        },
        "lines": line_summaries,
        "orders": {
            "total": len(orders),
            "active": len(active_orders),
            "status_distribution": order_statuses,
        },
        "mrr": total_mrr,
        "customers": total_customers,
        "leads": {"total": 0, "new": 0},  # NocoBase doesn't have leads yet
        "last_sync": None,
        "source": "nocobase",
    }
