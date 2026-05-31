# CrossWave 运营手册

> 版本: v1.0 | 最后更新: 2026-05-31

---

## 公司全貌

CrossWave 是一家 **AI-Native 技术公司**，通过 6 条产品线覆盖 AI 翻译 → 内容生成 → 自动化运营 → 部署托管 → 桌面客户端。

```
CrossWave 🌊 (Brand Umbrella)
├── 🌉 CrossBridge   — AI翻译 SaaS         [✅ Live on Railway]
├── 📝 CrossBlog     — SEO博客 SaaS         [✅ 就绪, 待部署]
├── 🏢 Polsia Fork   — 10-Agent 后端平台    [✅ 完成, 57+67 tests]
├── 📊 CrossWave     — BFF 管理面板+官网    [✅ 完成, 632行官网+5HTMX]
├── 🚀 CrossDeploy   — 代部署服务 ¥2K-5K    [✅ 就绪, 官网已含]
└── 🐝 HiveMind       — Tauri v2 桌面客户端  [✅ 完成, ACUI 入仓]
```

---

## 产品运营手册

### 🌉 CrossBridge (翻译 SaaS)

- **状态**: ✅ Live on Railway (自动部署)
- **访问**: 通过 Railway 提供的 URL
- **维护**: 无特殊维护需求 — Flask 轻量应用
- **恢复**: Railway Dashboard 一键重启

### 📝 CrossBlog (SEO 博客 SaaS)

- **状态**: ✅ 代码就绪，**未部署**
- **位置**: `projects/ai-blog-engine/`
- **启动**:
  ```bash
  cd projects/ai-blog-engine
  python -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  LLM_API_MOCK=true uvicorn app.main:app --port 9000
  ```
- **部署**: Railway GitHub 集成（`guish7423/ai-blog-engine`）
- **种子数据**: `python scripts/seed_posts.py`
- **测试**: `python -m pytest tests/ -v`
- **生成内容**: `POST /generate` with topic/tone/lang params
- **博客页面**: 自动从 SQLite 读取（/blog）
- **Mock 模式**: LLM_API_MOCK=true 无需 API key
- **监控**: `/health` 返回文章总数

### 🏢 Polsia Fork (10-Agent 后端平台)

- **状态**: ✅ 本地验证通过，**未上线**
- **位置**: `projects/polsia-fork/`
- **这是我们最核心的资产** — 10 专业 Agent + Celery 调度 + FastAPI API + Next.js 管理面板
- **完整开发指南**: 见 `CLAUDE.md`

**本地启动**:
```bash
cd projects/polsia-fork/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
SANDBOX_MODE=true uvicorn app.main:app --port 8000
```

**调用验证**:
```bash
curl http://localhost:8000/api/v1/health
curl -H "X-API-Key: dev-key" http://localhost:8000/api/v1/dashboard/summary
```

**种子数据**: `python scripts/seed_demo.py --fresh` (39 tasks + 31-day revenue)
**测试**: `python -m pytest tests/unit/ -v` (57 tests ✅)
**前端**: `cd frontend && npm test -- --watchAll=false` (67 tests ✅)
**前端构建**: `cd frontend && npm run build` (15 pages, 87 kB init)

### 📊 CrossWave (BFF 管理面板 + 官网)

- **状态**: ✅ 完成，GitHub 已推送
- **位置**: `projects/crosswave/`
- **作为 BFF 代理** Polsia Fork 的所有 API
- **5 HTMX 端点**: summary/task-summary/agents-status/rows/activity

**启动**:
```bash
cd projects/crosswave
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
POLSIA_MOCK=true uvicorn app.main:app --port 9999
```

**访问**: 浏览器打开 http://localhost:9999
**Dashboard**: 通过 nav 进入 → Dashboard
**验证**: `python -m pytest tests/ -v` (17 tests ✅)

### 🚀 CrossDeploy (代部署服务)

- **状态**: ✅ 服务包装就绪
- **官网可见**: 3 档定价 (¥2K Basic / ¥3K Standard / ¥5K Enterprise)
- **交付品**: 默认包装 Polsia Fork 为企业部署
- **联系**: sales@crosswave.app
- **案例**: CrossBlog / Polsia Fork / CrossWave 官网 (全部实际交付项目)

