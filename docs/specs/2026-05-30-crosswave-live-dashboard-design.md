# CrossWave Live Dashboard — 设计规格

## 概述

CrossWave 管理面板（Dashboard + Agents）目前是纯静态 HTML mockup，数据全部硬编码。本设计将管理面板连接到 Polsia Fork 的实时 API，使数据动态化。

## 架构

```
Browser ──→ CrossWave (FastAPI + Jinja2 + HTMX)
                  │
                  │ httpx (server-side)
                  ▼
           Polsia Fork (/api/v1/*)
```

- CrossWave 作为 **BFF（Backend-for-Frontend）** 代理 Polsia Fork API
- 模板渲染时嵌入实时数据
- HTMX 实现 Agent 状态和 Activity 的自动刷新

## 新增文件

| 文件 | 职责 |
|------|------|
| `app/services/polsia_client.py` | Polsia Fork API 客户端（httpx.AsyncClient） |
| `app/config.py` | CrossWave 配置（POLSIA_BASE_URL, POLSIA_API_KEY） |

## 修改文件

| 文件 | 改动 |
|------|------|
| `app/main.py` | 新增 `/api/v1/_proxy/*` 代理路由 + lifespan 初始化客户端 |
| `app/templates/dashboard.html` | 从 Polsia API 读取数据渲染；Agent 卡片区域加 hx-get |
| `app/templates/agents.html` | 从 Polsia API 读取数据渲染 |
| `app/static/style.css` | 新增 disconnected 状态样式 + 加载骨架屏 |
| `requirements.txt` | 新增 `httpx` |
| `Dockerfile` | 无需改动 |

## API 代理路由

| CrossWave 路由 | 目标 Polsia Fork | 用途 |
|----------------|------------------|------|
| `GET /api/v1/_proxy/dashboard/summary` | `/api/v1/dashboard/summary` | 4 个统计卡片 |
| `GET /api/v1/_proxy/agents/status` | `/api/v1/agents/status` | Agent 实时状态列表 |
| `GET /api/v1/_proxy/activity` | `/api/v1/dashboard/activity` | 活动日志列表 |

所有代理路由：
- 自动附加 `X-API-Key` header
- 超时 5s，失败返回 `{"status": "disconnected"}`
- 透传原始 JSON 响应（不做二次映射）

## 错误处理

| 场景 | 前端表现 |
|------|---------|
| Polsia Fork 不可达 | 卡片显示 "Disconnected" + 灰色状态 |
| 超时 | 同不可达，不影响页面其他部分 |
| 某 agent 状态缺失 | 单独显示 "Unknown"，不阻塞全部 |

## HTMX 配置

- Agent 状态区域：`hx-get="/api/v1/_proxy/agents/status" hx-trigger="load, every:30s" hx-swap="innerHTML"`
- Activity 区域：`hx-get="/api/v1/_proxy/activity" hx-trigger="load, every:60s" hx-swap="innerHTML"`
- 骨架屏：HTMX 加载时显示 CSS skeleton 动画

## 非功能需求

- 响应时间：首屏完整渲染 < 300ms（代理缓存只做 ttl=10s 内存缓存）
- 降级：Polsia Fork 不可用时不崩页面，只标记对应区域
- 安全：API Key 仅存服务器端，浏览器无法获取
- 依赖：仅新增 `httpx` 一个依赖
