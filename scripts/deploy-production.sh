#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════
# CrossWave Production Deployment Script
# ═══════════════════════════════════════════
# Prerequisites:
#   1. Docker + Docker Compose installed
#   2. Python 3.12+ with pip
#   3. Redis running (systemd or Docker)
#   4. Environment variables set (see .env.example)
#
# Usage:
#   bash scripts/deploy-production.sh [--build] [--no-celery]
#
# Flags:
#   --build       Rebuild Docker images
#   --no-celery   Skip Celery worker (agents won't run)
# ═══════════════════════════════════════════

CROSSWAVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD=false
CELERY=true
VERBOSE=false

for arg in "$@"; do
    case "$arg" in
        --build) BUILD=true ;;
        --no-celery) CELERY=false ;;
        --verbose) VERBOSE=true ;;
    esac
done

log() { echo "[$(date '+%H:%M:%S')] $*"; }
vlog() { $VERBOSE && echo "[DEBUG] $*" || true; }

# ── Health wait: poll endpoint until ready or timeout ──
wait_for_service() {
    local name=$1 url=$2 timeout=${3:-30} interval=${4:-2}
    log "  ⏳ Waiting for $name ($url)..."
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            log "  ✅ $name ready after ${elapsed}s"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    log "  ⚠️  $name not ready after ${timeout}s (check logs)"
    return 1
}

# ── 1. Verify dependencies ──
log "Checking prerequisites..."

for cmd in docker docker-compose python3 pip3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: $cmd not found. Install it first."
        exit 1
    fi
done

# Check Python version
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$(echo "$PY_VER >= 3.12" | bc)" != "1" ]; then
    echo "WARNING: Python $PY_VER detected. Recommended: 3.12+"
fi

# ── 2. Check environment ──
log "Checking environment..."

REQUIRED_VARS=(
    "POLSIA_BASE_URL"
    "POLSIA_API_KEY"
)

if [ -f "$CROSSWAVE_DIR/.env" ]; then
    set -a; source "$CROSSWAVE_DIR/.env"; set +a
    log "Loaded .env from $CROSSWAVE_DIR/.env"
fi

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "WARNING: $var not set. Using defaults (may fail at runtime)."
    fi
done

# ── 3. Install Python deps ──
log "Installing Python dependencies..."
pip3 install -q --upgrade pip
pip3 install -q -r "$CROSSWAVE_DIR/requirements.txt" 2>/dev/null || {
    echo "ERROR: pip install failed. Fix dependencies first."
    exit 1
}

# ── 4. Start services (order: dependencies first) ──
log "Starting services (dependencies first)..."

# 4a. NocoBase HQ Backend (via Docker Compose)
if [ -f "$CROSSWAVE_DIR/hq/docker-compose.yml" ]; then
    log "  → NocoBase HQ Backend (port 13000)..."
    cd "$CROSSWAVE_DIR/hq"
    docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null || log "  ⚠️  Docker Compose not available, skipping NocoBase"
    cd "$CROSSWAVE_DIR"
    log "  ✅ NocoBase stack started (PostgreSQL + NocoBase)"
fi

# 4b. Polsia Fork API (first — HQ bridge depends on its DB)
POLSIA_DIR="$CROSSWAVE_DIR/../polsia-fork"
if [ -d "$POLSIA_DIR" ]; then
    log "  → Polsia Fork API (port 8001)..."
    pkill -f "uvicorn.*8001" 2>/dev/null || true
    sleep 1
    cd "$POLSIA_DIR"
    DATABASE_URL="sqlite+aiosqlite:///./polsia.db" \
    setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/polsia.log 2>&1 &
    wait_for_service "Polsia Fork" "http://127.0.0.1:8001/api/v1/health" 30 2 || true

    if [ "$CELERY" = true ]; then
        log "  → Celery Worker..."
        setsid celery -A celery_app worker --loglevel=info --concurrency=2 -Q scheduler,agents,maintenance > /tmp/celery-worker.log 2>&1 &
        sleep 2
        log "  ✅ Celery Worker started"

        log "  → Celery Beat..."
        setsid celery -A celery_app beat --loglevel=info > /tmp/celery-beat.log 2>&1 &
        sleep 1
        log "  ✅ Celery Beat started"
    fi
else
    log "  ⏭️  Polsia Fork not found at $POLSIA_DIR, skipping"
fi

# 4c. HQ Bridge (CrossWave HQ — depends on Polsia Fork DB)
log "  → HQ Bridge (port 13001)..."
pkill -f "uvicorn hq.server:app" 2>/dev/null || true
sleep 1
cd "$CROSSWAVE_DIR"
setsid python3 -m uvicorn hq.server:app --host 0.0.0.0 --port 13001 > /tmp/hq-bridge.log 2>&1 &
wait_for_service "HQ Bridge" "http://127.0.0.1:13001/api/hq/summary" 30 2 || true

# 4d. CrossWave (Website)
log "  → CrossWave Website (port 9999)..."
pkill -f "uvicorn app.main:app.*9999" 2>/dev/null || true
sleep 1
cd "$CROSSWAVE_DIR"
setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9999 > /tmp/crosswave.log 2>&1 &
wait_for_service "CrossWave" "http://127.0.0.1:9999/health" 20 2 || true

# 4e. CrossBlog (if ai-blog-engine exists)
BLOG_DIR="$CROSSWAVE_DIR/../ai-blog-engine"
if [ -d "$BLOG_DIR" ]; then
    log "  → CrossBlog (port 8002)..."
    pkill -f "uvicorn.*8002" 2>/dev/null || true
    sleep 1
    cd "$BLOG_DIR"
    setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > /tmp/crossblog.log 2>&1 &
    wait_for_service "CrossBlog" "http://127.0.0.1:8002/health" 20 2 || true
else
    log "  ⏭️  CrossBlog not found at $BLOG_DIR, skipping"
fi

# ── 5. Final Health Summary ──
log ""
log "─────────────────────────────────"
log "  FINAL HEALTH SUMMARY"
log "─────────────────────────────────"
check_endpoint() {
    local name=$1 url=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        log "  ✅ $name — $url"
    else
        log "  ❌ $name — $url (DOWN)"
    fi
}

check_endpoint "CrossWave" "http://127.0.0.1:9999/health"
check_endpoint "HQ Bridge" "http://127.0.0.1:13001/api/hq/summary"
check_endpoint "CrossBlog" "http://127.0.0.1:8002/health" || true
check_endpoint "Polsia Fork" "http://127.0.0.1:8001/api/v1/health" || true

log ""
log "─────────────────────────────────"
log "  DEPLOYMENT COMPLETE"
log "─────────────────────────────────"
log "CrossWave:   http://localhost:9999"
log "HQ:          http://localhost:13001/dashboard"
log "All logs:    /tmp/{hq-bridge,crosswave,crossblog,polsia}.log"
log ""
log "To monitor:  watch ./scripts/health-check.sh"
