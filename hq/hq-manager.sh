#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# CrossWave HQ Service Manager — start/stop/status for all services
# ═══════════════════════════════════════════════════════════════
# Usage: bash hq/hq-manager.sh {start|stop|status|restart} [service]
#
# Services: polsia, celery-beat, celery-worker, hq, crosswave, blog, all
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

CROSSWAVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="$HOME/.crosswave/run"
mkdir -p "$PID_DIR"

# ── Resolve venv python for a project directory ──
resolve_python() {
    local project_dir=$1
    if [ -f "$project_dir/.venv/bin/python3" ]; then
        echo "$project_dir/.venv/bin/python3"
    elif [ -f "$project_dir/.venv/bin/python" ]; then
        echo "$project_dir/.venv/bin/python"
    else
        echo "python3"
    fi
}

# ── PID file helpers ──
pid_file() { echo "$PID_DIR/$1.pid"; }
log_file() { echo "$PID_DIR/$1.log"; }

write_pid() {
    local name=$1 pid=$2
    echo "$pid" > "$(pid_file "$name")"
}

read_pid() {
    local pid_file; pid_file=$(pid_file "$1")
    [ -f "$pid_file" ] && cat "$pid_file" || echo ""
}

is_running() {
    local pid; pid=$(read_pid "$1")
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

# ── Started / Up / Down labels ──
svc_status() {
    local name=$1
    if is_running "$name"; then
        local pid; pid=$(read_pid "$name")
        echo "  ✅ $name — running (pid $pid)"
        return 0
    elif [ -f "$(pid_file "$name")" ]; then
        echo "  ⚠️  $name — pid file exists but process dead"
        return 1
    else
        echo "  ⬜ $name — not started"
        return 1
    fi
}

# ── Wait for HTTP readiness ──
wait_ready() {
    local name=$1 url=$2 timeout=${3:-30}
    local elapsed=0 interval=2
    while [ $elapsed -lt $timeout ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo "  ✅ $name ready (${elapsed}s)"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    echo "  ⚠️  $name not ready after ${timeout}s (check logs)"
    return 1
}

# ═══════════════════════════════════════════
# SERVICE START FUNCTIONS
# ═══════════════════════════════════════════

start_polsia() {
    local dir="$CROSSWAVE_DIR/../polsia-fork"
    [ ! -d "$dir" ] && { echo "  ⏭️  Polsia Fork not found"; return 0; }

    local python; python=$(resolve_python "$dir")
    local logf; logf=$(log_file "polsia")
    local pid; pid=$(read_pid "polsia")

    # Don't restart if already running
    if is_running "polsia"; then echo "  ✅ Polsia Fork already running (pid $pid)"; return 0; fi

    echo "  → Polsia Fork (:8001)..."
    cd "$dir"
    env LLM_API_MOCK=false \
        DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}" \
        VOLC_ENGINE_API_KEY="${VOLC_ENGINE_API_KEY:-}" \
        setsid bash -c "
        export PATH=\"$(dirname "$python"):\$PATH\"
        export DATABASE_URL='sqlite+aiosqlite:///./polsia.db'
        export LLM_API_MOCK=false
        exec \"$python\" -m uvicorn app.main:app --host 0.0.0.0 --port 8001
    " > "$logf" 2>&1 &
    write_pid "polsia" $!
    wait_ready "Polsia Fork" "http://127.0.0.1:8001/api/v1/health" 30
    cd "$CROSSWAVE_DIR"
}

start_celery_worker() {
    local dir="$CROSSWAVE_DIR/../polsia-fork"
    [ ! -d "$dir" ] && { echo "  ⏭️  Polsia Fork not found — can't start worker"; return 0; }
    local python; python=$(resolve_python "$dir")
    local logf; logf=$(log_file "celery-worker")
    if is_running "celery-worker"; then echo "  ✅ Celery Worker already running"; return 0; fi
    mkdir -p "$PID_DIR"
    echo "  → Celery Worker (3 queues)..."
    cd "$dir"
    env LLM_API_MOCK=false \
        DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}" \
        VOLC_ENGINE_API_KEY="${VOLC_ENGINE_API_KEY:-}" \
        setsid bash -c "
        export PATH=\"$(dirname "$python"):\$PATH\"
        export DATABASE_URL=sqlite+aiosqlite:///./polsia.db
        export LLM_API_MOCK=false
        exec \"$python\" -m celery -A celery_app worker --loglevel=info --concurrency=2 -Q scheduler,agents,maintenance
    " > "$logf" 2>&1 &
    write_pid "celery-worker" $!
    sleep 2
    if is_running "celery-worker"; then echo "  ✅ Celery Worker started"; else echo "  ❌ Celery Worker failed to start"; fi
    cd "$CROSSWAVE_DIR"
}

