# CrossWave Live Dashboard — 实现计划

> **面向 AI 代理的工作者：** 步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 CrossWave Dashboard/Agents 页面从静态 mockup 升级为实时数据面板，连接 Polsia Fork API。

**架构：** CrossWave FastAPI 作为 BFF，通过 httpx 代理调用 Polsia Fork API，Jinja2 模板渲染数据，HTMX 实现局部自动刷新。

**技术栈：** FastAPI, httpx, Jinja2, HTMX (CDN)

---

## 文件清单

### 创建
- `app/services/polsia_client.py` — Polsia Fork API 客户端
- `app/config.py` — 配置管理

### 修改
- `app/main.py:18-28` — 添加代理路由 + lifespan 客户端初始化
- `app/templates/dashboard.html` — 动态数据 + HTMX 刷新
- `app/templates/agents.html` — 动态数据 + HTMX 刷新
- `app/static/style.css` — 新增 disconnected/loading 样式
- `requirements.txt` — 新增 httpx

---

### 任务 1：配置与 API 客户端

**文件：**
- 创建：`app/config.py`
- 创建：`app/services/polisia_client.py`
- 修改：`requirements.txt`

- [ ] **步骤 1：创建 config.py**

```python
"""CrossWave — centralized configuration."""
from dataclasses import dataclass, field
from os import environ


@dataclass
class Settings:
    polsia_base_url: str = field(
        default_factory=lambda: environ.get(
            "POLSIA_BASE_URL", "http://localhost:8001"
        )
    )
    polsia_api_key: str = field(
        default_factory=lambda: environ.get("POLSIA_API_KEY", "dev-key")
    )
    proxy_timeout: int = 5
    debug: bool = field(
        default_factory=lambda: environ.get("DEBUG", "true").lower() == "true"
    )


settings = Settings()
```

- [ ] **步骤 2：创建 polsia_client.py**

```python
"""Polsia Fork API client — server-side proxy."""
import json
from contextlib import asynccontextmanager

import httpx
from app.config import settings


class PolsiaClient:
    """HTTP client for Polsia Fork API."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def start(self):
        self._client = httpx.AsyncClient(
            base_url=settings.polsia_base_url,
            timeout=settings.proxy_timeout,
            headers={"X-API-Key": settings.polsia_api_key},
        )

    async def stop(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str) -> dict | list:
        """Make GET request with disconnect-safe error handling."""
        if not self._client:
            return {"status": "disconnected"}
        try:
            r = await self._client.get(path)
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException:
            return {"status": "disconnected", "error": "timeout"}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "error": str(e.response.status_code)}
        except httpx.RequestError:
            return {"status": "disconnected"}

    async def get_dashboard_summary(self) -> dict:
        return await self._get("/api/v1/dashboard/summary")

    async def get_agents_status(self) -> list:
        return await self._get("/api/v1/agents/status")

    async def get_activity(self, limit: int = 20) -> list:
        return await self._get(f"/api/v1/dashboard/activity?limit={limit}")


# Singleton
polsia_client = PolsiaClient()
```

