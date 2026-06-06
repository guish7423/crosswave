"""Sync logic for HQ Bridge server — NocoBase is the primary store, no CACHE."""

import asyncio
import os
import secrets
import time
from datetime import UTC, datetime

import httpx

# ─── Auth ─────────────────────────────────────────────────────────────────────
AUTH_TOKEN = os.environ.get("HQ_AUTH_TOKEN", "")
if not AUTH_TOKEN:
    AUTH_TOKEN = secrets.token_urlsafe(24)
    print(f"[hq] ⚠ No HQ_AUTH_TOKEN set — generated: {AUTH_TOKEN}")

# ─── Paths & Config ───────────────────────────────────────────────────────────
_HQ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_HQ_DIR)

DB_PATH = os.environ.get("POLSIA_DB", os.path.join(_PROJECT_ROOT, "polsia-fork", "polsia.db"))
CROSSBRIDGE_DB = os.environ.get(
    "CROSSBRIDGE_DB",
    os.path.join(_PROJECT_ROOT, "ai-content-bridge", "content_bridge.db"),
)
POLSIA_PORT = int(os.environ.get("POLSIA_PORT", "8001"))
HQ_URL = os.environ.get("HQ_URL", "http://localhost:13000/api")
HQ_TOKEN = os.environ.get("HQ_TOKEN", "")

_last_sync: str | None = None

# ─── Service Monitor ──────────────────────────────────────────────────────────
SERVICES_TO_CHECK = [
    {"name": "polsia-fork", "url": "http://localhost:8001/api/v1/health", "label": "Polsia Fork (AI Agents)"},
    {"name": "crosswave",   "url": "http://localhost:9999/health",        "label": "CrossWave (Website)"},
    {"name": "crossblog",   "url": "http://localhost:8002/health",        "label": "CrossBlog (80 Posts)"},
    {"name": "hq-bridge",   "url": "http://localhost:13001/health",       "label": "CrossWave HQ (Bridge)"},
]


async def _check_svc(name: str, url: str, timeout: int = 5) -> dict:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers={"User-Agent": "CrossWave-Monitor/1.0"})
        ms = int((time.monotonic() - start) * 1000)
        return {"service": name, "status": "up" if resp.is_success else "degraded",
                "http_status": resp.status_code, "response_time_ms": ms, "error": ""}
    except Exception as e:
        ms = int((time.monotonic() - start) * 1000)
        return {"service": name, "status": "down", "http_status": 0,
                "response_time_ms": ms, "error": str(e)[:120]}


async def polsia_sync() -> bool:
    """Pull data from Polsia Fork into NocoBase. Returns True on success.

    Replaced in-memory CACHE with direct NocoBase writes.
    """
    global _last_sync
    ok = await _try_nocobase_sync()
    if ok:
        _last_sync = datetime.now(UTC).isoformat()
    return ok


async def _try_nocobase_sync() -> bool:
    """Sync Polsia Fork data to NocoBase. Returns True on success."""
    try:
        from hq.polsia_bridge import sync as nocobase_sync  # noqa: PLC0415
        await nocobase_sync()
        print("[bridge] NocoBase sync completed")
        return True
    except Exception as nbe:
        print(f"[bridge] NocoBase sync skipped: {nbe}")
        return False


async def periodic_sync():
    """Background sync every 30 minutes."""
    while True:
        await polsia_sync()
        await asyncio.sleep(1800)
