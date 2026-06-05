"""CrossDeploy API client — fetches deployment orders for HQ dashboard."""

import os
from typing import Optional

import httpx

CROSSDEPLOY_BASE_URL = os.getenv("CROSSDEPLOY_URL", "http://localhost:8003")


async def get_deployment_orders(status: Optional[str] = None) -> list[dict]:
    """Fetch deployment orders from CrossDeploy API."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            params = {"status": status} if status else {}
            resp = await client.get(f"{CROSSDEPLOY_BASE_URL}/api/orders", params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return []


async def get_deployment_tiers() -> list[dict]:
    """Fetch available deployment tiers/pricing."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{CROSSDEPLOY_BASE_URL}/api/tiers")
            resp.raise_for_status()
            data = resp.json()
            return data.get("tiers", [])
    except Exception:
        return []