- [ ] **步骤 3：更新 requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
jinja2>=3.1.0
python-multipart>=0.0.18
httpx>=0.27.0
```

- [ ] **步骤 4：提交**

```bash
git add -A && git commit -m "feat: add Polsia Fork API client and config"
```

---

### 任务 2：代理路由 + lifespan 集成

**文件：**
- 修改：`app/main.py`

- [ ] **步骤 1：修改 main.py 添加 lifespan 和代理路由**

```python
"""CrossWave — Unified Management Platform"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
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
        return _render_agent_cards(data)
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


@app.get("/api/v1/_proxy/activity")
async def proxy_activity(limit: int = 10):
    data = await polsia_client.get_activity(limit=limit)
    if isinstance(data, list):
        return _render_activity_list(data)
    return HTMLResponse('<div class="disconnected">🔌 Activity unavailable</div>')


@app.get("/api/v1/_proxy/dashboard/summary")
async def proxy_dashboard_summary():
    data = await polsia_client.get_dashboard_summary()
    if isinstance(data, dict):
        return _render_stat_cards(data)
    return HTMLResponse('<div class="disconnected">🔌 Polsia Fork unavailable</div>')


# ─── Render helpers ──────────────────────────────────────────────────────

def _render_stat_cards(s: dict) -> str:
    """Render stat cards HTML fragment for HTMX."""
    agents = s.get("active_agents", 0)
    tasks_today = s.get("tasks_today_total", 0)
    mrr_cents = s.get("mrr_cents", 0)
    active_subs = s.get("active_subscribers", 0)
    mrr = f"${mrr_cents // 100}.{mrr_cents % 100:02d}" if mrr_cents else "$0"
    return f"""
    <div class="stat-card"><div class="num">{agents}</div><div class="label">Active Agents</div></div>
    <div class="stat-card"><div class="num">{tasks_today}</div><div class="label">Tasks Today</div></div>
    <div class="stat-card"><div class="num">{active_subs}</div><div class="label">Active Clients</div></div>
    <div class="stat-card"><div class="num">{mrr}</div><div class="label">MRR</div></div>
    """


def _render_agent_cards(agents: list) -> str:
    """Render agent cards HTML fragment for HTMX."""
    cards = []
    for a in agents:
        name = a.get("name", a.get("agent_type", "Unknown"))
        status = a.get("status", "idle")
        agent_type = a.get("agent_type", "")
        emoji = {
            "orchestrator": "👑", "business_planning": "📊",
            "competitor_research": "🔍", "social_media": "📱",
            "email_outreach": "✉️", "customer_support": "💬",
            "ads_management": "📢", "code_generation": "💻",
            "finance": "💰", "deployment": "🚀",
        }.get(agent_type, "🤖")

        if status == "running":
            badge = '<span class="status status-running">● Running</span>'
        elif status == "done":
            badge = '<span class="status status-done">✓ Done</span>'
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


def _render_activity_list(activities: list) -> str:
    """Render activity list HTML fragment for HTMX."""
    if not activities:
        return '<div class="activity-empty">No recent activity</div>'
    items = []
    for a in activities:
        agent = a.get("agent_type", "").replace("_", " ").title() if a.get("agent_type") else "System"
        action = a.get("action", "unknown")
        summary = a.get("summary", "")
        time = (a.get("created_at") or "")[:19].replace("T", " ") if a.get("created_at") else ""
        level = a.get("level", "info")
        icon = {"info": "ℹ️", "warning": "⚠️", "error": "🚨"}.get(level, "ℹ️")
        items.append(
            f'<div class="activity-row {level}">'
            f'<span class="activity-icon">{icon}</span>'
            f'<span class="activity-agent">{agent}</span>'
            f'<span class="activity-action">{action}</span>'
            f'<span class="activity-summary">{summary}</span>'
            f'<span class="activity-time">{time}</span>'
            f'</div>'
        )
    return "".join(items)


@app.get("/health")
async def health():
    return {"status": "ok", "app": "CrossWave", "version": "0.3.0"}
```

- [ ] **步骤 2：提交**

```bash
git add -A && git commit -m "feat: add proxy routes, lifespan, and HTMX render helpers"
```

---

### 任务 3：更新 Dashboard 模板

**文件：**
- 修改：`app/templates/dashboard.html`

- [ ] **步骤 1：替换 dashboard.html 为动态模板**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CrossWave — Management Platform</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  <link rel="stylesheet" href="/static/style.css">
  <style>
    :root {
      --bg: oklch(0.99 0.002 260);
      --surface: oklch(0.97 0.004 260);
      --border: oklch(0.91 0.008 260);
      --ink: oklch(0.18 0.02 260);
      --ink-dim: oklch(0.5 0.025 260);
      --accent: oklch(0.55 0.25 280);
      --green: oklch(0.55 0.2 160);
      --red: oklch(0.6 0.22 30);
      --font: 'Inter', system-ui, sans-serif;
      --radius: 10px;
      --space: 8px;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: var(--font); background: var(--bg); color: var(--ink); line-height: 1.6; font-size: 14px; }
    .app { display: flex; min-height: 100vh; }
    
    /* Sidebar */
    .sidebar { width: 240px; background: var(--surface); border-right: 1px solid var(--border); padding: calc(var(--space) * 3); flex-shrink: 0; }
    .sidebar .logo { font-weight: 700; font-size: 16px; margin-bottom: calc(var(--space) * 4); }
    .nav-item { display: flex; align-items: center; gap: var(--space); padding: var(--space) calc(var(--space) * 2); border-radius: var(--radius); color: var(--ink-dim); font-weight: 500; margin-bottom: 2px; text-decoration: none; font-size: 13px; }
    .nav-item:hover, .nav-item.active { background: oklch(0.55 0.25 280 / 0.1); color: var(--accent); }
    
    /* Main */
    .main { flex: 1; padding: calc(var(--space) * 4); max-width: 1200px; }
    h1 { font-size: 24px; font-weight: 700; margin-bottom: 4px; letter-spacing: -0.02em; }
    .subtitle { color: var(--ink-dim); margin-bottom: calc(var(--space) * 4); font-size: 14px; }
    
    /* Stats grid — HTMX target */
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: calc(var(--space) * 2); margin-bottom: calc(var(--space) * 4); }
    .stat-card { padding: calc(var(--space) * 3); border-radius: var(--radius); border: 1px solid var(--border); }
    .stat-card .num { font-size: 28px; font-weight: 800; letter-spacing: -0.03em; }
    .stat-card .label { font-size: 12px; color: var(--ink-dim); margin-top: 4px; font-weight: 500; }
    
    /* Agent grid — HTMX target */
    .agent-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: calc(var(--space) * 2); }
    .agent-card { padding: calc(var(--space) * 3); border-radius: var(--radius); border: 1px solid var(--border); display: flex; flex-direction: column; gap: calc(var(--space)); }
    .agent-card .name { font-weight: 600; font-size: 14px; }
    .agent-card .status { font-size: 12px; font-weight: 600; }
    .status-idle { color: var(--ink-dim); }
    .status-running { color: var(--accent); }
    .status-done { color: var(--green); }
    .agent-card .time { font-size: 11px; color: var(--ink-dim); }
    
    /* Disconnected */
    .disconnected { color: var(--ink-dim); font-style: italic; padding: var(--space) 0; }
    
    @media (max-width: 768px) { .stats { grid-template-columns: repeat(2, 1fr); } .sidebar { display: none; } }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="logo">✦ CrossWave</div>
      <a href="/dashboard" class="nav-item active">📊 Dashboard</a>
      <a href="/agents" class="nav-item">🤖 Agents</a>
      <a href="/" class="nav-item">🌐 Website</a>
    </aside>
    <main class="main">
      <h1>Dashboard</h1>
      <p class="subtitle">Autonomous company operations — real-time status</p>
      
      <div class="stats" id="stats"
           hx-get="/api/v1/_proxy/dashboard/summary"
           hx-trigger="load, every:30s"
           hx-swap="innerHTML">
        {% if summary.get("status") == "disconnected" %}
          <div class="stat-card" style="grid-column:1/-1">
            <div class="num">🔌</div>
            <div class="label">Polsia Fork unavailable</div>
          </div>
        {% else %}
          <div class="stat-card"><div class="num">{{ summary.get("active_agents", 0) }}</div><div class="label">Active Agents</div></div>
          <div class="stat-card"><div class="num">{{ summary.get("tasks_today_total", 0) }}</div><div class="label">Tasks Today</div></div>
          <div class="stat-card"><div class="num">{{ summary.get("active_subscribers", 0) }}</div><div class="label">Active Clients</div></div>
          <div class="stat-card"><div class="num">${{ "{:.0f}".format(summary.get("mrr_cents", 0) / 100) }}</div><div class="label">MRR</div></div>
        {% endif %}
      </div>

      <h2 style="font-size:16px;margin-bottom:12px;font-weight:600">Agent Status</h2>
      <div class="agent-grid" id="agent-grid"
           hx-get="/api/v1/_proxy/agents/status"
           hx-trigger="load, every:15s"
           hx-swap="innerHTML">
        {% if agents is defined and agents %}
          {% for a in agents %}
            {% set emoji = {
              "orchestrator": "👑", "business_planning": "📊", "competitor_research": "🔍",
              "social_media": "📱", "email_outreach": "✉️", "customer_support": "💬",
              "ads_management": "📢", "code_generation": "💻", "finance": "💰", "deployment": "🚀"
            }.get(a.get("agent_type", ""), "🤖") %}
            {% set s = a.get("status", "idle") %}
            {% if s == "running" %}
              {% set badge = '<span class="status status-running">● Running</span>' %}
            {% elif s == "done" %}
              {% set badge = '<span class="status status-done">✓ Done</span>' %}
            {% else %}
              {% set badge = '<span class="status status-idle">○ Idle</span>' %}
            {% endif %}
            <div class="agent-card">
              <span class="name">{{ emoji }} {{ a.get("name", a.get("agent_type", "Unknown")) }}</span>
              {{ badge | safe }}
              <span class="time">Last: {{ a.get("last_run") or "never" }}</span>
            </div>
          {% endfor %}
        {% else %}
          <div class="disconnected" style="grid-column:1/-1">🔌 Unable to load agent status</div>
        {% endif %}
      </div>
    </main>
  </div>
</body>
</html>
```

- [ ] **步骤 2：提交**

```bash
git add -A && git commit -m "feat: live dashboard with HTMX auto-refresh"
```

---

### 任务 4：更新 Agents 页面

**文件：**
- 修改：`app/templates/agents.html`

- [ ] **步骤 1：替换 agents.html 为动态模板**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agents — CrossWave</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  <link rel="stylesheet" href="/static/style.css">
  <style>
    :root { --bg: oklch(0.99 0.002 260); --surface: oklch(0.97 0.004 260); --border: oklch(0.91 0.008 260); --ink: oklch(0.18 0.02 260); --ink-dim: oklch(0.5 0.025 260); --accent: oklch(0.55 0.25 280); --green: oklch(0.55 0.2 160); --red: oklch(0.6 0.22 30); --font: 'Inter', system-ui, sans-serif; --radius: 10px; }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: var(--font); background: var(--bg); color: var(--ink); font-size: 14px; }
    .app { display: flex; min-height: 100vh; }
    .sidebar { width: 240px; background: var(--surface); border-right: 1px solid var(--border); padding: 24px; flex-shrink: 0; }
    .sidebar .logo { font-weight: 700; font-size: 16px; margin-bottom: 32px; }
    .nav-item { display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: var(--radius); color: var(--ink-dim); font-weight: 500; text-decoration: none; font-size: 13px; margin-bottom: 2px; }
    .nav-item:hover, .nav-item.active { background: oklch(0.55 0.25 280 / 0.1); color: var(--accent); }
    .main { flex: 1; padding: 32px; max-width: 1200px; }
    h1 { font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
    
    .agent-detail { display: grid; gap: 12px; margin-top: 24px; }
    .agent-row { display: grid; grid-template-columns: 200px 1fr auto; gap: 16px; padding: 12px 16px; border: 1px solid var(--border); border-radius: var(--radius); align-items: center; }
    .agent-row .name { font-weight: 600; }
    .agent-row .desc { font-size: 13px; color: var(--ink-dim); }
    .agent-row .badge { padding: 2px 10px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
    .badge-running { background: oklch(0.55 0.25 280 / 0.1); color: var(--accent); }
    .badge-idle { background: oklch(0.5 0 0 / 0.05); color: var(--ink-dim); }
    .badge-done { background: oklch(0.55 0.2 160 / 0.1); color: var(--green); }
    .badge-error { background: oklch(0.6 0.22 30 / 0.1); color: var(--red); }
    
    .disconnected { color: var(--ink-dim); font-style: italic; padding: 12px 0; }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="logo">✦ CrossWave</div>
      <a href="/dashboard" class="nav-item">📊 Dashboard</a>
      <a href="/agents" class="nav-item active">🤖 Agents</a>
      <a href="/" class="nav-item">🌐 Website</a>
    </aside>
    <main class="main">
      <h1>Agents</h1>
      <p style="color:var(--ink-dim);margin-bottom:24px">10 agents — autonomous company operations</p>
      
      <div class="agent-detail" id="agent-detail"
           hx-get="/api/v1/_proxy/agents/status"
           hx-trigger="load, every:15s"
           hx-swap="innerHTML">
        {% if agents is defined and agents %}
          {% for a in agents %}
            {% set name = a.get("name", a.get("agent_type", "Unknown")) %}
            {% set desc = a.get("description", "") %}
            {% set s = a.get("status", "idle") %}
            {% if s == "running" %}{% set badge_cls = "badge-running" %}{% set badge_text = "● Running" %}
            {% elif s == "done" %}{% set badge_cls = "badge-done" %}{% set badge_text = "✓ Done" %}
            {% elif s == "error" %}{% set badge_cls = "badge-error" %}{% set badge_text = "✗ Error" %}
            {% else %}{% set badge_cls = "badge-idle" %}{% set badge_text = "○ Idle" %}{% endif %}
            <div class="agent-row">
              <span class="name">{{ name }}</span>
              <span class="desc">{{ desc }}</span>
              <span class="badge {{ badge_cls }}">{{ badge_text }}</span>
            </div>
          {% endfor %}
        {% else %}
          <div class="disconnected">🔌 Unable to load agent data</div>
        {% endif %}
      </div>
    </main>
  </div>
</body>
</html>
```

- [ ] **步骤 2：提交**

```bash
git add -A && git commit -m "feat: live agents page with HTMX refresh"
```

---

### 任务 5：验证

- [ ] **步骤 1：本地启动验证**

```bash
# 在 crosswave 目录
python -m uvicorn app.main:app --port 8000
```

- [ ] **步骤 2：测试健康检查**

```bash
curl http://localhost:8000/health
# 预期: {"status":"ok","app":"CrossWave","version":"0.3.0"}
```

- [ ] **步骤 3：测试 Dashboard**

```bash
curl -s http://localhost:8000/dashboard | head -5
# 预期: 返回 HTML，页面正常渲染
```
