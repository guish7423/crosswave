# CrossWave PROJECT_STATUS.md

## 最新状态 (Phase C 完成)
**版本**: v0.9.1
**git**: 4703803 (`feat(phase-c): Event Bus — AI OS communication backbone`)
**测试**: ~210 passed ✓

## Phase C — Event Bus (AI OS 通信骨干)
### 完成
- `hq/event_bus/` 包: EventBus 单例, EventType 枚举, Event dataclass, Subscription
- REST API: `POST /api/hq/events` (发布), `GET /api/hq/events` (历史), `GET /api/hq/events/stream` (SSE)
- Plugin Registry 自动发布注册/注销事件
- 5 unit tests (singleton, publish, subscribe, filter, history_max)

### 待办
- **Push**: 等待用户授权推送到 GitHub
- **Phase D**: MCP 标准暴露
- **Step 5**: 安全删除 CACHE

## 运行中服务
- hq-nocobase-1, hq-postgres-1 (98 tables), crosswave-crossblog, searxng, redis

## 产品线
| 产品 | 状态 |
|------|------|
| CrossBridge | Live (Railway) |
| CrossBlog | Docker :9000 |
| CrossDeploy | v0.1.0 |
| Polsia Fork | submodule |
| HQ | v0.9.1, SSE + NocoBase + Event Bus |
