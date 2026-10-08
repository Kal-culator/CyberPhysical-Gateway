#!/usr/bin/env bash
# ==============================================================================
# start_pi_demo.sh - Master Orchestrator (Aesthetic Edition)
# ==============================================================================

BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

clear
echo -e "${CYAN}${BOLD}"
echo "╔════════════════════════════════════════════════════╗"
echo "║   🛡️  CYBER-PHYSICAL BIOMETRIC GATEWAY (EDGE) 🛡️   ║"
echo "╚════════════════════════════════════════════════════╝"
echo -e "${RESET}"

echo -e "${CYAN}▶ [1/2] System Check...${RESET}"
if [ ! -f "demo_config.json" ]; then
    echo -e "${RED}  ❌ ERROR: demo_config.json is missing!${RESET}"
    exit 1
else
    echo -e "${GREEN}  ✅ Config found.${RESET}"
fi

if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo -e "${GREEN}  ✅ Virtual environment activated.${RESET}"
else
    echo -e "${RED}  ❌ ERROR: Virtual environment '.venv' not found.${RESET}"
    exit 1
fi
echo ""

echo -e "${CYAN}▶ [2/2] Booting Hardware Sequence...${RESET}"
echo -e "${YELLOW}  ⏳ Initializing LCD, R307 Scanner, and Relays...${RESET}"
echo -e "${CYAN}──────────────────────────────────────────────────────${RESET}"
echo -e "${GREEN}${BOLD}  >>> SYSTEM LIVE (Press Ctrl+C TWICE to quit) <<<    ${RESET}"
echo -e "${CYAN}──────────────────────────────────────────────────────${RESET}"
echo ""

while true; do
    python3 demo.py run
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ System shut down gracefully.${RESET}"
        break
    fi
    echo ""
    echo -e "${RED}${BOLD}⚠️  SYSTEM DISCONNECTED (Error code: $EXIT_CODE)${RESET}"
    echo -e "${YELLOW}🔄 Auto-restarting in 3 seconds...${RESET}"
    echo -e "${CYAN}──────────────────────────────────────────────────────${RESET}"
    sleep 3
done