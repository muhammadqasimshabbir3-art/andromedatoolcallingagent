#!/bin/bash
# Andromeda Agent — Quick Start
# Assumes setup is already done (./setup.sh). Loads .env and starts services.

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# shellcheck source=scripts/services.sh
source "${SCRIPT_DIR}/scripts/services.sh"

LANGGRAPH_PID=""
STREAMLIT_PID=""

cleanup() {
    if [ -n "$LANGGRAPH_PID" ]; then
        kill "$LANGGRAPH_PID" 2>/dev/null || true
    fi
    if [ -n "$STREAMLIT_PID" ]; then
        kill "$STREAMLIT_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

echo -e "${BLUE}"
echo "=================================================================="
echo "              ANDROMEDA AGENT - QUICK START"
echo "=================================================================="
echo -e "${NC}"

# Load environment
if [ ! -f ".env" ]; then
    echo -e "${RED}.env not found. Run setup first:${NC}"
    echo "  cp .env.example .env"
    echo "  ./setup.sh"
    exit 1
fi

set -a
load_dotenv ".env"
set +a

if [ -z "$GROQ_API_KEY" ]; then
    echo -e "${RED}GROQ_API_KEY is not set in .env${NC}"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running setup...${NC}"
    ./setup.sh
    exit $?
fi

if ! uv run python -c "from agent import graph" 2>/dev/null; then
    echo -e "${YELLOW}Syncing dependencies...${NC}"
    uv sync --quiet
fi

run_ui() {
    stop_streamlit
    echo -e "${BLUE}Starting Streamlit Web UI...${NC}"
    echo -e "${YELLOW}Open: http://localhost:${STREAMLIT_PORT}${NC}"
    echo ""
    trap - EXIT INT TERM
    uv run streamlit run streamlit_ui.py --server.port "${STREAMLIT_PORT}"
}

run_server() {
    stop_langgraph
    echo -e "${BLUE}Starting LangGraph Server with Cloudflare Tunnel...${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Using tunnel to expose local server to smith.langchain.com${NC}"
    echo -e "${YELLOW}    (Browser security prevents direct localhost access)${NC}"
    echo ""
    echo -e "${YELLOW}After tunnel is ready, Studio will open automatically.${NC}"
    echo -e "${YELLOW}If not, visit the URL printed in the output below.${NC}"
    echo ""
    trap - EXIT INT TERM
    uv run langgraph dev --port "${LANGGRAPH_PORT}" --tunnel
}

run_both() {
    stop_all_services

    echo -e "${BLUE}Starting LangGraph Server (with Tunnel) + Streamlit UI...${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Using tunnel to expose local server to smith.langchain.com${NC}"
    echo -e "${YELLOW}    (Browser security prevents direct localhost access)${NC}"
    echo ""
    echo -e "${YELLOW}Studio will open automatically once tunnel is ready.${NC}"
    echo -e "${YELLOW}UI:     http://localhost:${STREAMLIT_PORT}${NC}"
    echo ""

    uv run langgraph dev --port "${LANGGRAPH_PORT}" --tunnel &
    LANGGRAPH_PID=$!

    echo "Waiting for LangGraph server..."
    wait_for_port "${LANGGRAPH_PORT}" 30

    trap cleanup EXIT INT TERM

    echo "Starting Streamlit UI..."
    uv run streamlit run streamlit_ui.py --server.port "${STREAMLIT_PORT}"
}

run_stop() {
    trap - EXIT INT TERM
    stop_all_services
}

run_restart() {
    local target="${1:-both}"
    run_stop
    sleep 1
    case "$target" in
        ui) run_ui ;;
        server) run_server ;;
        both) run_both ;;
        *)
            echo -e "${RED}Unknown restart target: $target${NC}"
            echo "Use: ./start.sh restart [ui|server|both]"
            exit 1
            ;;
    esac
}

show_help() {
    echo "Usage: ./start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  ui              Start Streamlit chat UI (default)"
    echo "  server          Start LangGraph Server + Studio"
    echo "  both            Start both services"
    echo "  stop            Stop services on ports ${LANGGRAPH_PORT} and ${STREAMLIT_PORT}"
    echo "  restart [target] Restart ui, server, or both (default: both)"
    echo ""
    echo "Examples:"
    echo "  ./start.sh"
    echo "  ./start.sh server"
    echo "  ./start.sh both"
    echo "  ./start.sh stop"
    echo "  ./start.sh restart server"
    echo ""
    echo "First time? Run: ./setup.sh"
    echo "Workflow docs:  AgentWorkflow.md"
}

MODE="${1:-ui}"
ARG2="${2:-}"

case "$MODE" in
    ui)
        run_ui
        ;;
    server)
        run_server
        ;;
    both)
        run_both
        ;;
    stop)
        run_stop
        ;;
    restart)
        run_restart "${ARG2:-both}"
        ;;
    -h|--help|help)
        show_help
        ;;
    "")
        run_ui
        ;;
    *)
        echo -e "${RED}Unknown option: $MODE${NC}"
        show_help
        exit 1
        ;;
esac
