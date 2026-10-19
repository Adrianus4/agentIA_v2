#!/usr/bin/env bash
# ==============================================================================
# scripts/start_backend_gpu.sh
# Start AgentIA Full Backend (Orchestrator + 4 Agent Microservices) + Qwen GPU LLM
# Designed for PC 1 (Backend + Qwen host) in a 1-PC or 2-PC split setup.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "${SCRIPT_DIR}/pyproject.toml" ] && [ -f "${SCRIPT_DIR}/../pyproject.toml" ]; then
    SCRIPT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi
cd "$SCRIPT_DIR"

if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

BACKEND_PORT="${PORT:-8000}"
VERIFIER_PORT="${VERIFIER_PORT:-8001}"
REPAIR_PORT="${REPAIR_PORT:-8002}"
VALIDATOR_PORT="${VALIDATOR_PORT:-8003}"
GENERATOR_PORT="${GENERATOR_PORT:-8004}"
LLAMA_PORT="${LLAMA_PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

echo "======================================================================"
echo " AgentIA v2 - Full Backend + Qwen Local LLM Launcher (PC 1)"
echo "======================================================================"

# Step 0: Pre-flight check for required host build & repair dependencies
MISSING_PKGS=()
for cmd in patch mvn java jq git curl; do
    if ! command -v "$cmd" &>/dev/null; then
        MISSING_PKGS+=("$cmd")
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo "--> [Pre-flight] Paquetes requeridos faltantes: ${MISSING_PKGS[*]}"
    if command -v dnf &>/dev/null; then
        echo "--> Instalando dependencias del sistema vía dnf (patch, maven, java-21-openjdk-devel, jq, git, curl)..."
        sudo dnf install -y patch maven java-21-openjdk-devel jq git curl || {
            echo "    [Aviso] No se pudieron instalar automáticamente con sudo dnf. Continuando..."
        }
    elif command -v apt-get &>/dev/null; then
        echo "--> Instalando dependencias del sistema vía apt..."
        sudo apt-get update -qq && sudo apt-get install -y patch maven openjdk-21-jdk jq git curl || true
    fi
else
    echo "--> [Pre-flight] Herramientas del sistema verificadas (patch, mvn, java, jq, git, curl)."
fi

# Step 0.5: Pre-warm Maven Quarkus cache if not present
if command -v mvn &>/dev/null && [ ! -d "$HOME/.m2/repository/io/quarkus" ]; then
    echo "--> [Pre-flight] Caché de Quarkus no detectada en ~/.m2/repository/io/quarkus."
    echo "--> Pre-calentando dependencias de Maven para acelerar las verificaciones..."
    if [ -f "${SCRIPT_DIR}/scripts/warm_maven_cache.sh" ]; then
        bash "${SCRIPT_DIR}/scripts/warm_maven_cache.sh" || true
    fi
fi

# Step 1: Kill any previous tasks occupying the backend, microservices, or LLM ports
echo "--> Cleaning up any stale tasks on ports ${BACKEND_PORT}, ${VERIFIER_PORT}, ${REPAIR_PORT}, ${VALIDATOR_PORT}, ${GENERATOR_PORT}, ${LLAMA_PORT}..."
if command -v fuser &>/dev/null; then
    for p in "$BACKEND_PORT" "$VERIFIER_PORT" "$REPAIR_PORT" "$VALIDATOR_PORT" "$GENERATOR_PORT"; do
        fuser -k "${p}/tcp" 2>/dev/null || true
    done
    if [ "${SKIP_LLAMA_SERVER:-0}" != "1" ]; then
        fuser -k "${LLAMA_PORT}/tcp" 2>/dev/null || true
    fi
fi
if [ "${SKIP_LLAMA_SERVER:-0}" != "1" ]; then
    pkill -f llama-server 2>/dev/null || true
fi
sleep 1

