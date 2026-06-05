"""Proxy routes — HTMX partials proxying Polsia Fork data."""

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.services.polsia_client import polsia_client

router = APIRouter(prefix="/api/v1/_proxy", tags=["proxy"])


class QuickQuoteData(BaseModel):
    name: str
    email: str
    company: str = ""
    phone: str = ""
    project_description: str = ""
    budget_range: str = ""
    preferred_tier: str = ""


# ── Quote flows ──────────────────────────────────────────────────────────


@router.post("/submit-quote")
async def submit_quote(data: QuickQuoteData):
    return await polsia_client.submit_quick_quote(data.model_dump())


@router.post("/track-view/{view_token}")
async def proxy_track_view(view_token: str):
    return await polsia_client.track_proposal_view(view_token)


@router.post("/accept-proposal/{view_token}")
async def proxy_accept_proposal(view_token: str):
    return await polsia_client.accept_proposal(view_token)


@router.post("/reject-proposal/{view_token}")
async def proxy_reject_proposal(view_token: str, data: dict = {}):
    reason = data.get("reason", "") if isinstance(data, dict) else ""
    return await polsia_client.reject_proposal(view_token, reason)


@router.post("/create-checkout/{order_id}")
async def proxy_create_checkout(order_id: int):
    return await polsia_client.create_checkout(order_id)


@router.post("/product-checkout")
async def proxy_product_checkout(data: dict):
    return await polsia_client.create_product_checkout(
        data.get("product_key", ""),
        data.get("customer_email", ""),
    )


@router.post("/execute-deploy/{order_id}")
async def proxy_execute_deploy(order_id: int):
    return await polsia_client.execute_deploy(order_id)


@router.get("/execution-status/{order_id}")
async def proxy_execution_status(order_id: int):
    return await polsia_client.get_execution_status(order_id)


@router.get("/download-deliverable/{order_id}")
async def proxy_download_deliverable(order_id: int):
    """Proxy the deliverable archive from Polsia Fork to the client."""
    polsia_url = (
        f"{settings.polsia_base_url}"
        f"/api/v1/orders/external/{order_id}/download-deliverable"
    )
    headers = {"X-API-Key": settings.polsia_api_key}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(polsia_url, headers=headers)
            resp.raise_for_status()
            disposition = resp.headers.get("content-disposition", "")
            filename = f"order-{order_id}-deliverable.tar.gz"
            if "filename=" in disposition:
                filename = disposition.split("filename=")[-1].strip('"\'')
            return StreamingResponse(
                resp.aiter_bytes(),
                media_type=resp.headers.get("content-type", "application/gzip"),
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": resp.headers.get("content-length", ""),
                },
            )
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": f"Polsia Fork returned {e.response.status_code}"},
        )
    except httpx.RequestError:
        return JSONResponse(
            status_code=503,
            content={"error": "Polsia Fork unreachable"},
        )


# ── HTMX partials ────────────────────────────────────────────────────────


@router.get("/agents/status")
async def proxy_agents_status():
    data = await polsia_client.get_agents_status()
    if isinstance(data, list):
        return HTMLResponse(_render_agent_cards(data))
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@router.get("/agents/rows")
async def proxy_agent_rows():
    data = await polsia_client.get_agents_status()
    if isinstance(data, list):
        return HTMLResponse(_render_agent_rows(data))
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@router.get("/activity")
async def proxy_activity(limit: int = 30):
    data = await polsia_client.get_activity(limit=limit)
    if isinstance(data, list):
        return HTMLResponse(_render_activity_items(data))
    return HTMLResponse('<div class="disconnected">No recent activity</div>')


@router.get("/dashboard/summary")
async def proxy_dashboard_summary():
    data = await polsia_client.get_dashboard_summary()
    if isinstance(data, dict):
        return HTMLResponse(_render_stat_cards(data))
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@router.get("/dashboard/task-summary")
async def proxy_task_summary():
    data = await polsia_client.get_dashboard_summary()
    if isinstance(data, dict):
        return HTMLResponse(_render_task_summary(data))
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@router.get("/analytics")
async def proxy_analytics():
    data = await polsia_client.get_analytics()
    if isinstance(data, dict) and data.get("status_distribution"):
        return data
    return {"status_distribution": [], "agent_breakdown": [], "daily_trend": []}


# ── Render helpers ────────────────────────────────────────────────────────


def _render_task_summary(s: dict) -> str:
    pending = s.get("tasks_today_pending", 0) or 0
    completed = s.get("tasks_today_completed", 0) or 0
    failed = s.get("tasks_today_failed", 0) or 0
    total = pending + completed + failed
    if total == 0:
        total = 1
    pct_pending = (pending / total) * 100
    pct_done = (completed / total) * 100
    pct_failed = (failed / total) * 100
    return f'''
<div class="task-summary">
  <div class="task-header">
    <span>Tasks Today: <strong>{total}</strong></span>
    <span class="task-legend">
      <span><span class="dot dot-pending"></span> {pending} pending</span>
      <span><span class="dot dot-done"></span> {completed} done</span>
      <span><span class="dot dot-failed"></span> {failed} failed</span>
    </span>
  </div>
  <div class="task-bar">
    <div class="task-bar-seg pending" style="width:{pct_pending:.1f}%"></div>
    <div class="task-bar-seg done" style="width:{pct_done:.1f}%"></div>
    <div class="task-bar-seg failed" style="width:{pct_failed:.1f}%"></div>
  </div>
</div>'''


