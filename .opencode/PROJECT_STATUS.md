# CrossWave PROJECT_STATUS.md

## 最新状态 (v0.9.3)
**git**: 05b88c5 (`feat: event stream — polsia_bridge + nocobase_client publish to Event Bus`)
**AI OS**: 四层架构全面就绪 ✅

## AI OS 架构

```
┌─────────────────────────────────────────┐
│  Phase D: MCP Standard (10 tools)       │
├─────────────────────────────────────────┤
│  Phase C: Event Bus (publish/subscribe)  │
├─────────────────────────────────────────┤
│  Phase B: Plugin Registry (5 products)   │
├─────────────────────────────────────────┤
│  Phase A: NocoBase-First Data Layer      │
└─────────────────────────────────────────┘
```

## 运行中服务
- hq-nocobase-1 :13000→80
- hq-postgres-1 (98 tables, healthy)
- crosswave-crossblog :9000
- searxng
- redis :6379

## 产品线
| 产品 | 状态 |
|------|------|
| CrossBridge | Live (Railway) |
| CrossBlog | Docker ready (Railway config) |
| CrossDeploy | v0.1.0 (Docker + Railway) |
| HQ/MCP | v0.9.3 (SSE + NocoBase + Plugin + Event + MCP) |

## 待办
- Step 5: CACHE 数据依赖清理
- 生产部署: SSL/域名/Stripe/SMTP/Sentry
- Ruff 清理 + 覆盖率提升
