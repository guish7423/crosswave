"""CrossWave — Unified Management Platform"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.services.polsia_client import polsia_client

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await polsia_client.start()
    yield
    await polsia_client.stop()


app = FastAPI(title="CrossWave", version="0.3.0", lifespan=lifespan)

try:
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
except RuntimeError:
    pass


# ─── Page routes ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    summary = await polsia_client.get_dashboard_summary()
    agents = await polsia_client.get_agents_status()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "summary": summary if isinstance(summary, dict) else {},
            "agents": agents if isinstance(agents, list) else [],
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


# ─── Render helpers ──────────────────────────────────────────────────────

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