def _render_stat_cards(s: dict) -> str:
    agents = s.get("active_agents", 0)
    tasks_today = s.get("tasks_today_total", 0)
    mrr_cents = s.get("mrr_cents", 0) or 0
    active_subs = s.get("active_subscribers", 0)
    mrr = f"${mrr_cents // 100}.{mrr_cents % 100:02d}"
    return "".join([
        f'<div class="stat-card"><div class="num">{agents}</div><div class="label">Active Agents</div></div>',
        f'<div class="stat-card"><div class="num">{tasks_today}</div><div class="label">Tasks Today</div></div>',
        f'<div class="stat-card"><div class="num">{active_subs}</div><div class="label">Active Clients</div></div>',
        f'<div class="stat-card"><div class="num">{mrr}</div><div class="label">MRR</div></div>',
    ])


def _render_agent_cards(agents: list) -> str:
    emoji_map = {
        "orchestrator": "👑", "business_planning": "📊",
        "competitor_research": "🔍", "social_media": "📱",
        "email_outreach": "✉️", "customer_support": "💬",
        "ads_management": "📢", "code_generation": "💻",
        "finance": "💰", "deployment": "🚀",
    }
    cards = []
    for a in agents:
        name = a.get("name", a.get("agent_type", "Unknown"))
        status = a.get("status", "idle")
        agent_type = a.get("agent_type", "")
        emoji = emoji_map.get(agent_type, "🤖")
        if status == "running":
            badge = '<span class="status status-running">● Running</span>'
        elif status == "done":
            badge = '<span class="status status-done">✓ Done</span>'
        elif status == "error":
            badge = '<span class="status status-error">✗ Error</span>'
        else:
            badge = '<span class="status status-idle">○ Idle</span>'
        last_run = a.get("last_run") or "never"
        cards.append(
            f'<div class="agent-card">'
            f'<span class="name">{emoji} {name}</span>'
            f'{badge}'
            f'<span class="time">Last: {last_run}</span>'
            f'</div>'
        )
    return "".join(cards)


def _render_agent_rows(agents: list) -> str:
    emoji_map = {
        "orchestrator": "👑", "business_planning": "📊",
        "competitor_research": "🔍", "social_media": "📱",
        "email_outreach": "✉️", "customer_support": "💬",
        "ads_management": "📢", "code_generation": "💻",
        "finance": "💰", "deployment": "🚀",
    }
    desc_map = {
        "orchestrator": "Plan daily tasks, assign work, generate reports",
        "business_planning": "Market research, business model design, growth strategy",
        "competitor_research": "Track competitors, price changes, product updates",
        "social_media": "Content creation, scheduled posting, multi-platform",
        "email_outreach": "Lead development, email automation, follow-ups",
        "customer_support": "Ticket classification, auto-reply, knowledge base",
        "ads_management": "Ad optimization, budget tracking, A/B testing",
        "code_generation": "Auto-programming, bug fix, feature implementation",
        "finance": "Revenue/expense tracking, reports, cost monitoring",
        "deployment": "Infrastructure management, CI/CD pipeline",
    }
    rows = []
    for a in agents:
        at = a.get("agent_type", "")
        name = a.get("name", at.replace("_", " ").title() if at else "Unknown")
        status = a.get("status", "idle")
        emoji = emoji_map.get(at, "🤖")
        desc = desc_map.get(at, "")
        if status == "running":
            badge = '<span class="badge badge-running">● Running</span>'
        elif status == "done":
            badge = '<span class="badge badge-done">✓ Done</span>'
        elif status == "error":
            badge = '<span class="badge badge-error">✗ Error</span>'
        else:
            badge = '<span class="badge badge-idle">○ Idle</span>'
        rows.append(
            f'<div class="agent-row">'
            f'<span class="name">{emoji} {name}</span>'
            f'<span class="desc">{desc}</span>'
            f'{badge}'
            f'</div>'
        )
    return "".join(rows)


def _render_activity_items(entries: list) -> str:
    items = []
    for e in entries:
        ts = e.get("created_at", "") or ""
        if len(ts) > 16:
            ts = ts[:16]
        agent = e.get("agent_type", "")
        summary = e.get("summary", "")
        items.append(
            f'<div class="activity-item">'
            f'<span class="time">{ts}</span>'
            f'<span class="action">{agent}:</span>'
            f'<span class="summary">{summary}</span>'
            f'</div>'
        )
    if not items:
        return '<div class="disconnected">No recent activity</div>'
    return "".join(items)
