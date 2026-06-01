# CrossDeploy Delivery Package

Standardized deployment service packages for CrossWave customers.

## Tier Overview

### Basic (¥2,000)
Single-service deployment on VPS:
- FastAPI/Next.js app deployment
- Docker containerization
- Domain + SSL (Let's Encrypt)
- Health check endpoint
- Delivery time: 1-2 days

### Standard (¥3,000)
Multi-service stack deployment:
- Everything in Basic
- Docker Compose multi-service setup
- PostgreSQL/Redis provisioning
- CI/CD pipeline (GitHub Actions)
- 30-day support
- Delivery time: 2-4 days

### Enterprise (¥5,000)
Production-grade infrastructure:
- Everything in Standard
- Kubernetes (K3s) cluster
- Auto-scaling + load balancing
- Database migration + backup
- Monitoring (Prometheus + Grafana)
- 7d SLA (4h response)
- Delivery time: 5-7 days

## Delivery Process

1. **Kickoff** — Collect requirements (stack, domain, expected traffic)
2. **Environment** — Provision VPS / configure access
3. **Deploy** — Containerize → deploy → health check
4. **Handover** — Domain → SSL → test → documentation
5. **Support** — Monitor for 7-30 days depending on tier

## Artifacts Delivered

- Dockerfile(s) + docker-compose.yml
- `.env.example` with all required variables
- Nginx/ reverse proxy config
- CI/CD workflow (GitHub Actions)
- `README.md` with deploy/restart instructions
- Monitoring dashboard URL (Enterprise)
