#!/usr/bin/env bash
#
# Mission Control — Interactive Setup Wizard
#
# Usage:
#   curl -sSL <url>/setup.sh | bash
#   or: ./setup.sh
#
set -euo pipefail

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║       Mission Control Setup          ║"
echo "  ║   Personal AI Command Center         ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ─── Prerequisites ────────────────────────────────────────

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}✗ $1 is required but not installed.${NC}"
        echo "  Install it from: $2"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} $1 found"
}

echo -e "${BOLD}Checking prerequisites...${NC}"
check_command "docker" "https://docs.docker.com/get-docker/"

# Check Docker Compose (v2 plugin or standalone)
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}✗ Docker Compose is required but not found.${NC}"
    echo "  Install: https://docs.docker.com/compose/install/"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker Compose found"

# Check if Docker daemon is running
if ! docker info &> /dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon is not running. Start Docker and try again.${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker daemon running"
echo ""

# ─── .env Generation ─────────────────────────────────────

SKIP_ENV=false
if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env file already exists.${NC}"
    read -p "  Overwrite? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo "  Keeping existing .env"
        SKIP_ENV=true
    fi
fi

# Initialize variables
API_KEY=""
OAUTH_TOKEN=""
OPENROUTER_KEY=""
OLLAMA_URL=""
USE_SQLITE="false"
PG_USER="missionctl"
PG_PASS="missionctl"
PG_DB="missioncontrol"
TG_TOKEN=""
TG_USERS=""
DISCORD_TOKEN=""
DISCORD_CHANNELS=""
GITHUB_TOKEN=""

if [ "$SKIP_ENV" = "false" ]; then

    # ── Step 1: Database ──────────────────────────────────

    echo -e "${BOLD}Step 1/4: Database${NC}"
    echo ""
    echo "  1) PostgreSQL (recommended for production)"
    echo "  2) SQLite (zero-config, great for trying out)"
    echo ""
    read -p "  Choose database [1-2]: " db_choice

    case "${db_choice:-1}" in
        2)
            USE_SQLITE="true"
            echo -e "  ${GREEN}✓${NC} SQLite mode — no database setup needed!"
            ;;
        *)
            USE_SQLITE="false"
            read -p "  Database password [missionctl]: " custom_pass
            PG_PASS="${custom_pass:-missionctl}"
            echo -e "  ${GREEN}✓${NC} PostgreSQL with password set"
            ;;
    esac
    echo ""

    # ── Step 2: LLM Provider ─────────────────────────────

    echo -e "${BOLD}Step 2/4: LLM Provider${NC}"
    echo ""
    echo "  1) Anthropic API Key ${DIM}(recommended — stable, no expiry)${NC}"
    echo "  2) Claude Code OAuth Token ${DIM}(Pro/Max subscription)${NC}"
    echo "  3) OpenRouter API Key ${DIM}(multi-provider)${NC}"
    echo "  4) Ollama ${DIM}(local, no key needed)${NC}"
    echo "  5) Skip ${DIM}(configure later)${NC}"
    echo ""
    read -p "  Choose provider [1-5]: " provider_choice

    case "${provider_choice:-1}" in
        1)
            read -p "  Anthropic API Key: " API_KEY
            if [ -n "$API_KEY" ]; then
                # Validate key format
                if [[ ! "$API_KEY" =~ ^sk-ant- ]]; then
                    echo -e "  ${YELLOW}⚠ Key doesn't match expected format (sk-ant-...). Continuing anyway.${NC}"
                fi
                # Health check
                echo -n "  Checking API key..."
                HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
                    -H "x-api-key: $API_KEY" \
                    -H "anthropic-version: 2023-06-01" \
                    -H "Content-Type: application/json" \
                    -d '{"model":"claude-haiku-4-5","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}' \
                    https://api.anthropic.com/v1/messages 2>/dev/null || echo "000")
                if [ "$HTTP_CODE" = "200" ]; then
                    echo -e " ${GREEN}✓ Valid!${NC}"
                elif [ "$HTTP_CODE" = "401" ]; then
                    echo -e " ${RED}✗ Invalid key (401 Unauthorized). Double-check your key.${NC}"
                elif [ "$HTTP_CODE" = "000" ]; then
                    echo -e " ${YELLOW}⚠ Could not reach API (network issue). Key saved anyway.${NC}"
                else
                    echo -e " ${YELLOW}⚠ Got HTTP $HTTP_CODE. Key saved, but verify it works.${NC}"
                fi
            fi
            ;;
        2)
            read -p "  OAuth Token: " OAUTH_TOKEN
            ;;
        3)
            read -p "  OpenRouter API Key: " OPENROUTER_KEY
            ;;
        4)
            OLLAMA_URL="${OLLAMA_URL:-http://host.docker.internal:11434}"
            echo -n "  Checking Ollama..."
            if curl -sf "$OLLAMA_URL/api/version" > /dev/null 2>&1; then
                echo -e " ${GREEN}✓ Ollama is running!${NC}"
            else
                echo -e " ${YELLOW}⚠ Ollama not reachable at $OLLAMA_URL. Start it before running agents.${NC}"
            fi
            ;;
        5)
            echo -e "  ${DIM}Skipping LLM config — set it in .env later${NC}"
            ;;
    esac
    echo ""

    # ── Step 3: Integrations (optional) ──────────────────

    echo -e "${BOLD}Step 3/4: Integrations ${DIM}(all optional, press Enter to skip)${NC}"
    echo ""

    # Telegram
    read -p "  Telegram Bot Token: " TG_TOKEN
    if [ -n "$TG_TOKEN" ]; then
        # Validate Telegram token
        echo -n "  Checking Telegram bot..."
        TG_RESP=$(curl -sf "https://api.telegram.org/bot${TG_TOKEN}/getMe" 2>/dev/null || echo '{"ok":false}')
        if echo "$TG_RESP" | grep -q '"ok":true'; then
            BOT_NAME=$(echo "$TG_RESP" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
            echo -e " ${GREEN}✓ @${BOT_NAME}${NC}"
        else
            echo -e " ${YELLOW}⚠ Token not valid or bot API unreachable${NC}"
        fi
        read -p "  Allowed Telegram user IDs (comma-separated, Enter for all): " TG_USERS
    fi

    # Discord
    read -p "  Discord Bot Token: " DISCORD_TOKEN
    if [ -n "$DISCORD_TOKEN" ]; then
        read -p "  Allowed Discord channel IDs (comma-separated, Enter for all): " DISCORD_CHANNELS
    fi

    # GitHub
    read -p "  GitHub Personal Access Token: " GITHUB_TOKEN
    if [ -n "$GITHUB_TOKEN" ]; then
        echo -n "  Checking GitHub token..."
        GH_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            https://api.github.com/user 2>/dev/null || echo "000")
        if [ "$GH_CODE" = "200" ]; then
            echo -e " ${GREEN}✓ Valid!${NC}"
        elif [ "$GH_CODE" = "401" ]; then
            echo -e " ${YELLOW}⚠ Invalid token. Saved anyway.${NC}"
        else
            echo -e " ${YELLOW}⚠ Could not verify (HTTP $GH_CODE). Saved anyway.${NC}"
        fi
    fi
    echo ""

    # ── Step 4: Write .env ────────────────────────────────

    echo -e "${BOLD}Step 4/4: Writing configuration...${NC}"

    cat > .env << ENVEOF
# Mission Control - Generated by setup.sh
# $(date -u +"%Y-%m-%d %H:%M:%S UTC")

# --- LLM Authentication ---
ANTHROPIC_API_KEY=${API_KEY}
CLAUDE_CODE_OAUTH_TOKEN=${OAUTH_TOKEN}
OPENROUTER_API_KEY=${OPENROUTER_KEY}
OLLAMA_BASE_URL=${OLLAMA_URL}

# --- Database ---
USE_SQLITE=${USE_SQLITE}
SQLITE_PATH=data/mission_control.db
POSTGRES_USER=${PG_USER}
POSTGRES_PASSWORD=${PG_PASS}
POSTGRES_DB=${PG_DB}

# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
TELEGRAM_ALLOWED_USERS=${TG_USERS}

# --- Discord Bot ---
DISCORD_BOT_TOKEN=${DISCORD_TOKEN}
DISCORD_ALLOWED_CHANNELS=${DISCORD_CHANNELS}

# --- GitHub ---
GITHUB_TOKEN=${GITHUB_TOKEN}

# --- Ports ---
API_PORT=8000
DASHBOARD_PORT=3000
DB_PORT=5432
REDIS_PORT=6379

# --- Agent Defaults ---
DEFAULT_MODEL=claude-haiku-4-5
SMART_MODEL=claude-sonnet-4-6
MAX_AGENT_BUDGET_USD=0.50
ENVEOF

    echo -e "${GREEN}✓${NC} .env file created"
fi

# ─── Start Services ──────────────────────────────────────

echo ""
echo -e "${BOLD}Starting Mission Control...${NC}"

# Use SQLite compose if configured
if grep -q "USE_SQLITE=true" .env 2>/dev/null; then
    echo -e "  ${DIM}Using SQLite mode (lightweight)${NC}"
    COMPOSE_FILE="docker-compose.sqlite.yml"
else
    COMPOSE_FILE="docker-compose.yml"
fi

$COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build

# Wait for backend health
echo ""
echo -n "  Waiting for backend"
for i in {1..30}; do
    if curl -sf http://localhost:${API_PORT:-8000}/health > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓${NC} Backend is healthy"
        break
    fi
    echo -n "."
    sleep 2
done

# Check dashboard
if curl -sf http://localhost:${DASHBOARD_PORT:-3000} > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Dashboard is running"
fi

echo ""
echo -e "${GREEN}${BOLD}Mission Control is ready!${NC}"
echo ""
echo -e "  Dashboard:  ${CYAN}http://localhost:${DASHBOARD_PORT:-3000}${NC}"
echo -e "  API:        ${CYAN}http://localhost:${API_PORT:-8000}/health${NC}"
echo -e "  API Docs:   ${CYAN}http://localhost:${API_PORT:-8000}/docs${NC}"
echo ""
echo -e "  ${DIM}Commands:${NC}"
echo "    docker compose logs -f    — view logs"
echo "    docker compose stop       — stop services"
echo "    docker compose restart    — restart services"
echo ""
