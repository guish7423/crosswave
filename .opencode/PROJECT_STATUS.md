# PROJECT_STATUS.md — Session 2026-06-03

Last updated: 2026-06-03

## 当前阶段: Audit + Kernel Refactor Phase

### Phase 0: 状态机 ✅ (1004acc5, 12 tests)
- `app/core/status_machine.py`: TaskStatus 枚举 + 合法转换表 + TaskStatusField descriptor
- `app/services/task_service.py`: 状态转换验证
- HQ: 前端新增 blocked/paused/in_review 过滤

### Phase 1a: 结构化 Agent Schema ✅ (407f0d8, 27 tests)
- `app/agents/schema.py`: AgentSchema dataclass (role/goal/backstory/tools/tier/schema/instructions)
- `app/agents/registry.py`: 17个 Agent 全部结构化注册

### Phase 1b: Redis Checkpoint ✅ (407f0d8, 9 tests)
- `app/core/checkpoint.py`: Inngest-style step-level checkpoint, Redis优先/内存回退
- `run(step_name, fn, *args)` 幂等执行

### Phase 1c: HITL Interrupt ✅ (ab5bebd2 + 96c9d881/d2a9f35, 39 tests)
- `app/core/interrupt_service.py`: JSON-backed pending queue + create/approve/reject
- `app/api/v1/interrupts.py`: GET /pending + POST approve/reject
- `app/agents/base.py`: request_interrupt() in BasePolsiaAgent
- `celery_app/tasks/agent_tasks.py`: interrupt gate
- HQ: interrupts.html + nav + proxy routes
- 26 unit + 13 integration = 39 tests + 40 Phase 0-1b = 79 core tests

### Phase 2: Industry Packs ✅ (本地, 4 YAML)
- `hq/industry-packs/`: SaaS / E-Commerce / Content / Agency 启动模板
- `hq/industry_pack_service.py`: YAML loader
- HQ industry-packs.html: 特色卡片+Agent映射+定价+交付物+排程
- PyYAML 依赖已添加

## 阻塞项
- ⛔ GitHub SSH/HTTPS 网络超时 (WSL2 网络问题)
- 5 个 commit (Phase 0 + Phase 1ab + 1c + 1c fix + Phase 2) 全部本地,下次 session 统一 push

## 全栈运行状态
| 服务 | 端口 | 状态 |
|------|------|------|
| Polsia Fork (19 Agents, 79+ core tests) | :8001 | ✅ 运行中 |
| Celery Worker+Beat (11 schedules) | - | ✅ |
| CrossWave (v0.3.0, 33 tests) | :9999 | ✅ |
| CrossBlog (140 posts, 47 tests) | :8002 | ✅ |
| HQ Bridge (27 modules, 55 tests) | :13001 | ✅ |
| NocoBase (PG16, 4 collections) | :13000 | ✅ |

## 待构建
- Phase 3: LLM Provider Abstraction (Dify-style ModelInstance)
- Phase 4: 多层级记忆 (Airymax 4-layer)
- Phase 5: Plugin Runtime Isolation
- HQ tests 从 55 扩展到覆盖新模块
