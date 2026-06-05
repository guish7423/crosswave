# CrossWave Launch Readiness Checklist

> **Status Tracking**: Check off items as completed. Every unchecked item is a risk.
> **Version**: v0.7.0 | Last updated: 2026-06-05
> **Tests**: 174 passed ✅ | **Coverage**: 80%+

---

## Phase 0: Pre-Flight (Critical Path)

### CrossBlog Deployment
- [ ] Deploy CrossBlog to Railway: `cd ai-blog-engine && railway up`
- [ ] Or: create Railway project from `guish7423/ai-blog-engine` GitHub repo
- [ ] Verify: `curl https://blog.crosswave.app/health` returns article count
- [ ] Configure `LLM_API_MOCK=false` + `LLM_API_KEY` in Railway env vars

### SSE Dashboard Verification
- [ ] Start HQ: `uvicorn hq.server:hq_app --port 13001`
- [ ] Verify SSE: `curl -N http://localhost:13001/api/hq/events` — should see heartbeat JSON every 5s
- [ ] Dashboard opens http://localhost:13001 with live KPI updates

### Stripe Payments — Revenue Readiness
- [ ] Create Stripe account (stripe.com) → verify business details
- [ ] Run `python scripts/setup_stripe.py` with your STRIPE_SECRET_KEY
- [ ] Copy output price IDs into production `.env`
- [ ] Create Stripe Payment Links for CrossDeploy tiers in Dashboard
- [ ] Add Payment Link URLs to `index.html` replacing `mailto:hello@...`

### Domain & DNS
- [ ] Purchase `crosswave.app` domain
- [ ] Configure DNS: `A` record pointing to server IP
- [ ] Configure `blog.crosswave.app` as CNAME or A record
- [ ] Configure `crossbridge.crosswave.app` as CNAME or A record

### SSL (via Nginx + Let's Encrypt)  
- [ ] Copy `nginx.conf` (production version) to `/opt/crosswave/`
- [ ] Run `bash scripts/setup-ssl.sh` (interactive) or `bash scripts/setup-ssl.sh --self-signed` (testing)
- [ ] Verify SSL: `curl -I https://crosswave.app`

---

## Phase 1: Infrastructure

### Server Setup
- [ ] Provision VPS (recommended: 4GB RAM, 2CPU, 80GB SSD)
- [ ] Install: Docker, Docker Compose, Python 3.12+, Redis, Nginx
- [ ] Clone repos: `git clone https://github.com/guish7423/crosswave`
- [ ] Clone: `git clone https://github.com/guish7423/polsia-fork`
- [ ] Clone: `git clone https://github.com/guish7423/ai-blog-engine`

### Environment Configuration
- [ ] Create `.env` files for all 3 projects (`crosswave/.env`, `polsia-fork/.env`, `ai-blog-engine/.env`)
- [ ] Set LLM API keys: `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY` (fallback)
- [ ] Set Stripe keys: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- [ ] Set API keys: `POLSIA_API_KEY=prod-key-...`
- [ ] CrossBridge: Add social media API keys (X/Twitter, LinkedIn)

### Database (Polsia Fork)
- [ ] Choose: SQLite (simple) or PostgreSQL (production)
- [ ] If PostgreSQL: Set `DATABASE_URL=postgresql+asyncpg://user:pass@host/db`
- [ ] Run `python scripts/seed_demo.py` for initial data
- [ ] Verify DB: all 17 tables created

---

## Phase 2: NocoBase HQ Setup

- [ ] Run `docker compose -f hq/docker-compose.yml up -d`
- [ ] Visit http://server:13000 → complete NocoBase admin setup
- [ ] Upload `hq/plugins/crosswave-hq/` plugin
- [ ] Verify 4 collections created: employees, business_lines, external_orders, platform_connections
- [ ] Run Polsia → NocoBase sync: `python hq/polsia_bridge.py`

---

## Phase 3: Deploy Services

### Option A: Railway (Zero Ops)
1. Connect GitHub repo to Railway
2. Deploy `polsia-fork` first (backend)
3. Deploy `crosswave` second (BFF + website)
4. Deploy `ai-blog-engine` third (blog)
5. Add MySQL + Redis via Railway dashboard
6. Set environment variables for each project

