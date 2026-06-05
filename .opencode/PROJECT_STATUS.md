# PROJECT_STATUS.md — Session 2026-06-05 (v0.5.0 → v0.6.0)

Last updated: 2026-06-05

## 当前阶段: Phase 3+ 项目完善 & 生态布局

### ✅ 本轮完成

| 组件 | 内容 | 状态 |
|------|------|------|
| **Sentry 错误追踪** | sentry-sdk 集成到 CrossWave (app/main.py) + .env.example 配置项 | ✅ |
| **Provider 错误处理** | 指数退避重试(429/5xx)、超时/连接错误优雅降级、ModelResponse.error 字段 | ✅ |
| **CLI 测试工具** | `hq/scripts/test-provider.sh` — 一键测试所有 Provider (mock/openai/deepseek) | ✅ |
| **Git Submodules** | polsia-fork + ai-blog-engine 作为 submodule 纳入 crosswave 生态 | ✅ |
| **Docker Compose 统一** | docker-compose.yml 路径更新 + docker-compose.override.yml (热重载) | ✅ |
| **集成测试** | 错误处理测试(25项) + 真实 API 集成测试(2项, 无 key 时跳过) | ✅ |

测试:
- **CrossWave 核心: 85/85 通过** ✅
- **Model Router: 25/25 通过** (另有 2 项真实 API 测试因无 key 跳过) ✅
- **HQ API: 18 项预存失败** (server.py 路由变更导致, 待修复)

### 版本: v0.6.0

### 新增文件
```
.gitmodules                              ← Submodule 注册
polsia-fork/                             ← Submodule: guish7423/polsia-fork
ai-blog-engine/                          ← Submodule: guish7423/ai-blog-engine
docker-compose.override.yml              ← 本地开发覆盖 (热重载)
hq/scripts/test-provider.sh              ← Provider 连通性测试
hq/scripts/README.md                     ← 脚本说明
```

### 架构说明 (更新)
```
┌────────────────────────────────────────────────────────────┐
│ crosswave (v0.6.0)                                         │
│   FastAPI + HTMX + Sentry + model_router                   │
│   Submodules: polsia-fork + ai-blog-engine                  │
├────────────────────────────────────────────────────────────┤
│ docker compose up -d  →  全部 7 个服务一键启动               │
├────────────────────────────────────────────────────────────┤
│ hq/scripts/test-provider.sh                                 │
│   → Mock: instant ✓                                        │
│   → OpenAI: needs LLM_API_KEY                              │
│   → DeepSeek: needs DEEPSEEK_API_KEY                       │
└────────────────────────────────────────────────────────────┘
```

### 各服务运行状态
| 服务 | 端口 | 运行方式 | 状态 |
|------|------|---------|------|
| Polsia Fork (19 Agents) | :8001 | submodule/systemd | ✅ |
| Celery Worker+Beat | - | submodule/systemd | ✅ |
| CrossWave (v0.6.0) | :9999 | systemd | ✅ |
| CrossBlog | :8002 | submodule/systemd | ✅ |
| HQ Bridge | :13001 | systemd | ✅ |
| NocoBase (PG16) | :13000 | hq/docker-compose.yml | ✅ |

### 下一步选择
1. **修复 HQ API 测试** (18项预存失败 — 需要更新 server.py 路由或测试用例)
2. **真实 LLM API 集成** — 设 LLM_PROVIDER_MOCK=false + 配置 API keys
3. **Deploy prep** — 域名/SSL/VPS 部署全栈
4. **Stripe 支付** — 生产密钥 + 支付流程
