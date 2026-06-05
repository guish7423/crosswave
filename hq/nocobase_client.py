"""
NocoBase REST API client for CrossWave HQ.

Queries synced business data from NocoBase (PostgreSQL) for dashboard display.
Sync happens via polsia_bridge.py (write path); this client is the read path.
"""
import json
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
