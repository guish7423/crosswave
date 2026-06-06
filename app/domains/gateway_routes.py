"""API Gateway — unified health aggregator and service discovery."""

from __future__ import annotations

from fastapi import APIRouter
import httpx
import asyncio

router = APIRouter(tags=["gateway"])

SERVICES = {
    "hq": "http://localhost:13001/health",
    "blog": "http://localhost:9000/health",
    "main": "http://localhost:9999/health",
    "nocobase": "http://localhost:13000/api/",
}


@router.get("/api/gateway/health")
async def gateway_health():
    results = {}
    async def check(name: str, url: str):
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(url)
            results[name] = {"status": "up" if r.is_success else "degraded"}
        except Exception:
            results[name] = {"status": "down"}
    tasks = [check(n, u) for n, u in SERVICES.items()]
    await asyncio.gather(*tasks)
    return {"gateway": "CrossWave API Gateway", "services": results}