start_celery_beat() {
    local dir="$CROSSWAVE_DIR/../polsia-fork"
    [ ! -d "$dir" ] && return 0

    local python; python=$(resolve_python "$dir")
    local logf; logf=$(log_file "celery-beat")

    if is_running "celery-beat"; then echo "  ✅ Celery Beat already running"; return 0; fi

    echo "  → Celery Beat (6 schedules)..."
    cd "$dir"
    env LLM_API_MOCK=false \
        DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}" \
        VOLC_ENGINE_API_KEY="${VOLC_ENGINE_API_KEY:-}" \
        setsid bash -c "
        export PATH=\"$(dirname "$python"):\$PATH\"
        export LLM_API_MOCK=false
        exec \"$python\" -m celery -A celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule
    " > "$logf" 2>&1 &
    write_pid "celery-beat" $!
    sleep 2
    if is_running "celery-beat"; then echo "  ✅ Celery Beat started"; else echo "  ❌ Celery Beat failed to start"; fi
    cd "$CROSSWAVE_DIR"
}

start_hq() {
    local python; python=$(resolve_python "$CROSSWAVE_DIR")
    local logf; logf=$(log_file "hq")

    if is_running "hq"; then echo "  ✅ HQ Bridge already running"; return 0; fi

    echo "  → HQ Bridge (:13001)..."
    cd "$CROSSWAVE_DIR"
    setsid bash -c "
        export PATH=\"$(dirname "$python"):\$PATH\"
        exec \"$python\" -m uvicorn hq.server:app --host 0.0.0.0 --port 13001
    " > "$logf" 2>&1 &
    write_pid "hq" $!
    wait_ready "HQ Bridge" "http://127.0.0.1:13001/health" 30
    cd "$CROSSWAVE_DIR"
}

start_crosswave() {
    local python; python=$(resolve_python "$CROSSWAVE_DIR")
    local logf; logf=$(log_file "crosswave")

    if is_running "crosswave"; then echo "  ✅ CrossWave already running"; return 0; fi

    echo "  → CrossWave (:9999)..."
    cd "$CROSSWAVE_DIR"
    setsid bash -c "
        export PATH=\"$(dirname "$python"):\$PATH\"
        export POLSIA_BASE_URL=http://127.0.0.1:8001
        export POLSIA_API_KEY=dev-key
        export POLSIA_MOCK=false
        exec \"$python\" -m uvicorn app.main:app --host 0.0.0.0 --port 9999
    " > "$logf" 2>&1 &
    write_pid "crosswave" $!
    wait_ready "CrossWave" "http://127.0.0.1:9999/health" 20
    cd "$CROSSWAVE_DIR"
}

start_blog() {
    local dir="$CROSSWAVE_DIR/../ai-blog-engine"
    [ ! -d "$dir" ] && { echo "  ⏭️  CrossBlog not found"; return 0; }

    local python; python=$(resolve_python "$dir")
    local logf; logf=$(log_file "blog")

    if is_running "blog"; then echo "  ✅ CrossBlog already running"; return 0; fi

    echo "  → CrossBlog (:8002)..."
    cd "$dir"
    setsid bash -c "
        export PATH=\"$(dirname "$python"):\$PATH\"
        exec \"$python\" -m uvicorn app.main:app --host 0.0.0.0 --port 8002
    " > "$logf" 2>&1 &
    write_pid "blog" $!
    wait_ready "CrossBlog" "http://127.0.0.1:8002/health" 20
    cd "$CROSSWAVE_DIR"
}

