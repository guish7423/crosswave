#!/usr/bin/env bash
# =============================================================================
# CrossWave — Secret Key Rotation Script
# =============================================================================
# Usage:
#   ./scripts/rotate-secrets.sh              # Preview what would change
#   ./scripts/rotate-secrets.sh --apply       # Generate and write new secrets
#   ./scripts/rotate-secrets.sh --dry-run     # Same as default
#   ./scripts/rotate-secrets.sh --rotate-key <name>  # Rotate a single key
#
# This script generates cryptographically secure random secrets and updates
# .env files across all repositories. Run monthly for security compliance.
# =============================================================================

set -euo pipefail

MODE="${1:---dry-run}"

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC} $1"; }

# --- Key generation functions ---
gen_token32()  { python3 -c "import secrets; print(secrets.token_urlsafe(32))"; }
gen_token64()  { python3 -c "import secrets; print(secrets.token_hex(32))"; }
gen_password() { python3 -c "
import secrets, string
alphabet = string.ascii_letters + string.digits + '!@#\$%^&*()-_=+'
print(''.join(secrets.choice(alphabet) for _ in range(24)))
"; }

# --- Backup existing .env ---
backup_env() {
    local target="$1"
    if [ -f "$target" ]; then
        local backup="${target}.$(date +%Y%m%d-%H%M%S).bak"
        cp "$target" "$backup"
        ok "Backed up $target → $backup"
    fi
}

# --- Update a single key in .env ---
update_key() {
    local file="$1"
    local key="$2"
    local value="$3"
    local comment="$4"

    if [ ! -f "$file" ]; then
        warn "$file not found, skipping"
        return
    fi

    if grep -q "^${key}=" "$file" 2>/dev/null; then
        # Key exists — rotate it
        if [ "$MODE" = "--apply" ]; then
            sed -i "s|^${key}=.*|${key}=${value}|" "$file"
            ok "Rotated ${key} in ${file}"
        else
            info "[DRY-RUN] Would rotate ${key} in ${file}"
        fi
    else
        # Key doesn't exist — add it after a comment
        if [ "$MODE" = "--apply" ]; then
            echo "" >> "$file"
            [ -n "$comment" ] && echo "# ${comment}" >> "$file"
            echo "${key}=${value}" >> "$file"
            ok "Added ${key} to ${file}"
        else
            info "[DRY-RUN] Would add ${key} to ${file}"
        fi
    fi
}

# =============================================================================
# Main Rotation
# =============================================================================

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   CrossWave — Secret Key Rotation                 ${NC}"
echo -e "${CYAN}   Mode: ${MODE}                                    ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""

# --- Generate new keys ---
NEW_POLSIA_API_KEY=$(gen_token32)
NEW_API_KEY=$(gen_token32)
NEW_SECRET_KEY=$(gen_token64)
NEW_DB_PASSWORD=$(gen_password)
NEW_REDIS_PASSWORD=$(gen_password)

ok "Generated new secrets (preview only in dry-run mode)"

# --- 1. CrossWave .env ---
CROSSWAVE_ENV="$(dirname "$0")/../.env"
if [ -f "$CROSSWAVE_ENV" ]; then
    backup_env "$CROSSWAVE_ENV"
    update_key "$CROSSWAVE_ENV" "POLSIA_API_KEY" "$NEW_POLSIA_API_KEY" "Rotated on $(date +%Y-%m-%d)"
    update_key "$CROSSWAVE_ENV" "DEBUG" "false" ""
fi

# --- 2. Polsia Fork .env ---
POLSIA_ENV="$(dirname "$0")/../../polsia-fork/.env"
if [ -f "$POLSIA_ENV" ]; then
    backup_env "$POLSIA_ENV"
    update_key "$POLSIA_ENV" "API_KEY" "$NEW_API_KEY" "Rotated on $(date +%Y-%m-%d)"
    update_key "$POLSIA_ENV" "LLM_API_KEY" "sk-$(gen_token32)" "LLM API Key — set from your provider dashboard"
    update_key "$POLSIA_ENV" "DATABASE_URL" "postgresql+asyncpg://polsia:${NEW_DB_PASSWORD}@postgres:5432/polsia" ""
    update_key "$POLSIA_ENV" "REDIS_URL" "redis://:${NEW_REDIS_PASSWORD}@redis:6379/0" ""
    update_key "$POLSIA_ENV" "CELERY_BROKER_URL" "redis://:${NEW_REDIS_PASSWORD}@redis:6379/0" ""
    update_key "$POLSIA_ENV" "CELERY_RESULT_BACKEND" "redis://:${NEW_REDIS_PASSWORD}@redis:6379/1" ""
    update_key "$POLSIA_ENV" "LLM_API_MOCK" "false" ""
fi

# --- 3. CrossBlog .env ---
BLOG_ENV="$(dirname "$0")/../../ai-blog-engine/.env"
if [ -f "$BLOG_ENV" ]; then
    backup_env "$BLOG_ENV"
    update_key "$BLOG_ENV" "LLM_API_KEY" "sk-$(gen_token32)" "LLM API Key — set from your provider dashboard"
    update_key "$BLOG_ENV" "LLM_API_MOCK" "false" ""
fi

# --- 4. CrossBridge .env ---
BRIDGE_ENV="$(dirname "$0")/../../ai-content-bridge/.env"
if [ -f "$BRIDGE_ENV" ]; then
    backup_env "$BRIDGE_ENV"
    update_key "$BRIDGE_ENV" "LLM_API_KEY" "sk-$(gen_token32)" "LLM API Key — set from your provider dashboard"
    update_key "$BRIDGE_ENV" "SECRET_KEY" "$NEW_SECRET_KEY" "Rotated on $(date +%Y-%m-%d)"
    update_key "$BRIDGE_ENV" "LLM_API_MOCK" "false" ""
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
if [ "$MODE" = "--apply" ]; then
    ok "Secret rotation complete! Restart all services for changes to take effect."
    echo ""
    echo "  bash scripts/deploy-production.sh --restart"
else
    info "Dry-run complete. Run with --apply to rotate secrets."
    echo ""
    echo "  ./scripts/rotate-secrets.sh --apply"
fi
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""

# --- Security Reminder ---
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}   Security Checklist                        ${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "  □ .env files are excluded from git via .gitignore (verify!)"
echo "  □ DEBUG=false in production"
echo "  □ API keys rotated"
echo "  □ Database password rotated"
echo "  □ Redis password rotated"
echo "  □ Restarted all services after rotation"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
