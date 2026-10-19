#!/usr/bin/env bash
# ==============================================================================
# scripts/start_vulkan_llm.sh
# Launch llama-server with Vulkan acceleration for AMD Radeon RX 570
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

LLAMA_SERVER="${LLAMA_SERVER:-${SCRIPT_DIR}/tools/llama-vulkan/llama-b11575/llama-server}"
MODEL_14B="${SCRIPT_DIR}/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf"
MODEL_7B="${SCRIPT_DIR}/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
MODEL_3B="${SCRIPT_DIR}/models/qwen2.5-coder-3b-instruct-q4_k_m.gguf"

AUTO_GPU_LAYERS=99
if [ -f "$MODEL_14B" ]; then
    DEFAULT_MODEL="$MODEL_14B"
    DEFAULT_ALIAS="qwen2.5-coder:14b"
    AUTO_GPU_LAYERS=24
elif [ -f "$MODEL_7B" ]; then
    DEFAULT_MODEL="$MODEL_7B"
    DEFAULT_ALIAS="qwen2.5-coder:7b"
    AUTO_GPU_LAYERS=99
else
    DEFAULT_MODEL="$MODEL_3B"
    DEFAULT_ALIAS="qwen2.5-coder:3b"
    AUTO_GPU_LAYERS=99
fi

MODEL_PATH="${MODEL_PATH:-$DEFAULT_MODEL}"
PORT="${LLAMA_PORT:-8080}"
HOST="${LLAMA_HOST:-0.0.0.0}"
MODEL_ALIAS="${MODEL_ALIAS:-$DEFAULT_ALIAS}"
CTX_SIZE="${CTX_SIZE:-8192}"
N_GPU_LAYERS="${N_GPU_LAYERS:-$AUTO_GPU_LAYERS}"

if [ ! -f "$LLAMA_SERVER" ]; then
    echo "ERROR: llama-server binary not found at $LLAMA_SERVER"
    exit 1
fi

if [ -z "${MODEL_PATH:-}" ] || [ ! -f "$MODEL_PATH" ]; then
    echo "ERROR: Model file not found in models/ directory."
    echo "Please run ./scripts/download_qwen_7b.sh or place a .gguf in models/."
    exit 1
fi

# Kill any previous instance occupying the target port
if command -v fuser &>/dev/null && fuser "${PORT}/tcp" &>/dev/null; then
    echo "Port ${PORT} is in use. Stopping previous instance..."
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    sleep 1
fi

echo "======================================================================"
echo " Starting Vulkan GPU Accelerated LLM Server"
echo " Binary       : $LLAMA_SERVER"
echo " Model        : $MODEL_PATH"
echo " Model Alias  : $MODEL_ALIAS"
echo " Endpoint     : http://${HOST}:${PORT}"
echo " GPU Offload  : -ngl ${N_GPU_LAYERS} (Vulkan / AMD Radeon RX 570)"
echo " Context Size : ${CTX_SIZE}"
echo "======================================================================"

exec "$LLAMA_SERVER" \
    --model "$MODEL_PATH" \
    --alias "$MODEL_ALIAS" \
    --alias "qwen2.5-coder:3b" \
    --alias "qwen2.5-coder:7b" \
    --host "$HOST" \
    --port "$PORT" \
    --n-gpu-layers "$N_GPU_LAYERS" \
    --ctx-size "$CTX_SIZE"
