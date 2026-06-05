#!/usr/bin/env python3
"""
polsia_bridge.py — Sync Polsia Fork SQLite → NocoBase REST API v2

Syncs 4 collections (employees, business_lines, external_orders, platform_connections)
with dedup by name/slug/external_id. Run standalone or integrated into bridge server.
"""
import asyncio
import json
import os
import time

import aiosqlite
import httpx

DB_PATH = os.environ.get("POLSIA_DB", "")
if not DB_PATH:
    # auto-detect relative to script location
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(SCRIPT_DIR, "..", "..", "polsia-fork", "polsia.db")

NB_URL = os.environ.get("HQ_URL", "http://localhost:13000/api")
NB_EMAIL = os.environ.get("NB_EMAIL", "admin@nocobase.com")
NB_PASSWORD = os.environ.get("NB_PASSWORD", "CrossWave@2026")

TOKEN = None
TOKEN_EXPIRES = 0

async def get_token(client: httpx.AsyncClient) -> str:
    global TOKEN, TOKEN_EXPIRES
    if TOKEN and time.time() < TOKEN_EXPIRES:
        return TOKEN
    r = await client.post(f"{NB_URL}/auth:signIn", json={"email": NB_EMAIL, "password": NB_PASSWORD}, timeout=10)
    r.raise_for_status()
    data = r.json()
    TOKEN = data["data"]["token"]
    TOKEN_EXPIRES = time.time() + 3600  # tokens last 1hr
    return TOKEN

async def list_collection(client: httpx.AsyncClient, collection: str, field: str = "id") -> set:
    """Fetch all IDs/names from NocoBase collection to avoid duplicates."""
    token = await get_token(client)
    items = set()
    page = 1
    while True:
        r = await client.get(
            f"{NB_URL}/{collection}:list",
            params={"page": page, "pageSize": 100},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.status_code != 200:
            break
        data = r.json()
        rows = data.get("data", [])
        if not rows:
            break
        for row in rows:
            val = row.get(field)
            if val:
                items.add(str(val))
        if len(rows) < 100:
            break
        page += 1
    return items

async def create_record(client: httpx.AsyncClient, collection: str, payload: dict) -> bool:
    token = await get_token(client)
    try:
        r = await client.post(
            f"{NB_URL}/{collection}:create",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.status_code in (200, 201):
            return True
        print(f"  [skip] {collection}: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        print(f"  [error] {collection}: {e}")
        return False

async def ensure_platform_connections(client: httpx.AsyncClient):
    """Seed platform connections if empty."""
    existing = await list_collection(client, "platform_connections", "platform")
    defaults = [
        {"platform": "Upwork", "status": "active", "account_name": "CrossWave", "config": json.dumps({"api_type": "rss", "feed_url": "https://remoteok.com/api"})},
        {"platform": "Fiverr", "status": "active", "account_name": "CrossWave", "config": json.dumps({"api_type": "scraper", "url": "https://www.fiverr.com"})},
        {"platform": "猪八戒", "status": "active", "account_name": "CrossWave", "config": json.dumps({"api_type": "api", "endpoint": "https://open.zbj.com"})},
    ]
    for d in defaults:
        if d["platform"] not in existing:
            await create_record(client, "platform_connections", d)

async def sync():
    print(f"[polsia_bridge] DB: {DB_PATH}  NB: {NB_URL}")
    if not os.path.exists(DB_PATH):
        print("  DB not found, skipping")
        return

    async with httpx.AsyncClient() as client:
        token = await get_token(client)
        print(f"  Authenticated: token={token[:16]}...")

        # ── 1. Employees (from DISTINCT agent_type in tasks) ──────────
        existing_emps = await list_collection(client, "employees", "name")
        async with aiosqlite.connect(DB_PATH) as db:
            rows = await db.execute_fetchall(
                "SELECT DISTINCT agent_type FROM tasks ORDER BY agent_type"
            )
            known = ["orchestrator", "social_media", "customer_support", "competitor_research",
                     "business_planning", "code_generation", "deployment",
                     "finance", "email_outreach", "ads_management",
                     "order_scanner", "order_fulfiller", "lead_nurturing",
                     "deploy_agent", "monitor", "evolution", "market_intel"]
            seen = set(r[0] for r in rows if r[0])
            for at in known:
                if at not in seen:
                    seen.add(at)
            for at in sorted(seen):
                name = at.replace("_", " ").title()
                if name in existing_emps:
                    continue
                await create_record(client, "employees", {
                    "name": name,
                    "type": "ai",
                    "role": name,
                    "status": "idle",
                    "performance_score": 0,
                    "metadata": json.dumps({"agent_type": at}),
                })

        # ── 2. Business Lines ──────────────────────────────────────
        existing_lines = await list_collection(client, "business_lines", "slug")
        lines = [
            {"name": "CrossBridge", "slug": "crossbridge", "status": "active"},
            {"name": "CrossBlog", "slug": "crossblog", "status": "active"},
            {"name": "CrossDeploy", "slug": "crossdeploy", "status": "active"},
            {"name": "Polsia Fork", "slug": "polsia", "status": "active"},
            {"name": "HiveMind", "slug": "hivemind", "status": "development"},
        ]
        for item in lines:
            if item["slug"] in existing_lines:
                continue
            await create_record(client, "business_lines", item)

        # ── 3. External Orders ─────────────────────────────────────
        existing_orders = await list_collection(client, "external_orders", "external_id")
        async with aiosqlite.connect(DB_PATH) as db:
            rows = await db.execute_fetchall(
                "SELECT id, title, platform, external_id, status, budget_min, "
                "budget_max, currency, score, score_reason, created_at "
                "FROM external_orders ORDER BY created_at DESC LIMIT 200"
            )
            for r in rows:
                eid = str(r[3] or r[0])  # external_id or local id
                if eid in existing_orders:
                    continue
                await create_record(client, "external_orders", {
                    "title": r[1] or f"Order-{r[0]}",
                    "platform": r[2] or "unknown",
                    "external_id": eid,
                    "status": r[4] or "scanned",
                    "budget_min": r[5] or 0,
                    "budget_max": r[6] or 0,
                    "currency": r[7] or "USD",
                    "score": r[8] or 0,
                    "description": r[9] or "",
                })

        # ── 4. Platform Connections (seed if empty) ────────────────
        await ensure_platform_connections(client)

        print("[polsia_bridge] sync complete")

async def main():
    """Standalone entry: run the full sync."""
    await sync()

if __name__ == "__main__":
    asyncio.run(main())
