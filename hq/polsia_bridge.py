import os
import json
import asyncio
import httpx
from datetime import datetime, timezone

DB_PATH = os.environ.get("POLSIA_DB", "../polsia.db")
HQ_URL = os.environ.get("HQ_URL", "http://localhost:13000/api")
HQ_TOKEN = os.environ.get("HQ_TOKEN", "")

async def sync_employees(client):
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            "SELECT type, name, role, status FROM agents"
        )
        for row in rows:
            payload = {
                "name": row[1] or row[0],
                "type": "ai",
                "role": row[2] or row[0],
                "status": row[3] or "idle",
                "metadata": json.dumps({"agent_type": row[0]}),
            }
            try:
                await client.post(
                    f"{HQ_URL}/employees:create",
                    json=payload,
                    headers={"Authorization": f"Bearer {HQ_TOKEN}"},
                    timeout=10,
                )
            except Exception as e:
                print(f"  [skip] {payload['name']}: {e}")

async def sync_business_lines(client):
    lines = [
        {"name": "CrossBridge", "slug": "crossbridge", "status": "active"},
        {"name": "CrossBlog", "slug": "crossblog", "status": "active"},
        {"name": "CrossDeploy", "slug": "crossdeploy", "status": "active"},
        {"name": "Polsia Fork", "slug": "polsia", "status": "active"},
        {"name": "HiveMind", "slug": "hivemind", "status": "development"},
    ]
    for line in lines:
        try:
            await client.post(
                f"{HQ_URL}/business_lines:create",
                json=line,
                headers={"Authorization": f"Bearer {HQ_TOKEN}"},
                timeout=10,
            )
        except Exception as e:
            print(f"  [skip] {line['name']}: {e}")

async def sync_orders(client):
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            "SELECT title, status, agent_type, created_at FROM tasks ORDER BY created_at DESC LIMIT 50"
        )
        for row in rows:
            payload = {
                "title": row[0] or f"task-{datetime.now(timezone.utc).isoformat()}",
                "platform": "internal",
                "status": row[1] or "pending",
                "description": f"Agent: {row[2] or 'unknown'}",
                "metadata": json.dumps({"agent_type": row[2], "created_at": row[3]}),
            }
            try:
                await client.post(
                    f"{HQ_URL}/external_orders:create",
                    json=payload,
                    headers={"Authorization": f"Bearer {HQ_TOKEN}"},
                    timeout=10,
                )
            except Exception as e:
                print(f"  [skip] {payload['title']}: {e}")

async def main():
    print(f"[polsia_bridge] DB: {DB_PATH}  HQ: {HQ_URL}")
    async with httpx.AsyncClient() as client:
        await sync_employees(client)
        await sync_business_lines(client)
        await sync_orders(client)
    print("[polsia_bridge] sync complete")

if __name__ == "__main__":
    asyncio.run(main())
