#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# CrossWave 生产一键部署脚本
# 用法: bash scripts/deploy-production.sh [--prod]
# ═══════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo -e "${CYAN}  CrossWave Production Deploy${NC}"
echo -e "${CYAN}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo ""

# ── Pre-flight checks ──────────────────────────────────────
echo -e "${YELLOW}Pre-flight checks...${NC}"

if [ ! -f .env ]; then
  echo -e "${RED}✗ .env file not found! Copy .env.example to .env and configure.${NC}"
  exit 1
fi

if [ ! -f ssl/fullchain.pem ] || [ ! -f ssl/privkey.pem ]; then
  echo -e "${YELLOW}⚠ SSL certificates not found at ssl/. Using self-signed or HTTP only.${NC}"
  echo -e "${YELLOW}  Run: bash scripts/setup-ssl.sh${NC}"
fi

# Check Docker
if ! docker info >/dev/null 2>&1; then
  echo -e "${RED}✗ Docker is not running.${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Pre-flight checks passed${NC}"
echo ""

# ── Deploy ─────────────────────────────────────────────────
echo -e "${YELLOW}Pulling latest images...${NC}"
docker compose pull --quiet 2>/dev/null || true

echo -e "${YELLOW}Building services...${NC}"
docker compose build --quiet 2>/dev/null || true

echo -e "${YELLOW}Starting all services...${NC}"

if [ "${1:-}" = "--prod" ] && [ -f docker-compose.prod.yml ]; then
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans
  echo -e "${GREEN}✓ Production mode (with docker-compose.prod.yml)${NC}"
else
  docker compose up -d --remove-orphans
  echo -e "${GREEN}✓ Standard mode${NC}"
fi

# ── Health check ───────────────────────────────────────────
echo ""
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 5

# Run the health check
bash scripts/health-check.sh

echo ""
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  CrossWave deployment complete!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo ""
echo "  HQ Dashboard:    http://localhost:13001"
echo "  CrossBlog:       http://localhost:8002"
echo "  CrossDeploy:     http://localhost:8003"
echo "  Grafana:         http://localhost:3000"
echo "  NocoBase:        http://localhost:13000"
echo "  Uptime Kuma:     http://localhost:3001"
echo ""
echo "  To monitor logs: docker compose logs -f"
echo "  To stop:         docker compose down"
echo ""