### Option B: VPS Docker
```bash
# One-command deploy:
bash scripts/deploy-production.sh

# Or manually:
docker compose -f hq/docker-compose.yml up -d   # NocoBase
cd polsia-fork && bash scripts/start.sh          # Polsia Fork
cd crosswave && nohup uvicorn app.main:app &     # CrossWave
cd ai-blog-engine && nohup uvicorn app.main:app & # CrossBlog
```

### Verify All Services
```bash
curl http://localhost:9999/health           # CrossWave
curl http://localhost:8001/api/v1/health    # Polsia Fork
curl http://localhost:8002/health            # CrossBlog
curl http://localhost:13001/api/hq/summary  # HQ Bridge
```

---

## Phase 4: Monitoring

### Automated Health Checks
- [ ] Setup cron: `*/5 * * * * bash /opt/crosswave/scripts/health-check.sh >> /var/log/health.log`
- [ ] Verify email/slack alert on service failure
- [ ] Configure log rotation for all `/tmp/*.log` files

### Backup Plan
- [ ] Database backup: Daily cron (`pg_dump` or SQLite copy)
- [ ] Upload backups to S3-compatible storage (Backblaze B2 / R2)
- [ ] Test restore process

### Incident Response
- [ ] Service goes down? → `bash scripts/deploy-production.sh` to restart all
- [ ] DB corruption? → Restore from latest backup
- [ ] Rate limited by API? → `LLM_API_MOCK=true` until limit resets

---

## Phase 5: Customer Ready

### Legal Pages
- [ ] Privacy Policy (generate from template)
- [ ] Terms of Service (generate from template)
- [ ] GDPR compliance check (data stored in user's own DB)
- [ ] Add `/privacy` and `/terms` routes to CrossWave

### Customer Support
- [ ] Email: `support@crosswave.app` configured
- [ ] Response SLA: < 24h for Free, < 4h for paid
- [ ] Add contact form to website (static, email-based)

### Pricing Page
- [ ] Verify Stripe Payment Links work end-to-end
- [ ] Test: Free tier signup → API key issued
- [ ] Test: Paid tier → Stripe Checkout → Webhook → Tier upgraded
- [ ] Test: Cancel subscription → Graceful downgrade to Free

---

## Phase 6: Go-To-Market

### SEO Final Check
- [ ] Sitemap: `https://blog.crosswave.app/sitemap.xml`
- [ ] RSS Feed: `https://blog.crosswave.app/feed.xml`
- [ ] robots.txt: `https://crosswave.app/robots.txt`
- [ ] Google Search Console: Submit sitemaps
- [ ] Verify all 80 blog posts indexed (search site:blog.crosswave.app)

### Content Engine
- [ ] Verify newsletter subscription works
- [ ] Generate 1 new blog post/day automatically (Celery beat)
- [ ] Auto-post to social media (LinkedIn, X/Twitter)

### Lead Generation
- [ ] Blog CTA → CrossBridge free trial signup
- [ ] CrossDeploy page → Contact/Quote request
- [ ] Newsletter → Weekly digest → CrossBridge upsell

---

## Revenue Targets

| Tier | Price | Break-even | Target |
|------|-------|-----------|--------|
| CrossBridge Free | ¥0/mo | — | 100 users |
| CrossBridge Starter | ¥149/mo | 3 users | 50 users |
| CrossBridge Pro | ¥499/mo | 1 user | 20 users |
| CrossDeploy Basic | ¥2K/project | 2 projects | 5 projects/mo |
| CrossDeploy Standard | ¥3K/project | 2 projects | 5 projects/mo |
| CrossDeploy Enterprise | ¥5K/project | 1 project | 2 projects/mo |

**Monthly revenue target**: ¥20,000/mo ($2,750/mo)

---

## Quick-Start (CEO's 30-min Launch)

```bash
# 1. Clone & deploy
git clone https://github.com/guish7423/crosswave /opt/crosswave
cd /opt/crosswave
cp .env.example .env
nano .env  # paste your API keys

# 2. Start everything
bash scripts/deploy-production.sh

# 3. Verify
bash scripts/health-check.sh

# 4. Go live — point DNS, configure SSL, done
```

---

**Prepared by CrossWave CEO Agent**
**Last updated**: 2026-06-01
