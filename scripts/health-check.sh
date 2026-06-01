#!/usr/bin/env bash
# CrossWave Health Monitor
# Usage: watch -n 30 ./scripts/health-check.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ENDPOINTS=(
    "CrossWave:9999/health"
    "HQ Bridge:13001/api/hq/summary"
    "CrossBlog:8002/health"
    "Polsia Fork:8001/api/v1/health"
)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CrossWave Health Monitor"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for entry in "${ENDPOINTS[@]}"; do
    name="${entry%%:*}"
    port_and_path="${entry#*:}"
    url="http://127.0.0.1:$port_and_path"

    start=$(date +%s%N)
    status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
    end=$(date +%s%N)
    ms=$(( (end - start) / 1000000 ))

    if [ "$status_code" = "200" ]; then
        printf "  ${GREEN}✅${NC} %-15s %5s %3dms\n" "$name" "$status_code" "$ms"
    elif [ "$status_code" = "000" ]; then
        printf "  ${RED}❌${NC} %-15s %5s\n" "$name" "DOWN"
    else
        printf "  ${YELLOW}⚠️${NC}  %-15s %5s %3dms\n" "$name" "$status_code" "$ms"
    fi
done

# Disk usage
echo ""
echo "  Disk: $(df -h / | awk 'NR==2{print $5}') used"
echo "  RAM:  $(free -h | awk '/^Mem:/{print $3"/"$2}')"

# Process check
for proc in "uvicorn hq.server" "uvicorn app.main:app --port 9999" "uvicorn app.main:app --port 8002"; do
    if pgrep -f "$proc" > /dev/null 2>&1; then
        pid=$(pgrep -f "$proc" | head -1)
        rss=$(ps -o rss= -p "$pid" 2>/dev/null | awk '{printf "%.0f MB", $1/1024}')
        echo "  $(echo "$proc" | awk '{print $1}') PID:$pid ($rss)"
    fi
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
