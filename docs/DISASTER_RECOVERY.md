# CrossWave — Disaster Recovery Handbook

> **Version**: 1.0
> **Last Updated**: 2026-06-01
> **Owner**: CrossWave CEO (AI Operator)

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Backup Locations](#2-backup-locations)
3. [Service Recovery Procedures](#3-service-recovery-procedures)
4. [Data Restore Procedures](#4-data-restore-procedures)
5. [Full System Rebuild](#5-full-system-rebuild)
6. [Common Failure Scenarios](#6-common-failure-scenarios)
7. [Monitoring Thresholds](#7-monitoring-thresholds)
8. [Emergency Contacts & Credentials](#8-emergency-contacts--credentials)

---

## 1. System Architecture Overview

```
                    ┌─────────────────┐
                    │  NocoBase HQ    │  :13000
                    │  (Optional)     │
                    └────────┬────────┘
                             │
┌──────────────┐    ┌───────┴────────┐    ┌──────────────┐
│  Polsia Fork │◄───│  HQ Bridge     │───►│  CrossWave   │
│  :8001       │    │  :13001        │    │  :9999       │
│  16 Agents   │    │  8 Modules     │    │  Website     │
│  DeepSeek API│    │  SQLite Cache  │    │  Dashboard   │
└──────┬───────┘    └────────────────┘    └──────────────┘
       │
       ├────────────────────────────────┐
       ▼                                ▼
┌──────────────┐              ┌─────────────────┐
│  CrossBlog   │              │  CrossBridge    │
│  :8002       │              │  :8000          │
│  80 posts    │              │  Live on Railway│
│  DeepSeek    │              │  Stripe + Auth  │
└──────────────┘              └─────────────────┘
```

### Data Dependencies

| Service | Database | Location | Backup Script |
|---------|----------|----------|---------------|
| Polsia Fork | SQLite (polsia.db) | `projects/polsia-fork/` | `backup-db.sh` |
| CrossBlog | SQLite (blog.db) | `projects/ai-blog-engine/` | `backup-db.sh` |
| CrossBridge | SQLite (content_bridge.db) | `projects/ai-content-bridge/` | `backup-db.sh` |
| CrossWave | None (stateless proxy) | — | — |
| HQ Bridge | None (reads Polsia SQLite) | — | — |

---

## 2. Backup Locations

### Automated Backups

Backup script: `scripts/backup-db.sh`

**Backup directory**: `/home/guish/.opencode-workspace/projects/crosswave/backups/`

**Schedule**: Cron or manual `--cron` mode

**Retention**: 7 days (configurable in `.backup-config`)

### Backup Contents

Each backup is a timestamped directory:
```
backups/
├── polsia-fork-20260601-120000.db     # SQLite .backup (live-safe)
├── ai-blog-engine-20260601-120000.db
└── ai-content-bridge-20260601-120000.db
```

### What IS Backed Up

| Data | Backed Up? | Notes |
|------|-----------|-------|
| Task data (39 tasks) | ✅ | Via polsia.db |
| Agent configs | ✅ | Via polsia.db |
| Leads (CRM) | ✅ | Via polsia.db |
| External orders | ✅ | Via polsia.db |
| Revenue history | ✅ | Via polsia.db |
| Blog posts (80) | ✅ | Via blog.db |
| Blog subscribers | ✅ | Via blog.db |
| CrossBridge data | ✅ | Via content_bridge.db |
| Environment config | ❌ | Must re-create `.env` manually |
| SSL certificates | ❌ | Must re-obtain via certbot |
| GitHub repos | ✅ | Remote is source of truth |

### What is NOT Backed Up (and Why)

- **`.env` files** — contain secrets, excluded by policy. Templates in `.env.production.template`
- **`__pycache__` / `node_modules`** — can be regenerated
- **System packages** — documented in `requirements.txt`
- **Docker images** — rebuilt from Dockerfiles

---

## 3. Service Recovery Procedures

### 3.1 Polsia Fork (Core Backend)

**Symptoms**: Dashboard shows "Disconnected", agents not running, `/api/v1/health` returns 5xx

**Recovery**:
```bash
# 0. Check if process exists
ps aux | grep polsia-fork | grep uvicorn

# 1. Kill stale process
pkill -f "polsia-fork.*uvicorn" || true
sleep 2

# 2. Verify DB integrity
cd ~/.opencode-workspace/projects/polsia-fork
python3 -c "
import sqlite3
conn = sqlite3.connect('polsia.db')
conn.execute('PRAGMA integrity_check')
print('DB integrity: OK')
conn.close()
"

# 3. Start with production config
DATABASE_URL=sqlite+aiosqlite:///./polsia.db \
LLM_API_KEY=$DEEPSEEK_API_KEY \
LLM_API_MOCK=false \
setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 \
    > /tmp/polsia-fork.log 2>&1 &

# 4. Start Celery worker + beat
cd ~/.opencode-workspace/projects/polsia-fork
setsid python3 -m celery -A celery_app worker -l info -c 2 -Q scheduler,agents,maintenance \
    > /tmp/celery-worker.log 2>&1 &
setsid python3 -m celery -A celery_app beat -l info \
    > /tmp/celery-beat.log 2>&1 &

# 5. Verify
sleep 3
curl -s http://127.0.0.1:8001/api/v1/health | python3 -m json.tool
```

**Expected recovery time**: < 30 seconds

### 3.2 HQ Bridge (Management Dashboard)

**Symptoms**: HQ pages 5xx, monitor shows "down", `:13001` not responding

**Recovery**:
```bash
# 0. Kill stale
pkill -f "hq.server" || true
sleep 1

# 1. Start
cd ~/.opencode-workspace/projects/crosswave/hq
setsid python3 -m uvicorn server:app --host 0.0.0.0 --port 13001 \
    > /tmp/hq-bridge.log 2>&1 &

# 2. Verify
sleep 2
curl -s http://127.0.0.1:13001/health
```

**Expected recovery time**: < 10 seconds

### 3.3 CrossWave (Website + Dashboard)

**Symptoms**: Website 5xx, `:9999` not responding, blog preview broken

**Recovery**:
```bash
cd ~/.opencode-workspace/projects/crosswave
pkill -f "crosswave.*uvicorn" || true
sleep 1

setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9999 \
    > /tmp/crosswave.log 2>&1 &

sleep 2
curl -s http://127.0.0.1:9999/health
```

**Expected recovery time**: < 10 seconds

### 3.4 CrossBlog (Content Engine)

**Symptoms**: Blog 5xx, `:8002` not responding, /blog shows error

**Recovery**:
```bash
cd ~/.opencode-workspace/projects/ai-blog-engine
pkill -f "blog-engine.*uvicorn" || true
sleep 1

# Restore posts from backup if DB corrupt
# cp backups/ai-blog-engine-*.db blog.db  # if needed

setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002 \
    > /tmp/blog.log 2>&1 &

sleep 2
curl -s http://127.0.0.1:8002/health
```

**Expected recovery time**: < 10 seconds

### 3.5 Celery (Task Queue)

**Symptoms**: Agents not running, Beat tasks not firing, Redis connection errors

**Recovery**:
```bash
# Check Redis first
redis-cli ping  # Should return PONG

# If Redis is down:
sudo systemctl restart redis  # or `redis-server &`

# Kill stale workers
pkill -f "celery -A celery_app" || true
sleep 2

# Start worker
cd ~/.opencode-workspace/projects/polsia-fork
setsid python3 -m celery -A celery_app worker -l info -c 2 \
    -Q scheduler,agents,maintenance \
    > /tmp/celery-worker.log 2>&1 &

# Start beat
setsid python3 -m celery -A celery_app beat -l info \
    > /tmp/celery-beat.log 2>&1 &

# Verify
sleep 3
celery -A celery_app status
```

**Expected recovery time**: < 30 seconds

---

## 4. Data Restore Procedures

### 4.1 Restore SQLite Database from Backup

```bash
cd ~/.opencode-workspace/projects/crosswave

# List available backups
bash scripts/backup-db.sh --list

# Restore specific service (example: polsia-fork)
# STEP 1: Stop the service
pkill -f "polsia-fork.*uvicorn" || true
pkill -f "celery.*polsia" || true

# STEP 2: Copy backup to target location
cp /path/to/backups/polsia-fork-20260601-120000.db \
   ~/.opencode-workspace/projects/polsia-fork/polsia.db

# STEP 3: Verify integrity
cd ~/.opencode-workspace/projects/polsia-fork
python3 -c "
import sqlite3
conn = sqlite3.connect('polsia.db')
result = conn.execute('PRAGMA integrity_check').fetchone()
print(f'Integrity check: {result[0]}')
# Quick data sanity
count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
print(f'Tasks in DB: {count}')
conn.close()
"

# STEP 4: Restart the service
# (See service recovery section above)
```

### 4.2 Factory Reset (All Data Cleared)

```bash
# ⚠️ IRREVERSIBLE — only for full reset scenarios

cd ~/.opencode-workspace/projects/polsia-fork
rm -f polsia.db  # Delete database
python3 -c "from app.models.base import Base; from app.core.database import engine; Base.metadata.create_all(bind=engine)"  # Re-create schema
python3 scripts/seed_demo.py --fresh  # Re-seed demo data

cd ~/.opencode-workspace/projects/ai-blog-engine
rm -f blog.db
python3 scripts/seed_posts.py  # Re-seed blog posts
```

---

## 5. Full System Rebuild

### Prerequisites (checklist)

- [ ] Git repositories cloned
- [ ] Python 3.11+ installed
- [ ] Redis installed and running
- [ ] DeepSeek API key available
- [ ] `.env` files configured (use `.env.production.template`)

### Step-by-Step

```bash
# 1. Clone repositories
cd ~/.opencode-workspace
git clone https://github.com/guish7423/polsia-fork.git
git clone https://github.com/guish7423/crosswave.git
git clone https://github.com/guish7423/ai-blog-engine.git
git clone https://github.com/guish7423/ai-content-bridge.git

# 2. Configure environment
# Copy .env.production.template → .env for each project
# Fill in all secrets

# 3. Install dependencies
cd ~/.opencode-workspace/projects/polsia-fork
pip install -r requirements.txt

cd ~/.opencode-workspace/projects/crosswave
pip install -r requirements.txt

cd ~/.opencode-workspace/projects/ai-blog-engine
pip install -r requirements.txt

cd ~/.opencode-workspace/projects/ai-content-bridge
pip install -r requirements.txt

# 4. Seed demo data
cd ~/.opencode-workspace/projects/polsia-fork
python3 scripts/seed_demo.py --fresh
python3 scripts/seed_hq_data.py --fresh

cd ~/.opencode-workspace/projects/ai-blog-engine
python3 scripts/seed_posts.py

# 5. Start all services
cd ~/.opencode-workspace/projects/crosswave
bash scripts/deploy-production.sh

# 6. Verify
bash scripts/health-check.sh
```

---

## 6. Common Failure Scenarios

### Scenario A: "Polsia Fork starts but returns 500 on API calls"

**Symptoms**: CrossWave Dashboard shows errors, `/api/v1/health` returns 200 but data endpoints fail

**Diagnosis**:
```bash
# Check if database exists and has data
ls -la ~/.opencode-workspace/projects/polsia-fork/polsia.db
python3 -c "
import sqlite3
conn = sqlite3.connect('polsia.db')
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print(f'Tables: {[t[0] for t in tables]}')
conn.close()
"

# Check logs
tail -50 /tmp/polsia-fork.log
```

**Fix**: Run `python3 scripts/seed_demo.py` if DB is empty or corrupt.

### Scenario B: "Redis connection refused"

**Symptoms**: Celery workers fail to start, "Connection refused" errors

**Diagnosis**:
```bash
redis-cli ping
# If error: Redis not running
sudo service redis-server status
```

**Fix**:
```bash
redis-server --daemonize yes  # Start Redis
# Or: sudo systemctl start redis
```

### Scenario C: "DeepSeek API calls failing"

**Symptoms**: Agent calls return "API error", blog generation fails

**Diagnosis**:
```bash
# Test API key
curl -s https://api.deepseek.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}],"max_tokens":10}' \
  | python3 -m json.tool
```

**Fix**:
- Check `DEEPSEEK_API_KEY` is set: `echo ${#DEEPSEEK_API_KEY}` (should be > 0)
- Set `LLM_API_MOCK=true` as temporary fallback
- Top up API key balance at platform.deepseek.com

### Scenario D: "Port conflict on startup"

**Symptoms**: "Address already in use" errors when starting services

**Diagnosis**:
```bash
sudo lsof -i :8001  # Check what's using port 8001
```

**Fix**:
```bash
kill -9 $(sudo lsof -t -i :8001)  # Kill the stale process
# Then restart
```

### Scenario E: "Database disk full"

**Symptoms**: Write operations fail, SQLite "disk or I/O error"

**Diagnosis**:
```bash
df -h /  # Check disk space
du -sh ~/.opencode-workspace/projects/*/  # Check project sizes
```

**Fix**:
```bash
# Clean Python cache
find ~/.opencode-workspace -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# Remove old backups (keep only last 3)
ls -t ~/.opencode-workspace/projects/crosswave/backups/*.db | tail -n +4 | xargs rm -f

# Compress old logs
gzip /tmp/*.log 2>/dev/null || true
```

---

## 7. Monitoring Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Service uptime | Any 5xx in 5min | 3 consecutive failures | Restart service |
| Response time | > 1s | > 3s | Check logs, scale |
| Disk usage | > 80% | > 90% | Clean cache + backups |
| Backup age | > 24h | > 48h | Run backup-db.sh |
| Redis memory | > 200MB | > 500MB | Flush old tasks |
| API key balance | — | API returns 401 | Top up DeepSeek credits |

---

## 8. Emergency Contacts & Credentials

### Where to find credentials

| Secret | Location |
|--------|----------|
| DeepSeek API Key | platform.deepseek.com |
| Stripe Keys | dashboard.stripe.com |
| GitHub Tokens | github.com/settings/tokens |
| Domain DNS | Cloudflare Dashboard |
| Railway Access | railway.com/dashboard |

### Production `.env` configuration checklist

- [ ] ALL 4 `.env` files configured from `.env.production.template`
- [ ] `DEBUG=false` everywhere
- [ ] `LLM_API_MOCK=false` everywhere
- [ ] `SECRET_KEY` generated (64-char hex)
- [ ] `API_KEY` generated (32-char token)
- [ ] PostgreSQL password set
- [ ] Redis password set

---

> **Remember**: The most important recovery tool is **backups**. Run backup-db.sh --cron daily.
> The second most important: **this document**. Keep it updated.
