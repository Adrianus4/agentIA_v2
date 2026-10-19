#!/usr/bin/env bash
# ==============================================================================
# scripts/benchmark_llm.sh
# Benchmark local model latency and JSON schema fidelity on Ollama
# ==============================================================================
set -euo pipefail

MODEL="${1:-qwen2.5-coder:3b}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"

echo "======================================================================"
echo " AgentIA v2 - Local LLM Benchmark"
echo " Target Model : $MODEL"
echo " Endpoint     : $OLLAMA_URL"
echo "======================================================================"

# Check Ollama connectivity
if ! curl -sf "${OLLAMA_URL}/api/tags" &>/dev/null; then
    echo "ERROR: Could not connect to Ollama at $OLLAMA_URL"
    echo "Please ensure Ollama is running: ollama serve"
    exit 1
fi

echo -e "\n--> Currently running Ollama models:"
curl -s "${OLLAMA_URL}/api/ps" | grep -o '"name":"[^"]*"' || echo "No models currently loaded in VRAM."

echo -e "\n[1] Testing Raw JSON Generation Latency..."
time curl -s "${OLLAMA_URL}/api/generate" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"$MODEL\",
        \"prompt\": \"Return only JSON: {\\\"status\\\":\\\"ok\\\", \\\"architecture\\\":\\\"hexagonal\\\"}\",
        \"stream\": false
    }" | grep -o '"response":"[^"]*"' || true

echo -e "\n\n[2] Testing Structured Chat Completion (Quarkus Specification Prompt)..."
time curl -s "${OLLAMA_URL}/v1/chat/completions" \
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
echo " Benchmark completed for $MODEL"
echo "======================================================================"

