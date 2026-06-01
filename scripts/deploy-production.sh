#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════
# CrossWave Production Deployment Script
# ═══════════════════════════════════════════
# Prerequisites:
#   1. Docker + Docker Compose installed
#   2. Python 3.12+ with virtual environment (.venv/)
#   3. Redis running (systemd or Docker)
#   4. Environment variables set (see .env.example)
#
# Usage:
#   bash scripts/deploy-production.sh [--build] [--no-celery] [--verbose]
#
# Flags:
#   --build       Rebuild Docker images
#   --no-celery   Skip Celery worker (agents won't run)
#   --verbose     Debug output
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

# ── Resolve Python: prefer .venv, fallback to system ──
resolve_python() {
    local project_dir=$1
    if [ -f "$project_dir/.venv/bin/python3" ]; then
        echo "$project_dir/.venv/bin/python3"
    elif [ -f "$project_dir/venv/bin/python3" ]; then
        echo "$project_dir/venv/bin/python3"
    elif command -v python3 &>/dev/null; then
        echo "$(command -v python3)"
    else
        echo ""
    fi
}

resolve_pip() {
    local python_bin=$1
    local pip_bin="${python_bin/python3/pip}"
    if [ -f "$pip_bin" ]; then
        echo "$pip_bin"
    elif [ -f "${python_bin%/*}/pip" ]; then
        echo "${python_bin%/*}/pip"
    else
        # Fallback: use pip3 module
        echo "$python_bin -m pip"
    fi
}

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

for cmd in docker docker-compose curl; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "WARNING: $cmd not found. Some features may be unavailable."
    fi
done

# ── 2. Resolve Python for CrossWave project ──
CW_PYTHON=$(resolve_python "$CROSSWAVE_DIR")
if [ -z "$CW_PYTHON" ]; then
    echo "ERROR: No Python interpreter found in $CROSSWAVE_DIR/.venv or system"
    echo "Create one: cd $CROSSWAVE_DIR && python3 -m venv .venv"
    exit 1
fi
CW_PIP=$(resolve_pip "$CW_PYTHON")
log "Using Python: $CW_PYTHON"

