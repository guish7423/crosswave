# PROJECT_STATUS.md — Session 2026-06-05 (v0.6.3)

Last updated: 2026-06-05  (end of 3rd major session)

## 当前阶段: Phase 3+ 完善 → Phase 4 完成 ✅

### 本轮交付

| 功能 | 状态 | Commit |
|------|------|--------|
| Admin 登录页 (bcrypt + itsdangerous session) | ✅ | a63f7b7 |
| Stripe 支付基础设施 (webhook + checkout + setup脚本) | ✅ | 97ab51f |
| Sentry 配置文档 + README | ✅ | f1fad1c |
| ruff 全面清理 (23处) | ✅ | 80e0fff |
| CI 增强 (pytest-xdist + ruff scripts) | ✅ | 80e0fff |

### 架构快照 (v0.6.3)

```
app/
├── config.py              # Pydantic Settings v2
├── main.py                # create_app() 工厂
├── core/
│   ├── exceptions.py       # AppError 层次
│   └── middleware.py        # 安全头 + 请求ID
├── domains/
│   ├── page_routes.py
│   ├── proxy_routes.py
│   ├── blog_proxy.py
│   └── mcp_routes.py
├── services/
│   └── polsia_client.py
├── templates/
└── static/

hq/
├── server.py (25行工厂)
├── domains/
│   ├── data.py, middleware.py
│   ├── page_routes.py, api_routes.py
│   ├── monitor_routes.py, model_router_routes.py
│   ├── auth_routes.py, stripe_routes.py     ← NEW
├── model_router/          # Phase 3 LLM Provider
├── polsia_bridge.py
├── plugins/crosswave-hq/  # NocoBase 插件
├── scripts/
│   ├── seed_hq_data.py
│   └── test-provider.sh
├── templates/
└── tests/ (55 + 23 unit + 7 auth + 2 stripe)

scripts/
├── setup_stripe.py        # ← NEW: Stripe Product/Price 创建
└── setup-ssl.sh
```

### 测试矩阵

| Suite | Count | Status |
|-------|-------|--------|
| Core (tests/) | 85 | ✅ |
| HQ API (hq/tests/test_api.py) | ~40+ | ✅ |
| HQ Pages (hq/tests/test_pages.py) | 13 | ✅ |
| Model Router Unit | 23 | ✅ |
| Auth (hq/tests/test_auth.py) | 7 | ✅ NEW |
| Stripe (hq/tests/test_stripe.py) | 2 | ✅ NEW |
| Integration (需要API keys) | 4 | ⏭️ skip |
| **Total** | **~176** | **✅ all pass** |

### 已安装依赖

```
pydantic-settings, bcrypt, itsdangerous, stripe
pytest-xdist, pytest-cov, pytest-asyncio, respx
sentry-sdk (代码就绪)
```

### 产品线状态

| 产品 | 代码 | 部署 | 支付 | 状态 |
|------|------|------|------|------|
| CrossBridge | ✅ | ✅ Railway | 🔲 待配密钥 | 上线 |
| CrossBlog | ✅ | ❌ | 🔲 | 待部署 |
| CrossDeploy | ✅ | ❌ | 🔲 待配密钥 | 待部署 |
| HiveMind (Tauri) | ✅ | ❌ | N/A | 待发布 |
| Polsia Fork | ✅ | ❌ | N/A | 待部署 |
| CrossWave HQ | ✅ | ❌ | N/A | 本机运行 |

### 待用户手动操作

| 操作 | 文件参考 |
|------|---------|
| 配置 `SENTRY_DSN` | .env 第5行 |
| 配置 `ADMIN_PASSWORD_HASH` | `python -c "import bcrypt; print(bcrypt.hashpw(b'...', bcrypt.gensalt()).decode())"` |
| 配置 `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` | .env 第14-15行 |
| 运行 `python scripts/setup_stripe.py` 创建产品/价格 | 生成 Price IDs |
| 配置 `BASE_URL` | .env 第49行 |
| 域名/DNS/SSL | CROSSWAVE_OPS.md, scripts/setup-ssl.sh |
| 生产 VPS / Railway | pyproject.toml, render.yaml |
