"""CrossBlog BFF — proxies to CrossBlog engine."""

from fastapi import APIRouter, Depends
from app.core.auth.middleware import require_jwt
from app.core.auth.models import UserClaims

router = APIRouter(prefix="/blog", tags=["crossblog"])

import httpx

CROSSBLOG_URL = "http://localhost:9000"


@router.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{CROSSBLOG_URL}/health")
        return {"status": "ok" if resp.is_success else "degraded", "backend": resp.status_code}
    except Exception:
        return {"status": "offline", "backend": 0}