# Check Python version
PY_VER=$("$CW_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log "Python version: $PY_VER"

# ── 3. Check environment ──
log "Checking environment..."

if [ -f "$CROSSWAVE_DIR/.env" ]; then
    set -a; source "$CROSSWAVE_DIR/.env"; set +a
    log "Loaded .env from $CROSSWAVE_DIR/.env"
fi

REQUIRED_VARS=("POLSIA_BASE_URL" "POLSIA_API_KEY")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "WARNING: $var not set. Using defaults (may fail at runtime)."
    fi
done

# ── 4. Install Python deps ──
log "Installing Python dependencies..."
$CW_PIP install -q --upgrade pip 2>/dev/null || true
$CW_PIP install -q -r "$CROSSWAVE_DIR/requirements.txt" 2>/dev/null || {
    echo "ERROR: pip install failed in CROSSWAVE_DIR. Fix dependencies first."
    exit 1
}

# Also install deps in Polsia Fork and CrossBlog if they exist
for dep_dir in "$CROSSWAVE_DIR/../polsia-fork" "$CROSSWAVE_DIR/../ai-blog-engine"; do
    if [ -d "$dep_dir" ] && [ -f "$dep_dir/requirements.txt" ]; then
        DEP_PY=$(resolve_python "$dep_dir")
        if [ -n "$DEP_PY" ]; then
            DEP_PIP=$(resolve_pip "$DEP_PY")
            $DEP_PIP install -q -r "$dep_dir/requirements.txt" 2>/dev/null || log "  ⚠️  Dep install skipped for $(basename $dep_dir)"
        fi
    fi
done

# ── 5. Start services (order: dependencies first) ──
log "Starting services (dependencies first)..."

# 5a. NocoBase HQ Backend (via Docker Compose)
if [ -f "$CROSSWAVE_DIR/hq/docker-compose.yml" ]; then
    log "  → NocoBase HQ Backend (port 13000)..."
    cd "$CROSSWAVE_DIR/hq"
    docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null || log "  ⚠️  Docker Compose not available, skipping NocoBase"
    cd "$CROSSWAVE_DIR"
    log "  ✅ NocoBase stack started (PostgreSQL + NocoBase)"
fi

# 5b. Polsia Fork API (first — HQ bridge depends on its DB)
POLSIA_DIR="$CROSSWAVE_DIR/../polsia-fork"
if [ -d "$POLSIA_DIR" ]; then
    POLSIA_PY=$(resolve_python "$POLSIA_DIR")
    if [ -z "$POLSIA_PY" ]; then
        log "  ⚠️  No Python for Polsia Fork, skipping"
    else
        log "  → Polsia Fork API (port 8001)..."
        pkill -f "uvicorn.*8001" 2>/dev/null || true
        sleep 1
        cd "$POLSIA_DIR"
        DATABASE_URL="sqlite+aiosqlite:///./polsia.db" \
        "$POLSIA_PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/polsia.log 2>&1 &
        wait_for_service "Polsia Fork" "http://127.0.0.1:8001/api/v1/health" 30 2 || true

        if [ "$CELERY" = true ]; then
            CELERY_BIN="${POLSIA_PY%/*}/celery"
            if [ -f "$CELERY_BIN" ]; then
                log "  → Celery Worker..."
                "$CELERY_BIN" -A celery_app worker --loglevel=info --concurrency=2 -Q scheduler,agents,maintenance > /tmp/celery-worker.log 2>&1 &
                sleep 2
                log "  ✅ Celery Worker started"

                log "  → Celery Beat..."
                "$CELERY_BIN" -A celery_app beat --loglevel=info > /tmp/celery-beat.log 2>&1 &
                sleep 1
                log "  ✅ Celery Beat started"
            else
                log "  ⏭️  Celery binary not found, skipping"
            fi
        fi
    fi
else
    log "  ⏭️  Polsia Fork not found at $POLSIA_DIR, skipping"
fi

# 5c. HQ Bridge (CrossWave HQ — depends on Polsia Fork DB)
log "  → HQ Bridge (port 13001)..."
pkill -f "uvicorn hq.server:app" 2>/dev/null || true
sleep 1
cd "$CROSSWAVE_DIR"
"$CW_PYTHON" -m uvicorn hq.server:app --host 0.0.0.0 --port 13001 > /tmp/hq-bridge.log 2>&1 &
wait_for_service "HQ Bridge" "http://127.0.0.1:13001/health" 30 2 || true

# 5d. CrossWave (Website)
log "  → CrossWave Website (port 9999)..."
pkill -f "uvicorn app.main:app.*9999" 2>/dev/null || true
sleep 1
cd "$CROSSWAVE_DIR"
"$CW_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 9999 > /tmp/crosswave.log 2>&1 &
wait_for_service "CrossWave" "http://127.0.0.1:9999/health" 20 2 || true

# 5e. CrossBlog (if ai-blog-engine exists)
BLOG_DIR="$CROSSWAVE_DIR/../ai-blog-engine"
if [ -d "$BLOG_DIR" ]; then
    BLOG_PY=$(resolve_python "$BLOG_DIR")
    if [ -n "$BLOG_PY" ]; then
        log "  → CrossBlog (port 8002)..."
        pkill -f "uvicorn.*8002" 2>/dev/null || true
        sleep 1
        cd "$BLOG_DIR"
        "$BLOG_PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > /tmp/crossblog.log 2>&1 &
        wait_for_service "CrossBlog" "http://127.0.0.1:8002/health" 20 2 || true
    fi
else
    log "  ⏭️  CrossBlog not found at $BLOG_DIR, skipping"
fi

# ── 6. Final Health Summary ──
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
check_endpoint "HQ Bridge" "http://127.0.0.1:13001/health"
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
