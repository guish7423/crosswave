"""CrossWave — Unified Management Platform"""
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import os

import httpx

from app.services.polsia_client import polsia_client
from app.config import settings
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
# Landing page (index.html) source of truth is at project root
templates_root = Jinja2Templates(directory=str(PROJECT_ROOT))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await polsia_client.start()
    yield
    await polsia_client.stop()


app = FastAPI(title="CrossWave", version="0.3.0", lifespan=lifespan)

with suppress(RuntimeError):
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/robots.txt", response_class=HTMLResponse)
async def robots():
    return """User-agent: *
Allow: /

Sitemap: https://crosswave.app/sitemap.xml
"""

# ─── Page routes ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates_root.TemplateResponse(request, "index.html", {"request": request})


@app.get("/deploy", response_class=HTMLResponse)
async def deploy_service(request: Request):
    return templates.TemplateResponse(request, "deploy-service.html")


@app.get("/request-quote", response_class=HTMLResponse)
async def request_quote(request: Request):
    return templates.TemplateResponse(request, "request-quote.html", {"request": request})


class QuickQuoteData(BaseModel):
    name: str
    email: str
    company: str = ""
    phone: str = ""
    project_description: str = ""
    budget_range: str = ""
    preferred_tier: str = ""


@app.get("/quote/{view_token}", response_class=HTMLResponse)
async def quote_view(request: Request, view_token: str):
    proposal = await polsia_client.get_proposal_by_token(view_token)
    if isinstance(proposal, dict) and proposal.get("id") is not None:
        return templates.TemplateResponse(
            request, "quote-view.html", {"request": request, "proposal": proposal}
        )
    return templates.TemplateResponse(
        request,
        "quote-view.html",
        {"request": request, "proposal": None, "error": "Proposal not found or expired."},
    )


@app.post("/api/v1/_proxy/submit-quote")
async def submit_quote(data: QuickQuoteData):
    result = await polsia_client.submit_quick_quote(data.model_dump())
    return result


@app.post("/api/v1/_proxy/track-view/{view_token}")
async def proxy_track_view(view_token: str):
    result = await polsia_client.track_proposal_view(view_token)
    return result


@app.post("/api/v1/_proxy/accept-proposal/{view_token}")
async def proxy_accept_proposal(view_token: str):
    result = await polsia_client.accept_proposal(view_token)
    return result


@app.post("/api/v1/_proxy/reject-proposal/{view_token}")
async def proxy_reject_proposal(view_token: str, data: dict = {}):
    reason = data.get("reason", "") if isinstance(data, dict) else ""
    result = await polsia_client.reject_proposal(view_token, reason)
    return result


@app.post("/api/v1/_proxy/create-checkout/{order_id}")
async def proxy_create_checkout(order_id: int):
    result = await polsia_client.create_checkout(order_id)
    return result

@app.post("/api/v1/_proxy/product-checkout")
async def proxy_product_checkout(data: dict):
    result = await polsia_client.create_product_checkout(
        data.get("product_key", ""),
        data.get("customer_email", ""),
    )
    return result

@app.post("/api/v1/_proxy/execute-deploy/{order_id}")
async def proxy_execute_deploy(order_id: int):
    result = await polsia_client.execute_deploy(order_id)
    return result


@app.get("/api/v1/_proxy/execution-status/{order_id}")
async def proxy_execution_status(order_id: int):
    result = await polsia_client.get_execution_status(order_id)
    return result


@app.get("/api/v1/_proxy/download-deliverable/{order_id}")
async def proxy_download_deliverable(order_id: int):
    """Proxy the deliverable archive from Polsia Fork to the client."""
    polsia_url = f"{settings.polsia_base_url}/api/v1/orders/external/{order_id}/download-deliverable"
    headers = {"X-API-Key": settings.polsia_api_key}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(polsia_url, headers=headers)
            resp.raise_for_status()
            # Extract filename from Content-Disposition or use default
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


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    summary = await polsia_client.get_dashboard_summary()
    agents = await polsia_client.get_agents_status()
    activity = await polsia_client.get_activity(limit=15)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "summary": summary if isinstance(summary, dict) else {},
            "agents": agents if isinstance(agents, list) else [],
            "activity": activity if isinstance(activity, list) else [],
        },
    )


