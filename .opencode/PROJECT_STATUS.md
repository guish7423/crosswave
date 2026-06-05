# PROJECT_STATUS.md — Session 2026-06-05 (v0.7.0)

Last updated: 2026-06-05

## 当前阶段: Phase 5a ✅

### 本轮交付 (Phase 5a)

| 功能 | 状态 | Commit |
|------|------|--------|
| **修复 15 处 HTML 合并冲突** | ✅ | c419357 |
| → dashboard.html (6处), employees.html (2处), orders.html (7处) | ✅ | |
| **SSE 实时 Dashboard 端点** `/api/hq/events` | ✅ | c419357 |
| **Dashboard EventSource 自动刷新** (SSE 心跳 → KPI 刷新) | ✅ | c419357 |
| **CrossBlog Railway 部署配置** `crossblog.railway.toml` | ✅ | c419357 |

### 架构快照 (v0.7.0)

```
hq/domains/
├── data.py               # CACHE + Polsia Fork 同步
├── middleware.py          # require_token + require_session
├── page_routes.py        # 11 页面路由
├── api_routes.py         # 8 API 端点
├── monitor_routes.py     # health + monitor + evolution + portal + SSE ← NEW
├── model_router_routes.py
├── auth_routes.py
└── stripe_routes.py
```

### 测试矩阵 (Current: HEAD c419357)

| Suite | Count | Status |
|-------|-------|--------|
| Core (tests/) | 85 | ✅ |
| HQ API + Pages | 55 | ✅ |
| Model Router Unit | 23 | ✅ (2 skip) |
| Auth | 7 | ✅ |
| Stripe | 2 | ✅ |
| **Total** | **174** | **✅ (2 skip)** |

### 产品线状态

| 产品 | 代码 | 部署 | 支付 | 状态 |
|------|------|------|------|------|
| CrossBridge | ✅ | ✅ Railway | 🔲 待配密钥 | 上线 |
| CrossBlog | ✅ | railway.toml 就绪 | 🔲 | 部署就绪 |
| CrossDeploy | ✅ | ❌ 待配置 | 🔲 | 待部署 |
| HiveMind (Tauri) | ✅ | ❌ | N/A | 待发布 |
| Polsia Fork | ✅ | ❌ | N/A | 待部署 |
| CrossWave HQ | ✅ | ❌ | N/A | 本机运行 |

### 待用户手动操作

| 操作 | 参考 |
|------|------|
| 配置 `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` | .env |
| 运行 `python scripts/setup_stripe.py` 创建产品/价格 | scripts/ |
| 配置 `ADMIN_PASSWORD_HASH` | .env |
| 配置域名/DNS/SSL (crosswave.app / blog.crosswave.app) | nginx.conf |
| 推 CrossBlog 到 Railway: `cd ai-blog-engine && railway up` | crossblog.railway.toml |
