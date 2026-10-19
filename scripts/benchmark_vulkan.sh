#!/usr/bin/env bash
# ==============================================================================
# scripts/benchmark_vulkan.sh
# Benchmark Vulkan GPU-accelerated llama-server on AMD Radeon RX 570
# ==============================================================================
set -euo pipefail

MODEL="${1:-qwen2.5-coder:3b}"
LLAMA_URL="${LLAMA_URL:-http://127.0.0.1:8080}"

echo "======================================================================"
echo " AgentIA v2 - Vulkan GPU LLM Benchmark"
echo " Target Model : $MODEL"
echo " Endpoint     : $LLAMA_URL"
echo "======================================================================"

# Check llama-server connectivity
if ! curl -sf "${LLAMA_URL}/v1/models" &>/dev/null; then
    echo "ERROR: Could not connect to llama-server at $LLAMA_URL"
    echo "Please ensure the server is running: ./scripts/start_vulkan_llm.sh"
    exit 1
fi

echo -e "\n--> llama-server model info:"
curl -s "${LLAMA_URL}/v1/models" | grep -o '"id":"[^"]*"' || true

echo -e "\n[1] Testing Structured Chat Completion (Quarkus Specification Prompt) on GPU..."
time curl -s "${LLAMA_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"$MODEL\",
        \"messages\": [
            {
                \"role\": \"system\",
                \"content\": \"You are a senior software architect. Return only valid JSON with keys: service_name, package_name, business_objective.\"
            },
            {
                \"role\": \"user\",
                \"content\": \"Create specification for an order payment processing microservice.\"
            }
        ],
        \"temperature\": 0.1
    }" | grep -o '"content":"[^"]*"' || true

echo -e "\n\n======================================================================"
echo " Benchmark completed on Vulkan GPU for $MODEL"
echo "======================================================================"

