#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# CrossWave Credential Setup Wizard
# ═══════════════════════════════════════════════════════════════
# Interactive tool to configure all platform credentials.
# Run: bash scripts/credential-setup.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

CROSSWAVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
POLSIA_DIR="$CROSSWAVE_DIR/../polsia-fork"
ENV_FILE="$CROSSWAVE_DIR/.env"
ENV_EXAMPLE="$CROSSWAVE_DIR/.env.example"
ENV_PROD="$CROSSWAVE_DIR/.env.production.template"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     CrossWave Credential Setup Wizard          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── Helper: read or skip ──
prompt() {
    local var_name=$1 label=$2 default=${3:-}
    local cur_val cur_display
    cur_val=$(grep "^${var_name}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "")
    if [ -n "$cur_val" ]; then
        cur_display="${cur_val:0:20}..."
    else
        cur_display="(not set)"
    fi
    echo -e "  ${YELLOW}$label${NC}"
    echo -e "  Current: ${cur_display}"
    if [ -n "$default" ]; then
        echo -e "  Default: $default"
        read -rp "  Value (Enter for default): " input
        if [ -z "$input" ]; then input="$default"; fi
    else
        read -rp "  Value (Enter to skip): " input
    fi
    echo "$var_name|$input"
}

# ── Detect which .env to edit ──
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}No .env found. Creating from .env.example...${NC}"
    cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

# ── Backup ──
cp "$ENV_FILE" "$ENV_FILE.$(date +%Y%m%d-%H%M%S).bak"
echo -e "${GREEN}Backup saved to ${ENV_FILE}.bak${NC}"
echo ""

# ── Collect all credentials ──
declare -A results

echo -e "${CYAN}═══ LLM / AI API Keys ═══${NC}"
echo ""
results[DEEPSEEK_API_KEY]=$(prompt DEEPSEEK_API_KEY "DeepSeek API Key (https://platform.deepseek.com/api_keys)" "")
results[VOLC_ENGINE_API_KEY]=$(prompt VOLC_ENGINE_API_KEY "Volc Engine API Key (https://console.volcengine.com/ark)" "")
results[LLM_API_KEY]=$(prompt LLM_API_KEY "Generic LLM API Key (fallback)" "")

echo ""
echo -e "${CYAN}═══ Payment Processing ═══${NC}"
echo ""
echo -e "  ${YELLOW}Stripe (https://dashboard.stripe.com/apikeys)${NC}"
results[STRIPE_SECRET_KEY]=$(prompt STRIPE_SECRET_KEY "  Stripe Secret Key (sk_live_...)" "")
results[STRIPE_WEBHOOK_SECRET]=$(prompt STRIPE_WEBHOOK_SECRET "  Stripe Webhook Secret (whsec_...)" "")

echo ""
echo -e "${CYAN}═══ Email / SMTP ═══${NC}"
echo ""
results[SMTP_HOST]=$(prompt SMTP_HOST "SMTP Host (e.g. smtp.sendgrid.net)" "")
results[SMTP_PORT]=$(prompt SMTP_PORT "SMTP Port" "587")
results[SMTP_USER]=$(prompt SMTP_USER "SMTP Username" "")
results[SMTP_PASSWORD]=$(prompt SMTP_PASSWORD "SMTP Password" "")
results[SMTP_FROM_EMAIL]=$(prompt SMTP_FROM_EMAIL "From Email (e.g. hello@crosswave.app)" "")
results[SMTP_FROM_NAME]=$(prompt SMTP_FROM_NAME "From Name" "CrossWave")

echo ""
echo -e "${CYAN}═══ External Freelance Platforms ═══${NC}"
echo ""
echo -e "  ${YELLOW}Upwork (https://www.upwork.com/developer/keys/apply)${NC}"
results[UPWORK_CLIENT_ID]=$(prompt UPWORK_CLIENT_ID "  Upwork Client ID" "")
results[UPWORK_CLIENT_SECRET]=$(prompt UPWORK_CLIENT_SECRET "  Upwork Client Secret" "")

echo ""
echo -e "  ${YELLOW}猪八戒开放平台 (https://open.zbj.com/)${NC}"
results[ZHUBAJIE_APP_KEY]=$(prompt ZHUBAJIE_APP_KEY "  猪八戒 App Key" "")
results[ZHUBAJIE_APP_SECRET]=$(prompt ZHUBAJIE_APP_SECRET "  猪八戒 App Secret" "")

echo ""
echo -e "${CYAN}═══ AI Content Bridge (CrossBridge) ═══${NC}"
echo ""
results[CROSSBRIDGE_DB]=$(prompt CROSSBRIDGE_DB "CrossBridge DB Path" "../ai-content-bridge/content_bridge.db")

