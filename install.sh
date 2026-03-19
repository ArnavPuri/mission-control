#!/usr/bin/env bash
#
# Mission Control — One-Command Installer
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/<owner>/mission-control/main/install.sh | bash
#
# What it does:
#   1. Checks prerequisites (git, docker)
#   2. Clones the repository
#   3. Runs the interactive setup wizard
#
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

REPO_URL="${MC_REPO_URL:-https://github.com/ArnavPuri/mission-control.git}"
INSTALL_DIR="${MC_INSTALL_DIR:-mission-control}"

echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║    Mission Control — Installer       ║"
echo "  ║   Personal AI Command Center         ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ─── Check prerequisites ─────────────────────────────────

check() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}✗ $1 is required. Install from: $2${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} $1"
}

echo -e "${BOLD}Checking prerequisites...${NC}"
check "git" "https://git-scm.com/downloads"
check "docker" "https://docs.docker.com/get-docker/"
check "curl" "your package manager (apt, brew, etc.)"
echo ""

# ─── Clone ────────────────────────────────────────────────

if [ -d "$INSTALL_DIR" ]; then
    echo -e "Directory ${CYAN}$INSTALL_DIR${NC} already exists."
    read -p "  Use existing directory? (Y/n): " use_existing
    if [[ "$use_existing" =~ ^[Nn]$ ]]; then
        echo "  Aborted. Remove or rename the directory and try again."
        exit 1
    fi
    cd "$INSTALL_DIR"
    echo -e "${GREEN}✓${NC} Using existing directory"
else
    echo -e "Cloning Mission Control..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    echo -e "${GREEN}✓${NC} Cloned to ${CYAN}$INSTALL_DIR${NC}"
fi
echo ""

# ─── Run setup wizard ────────────────────────────────────

echo -e "Starting setup wizard..."
echo ""
bash setup.sh
