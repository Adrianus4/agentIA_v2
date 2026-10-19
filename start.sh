#!/usr/bin/env bash
# AgentIA v2 - Linux local launcher: orchestrator (LangGraph) + 4 agent microservices + Web Studio.
# For the containerized stack (same topology Openship deploys) use: bash scripts/start_microservices.sh
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    cat <<'HELP'
Uso: bash start.sh [--no-frontend]
Requisitos: Python >=3.11 (uv opcional), Node >=18 + npm, JDK 21 y Maven.
Carga .env (formato KEY=VALUE). Ctrl+C detiene todos los procesos de la sesion.

Puertos: PORT=8000 FRONTEND_PORT=3000 VERIFIER_PORT=8001 REPAIR_PORT=8002
         VALIDATOR_PORT=8003 GENERATOR_PORT=8004
LLM:     GEMINI_API_KEY=...            (proveedor gemini)
         LLM_PROVIDER=local            (Ollama en LOCAL_LLM_ENDPOINT, por defecto :11434)
         LLM_PROVIDER=openai OPENAI_API_KEY=... [OPENAI_API_BASE=...]
         LLM_MODEL=<modelo>            (opcional; por defecto segun proveedor)
Ejemplo: PORT=9000 FRONTEND_PORT=3001 bash start.sh
HELP
    exit 0
