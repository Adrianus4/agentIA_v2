#!/usr/bin/env bash
# ==============================================================================
# scripts/setup_fedora.sh
# Automated environment setup for Fedora Workstation / Server
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo " AgentIA v2 - Fedora Environment Setup"
echo "======================================================================"

# 1. System packages
echo "--> Installing system development packages, Java, Maven, and GPU diagnostics..."
sudo dnf install -y \
    git curl gcc gcc-c++ make nodejs \
    patch maven java-21-openjdk-devel jq \
    moby-engine docker-compose \
    mesa-demos vulkan-tools mesa-vulkan-drivers radeontop

# 2. Docker daemon enablement
echo "--> Enabling and starting Docker daemon..."
sudo systemctl enable --now docker
if ! groups "$USER" | grep -q '\bdocker\b'; then
    echo "--> Adding user $USER to docker group..."
    sudo usermod -aG docker "$USER"
    echo "[NOTE] You may need to log out and log back in for docker group to take effect."
fi

# 3. Astral uv
if ! command -v uv &>/dev/null; then
    echo "--> Installing Astral uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
else
    echo "--> Astral uv already installed: $(uv --version)"
fi

# 4. Ollama installation (optional prompt)
if ! command -v ollama &>/dev/null; then
    echo "--> Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "--> Ollama already installed: $(ollama --version)"
fi

# 5. Firewall configuration for ports 3000 & 8000
echo "--> Configuring firewalld for ports 3000 and 8000..."
if command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld; then
    sudo firewall-cmd --permanent --add-port=3000/tcp
    sudo firewall-cmd --permanent --add-port=8000/tcp
    sudo firewall-cmd --reload
    echo "    Open ports: $(sudo firewall-cmd --list-ports)"
else
    echo "    [Notice] firewalld is not active; skipping firewall port rules."
fi

# 6. Repository dependencies
echo "--> Syncing backend dependencies via uv..."
uv sync --extra dev

echo "--> Installing frontend dependencies via npm..."
(cd frontend && npm install)

# 7. Warm Maven dependency cache for Quarkus verification
if [ -f "scripts/warm_maven_cache.sh" ]; then
    echo "--> Pre-warming Maven dependency cache (for fast local Quarkus compilation)..."
    bash scripts/warm_maven_cache.sh || true
fi

echo "======================================================================"
echo " Setup complete!"
echo " Next steps:"
echo "   1. Pull the recommended model: ollama pull qwen2.5-coder:3b"
echo "   2. Run GPU check:             ./scripts/check_gpu.sh"
echo "   3. Benchmark local model:     ./scripts/benchmark_llm.sh"
echo "   4. Launch the studio:         ./start.sh"
echo "======================================================================"

