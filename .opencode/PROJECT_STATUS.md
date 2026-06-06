# CrossWave PROJECT_STATUS.md

## 最新状态 (Phase D 完成)
**版本**: v0.9.2
**git**: f3bbdd4 (`feat(phase-d): MCP tool definitions — Plugin Registry + Event Bus + NocoBase queries`)
**测试**: ~202+ passing
**提交**: f3bbdd4 → origin/main

## 运行中服务
- hq-nocobase-1 (NocoBase, :13000→80)
- hq-postgres-1 (PostgreSQL, 98 tables, healthy)
- crosswave-crossblog (CrossBlog, :9000)
- searxng (搜索引擎)
- redis (主机 :6379)

## AI OS 架构进展

### Phase A — NocoBase-First 数据层 ✅
- polsia_bridge 扩展同步 5 集合到 NocoBase
- nocobase_client 扩展读取方法
- 所有端点 NocoBase-first, CACHE-fallback

### Phase B — Plugin Registry ✅
- hq/plugin_registry/ 包: 模型+单例+REST API
- 自动注册 5 产品到 lifespan
- 60s 健康检查后台任务
- SSE 集成插件状态

### Phase C — Event Bus ✅
- hq/event_bus/ 包: EventBus 单例+EventType 枚举+Event dataclass
- HTTP API + SSE stream for real-time events
- Plugin Registry 自动发布注册/注销事件

### Phase D — MCP 标准暴露 ✅
- hq/mcp_server.py: 10 个 MCP 工具定义
- crosswave.plugins.{list,get,register,heartbeat}
- crosswave.events.{publish,history}
- crosswave.system.status
- crosswave.nocobase.{stats,summary,query}
- SSE transport at /api/hq/mcp/

## 产品线
| 产品 | 状态 | 部署 |
|------|------|------|
| CrossBridge | Live | Railway |
| CrossBlog | ✓ Docker 就绪 | Railway 配置就绪 |
| CrossDeploy | v0.1.0, 11 tests | railway.toml 就绪 |
| Polsia Fork | submodule | docker-compose 集成 |
| HQ (管理层) | v0.9.2 | SSE + NocoBase + MCP |
| HiveMind | ❌ 已移除(私有仓库) | — |

## 待办
1. Step 5: 安全移除 CACHE 数据依赖
2. Dashboard UI: 插件状态面板
3. 部署上生产: SSL/域名/Stripe live/SMTP/Sentry
4. Ruff minior issues 清理
5. Coverage 提升 (>80%)
