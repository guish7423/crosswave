# CrossWave 公司战略手册 v1.0

> 统一战略文档 — 整合 PLAN_BUSINESS.md / action-plan.md / final-research-plan.md / CROSSWAVE_OPS.md

---

## 一、公司使命

**让中国创业者零障碍走向全球**

CrossWave 不是软件公司，是 **AI-Native 运营基础设施**。我们的产品帮助中国出海者解决从技术到内容到运营的一切问题。

---

## 二、产品矩阵

| 产品 | 角色 | 目标用户 | 营收模式 | 状态 |
|------|------|----------|----------|------|
| **Polsia Fork** | 🏢 核心引擎 | 内部平台（不直接销售） | 成本中心 | ✅ |
| **CrossBridge** | 🌉 现金牛 #1 | 出海团队 | $19-49/月 SaaS | ✅ Live |
| **CrossBlog** | 📝 内容引擎 | SEO + 内容营销 | 支撑其他产品 | ✅ |
| **CrossDeploy** | 🚀 现金牛 #2 | 传统企业 | ¥2K-5K/单次 | ✅ |
| **CrossWave** | 📊 管理面板 | 内部运营 | 支撑平台 | ✅ |
| **HiveMind** | 🐝 战略产品 | 技术用户 | 远期变现 | ✅ |
| **CrossPost (规划中)** | 📣 核心变现 | 出海创业者 | $19-49/月 SaaS | 📋 |

### 产品依赖关系

```
用户 → CrossBlog (SEO引流)
     → CrossDeploy (传统企业)
     → CrossPost (出海创业者) [规划]
         ↓
    CrossWave BFF (统一路由)
         ↓
    Polsia Fork (10 Agent 引擎)
         ↓
    DeepSeek API (LLM)
         ↑
    CrossBridge (翻译能力复用)
```

---

## 三、市场定位

### 我们不是
- 又一个 cross-posting 工具（赛道已饱和）
- 纯技术外包公司
- AI 聊天机器人模板

### 我们是
**出海 AI 基础设施** — 从内容本地化 → 多平台发布 → 效果追踪的全链路平台

### 目标市场
- **TAM**: 中国出海 AI 营销市场 800 亿元（2026 预计）
- **目标用户画像**:
  1. 出海独立开发者（有产品、不会英文营销）
  2. 跨境电商（需持续在 X/LinkedIn 建立品牌）
  3. AI 创业者（想做 Global 但缺英文内容能力）

### 竞争优势
Polsia Fork 10-Agent 平台 = 6-12 个月的工程护城河。竞品需从零搭建 Agent 编排/调度/记忆/工具链系统，我们已完成。

---

## 四、Go-to-Market 路线图

### 当前阶段：Pre-Launch（已完成）
- ✅ 全栈 6 产品线代码就绪
- ✅ 57+67+18+17+49 = **208 tests 全部通过**
- ✅ 官网 632 行中英双语
- ✅ Dashboard 实时数据
- ✅ 7-21 篇种子内容
- ✅ Docker Compose 一键部署
- ❌ 未上线（用户要求）

### Phase 1：冷启动（你决定上线后）

**第 1 步：部署 Polsia Fork → Railway**
- 多数据库 PostgreSQL（Railway 内置）
- 配置 Redis（Railway 内置）
- 设置 X-API-Key 生产密钥
- 部署时间：30 分钟

**第 2 步：部署 CrossWave → Railway**
- 指向 Polsia Fork 生产 URL
- 官网 + Dashboard 自动激活
- 部署时间：15 分钟

**第 3 步：部署 CrossBlog → Railway**
- 运行种子脚本（21 篇基础内容）
- 连接 CrossWave 导航
- 部署时间：15 分钟

### Phase 2：变现启动

**第 4 步：激活 Agents（按 AGENT_ACTIVATION.md）**
- Week 1: 单 Agent 验证（config DeepSeek Key）
- Week 2: Social + Content Agent
- Week 3: 批次激活（Analysis + Outreach + Ad）
- Week 4: 全量切换生产

**第 5 步：CrossPost 产品化**
- 用 Polsia Social Media Agent + Content Agent 包装为独立 SaaS
- Landing Page + Stripe 支付
- Product Hunt 发布
- Build in Public（X/Twitter 日更）

---

## 五、营收模型

| 收入来源 | 单价 | 目标 MRR | 时间线 |
|----------|------|----------|--------|
| CrossBridge (§19-49/月) | $19-49 | $500-2000 | ✅ 已有 |
| CrossDeploy (¥2K-5K/单) | ¥2000-5000 | ¥6000-15000 | 即时 |
| CrossPost (§19-49/月) | $19-49 | $1000-5000 | Phase 2 |

### 成本结构
| 项目 | 月费 |
|------|------|
| DeepSeek API | $5-50 |
| Railway 托管 | $7-20 |
| 域名 | $1 |
| Stripe 抽成 | 2.9% + $0.30 |
| **总计** | **~$50/月** |

**Break-even**: 3 个 Starter 订阅 或 1 单 CrossDeploy

---

## 六、运营架构

### 日常运营流程

```
内容生产 (CrossBlog) → SEO 自然流量 → CrossWave 官网
     ↓
用户触达 → Sales@crosswave.app → CrossDeploy 报价
     ↓
Agent 运营 → Social Agent (海外社媒)
           → Content Agent (博客自动生成)
           → Outreach Agent (客户触达)
           → Analysis Agent (数据监控)
```

### 关键指标

| 指标 | 当前 | Phase 1 目标 | Phase 2 目标 |
|------|------|-------------|-------------|
| 官网内容页面 | 1 (632行) | 5 | 15 |
| 博客文章 | 21 | 50 | 200+ |
| Agent 运营时间 | 0h | 24/7 | 24/7 |
| 客户 | 0 | 5 | 50 |
| MRR | $0 | $500 | $5000 |

---

## 七、竞争格局

| 竞品 | 与我们差异 |
|------|-----------|
| SiteGPT ($100K MRR) | 单点工具 vs 全链路平台 |
| Stanley for X ($4K/48h) | X 平台仅限 vs 多平台 |
| Kleo ($62K) | LinkedIn 仅限 vs 全平台 |
| ShipFast ($20K) | 开发模板 vs 运营平台 |
| 智媒通/PostAll | 纯调度 vs AI 原生改写 |

**我们的不可替代性**：
1. 中文→英文文化本地化（不是翻译，是改写）
2. 10-Agent 自主运营（不是工具，是团队）
3. 全链路（内容→发布→分析→优化）

---

## 八、风险评估

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 市场太小（CN出海） | 低 | 中 | 扩展到 EN→多语言 |
| 竞品抄袭功能 | 中 | 中 | Build in Public + 品牌信任 |
| LLM API 成本失控 | 低 | 高 | DeepSeek Flash $0.01/1K tokens, 设用量上限 |
| Agent 激活后不稳定 | 中 | 高 | 4 阶段逐步激活，每阶段有回滚方案 |
| 无人付费 | 中 | 高 | 免费层积累用户 → 付费转化 |

---

*本文件是 CrossWave 公司战略的事实来源。与 CROSSWAVE_OPS.md（运营手册）、AGENT_ACTIVATION.md（Agent 激活指南）组成公司文档体系。*
