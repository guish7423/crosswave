"""HQ middleware and lifespan."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from itsdangerous import URLSafeTimedSerializer

from app.config import settings
from hq.domains.data import AUTH_TOKEN, periodic_sync
from hq.plugin_registry.plugins import ALL_PRODUCT_PLUGINS

_session_serializer = URLSafeTimedSerializer(settings.secret_key, salt="admin-session")


async def require_token(request: Request):
    """Reject requests missing X-HQ-Token header. Skip public paths."""
    path = request.url.path
    if (path.startswith("/api/portal/")
        or path.startswith("/portal/")
        or path in ("/health", "/login", "/logout")
        or path.startswith("/api/hq/auth")
        or path.startswith("/static")
        or path.startswith("/api/hq/models")
        or path.startswith("/api/hq/agents/")
        or path.startswith("/api/hq/plugins/")
        or path.startswith("/api/hq/events/")):
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
    for p in ALL_PRODUCT_PLUGINS:
        registry.register_plugin(p)

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
