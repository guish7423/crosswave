#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# CrossWave 全栈健康检查
# 用法: bash scripts/health-check.sh
# 返回: 所有在线服务状态汇总, 非0退出码表示有服务异常
# ═══════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
FAIL=0

check_http() {
  local name=$1 url=$2
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
  if [[ "$code" == "000" ]]; then
    echo -e "  ${RED}✗${NC} $name — unreachable"
    FAIL=1
  elif [[ "$code" -ge 200 && "$code" -lt 500 ]]; then
    echo -e "  ${GREEN}✓${NC} $name — HTTP $code"
  else
    echo -e "  ${RED}✗${NC} $name — HTTP $code"
    FAIL=1
  fi
}

check_container() {
  local name=$1
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
    echo -e "  ${GREEN}✓${NC} $name — running"
  else
    echo -e "  ${RED}✗${NC} $name — not running"
    FAIL=1
  fi
}

echo ""
echo "═══════════════════════════════════════════"
echo "  CrossWave Health Check — $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════"
echo ""

echo "── Containers ──"
check_container "hq-nocobase-1"
check_container "hq-postgres-1"
check_container "searxng"
check_container "crosswave-crossblog"

echo ""
echo "── HTTP Endpoints ──"
check_http "NocoBase"     "http://localhost:13000/"
check_http "CrossBlog"    "http://localhost:9000/health"
check_http "SearXNG"      "http://localhost:4000/"

echo ""
echo "── Database ──"
if docker exec hq-postgres-1 pg_isready -U nocobase >/dev/null 2>&1; then
  echo -e "  ${GREEN}✓${NC} PostgreSQL — accepting connections"
else
  echo -e "  ${RED}✗${NC} PostgreSQL — NOT accepting connections"
  FAIL=1
fi

# Quick table count sanity
TABLE_COUNT=$(docker exec hq-postgres-1 psql -U nocobase -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")
echo -e "  ${GREEN}✓${NC} NocoBase tables: $TABLE_COUNT"

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}✅ All services healthy${NC}"
else
  echo -e "${RED}❌ Some services have issues${NC}"
fi
echo ""
exit $FAIL