### 🐝 HiveMind (桌面客户端)

- **状态**: ✅ 完成，GitHub Remote 已配置
- **仓库**: `guish7423/hivemind` (private)
- **位置**: `projects/hivemind/`
- **技术栈**: Tauri v2 + React 19 + Rust + ACUI
- **验证**: `cargo test --lib` (49/49 ✅), `tsc --noEmit` (0 errors)
- **构建**: `npm run tauri build`
- **注意**: 独立产品线，不直接参与 CrossWave 运营

---

## 依赖拓扑

```
用户 → CrossWave (9999) → Polsia Fork (8000) → DeepSeek API
      → CrossBridge → Railway (🧬 Live)
      → CrossBlog (9000) → SQLite / DeepSeek API
      → CrossDeploy → 静态页面 (官网)
```

**本地全栈启动命令** (启动 CrossWave + Polsia Fork):
```bash
# Terminal 1: Polsia Fork
cd ~/.opencode-workspace/projects/polsia-fork/backend
source venv/bin/activate
SANDBOX_MODE=true uvicorn app.main:app --port 8000

# Terminal 2: CrossWave
cd ~/.opencode-workspace/projects/crosswave
source venv/bin/activate
uvicorn app.main:app --port 9999

# 浏览器: http://localhost:9999
# 测试 Polsia Fork: curl -H "X-API-Key: dev-key" http://localhost:8000/api/v1/dashboard/summary
```

---

## 上线运营准备 Checklist

### 即刻可用 (零成本)
- [x] CrossWave 官网已上线 (localhost:9999)
- [x] Dashboard 数据可视化 (5 HTMX 端点)
- [x] Polsia Fork 57/57 后端测试 + 67/67 前端测试
- [x] 17 种子数据表 (SQLite)
- [x] 39 种子任务 + 31 天收入曲线
- [x] CrossBlog 18 测试 + 7 种子文章
- [ ] 部署 Polsia Fork 到 Railway → **激活 Dashboard**
- [ ] 部署 CrossBlog 到 Railway

### 运营准备 (需操作)
- [ ] 注册公司域名 (crosswave.app 已指向?)
- [ ] 配置 Polsia Fork 生产数据库 (PostgreSQL → Supabase/Neon)
- [ ] 配置 Redis (Redis Cloud / Railway Redis)
- [ ] PM2/Systemd 保活配置 (生产环境)
- [ ] 监控告警 (Healthchecks.io / Uptime Kuma)

### 变现准备 (需付费/API)
- [ ] 激活 Polsia Fork Agents (配置 DeepSeek API Key)
- [ ] 配置 Stripe 支付 (CrossBridge 已有)
- [ ] CrossDeploy 正式报价单模板
- [ ] CrossBlog 付费定价上线

---

## 故障恢复

| 症状 | 原因 | 修复 |
|------|------|------|
| Dashboard 显示 "Disconnected" | Polsia Fork 未运行 | `POLSIA_MOCK=true` 重启 CrossWave |
| Polsia Fork 启动慢 | chromadb 导入 | 等待 10-15s |
| CrossBlog 点 /blog 500 | DB 未初始化 | `python scripts/seed_posts.py` |
| Agent 返回 mock 响应 | SANDBOX_MODE=true | 配置 LLM_API_KEY + SANDBOX_MODE=false |
| npm test 失败 | jest-dom 版本冲突 | 检查 package.json，降级到 v5 |

---

## 商业方向

从 `projects/polsia-fork/PLAN_BUSINESS.md` 和 `marketing/` 文件的研究结论：

**已验证商业机会**: AI Content Bridge — 中文→英文文化本地化 + 多平台发布工具
- 目标用户: 中国出海创业者/独立开发者
- 定价: $19-49/月
- 技术: 复用 Polsia Fork 的 LLM/Agent/Celery 基础设施
- 启动成本: ~$30/月

**备选**: AI 自动化部署 (CrossDeploy)、AI 网站聊天机器人

**核心优势**: Polsia Fork 10-Agent 平台是技术护城河 — 传统 SaaS 需要 6-12 月开发的功能我们已经完成。

---

*本文件是 CrossWave 公司运营的事实来源。修改前需更新相关产品代码或配置。*
