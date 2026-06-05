# CrossDeploy 🚀

Deployment management service — order, track, and fulfill deployment projects.

**Status**: ✅ v0.1.0 | FastAPI + SQLite

### API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/tiers` | List 3 pricing tiers (Basic ¥2K / Standard ¥3K / Enterprise ¥5K) |
| `POST /api/orders` | Create deployment order |
| `GET /api/orders` | List orders (optional `?status=` filter) |
| `GET /api/orders/{id}` | Get order details |
| `PATCH /api/orders/{id}/status` | Update order status |

### Quick Start

```bash
cd products/deploy
pip install -r requirements.txt
uvicorn app.main:app --port 8002 --reload
```

### Docker

```bash
docker compose build crossdeploy
docker compose up -d crossdeploy
# → http://localhost:8003
```

### Tests

```bash
cd products/deploy
python -m pytest tests/ -v
# 11 tests ✅
```

### Pricing

| Tier | Price | Product |
|------|-------|---------|
| Basic | ¥2,000 | CrossBridge |
| Standard | ¥3,000 | CrossBridge + CrossBlog |
| Enterprise | ¥5,000 | Polsia Fork (10 agents) |