fi
WITH_FRONTEND=1
if [[ ${1:-} == --no-frontend ]]; then WITH_FRONTEND=0; shift; fi
if (( $# > 0 )); then echo 'Argumento desconocido. Usa --help.' >&2; exit 1; fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

missing=()
for tool in java mvn; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
done
if (( WITH_FRONTEND )); then
    for tool in node npm; do command -v "$tool" >/dev/null 2>&1 || missing+=("$tool"); done
fi
PYTHON_BOOT="$(command -v python3 || command -v python || true)"
[[ -n "$PYTHON_BOOT" ]] || missing+=("python3")
if (( ${#missing[@]} )); then
    echo "Faltan herramientas: ${missing[*]}. Instalalas y vuelve a ejecutar el script." >&2
    exit 1
fi

PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
VERIFIER_PORT="${VERIFIER_PORT:-8001}"
REPAIR_PORT="${REPAIR_PORT:-8002}"
VALIDATOR_PORT="${VALIDATOR_PORT:-8003}"
GENERATOR_PORT="${GENERATOR_PORT:-8004}"
RUNTIME_DIR="$SCRIPT_DIR/.agentia-runtime"

export ORCHESTRATOR_API_KEY="${ORCHESTRATOR_API_KEY:-secret}"
export ORCHESTRATOR_ALLOW_PUBLIC_READ="${ORCHESTRATOR_ALLOW_PUBLIC_READ:-1}"
export AGENT_GATEWAY_API_KEY="${AGENT_GATEWAY_API_KEY:-$ORCHESTRATOR_API_KEY}"
if [[ -z "${LLM_PROVIDER:-}" ]]; then
    if [[ -n "${GEMINI_API_KEY:-}" ]]; then export LLM_PROVIDER=gemini; else export LLM_PROVIDER=local; fi
fi
export LOCAL_LLM_ENDPOINT="${LOCAL_LLM_ENDPOINT:-http://127.0.0.1:11434}"
export VERIFIER_RUNNER=host
export VERIFIER_TIMEOUT_SECONDS="${VERIFIER_TIMEOUT_SECONDS:-900}"
export AGENT_CLIENT_TIMEOUT_SECONDS="${AGENT_CLIENT_TIMEOUT_SECONDS:-960}"
export AGENTIA_MAX_REPAIR_ATTEMPTS="${AGENTIA_MAX_REPAIR_ATTEMPTS:-3}"
export VERIFIER_URL="http://127.0.0.1:$VERIFIER_PORT"
export REPAIR_URL="http://127.0.0.1:$REPAIR_PORT"
export BLUEPRINT_VALIDATOR_URL="http://127.0.0.1:$VALIDATOR_PORT"
export GENERATOR_URL="http://127.0.0.1:$GENERATOR_PORT"
export BACKEND_URL="http://127.0.0.1:$PORT"
export WORKFLOW_STATE_DIR="${WORKFLOW_STATE_DIR:-$RUNTIME_DIR/workflow-state}"
export AGENTIA_WORKSPACE_ROOT="${AGENTIA_WORKSPACE_ROOT:-$RUNTIME_DIR/workspaces}"
export VERIFIER_SCRATCH_DIR="${VERIFIER_SCRATCH_DIR:-$RUNTIME_DIR/verify}"
export ORCHESTRATOR_DATABASE_PATH="${ORCHESTRATOR_DATABASE_PATH:-$RUNTIME_DIR/runs.db}"

echo 'Preparando entorno Python...'
if command -v uv >/dev/null 2>&1; then
    uv sync --extra dev
else
    if [[ ! -x .venv/bin/python ]]; then "$PYTHON_BOOT" -m venv .venv; fi
    .venv/bin/python -m pip install -q --upgrade pip
    .venv/bin/python -m pip install -q -r requirements.txt pytest pytest-asyncio respx
fi
PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo 'No existe .venv/bin/python. Si copiaste el proyecto desde Windows, borra .venv y reintenta.' >&2
    exit 1
fi

ports=("$PORT" "$VERIFIER_PORT" "$REPAIR_PORT" "$VALIDATOR_PORT" "$GENERATOR_PORT")
(( WITH_FRONTEND )) && ports+=("$FRONTEND_PORT")
# Refuse occupied ports; never terminate another application's processes.
"$PYTHON" - "${ports[@]}" <<'PY'
import socket
import sys
sockets = []
try:
    ports = [int(p) for p in sys.argv[1:]]
    if len(set(ports)) != len(ports) or any(not 1 <= p <= 65535 for p in ports):
        raise ValueError("Los puertos deben ser distintos y estar entre 1 y 65535")
    for port in ports:
        sock = socket.socket()
        sockets.append(sock)
        sock.bind(("127.0.0.1", port))
except (ValueError, OSError) as exc:
    sys.exit(f"No se pueden usar los puertos configurados ({exc}). Libera el puerto o cambia PORT/*_PORT.")
finally:
    for sock in sockets:
        sock.close()
PY

if (( WITH_FRONTEND )); then
    echo 'Instalando dependencias frontend...'
    (cd frontend && npm ci --no-audit --no-fund)
fi

LOG_DIR="$RUNTIME_DIR/launcher"
mkdir -p "$LOG_DIR" "$WORKFLOW_STATE_DIR" "$AGENTIA_WORKSPACE_ROOT" "$VERIFIER_SCRATCH_DIR"
pids=()
cleanup() {
    trap - EXIT INT TERM
    if (( ${#pids[@]} )); then
        echo 'Deteniendo los servicios de esta sesion...'
        kill "${pids[@]}" 2>/dev/null || true
        for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_service() {
    local name="$1" target="$2" port="$3"; shift 3
    "$PYTHON" -m uvicorn "$target" "$@" --host 127.0.0.1 --port "$port" >"$LOG_DIR/$name.log" 2>&1 &
    pids+=("$!")
}
start_service validator services.validator_service:app "$VALIDATOR_PORT"
start_service generator services.generator_service:app "$GENERATOR_PORT"
start_service verifier services.verifier_service:app "$VERIFIER_PORT"
start_service repair services.repair_service:app "$REPAIR_PORT"
start_service orchestrator app.main:create_app "$PORT" --factory
health_urls=(
    "http://127.0.0.1:$VALIDATOR_PORT/health" "http://127.0.0.1:$GENERATOR_PORT/health"
    "http://127.0.0.1:$VERIFIER_PORT/health" "http://127.0.0.1:$REPAIR_PORT/health"
    "http://127.0.0.1:$PORT/health"
)
if (( WITH_FRONTEND )); then
    # Empty base URL: the UI calls /v1 on its own origin and Vite proxies it to BACKEND_URL
    VITE_API_BASE_URL="" node "$SCRIPT_DIR/frontend/node_modules/vite/bin/vite.js" "$SCRIPT_DIR/frontend" \
        --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort >"$LOG_DIR/frontend.log" 2>&1 &
    pids+=("$!")
    health_urls+=("http://127.0.0.1:$FRONTEND_PORT")
fi

echo "Esperando el arranque. Logs: $LOG_DIR"
"$PYTHON" - "${health_urls[@]}" <<'PY'
import sys
import time
import urllib.error
import urllib.request
pending = set(sys.argv[1:])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
deadline = time.monotonic() + 60
while pending and time.monotonic() < deadline:
    for url in list(pending):
        try:
            with opener.open(url, timeout=0.5) as response:
                if response.status == 200:
                    pending.remove(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
    if pending:
        time.sleep(0.25)
if pending:
    sys.exit("Fallo de arranque; consulta los logs. Sin respuesta: " + ", ".join(sorted(pending)))
PY
(( WITH_FRONTEND )) && echo "Interfaz:  http://127.0.0.1:$FRONTEND_PORT"
echo "API/docs:  $BACKEND_URL/docs"
echo "LLM:       proveedor=$LLM_PROVIDER modelo=${LLM_MODEL:-<por defecto>}"
echo "Clave API del orquestador (configurala en la interfaz): $ORCHESTRATOR_API_KEY"
echo 'Pulsa Ctrl+C para detener todos los servicios.'
status=0
wait -n "${pids[@]}" || status=$?
echo "Un servicio se detuvo (codigo $status). Consulta $LOG_DIR." >&2
if (( status == 0 )); then status=1; fi
exit "$status"
