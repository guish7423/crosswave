# Phase R4 — 共享 Auth 服务设计

## 问题

当前 3 个独立应用各有一套认证逻辑:
- 官网 (:9999) — 无认证
- HQ 管理端 (:9999/hq) — 自定义 token/session
- 产品线 (CrossBridge/CrossBlog/CrossDeploy) — 各自实现

## 方案: 统一 JWT + SSO

### 架构

```
products/ (各产品微服务)
  ├── auth/              ← 共享认证包 (packages/auth)
  │   ├── jwt.py          ← JWT 签发/验证
  │   ├── middleware.py   ← FastAPI Depends
  │   └── models.py      ← TokenPayload, UserClaims
  ├── bridge/
  ├── blog/
  └── deploy/
```

### 核心设计

```python
# packages/auth/jwt.py
class TokenPayload(BaseModel):
    sub: str          # user_id
    org_id: str       # 组织
    app_id: str       # 产品标识 (crossbridge/crossblog/crossdeploy/hq)
    role: str         # admin/member/viewer
    exp: datetime     # 过期时间

def create_token(payload: TokenPayload, secret: str) -> str: ...
def verify_token(token: str, secret: str) -> TokenPayload: ...
```

### 工作流

```
┌─────────┐     POST /auth/login      ┌──────────┐
│  Client  │ ───────────────────────→  │ Auth API │
│          │ ←─── { access_token } ─── │ (packages/auth/routes.py)
└─────────┘                            └──────────┘
        │                                    │
        │  GET /api/resource                 │
        │  Authorization: Bearer <token>     │
        │                                    ▼
        └────────────────────────→ 产品微服务
                                     │
                                     ├─ jwt.verify_token()
                                     └─ TokenPayload → request.state.user
```

### 迁移路径

| 步骤 | 改动 | 依赖 |
|------|------|------|
| 1 | `packages/auth/` 包 (JWT + middleware + models) | `pyjwt` |
| 2 | HQ `/login` 改为签发 JWT (兼容旧 session) | Step 1 |
| 3 | HQ middleware 支持 JWT bearer token | Step 2 |
| 4 | 产品线接入 JWT 验证 | Step 1 |
| 5 | SSO — 跨产品单点登录 | Step 3-4 |

### 非设计决策
- 不引入新数据库 (基于 JWT, 无状态)
- 不引入第三方 Auth 服务 (Clerk/Supabase 留待 Phase S)
- 兼容现有 X-HQ-Token (迁移期间双支持)
