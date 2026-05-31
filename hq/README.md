# HQ — NocoBase 部署

`hq/` 目录包含 NocoBase 低代码平台的 Docker 部署配置，使用 PostgreSQL 16 作为数据库。

## 启动

```bash
cd hq
docker compose up -d
```

## 验证

```bash
curl http://localhost:13000/api/health
```

## 配置

编辑 `.env` 文件可修改数据库连接信息和 NocoBase 管理员账户密码。
