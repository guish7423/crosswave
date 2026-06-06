# CrossWave PROJECT_STATUS.md

## 最新状态 (Phase A 完成)
**版本**: v0.9.1
**git**: 90750f8 (`feat(phase-a): NocoBase-first data layer — CACHE fallback for all HQ routes`)
**测试**: 202 passed ✓

## 运行中服务
- hq-nocobase-1 (NocoBase, :13000→80)
- hq-postgres-1 (PostgreSQL, 98 tables, healthy)
- crosswave-crossblog (CrossBlog, :9000)
- searxng (搜索引擎)
- redis (主机 :6379)

## Phase A — CACHE→NocoBase 迁移
### 完成 (Steps 1-4)
- polsia_bridge.py: 扩展同步 leads/tasks/proposals/expenses/revenue_snapshots → NocoBase
- nocobase_client.py: 扩展 get_leads/get_tasks/get_proposals/get_expenses/get_revenue_history
- api_routes.py: 所有端点 NocoBase-first, CACHE-fallback
- monitor_routes + SSE/portal: 改为 NocoBase-first
- 测试: conftest NB_DISABLED=true + 扩展新集合断言

### 待办 (Step 5)
- 删除 CACHE 数据依赖（保留中，不安全一次性移除）

## 产品线
| 产品 | 状态 | 部署 |
|------|------|------|
| CrossBridge | Live | Railway |
| CrossBlog | ✓ Docker 就绪 | Railway 配置就绪 |
| CrossDeploy | v0.1.0, 11 tests | railway.toml 就绪 |
| Polsia Fork | submodule | docker-compose 集成 |
| HQ (管理层) | v0.9.1 | SSE + NocoBase |
| ~~HiveMind~~ | ❌ 已移除(独立私有仓库) | — |

## 下一阶段
1. Phase A Step 5: 安全移除 CACHE
2. Phase B: 插件系统注册表
3. Phase C: 事件总线
4. Phase D: MCP 标准暴露
5. 部署上生产: SSL/域名/Stripe live/SMTP/Sentry

## 已知问题
- coverage ~72% (polsia_bridge/scheduler 仍有gap)
- Ruff minor issues (~26)
- CACHE 仍作为 fallback 存在
- 无生产域名/SSL