pids=()
cleanup() {
    trap - SIGINT SIGTERM EXIT
    echo ""
    echo "Shutting down AgentIA backend & GPU services..."
    if (( ${#pids[@]} )); then
        kill "${pids[@]}" 2>/dev/null || true
        for pid in "${pids[@]}"; do
            wait "$pid" 2>/dev/null || true
        done
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Step 2: Verify or Launch Local Qwen LLM Server (Vulkan llama-server or external/Ollama)
LLAMA_SERVER="${LLAMA_SERVER:-${SCRIPT_DIR}/tools/llama-vulkan/llama-b11575/llama-server}"
MODEL_14B="${SCRIPT_DIR}/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf"
MODEL_7B="${SCRIPT_DIR}/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
MODEL_3B="${SCRIPT_DIR}/models/qwen2.5-coder-3b-instruct-q4_k_m.gguf"

MODEL_ALIAS_DEFAULT="qwen2.5-coder:3b"
AUTO_GPU_LAYERS=99

if [ -n "${MODEL_PATH:-}" ]; then
    if [[ "$MODEL_PATH" == *"14b"* ]] || [[ "$MODEL_PATH" == *"14B"* ]]; then
        MODEL_ALIAS_DEFAULT="qwen2.5-coder:14b"
        AUTO_GPU_LAYERS=24
    elif [[ "$MODEL_PATH" == *"7b"* ]] || [[ "$MODEL_PATH" == *"7B"* ]]; then
        MODEL_ALIAS_DEFAULT="qwen2.5-coder:7b"
        AUTO_GPU_LAYERS=99
    fi
elif [ -f "$MODEL_14B" ]; then
    MODEL_PATH="$MODEL_14B"
    MODEL_ALIAS_DEFAULT="qwen2.5-coder:14b"
    AUTO_GPU_LAYERS=24
elif [ -f "$MODEL_7B" ]; then
    MODEL_PATH="$MODEL_7B"
    MODEL_ALIAS_DEFAULT="qwen2.5-coder:7b"
    AUTO_GPU_LAYERS=99
elif [ -f "$MODEL_3B" ]; then
    MODEL_PATH="$MODEL_3B"
    MODEL_ALIAS_DEFAULT="qwen2.5-coder:3b"
    AUTO_GPU_LAYERS=99
else
    MODEL_PATH=$(find "${SCRIPT_DIR}/models" -name "*.gguf" 2>/dev/null | head -n 1 || true)
fi

MODEL_ALIAS="${MODEL_ALIAS:-$MODEL_ALIAS_DEFAULT}"
CTX_SIZE="${CTX_SIZE:-8192}"
GPU_LAYERS="${N_GPU_LAYERS:-$AUTO_GPU_LAYERS}"

if [ "${SKIP_LLAMA_SERVER:-0}" = "1" ] && [ -n "${LOCAL_LLM_ENDPOINT:-}" ]; then
    echo "--> [LLM] Using external local LLM endpoint: ${LOCAL_LLM_ENDPOINT} (Model: ${MODEL_ALIAS})"
elif [ -f "$LLAMA_SERVER" ] && [ -n "${MODEL_PATH:-}" ] && [ -f "$MODEL_PATH" ]; then
    echo "--> Selected Model: $(basename "$MODEL_PATH") [Alias: ${MODEL_ALIAS}]"
    echo "--> Starting Vulkan GPU LLM server on port ${LLAMA_PORT} (Model: ${MODEL_ALIAS}, Layers: ${GPU_LAYERS}, Context: ${CTX_SIZE})..."
    "$LLAMA_SERVER" \
        --model "$MODEL_PATH" \
        --alias "$MODEL_ALIAS" \
        --alias "qwen2.5-coder:14b" \
        --alias "qwen2.5-coder:7b" \
        --alias "qwen2.5-coder:3b" \
        --host "$HOST" \
        --port "$LLAMA_PORT" \
        --n-gpu-layers "$GPU_LAYERS" \
        --ctx-size "$CTX_SIZE" &
    LLAMA_PID=$!
    pids+=("$LLAMA_PID")

    echo "--> Waiting for GPU LLM to initialize on port ${LLAMA_PORT}..."
    for i in {1..20}; do
        if curl -sf "http://127.0.0.1:${LLAMA_PORT}/v1/models" &>/dev/null; then
            echo "    GPU LLM ready! (PID: ${LLAMA_PID})"
            break
        fi
        sleep 1
    done
elif curl -sf "http://127.0.0.1:${LLAMA_PORT}/v1/models" &>/dev/null; then
    echo "--> [LLM] Detected existing OpenAI-compatible LLM server on port ${LLAMA_PORT}."
elif curl -sf "http://127.0.0.1:11434/v1/models" &>/dev/null; then
    LLAMA_PORT="11434"
    echo "--> [LLM] Detected local Ollama server on port 11434 (Model: ${MODEL_ALIAS})."
else
    echo "ERROR: Neither Vulkan llama-server ($LLAMA_SERVER + models/*.gguf) nor an active local LLM on port ${LLAMA_PORT}/11434 was found."
    echo "       Place your Qwen .gguf model in models/ (or run ./scripts/download_qwen_7b.sh) or start Ollama."
    exit 1
fi

# Step 3: Prepare Python runtime and shared directories
LOG_DIR="${SCRIPT_DIR}/.agentia-runtime/launcher"
export WORKFLOW_STATE_DIR="${WORKFLOW_STATE_DIR:-${SCRIPT_DIR}/.agentia-runtime/workflow-state}"
export AGENTIA_WORKSPACE_ROOT="${AGENTIA_WORKSPACE_ROOT:-${SCRIPT_DIR}/.agentia-runtime/workspaces}"
mkdir -p "$LOG_DIR" "$WORKFLOW_STATE_DIR" "$AGENTIA_WORKSPACE_ROOT"

if [ ! -x "${SCRIPT_DIR}/.venv/bin/python" ] && command -v uv &>/dev/null; then
    echo "--> Synchronizing Python virtual environment with uv..."
    uv sync --locked --extra dev || uv sync
fi

# Step 4: Configure environment for Orchestrator + 4 Agent Microservices
export ORCHESTRATOR_API_KEY="${ORCHESTRATOR_API_KEY:-secret}"
export AGENT_GATEWAY_API_KEY="${AGENT_GATEWAY_API_KEY:-$ORCHESTRATOR_API_KEY}"
export ORCHESTRATOR_ALLOW_PUBLIC_READ="${ORCHESTRATOR_ALLOW_PUBLIC_READ:-1}"
export ORCHESTRATOR_GENERATION_ENABLED="1"
export ORCHESTRATOR_DATABASE_PATH="${ORCHESTRATOR_DATABASE_PATH:-runs.db}"
export LLM_PROVIDER="${LLM_PROVIDER:-local}"
export LOCAL_LLM_ENDPOINT="${LOCAL_LLM_ENDPOINT:-http://127.0.0.1:${LLAMA_PORT}}"
export LLM_MODEL="${MODEL_ALIAS}"
export VERIFIER_RUNNER="${VERIFIER_RUNNER:-host}"
export VERIFIER_TIMEOUT_SECONDS="${VERIFIER_TIMEOUT_SECONDS:-600}"
export VERIFIER_URL="http://127.0.0.1:${VERIFIER_PORT}"
export REPAIR_URL="http://127.0.0.1:${REPAIR_PORT}"
export BLUEPRINT_VALIDATOR_URL="http://127.0.0.1:${VALIDATOR_PORT}"
export GENERATOR_URL="http://127.0.0.1:${GENERATOR_PORT}"

run_uvicorn() {
    local module="$1" bind_host="$2" bind_port="$3" log_file="$4"
    if [ -x "${SCRIPT_DIR}/.venv/bin/python" ]; then
        "${SCRIPT_DIR}/.venv/bin/python" -m uvicorn "${module}:app" --host "$bind_host" --port "$bind_port" >"$log_file" 2>&1 &
    else
        uv run uvicorn "${module}:app" --host "$bind_host" --port "$bind_port" >"$log_file" 2>&1 &
    fi
    pids+=("$!")
}

echo "--> Starting 4 internal agent microservices (validator:${VALIDATOR_PORT}, generator:${GENERATOR_PORT}, verifier:${VERIFIER_PORT}, repair:${REPAIR_PORT})..."
run_uvicorn "services.validator_service" "127.0.0.1" "$VALIDATOR_PORT" "$LOG_DIR/validator.log"
run_uvicorn "services.generator_service" "127.0.0.1" "$GENERATOR_PORT" "$LOG_DIR/generator.log"
run_uvicorn "services.verifier_service"  "127.0.0.1" "$VERIFIER_PORT"  "$LOG_DIR/verifier.log"
run_uvicorn "services.repair_service"    "127.0.0.1" "$REPAIR_PORT"    "$LOG_DIR/repair.log"

echo "--> Starting FastAPI Orchestrator Gateway on ${HOST}:${BACKEND_PORT}..."
if [ -x "${SCRIPT_DIR}/.venv/bin/python" ]; then
    "${SCRIPT_DIR}/.venv/bin/python" -m uvicorn app.main:app --host "$HOST" --port "$BACKEND_PORT" 2>&1 | tee "$LOG_DIR/api.log" &
else
    uv run uvicorn app.main:app --host "$HOST" --port "$BACKEND_PORT" 2>&1 | tee "$LOG_DIR/api.log" &
fi
BACKEND_PID=$!
pids+=("$BACKEND_PID")

# Wait for all 5 FastAPI services to answer /openapi.json
echo "--> Waiting for Orchestrator and Agent Microservices to become ready..."
for svc_port in "$VALIDATOR_PORT" "$GENERATOR_PORT" "$VERIFIER_PORT" "$REPAIR_PORT" "$BACKEND_PORT"; do
    ready=0
    for _ in {1..30}; do
        if curl -sf "http://127.0.0.1:${svc_port}/openapi.json" &>/dev/null; then
            ready=1
            break
        fi
        sleep 0.5
    done
    if [ "$ready" -ne 1 ]; then
        echo "ERROR: Service on port ${svc_port} failed to start. Check logs in ${LOG_DIR}/" >&2
        exit 1
    fi
done

LOCAL_IP=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n 1 || echo "localhost")

echo "======================================================================"
echo " Services Active on Backend PC (${LOCAL_IP}):"
echo "   - FastAPI Orchestrator : http://${LOCAL_IP}:${BACKEND_PORT} (LAN accessible)"
echo "   - Validator Service    : http://127.0.0.1:${VALIDATOR_PORT}"
echo "   - Generator Service    : http://127.0.0.1:${GENERATOR_PORT}"
echo "   - Verifier Service     : http://127.0.0.1:${VERIFIER_PORT}"
echo "   - Repair Service       : http://127.0.0.1:${REPAIR_PORT}"
echo "   - Local Qwen LLM       : ${LOCAL_LLM_ENDPOINT} (${MODEL_ALIAS})"
echo ""
echo " On the Frontend PC, run:"
echo "   FEDORA_IP=${LOCAL_IP} bash start_frontend.sh"
echo ""
echo " Web Studio Settings (if configured manually in UI):"
echo "   - Backend URL          : http://${LOCAL_IP}:${BACKEND_PORT}"
echo "   - LLM Endpoint         : ${LOCAL_LLM_ENDPOINT}"
echo "   - Model                : ${MODEL_ALIAS}"
echo "   - Orchestrator API Key : ${ORCHESTRATOR_API_KEY}"
echo " Press Ctrl+C to stop all services cleanly."
echo "======================================================================"

wait "$BACKEND_PID"