echo ""
echo -e "${CYAN}═══ Base URL (for email links) ═══${NC}"
echo ""
results[BASE_URL]=$(prompt BASE_URL "Public Base URL" "http://127.0.0.1:9999")

echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Applying configuration...${NC}"

# ── Write updated .env ──
> "$ENV_FILE"
cat <<'HEADER' >> "$ENV_FILE"
# CrossWave — Environment Configuration
# Managed by credential-setup.sh. Edit with care.
HEADER
echo "" >> "$ENV_FILE"

cat <<'SECTION' >> "$ENV_FILE"
# --- LLM / AI API Keys ---
SECTION
for key in DEEPSEEK_API_KEY VOLC_ENGINE_API_KEY LLM_API_KEY; do
    val="${results[$key]#*|}"
    [ -n "$val" ] && echo "${key}=${val}" >> "$ENV_FILE" || echo "# ${key}=" >> "$ENV_FILE"
done

echo "" >> "$ENV_FILE"; cat <<'SECTION' >> "$ENV_FILE"
# --- Payment Processing (Stripe) ---
# STRIPE_SECRET_KEY: sk_live_... from https://dashboard.stripe.com/apikeys
# STRIPE_WEBHOOK_SECRET: whsec_... from Stripe webhook settings
SECTION
for key in STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET; do
    val="${results[$key]#*|}"
    [ -n "$val" ] && echo "${key}=${val}" >> "$ENV_FILE" || echo "# ${key}=" >> "$ENV_FILE"
done

echo "" >> "$ENV_FILE"; cat <<'SECTION' >> "$ENV_FILE"
# --- Email / SMTP ---
SECTION
for key in SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASSWORD SMTP_FROM_EMAIL SMTP_FROM_NAME; do
    val="${results[$key]#*|}"
    [ -n "$val" ] && echo "${key}=${val}" >> "$ENV_FILE" || echo "# ${key}=${val:-}" >> "$ENV_FILE"
done

echo "" >> "$ENV_FILE"; cat <<'SECTION' >> "$ENV_FILE"
# --- External Freelance Platforms ---
SECTION
for key in UPWORK_CLIENT_ID UPWORK_CLIENT_SECRET ZHUBAJIE_APP_KEY ZHUBAJIE_APP_SECRET; do
    val="${results[$key]#*|}"
    [ -n "$val" ] && echo "${key}=${val}" >> "$ENV_FILE" || echo "# ${key}=" >> "$ENV_FILE"
done

echo "" >> "$ENV_FILE"; cat <<'SECTION' >> "$ENV_FILE"
# --- CrossBridge ---
SECTION
echo "CROSSBRIDGE_DB=${results[CROSSBRIDGE_DB]#*|}" >> "$ENV_FILE"

echo "" >> "$ENV_FILE"; cat <<'SECTION' >> "$ENV_FILE"
# --- Polsia Fork API Connection ---
POLSIA_BASE_URL=http://127.0.0.1:8001
POLSIA_API_KEY=dev-key
POLSIA_MOCK=false
PROXY_TIMEOUT=10
DEBUG=false

# --- Public URL (for email links) ---
BASE_URL=${results[BASE_URL]#*|}
SECTION

echo ""
echo -e "${GREEN}✅ .env updated successfully!${NC}"

# ── Generate secrets report ──
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Credential Status Summary${NC}"
echo ""

check() {
    local name=$1 val=$2
    if [ -n "$val" ]; then
        echo -e "  ${GREEN}✅${NC} $name"
    else
        echo -e "  ${RED}❌${NC} $name ${YELLOW}(not set — will use fallback)${NC}"
    fi
}

check "DeepSeek API Key"     "${results[DEEPSEEK_API_KEY]#*|}"
check "Volc Engine API Key"  "${results[VOLC_ENGINE_API_KEY]#*|}"
check "LLM API Key"          "${results[LLM_API_KEY]#*|}"
check "Stripe Secret Key"    "${results[STRIPE_SECRET_KEY]#*|}"
check "Stripe Webhook Secret" "${results[STRIPE_WEBHOOK_SECRET]#*|}"
check "SMTP"                 "${results[SMTP_HOST]#*|}"
check "Upwork OAuth"         "${results[UPWORK_CLIENT_ID]#*|}"
check "猪八戒 Open API"      "${results[ZHUBAJIE_APP_KEY]#*|}"
check "CrossBridge DB"       "${results[CROSSBRIDGE_DB]#*|}"

echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Next steps:${NC}"
echo "  1. Restart all services: bash hq/hq-manager.sh restart all"
echo "  2. For detailed platform registration guides, see: docs/PLATFORM_SETUP.md"
echo "  3. For production deployment hardening, see: LAUNCH_CHECKLIST.md"
echo ""
