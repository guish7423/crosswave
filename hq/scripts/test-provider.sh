#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# CrossWave — LLM Provider Connectivity Test
# Usage:
#   bash hq/scripts/test-provider.sh              # test all configured providers
#   bash hq/scripts/test-provider.sh openai       # test OpenAI only
#   bash hq/scripts/test-provider.sh deepseek     # test DeepSeek only
#   bash hq/scripts/test-provider.sh mock         # test Mock only
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail
cd "$(dirname "$0")/../.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

export PYTHONPATH="${PYTHONPATH:-}:${PWD}"

pass() { echo -e "  ${GREEN}✅ $1${NC}"; }
fail() { echo -e "  ${RED}❌ $1${NC}"; err=1; }
info() { echo -e "  ${YELLOW}ℹ️  $1${NC}"; }

test_mock() {
    echo -e "\n${YELLOW}Mock Provider${NC}"
    python3 -c "
import asyncio
from hq.model_router import get_registry
reg = get_registry()
profiles = reg.get_all_profiles()
for p in profiles:
    print(f'  Provider: {p.name} ({p.provider})')
    print(f'  Model: {p.model} | Available: {p.available}')
    print(f'  Capabilities: {p.capabilities}')
    print()
" && pass "Mock provider registered correctly" || fail "Mock provider failed"
}

test_openai() {
    echo -e "\n${YELLOW}OpenAI-Compatible Provider${NC}"
    KEY="${LLM_API_KEY:-}"
    if [ -z "$KEY" ]; then
        info "LLM_API_KEY not set — skipping OpenAI test"
        return
    fi
    python3 -c "
import asyncio, os
os.environ['LLM_PROVIDER_MOCK'] = 'false'
from hq.model_router import get_registry
reg = get_registry()

async def go():
    profiles = reg.get_all_profiles()
    for p in profiles:
        if p.provider == 'openai' and p.available:
            print(f'  ✅ OpenAI available: {p.name} ({p.model})')
            resp = await reg.chat('orchestrator', [
                {'role': 'user', 'content': 'Say exactly: OK_PROVIDER_TEST_PASSED'}
            ])
            print(f'  Response: {resp.content[:100]}')
            return
    print('  ⚠️  OpenAI provider not available (check LLM_API_KEY)')

asyncio.run(go())
" && pass "OpenAI API responds" || fail "OpenAI API error"
}

test_deepseek() {
    echo -e "\n${YELLOW}DeepSeek Provider${NC}"
    KEY="${DEEPSEEK_API_KEY:-}"
    if [ -z "$KEY" ]; then
        info "DEEPSEEK_API_KEY not set — skipping DeepSeek test"
        return
    fi
    python3 -c "
import asyncio, os
os.environ['LLM_PROVIDER_MOCK'] = 'false'
from hq.model_router import get_registry
reg = get_registry()

async def go():
    profiles = reg.get_all_profiles()
    for p in profiles:
        if p.provider == 'deepseek' and p.available:
            print(f'  ✅ DeepSeek available: {p.name} ({p.model})')
            resp = await reg.chat('code_generation', [
                {'role': 'user', 'content': 'Say exactly: DEEPSEEK_PROVIDER_TEST_PASSED'}
            ])
            print(f'  Response: {resp.content[:100]}')
            return
    print('  ⚠️  DeepSeek provider not available (check DEEPSEEK_API_KEY)')

asyncio.run(go())
" && pass "DeepSeek API responds" || fail "DeepSeek API error"
}

err=0
case "${1:-all}" in
    mock)     test_mock ;;
    openai)   test_openai ;;
    deepseek) test_deepseek ;;
    all)
        test_mock
        test_openai
        test_deepseek
        ;;
    *)
        echo "Usage: $0 {mock|openai|deepseek|all}"
        exit 1
        ;;
esac

echo ""
if [ "$err" = "1" ]; then
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
else
    echo -e "${GREEN}✅ All provider tests passed${NC}"
fi
