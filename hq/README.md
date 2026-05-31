# CrossWave HQ

公司统一后台管理系统，包含 NocoBase 数据平台 + Bridge API 服务。

## 架构

```
hq/
├── docker-compose.yml    # NocoBase + PostgreSQL 16 (:13000)
├── server.py             # Bridge API 服务 (:13001)
├── dashboard.html        # 战情室仪表板
├── employees.html        # 员工管理页面
├── orders.html           # 订单中心页面
├── scheduler.py          # 独立定时同步脚本
├── polsia_bridge.py      # Polsia DB → NocoBase 数据同步
└── plugins/crosswave-hq/ # NocoBase 插件 (4个集合定义)
```

## 启动

### 1. NocoBase 数据平台
```bash
cd hq && docker compose up -d
```
访问 http://localhost:13000

### 2. Bridge API 服务
```bash
cd hq && python3 server.py
```
访问 http://localhost:13001 (战情室页面)

### 3. 数据同步
Bridge 启动后每 30 分钟自动同步一次 Polsia Fork 数据。
也可手动触发: `python3 scheduler.py`

## 页面

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 战情室 | KPI + 3 Chart.js 图表 + 业务线健康 + 员工 + 活动 |
| `/employees` | 员工管理 | 角色/状态分布 + 详细员工表格 |
| `/orders` | 订单中心 | 订单筛选 + 平台连接状态 |

## 配置

环境变量 (server.py):
- `POLSIA_DB` — Polsia Fork SQLite 路径 (默认 ~/.opencode-workspace/projects/polsia-fork/polsia.db)
- `HQ_URL` — NocoBase API 地址 (默认 http://localhost:13000/api)
- `HQ_TOKEN` — NocoBase API Token
