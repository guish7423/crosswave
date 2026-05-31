#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
# CrossWave 全栈启动脚本
# 一键启动 Polsia Fork + CrossWave + CrossBlog
# 依赖: Python 3.12+, 各项目 uv pip 已安装
# ═══════════════════════════════════════════════════════

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
POLSIA_DIR="$ROOT_DIR/../polsia-fork"
BLOG_DIR="$ROOT_DIR/../ai-blog-engine"
LOG_DIR="$ROOT_DIR/logs"

mkdir -p "$LOG_DIR"
PIDS=()

cleanup() {
    echo ""
    echo "🧹 关闭所有服务..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    echo "✅ 全部已关闭"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── 确认依赖 ──────────────────────────────────────────
echo "═══ CrossWave 全栈启动 ═══"
echo ""

# ── 1. Polsia Fork 后端 ──────────────────────────────
echo "1️⃣  启动 Polsia Fork 后端..."
cd "$POLSIA_DIR"
rm -f polsia.db  # 生产环境请注释此行
python scripts/seed_demo.py --fresh 2>&1 >> "$LOG_DIR/polsia_seed.log" || true
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
PIDS+=($!)
echo "  → Polsia Fork: http://localhost:8000"
echo "  → API Docs:    http://localhost:8000/docs"
sleep 2

# ── 2. CrossWave BFF ─────────────────────────────────
echo "2️⃣  启动 CrossWave BFF..."
cd "$ROOT_DIR"
uvicorn app.main:app --host 0.0.0.0 --port 9999 &
PIDS+=($!)
echo "  → CrossWave:   http://localhost:9999"
echo "  → Dashboard:   http://localhost:9999/dashboard"
echo "  → Agents:      http://localhost:9999/agents"
sleep 2

# ── 3. CrossBlog ─────────────────────────────────────
echo "3️⃣  启动 CrossBlog..."
cd "$BLOG_DIR"
LLM_API_MOCK=true python -c "
from app.database import init_db, save_post, get_all_posts
init_db()
count = len(get_all_posts(1, 100))
print(f'  → 博客已就绪 ({count} 篇种子文章)')
" 2>&1 >> "$LOG_DIR/blog_seed.log" || true
LLM_API_MOCK=true uvicorn app.main:app --host 0.0.0.0 --port 7777 &
PIDS+=($!)
echo "  → CrossBlog:   http://localhost:7777"
echo "  → Blog Listing: http://localhost:7777/blog"
echo ""

# ── 结果显示 ──────────────────────────────────────────
echo "═══════════════════════════════════════════════"
echo "✅ 全栈已启动！访问以下地址："
echo ""
echo "  📊 CrossWave 官网  http://localhost:9999"
echo "  📈 Dashboard       http://localhost:9999/dashboard"
echo "  🤖 Agents          http://localhost:9999/agents"
echo "  📝 CrossBlog       http://localhost:7777/blog"
echo "  🏢 Polsia API      http://localhost:8000/docs"
echo ""
echo "        按 Ctrl+C 停止全部服务"
echo "═══════════════════════════════════════════════"

# 等待
wait