# ═══════════════════════════════════════════
# SERVICE STOP FUNCTIONS
# ═══════════════════════════════════════════

stop_service() {
    local name=$1
    local pid; pid=$(read_pid "$name")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "  → Stopping $name (pid $pid)..."
        kill "$pid" 2>/dev/null || true
        # Graceful wait up to 5s
        for i in $(seq 1 5); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 1
        done
        kill -0 "$pid" 2>/dev/null && { kill -9 "$pid" 2>/dev/null || true; echo "  ⚠️  $name force killed"; }
        echo "  ✅ $name stopped"
    else
        echo "  ⬜ $name not running"
    fi
    rm -f "$(pid_file "$name")"
}

# ═══════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════

cmd_start() {
    local service=${1:-all}
    echo "─────────────────────────────────"
    echo "  STARTING SERVICES"
    echo "─────────────────────────────────"

    case "$service" in
        all)
            start_polsia
            start_celery_worker
            start_celery_beat
            start_hq
            start_crosswave
            start_blog
            cmd_status
            ;;
        polsia) start_polsia ;;
        celery-worker) start_celery_worker ;;
        celery-beat) start_celery_beat ;;
        hq) start_hq ;;
        crosswave) start_crosswave ;;
        blog) start_blog ;;
        *)
            echo "Unknown service: $service"
            echo "Usage: $0 start {polsia|celery-worker|celery-beat|hq|crosswave|blog|all}"
            exit 1
            ;;
    esac
}

cmd_stop() {
    local service=${1:-all}
    echo "─────────────────────────────────"
    echo "  STOPPING SERVICES"
    echo "─────────────────────────────────"

    case "$service" in
        all)
            # Stop in reverse dependency order
            stop_service "blog"
            stop_service "crosswave"
            stop_service "hq"
            stop_service "celery-beat"
            stop_service "celery-worker"
            stop_service "polsia"
            ;;
        polsia) stop_service "polsia" ;;
        celery-worker) stop_service "celery-worker" ;;
        celery-beat) stop_service "celery-beat" ;;
        hq) stop_service "hq" ;;
        crosswave) stop_service "crosswave" ;;
        blog) stop_service "blog" ;;
        *)
            echo "Unknown service: $service"
            exit 1
            ;;
    esac
}

cmd_status() {
    echo "═══════════════════════════════════════════"
    echo "  CrossWave HQ — Service Status"
    echo "═══════════════════════════════════════════"
    svc_status "polsia"
    svc_status "celery-worker"
    svc_status "celery-beat"
    svc_status "hq"
    svc_status "crosswave"
    svc_status "blog"
    echo "─────────────────────────────────"
    echo "  PID directory: $PID_DIR"
    echo "  Log files:     *.log in $PID_DIR"
}

cmd_restart() {
    local service=${1:-all}
    cmd_stop "$service"
    sleep 1
    cmd_start "$service"
}

# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

case "${1:-status}" in
    start)   shift; cmd_start "${1:-all}" ;;
    stop)    shift; cmd_stop "${1:-all}" ;;
    status)  cmd_status ;;
    restart) shift; cmd_restart "${1:-all}" ;;
    *)
        echo "CrossWave HQ Service Manager"
        echo ""
        echo "Usage: bash hq/hq-manager.sh <command> [service]"
        echo ""
        echo "Commands:"
        echo "  start [svc]   Start services (default: all)"
        echo "  stop [svc]    Stop services (default: all)"
        echo "  status        Show all service statuses"
        echo "  restart [svc] Restart services"
        echo ""
        echo "Services: polsia, celery-worker, celery-beat, hq, crosswave, blog, all"
        exit 1
        ;;
esac
