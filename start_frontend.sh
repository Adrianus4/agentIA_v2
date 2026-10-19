#!/usr/bin/env bash
# ==============================================================================
# start_frontend.sh (Client PC / Laptop Launcher)
# Starts only the Vite Web Studio connected to your Qwen Backend PC.
#
# Usage:
#   FEDORA_IP=192.168.1.135 bash start_frontend.sh
#   or:
#   bash start_frontend.sh 192.168.1.135
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
    echo "Usage: FEDORA_IP=<BACKEND_PC_IP> bash start_frontend.sh"
    echo "   or: bash start_frontend.sh <BACKEND_PC_IP>"
    exit 0
fi

# Configurable backend host/port (accepts positional arg $1, BACKEND_IP, or FEDORA_IP)
TARGET_IP="${1:-${BACKEND_IP:-${FEDORA_IP:-192.168.1.135}}}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_URL="${VITE_API_BASE_URL:-http://${TARGET_IP}:${BACKEND_PORT}}"

echo "======================================================================"
echo " AgentIA v2 - Web Studio Client Launcher (PC 2)"
echo " Target Qwen Backend   : ${BACKEND_URL}"
echo " Local Web UI Port     : ${FRONTEND_PORT}"
echo "======================================================================"

# Quick reachability check
echo "--> Checking connection to backend at ${BACKEND_URL}..."
if curl -sf -m 3 "${BACKEND_URL}/openapi.json" >/dev/null || curl -sf -m 3 "${BACKEND_URL}/docs" >/dev/null; then
    echo "    [OK] Backend is online and reachable at ${BACKEND_URL}!"
else
    echo "    [WARNING] Could not reach ${BACKEND_URL}/openapi.json within 3 seconds."
    echo "    Verify that start_gpu_backend.sh is running on ${TARGET_IP} and port ${BACKEND_PORT} is open."
fi

# Ensure frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "--> Installing frontend dependencies..."
    (cd frontend && npm install)
fi

echo "--> Launching Web Studio on http://localhost:${FRONTEND_PORT}..."
echo "    Press Ctrl+C to stop."
echo "======================================================================"

cd frontend
export VITE_API_BASE_URL="${BACKEND_URL}"
export BACKEND_URL="${BACKEND_URL}"
exec npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}"
