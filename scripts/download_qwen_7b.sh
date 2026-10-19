#!/usr/bin/env bash
# ==============================================================================
# scripts/download_qwen_7b.sh
# Download Qwen 2.5 Coder 7B Instruct (Q4_K_M) with resume support
# Size: ~4.4 GB - High Quality Java / Quarkus Code Generation
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${SCRIPT_DIR}/models"

TARGET="${SCRIPT_DIR}/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
URL="https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"

echo "======================================================================"
echo " AgentIA v2 - Downloading Qwen 2.5 Coder 7B (Q4_K_M GGUF)"
echo " Destination: $TARGET"
echo " Size       : ~4.48 GB"
echo "======================================================================"

if [ -f "$TARGET" ]; then
    CURRENT_SIZE=$(stat -c%s "$TARGET" 2>/dev/null || stat -f%z "$TARGET" 2>/dev/null || echo 0)
    if [ "$CURRENT_SIZE" -gt 4000000000 ]; then
        echo "--> Model is already downloaded ($CURRENT_SIZE bytes)!"
        exit 0
    else
        echo "--> Incomplete download detected ($CURRENT_SIZE bytes). Resuming..."
    fi
fi

if command -v curl &>/dev/null; then
    curl -C - -L --progress-bar -o "$TARGET" "$URL"
elif command -v wget &>/dev/null; then
    wget -c -O "$TARGET" "$URL"
else
    echo "ERROR: Neither curl nor wget found on system."
    exit 1
fi

echo ""
echo "======================================================================"
echo " Download complete successfully!"
echo " File: $TARGET"
echo " Now run: ./start_gpu_backend.sh to launch with Qwen 2.5 Coder 7B!"
echo "======================================================================"

