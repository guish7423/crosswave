# CrossWave 🌊 — AI Globalization Stack

> 帮助中国创业者走向全球。一站式 AI 翻译、SEO 内容生成、技术部署。

## 产品矩阵

| 产品 | 状态 | 目录 | 链接 |
|------|------|------|------|
| 🌉 **CrossBridge** | ✅ 已上线 | `products/bridge/` | [Live](https://ai-content-bridge-production.up.railway.app) |
| 📝 **CrossBlog** | ✅ 代码就绪 | `products/blog/` | 待部署 |
| 🚀 **CrossDeploy** | ✅ 服务就绪 | `products/deploy/` | [报价](https://ai-content-bridge-production.up.railway.app/crosswave) |

## 技术栈

- **后端**: FastAPI + SQLAlchemy + Celery + Redis
- **前端**: 静态 HTML/CSS + HTMX
- **AI**: DeepSeek API / NVIDIA Llama 3.1 8B
- **支付**: Stripe (待配置密钥)
- **部署**: Docker + Railway

## 快速开始

```bash
# 官网（FastAPI）
cd app && pip install -r requirements.txt
uvicorn app.main:app --reload

# CrossBridge（独立部署）
cd products/bridge
uvicorn app.main:app --port 8001 --reload
```

## 目录结构

```
crosswave/
├── app/                  # CrossWave 官网后端
├── products/
│   ├── bridge/           # CrossBridge - AI翻译 (已上线)
│   ├── blog/             # CrossBlog - SEO博客 (就绪)
│   └── deploy/           # CrossDeploy - 技术服务 (就绪)
├── docs/                 # 业务文档
├── marketing/            # 营销物料 (V2EX帖等)
├── static/               # 静态资源
├── Dockerfile
└── README.md
```

## 商业计划

1. **Phase 1**: V2EX 发帖 → 接代部署单 (¥2K-5K/单)
2. **Phase 2**: 开通 Stripe → SaaS 订阅 ($19-49/月)
3. **Phase 3**: 产品矩阵 → 交叉销售

## Configuration

### Sentry Error Tracking

1. Create a Sentry account at https://sentry.io
2. Create a new Python project, copy the DSN
3. Add to `.env`: `SENTRY_DSN=https://xxx@xxx.ingest.us.sentry.io/xxx`

### Stripe

1. Create a Stripe account at https://stripe.com
2. Copy secret key to `.env`: `STRIPE_SECRET_KEY=sk_test_xxx`
3. Copy webhook secret to `.env`: `STRIPE_WEBHOOK_SECRET=whsec_xxx`
4. Run product setup: `STRIPE_SECRET_KEY=sk_test_xxx python scripts/setup_stripe.py`
5. Set price IDs in `.env` from the script output

### Admin Login

1. Generate password hash: `python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"`
2. Set in `.env`:
   ```
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD_HASH=$2b$12$...
   ```

---

*Built for the global Chinese creator community.*
