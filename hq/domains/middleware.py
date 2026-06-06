"""HQ middleware and lifespan."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from itsdangerous import URLSafeTimedSerializer

from app.config import settings
from hq.domains.data import AUTH_TOKEN, periodic_sync
from hq.plugin_registry.models import PluginRegisterRequest

_session_serializer = URLSafeTimedSerializer(settings.secret_key, salt="admin-session")


async def require_token(request: Request):
    """Reject requests missing X-HQ-Token header. Skip public paths."""
    if (request.url.path.startswith("/api/portal/")
        or request.url.path.startswith("/portal/")
        or request.url.path in ("/health", "/login", "/logout")
        or request.url.path.startswith("/api/hq/auth")
        or request.url.path.startswith("/static")
        or request.url.path.startswith("/api/hq/models")
        or request.url.path.startswith("/api/hq/agents/")
        or request.url.path.startswith("/api/hq/plugins/")):
        return True
    token = request.headers.get("X-HQ-Token", "")
    if token == AUTH_TOKEN:
        return True
    raise HTTPException(status_code=401, detail="Unauthorized — provide X-HQ-Token header")


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Start background sync + plugin health checks on startup."""
    from hq.plugin_registry import get_registry

    registry = get_registry()
    products = [
        {"name": "CrossBridge", "description": "AI translation SaaS", "base_url": "https://crossbridge.example.com", "capabilities": ["translation", "api"]},
        {"name": "CrossBlog", "description": "SEO blog engine", "base_url": settings.crossblog_url, "capabilities": ["content", "seo"]},
        {"name": "CrossDeploy", "description": "Deployment service", "base_url": "http://localhost:8002", "capabilities": ["deployment", "infra"]},
        {"name": "Polsia Fork", "description": "10-agent backend platform", "base_url": settings.polsia_base_url, "capabilities": ["agents", "orchestration", "llm"]},
        {"name": "NocoBase", "description": "Low-code data platform", "base_url": "http://localhost:13000", "capabilities": ["database", "cms"]},
    ]
    for p in products:
        registry.register(PluginRegisterRequest(**p))

    asyncio.create_task(periodic_sync())
    asyncio.create_task(_health_loop(registry))
    yield


async def _health_loop(registry):
    await asyncio.sleep(30)
    while True:
        await registry.check_all_health()
        await asyncio.sleep(60)


async def require_session(request: Request):
    """Optional session cookie check — falls back to require_token."""
    session_token = request.cookies.get("session")
    if session_token:
        try:
            data = _session_serializer.loads(session_token, max_age=86400)
            request.state.username = data["username"]
            return  # Authenticated via session
        except Exception:
            pass
    # Fall back to token auth
    return await require_token(request)