@app.get("/agents", response_class=HTMLResponse)
async def agent_status(request: Request):
    agents = await polsia_client.get_agents_status()
    activity = await polsia_client.get_activity(limit=30)
    return templates.TemplateResponse(
        request,
        "agents.html",
        {
            "request": request,
            "agents": agents if isinstance(agents, list) else [],
            "activity": activity if isinstance(activity, list) else [],
        },
    )


# ─── Proxy routes (HTMX partials) ────────────────────────────────────────

@app.get("/api/v1/_proxy/agents/status")
async def proxy_agents_status():
    data = await polsia_client.get_agents_status()
    if isinstance(data, list):
        return HTMLResponse(_render_agent_cards(data))
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@app.get("/api/v1/_proxy/agents/rows")
async def proxy_agent_rows():
    data = await polsia_client.get_agents_status()
    if isinstance(data, list):
        return HTMLResponse(_render_agent_rows(data))
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@app.get("/api/v1/_proxy/activity")
async def proxy_activity(limit: int = 30):
    data = await polsia_client.get_activity(limit=limit)
    if isinstance(data, list):
        return HTMLResponse(_render_activity_items(data))
    return HTMLResponse('<div class="disconnected">No recent activity</div>')


@app.get("/api/v1/_proxy/dashboard/summary")
async def proxy_dashboard_summary():
    data = await polsia_client.get_dashboard_summary()
    if isinstance(data, dict):
        return HTMLResponse(_render_stat_cards(data))
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@app.get("/api/v1/_proxy/dashboard/task-summary")
async def proxy_task_summary():
    data = await polsia_client.get_dashboard_summary()
    if isinstance(data, dict):
        return HTMLResponse(_render_task_summary(data))
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@app.get("/api/v1/_proxy/analytics")
async def proxy_analytics():
    data = await polsia_client.get_analytics()
    if isinstance(data, dict) and data.get("status_distribution"):
        return data
    return {"status_distribution": [], "agent_breakdown": [], "daily_trend": []}


BLOG_URL = os.getenv("CROSSBLOG_URL", "http://127.0.0.1:8001")

async def _fetch_blog(path: str) -> dict | list:
    """Fetch from CrossBlog JSON API with timeout + fallback."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BLOG_URL}{path}")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"posts": []} if "posts" in path else []


@app.get("/api/v1/_proxy/blog/latest")
async def proxy_blog_latest():
    """Proxy popular blog posts from CrossBlog API."""
    result = await _fetch_blog("/api/posts/popular")
    return {"posts": result if isinstance(result, list) else []}


@app.get("/api/v1/_proxy/blog/recent")
async def proxy_blog_recent(limit: int = 6):
    """Proxy recent blog posts."""
    result = await _fetch_blog(f"/api/posts/recent?limit={limit}")
    return {"posts": result if isinstance(result, list) else []}


@app.get("/api/v1/_proxy/blog/by-tag/{tag}")
async def proxy_blog_by_tag(tag: str):
    """Proxy blog posts filtered by tag."""
    from urllib.parse import quote
    result = await _fetch_blog(f"/api/posts/by-tag/{quote(tag)}")
    return {"posts": result if isinstance(result, list) else []}


@app.get("/api/v1/_proxy/blog/tags")
async def proxy_blog_tags():
    """Proxy all blog tags."""
    result = await _fetch_blog("/api/tags")
    if isinstance(result, dict):
        return {"tags": result.get("tags", []), "total": result.get("total", 0)}
    return {"tags": result if isinstance(result, list) else [], "total": 0}


# ─── Render helpers ──────────────────────────────────────────────────────

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


@app.get("/health")
async def health():
    return {"status": "ok", "app": "CrossWave", "version": "0.3.0"}
