"""HQ monitor, evolution, portal, and SSE real-time routes."""

import asyncio
import json
import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from hq.domains.data import CACHE, DB_PATH, SERVICES_TO_CHECK, _check_svc

router = APIRouter(tags=["monitor"])


async def event_stream():
    """SSE event stream: pushes dashboard KPI updates every 5 seconds."""
    while True:
        try:
            # Quick service health check (non-blocking gather)
            tasks = [_check_svc(s["name"], s["url"]) for s in SERVICES_TO_CHECK]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            services = []
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    services.append({"service": SERVICES_TO_CHECK[i]["name"], "status": "error"})
                else:
                    services.append(r)

            # Dashboard heartbeat event
            data = json.dumps({
                "type": "heartbeat",
                "timestamp": datetime.now(UTC).isoformat(),
                "services": services,
                "kpi": {
                    "employees": len(CACHE.get("employees", [])),
                    "orders": len(CACHE.get("orders", [])),
                    "leads": len(CACHE.get("leads", [])),
                    "external_orders": len(CACHE.get("external_orders", [])),
                },
            })
            yield f"data: {data}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        await asyncio.sleep(5)


@router.get("/api/hq/events")
async def sse_events(request: Request):
    """SSE endpoint for real-time dashboard updates."""
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def hq_health():
    return {"status": "ok", "app": "CrossWave HQ Bridge", "services": len(SERVICES_TO_CHECK)}


@router.get("/api/hq/monitor")
async def get_monitor():
    tasks = [_check_svc(s["name"], s["url"]) for s in SERVICES_TO_CHECK]
    results = await asyncio.gather(*tasks)
    up = sum(1 for r in results if r["status"] == "up")
    degraded = sum(1 for r in results if r["status"] == "degraded")
    down = sum(1 for r in results if r["status"] == "down")
    valid_ms = [r["response_time_ms"] for r in results if r["response_time_ms"] > 0]
    avg_ms = round(sum(valid_ms) / len(valid_ms)) if valid_ms else 0
    return {
        "summary": {
            "total": len(results), "up": up, "degraded": degraded, "down": down,
            "avg_response_time_ms": avg_ms, "all_up": up == len(results),
            "timestamp": datetime.now(UTC).isoformat(),
        },
        "results": [
            {**r, "label": next((s["label"] for s in SERVICES_TO_CHECK if s["name"] == r["service"]), r["service"])}
            for r in results
        ],
    }


@router.get("/api/hq/evolution")
async def get_evolution():
    if not os.path.exists(DB_PATH):
        return {
            "error": "Polsia DB not found — run Polsia Fork first",
            "agent_metrics": [],
            "suggestions": ["启动 Polsia Fork 后再查看进化分析"],
            "total_activities": 0,
        }
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            act_rows = await db.execute_fetchall(
                "SELECT agent_type, level, COUNT(*) as cnt FROM activity_log "
                "WHERE created_at >= datetime('now', '-7 days') "
                "GROUP BY agent_type, level ORDER BY agent_type"
            )
            task_rows = await db.execute_fetchall(
                "SELECT agent_type, status, COUNT(*) as cnt FROM tasks "
                "WHERE created_at >= datetime('now', '-7 days') "
                "GROUP BY agent_type, status ORDER BY agent_type"
            )
            total_activities = (await db.execute_fetchall(
                "SELECT COUNT(*) FROM activity_log WHERE created_at >= datetime('now', '-7 days')"
            ))[0][0] or 0
    except Exception as e:
        return {"error": f"DB read error: {e}", "agent_metrics": [], "suggestions": []}
    agent_data = {}
    for row in act_rows:
        at, level, cnt = row[0] or "unknown", row[1] or "info", row[2] or 0
        if at not in agent_data:
            agent_data[at] = {"agent_type": at, "total": 0, "errors": 0, "warnings": 0}
        agent_data[at]["total"] += cnt
        if level == "error":
            agent_data[at]["errors"] += cnt
        elif level == "warning":
            agent_data[at]["warnings"] += cnt
    for row in task_rows:
        at, st, cnt = row[0] or "unknown", row[1] or "pending", row[2] or 0
        if at not in agent_data:
            agent_data[at] = {"agent_type": at, "total": 0, "errors": 0, "warnings": 0}
        agent_data[at]["total"] += cnt
        if st == "failed":
            agent_data[at]["errors"] += cnt
    metrics = []
    suggestions = []
    for at, d in sorted(agent_data.items()):
        success_rate = round((d["total"] - d["errors"]) / d["total"] * 100, 1) if d["total"] else 100.0
        d["success_rate"] = success_rate
        metrics.append(d)
        if d["errors"] > 0 and d["total"] >= 3:
            suggestions.append(f"{at}: 成功率 {success_rate}% ({d['errors']}/{d['total']} 错误)")
    if not suggestions:
        suggestions.append("所有 Agent 运行正常，无需优化")
    return {"agent_metrics": metrics, "suggestions": suggestions, "total_activities": total_activities,
            "analyzed_at": datetime.now(UTC).isoformat()}


@router.get("/api/portal/order/{order_id}")
async def portal_order(order_id: int):
    orders = CACHE.get("external_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    stage_order = ["pending", "scanned", "accepted", "in_progress", "deploying", "testing", "completed", "delivered"]
    stage_idx = {"pending": 0, "scanned": 1, "accepted": 2, "in_progress": 3, "deploying": 4, "testing": 5, "completed": 6, "delivered": 7}
    status = order.get("status", "pending")
    progress_idx = stage_idx.get(status, 0)
    deployment_plan = None
    if "deployment_plan" in order:
        try:
            deployment_plan = json.loads(order["deployment_plan"]) if isinstance(order["deployment_plan"], str) else order["deployment_plan"]
        except (json.JSONDecodeError, TypeError):
            deployment_plan = None
    return {
        "id": order["id"], "title": order.get("title", "CrossDeploy Project"),
        "status": status, "progress_idx": min(progress_idx, len(stage_order) - 1),
        "total_stages": len(stage_order), "stages": stage_order,
        "score": order.get("score"), "platform": order.get("platform", "direct"),
        "created_at": order.get("created_at", ""), "deployment_plan": deployment_plan,
    }
