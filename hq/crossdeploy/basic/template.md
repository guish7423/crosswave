# CrossDeploy Basic — Delivery Template

## Files to Create
```
project/
├── Dockerfile
├── .dockerignore
├── .env.example
├── railway.toml       (optional, Platform-agnostic)
└── README.md          (deploy instructions)
```

## Dockerfile Template (FastAPI)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Dockerfile Template (Next.js)
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./
EXPOSE 3000
CMD ["npm", "start"]
```

## Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name example.com;
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Health Check
```python
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
```

## Verification
```bash
curl -s https://example.com/health | grep "ok"
# Expected: {"status":"ok"}
```
