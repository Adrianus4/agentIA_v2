# AgentIA v2: Network Deployment & Multi-PC Setup Guide (Fedora + RX 570)

This guide documents how to pull and run AgentIA v2 on a dedicated Linux/Fedora machine (e.g., equipped with an AMD Radeon RX 570 8GB GPU and local models via Ollama) and access the Web Studio from a remote client (laptop or workstation) on your private local network.

---

## 1. Architecture & Network Topology

```text
+------------------------------------------+
|          CLIENT LAPTOP / BROWSER         |
|  - Web UI: http://<FEDORA_IP>:3000       |
|  - No local LLM or Docker needed         |
+------------------------------------------+
                    |
                    | LAN HTTP (:3000 / :8000)
                    v
+------------------------------------------+
|            FEDORA WORKSTATION            |
|  - FastAPI Backend (:8000 on 0.0.0.0)    |
|  - Vite Dev/Preview (:3000 on 0.0.0.0)   |
|  - Hermetic Docker Runner (Maven test)   |
|  - Local LLM Runtime (Ollama / llama.cpp)|
|    -> Binds strictly to 127.0.0.1:11434  |
+------------------------------------------+
```

> [!IMPORTANT]
> **Network Security Rules**:
> 1. Only ports `3000` (Frontend) and `8000` (Backend) are opened to your local network.
> 2. Ollama (`11434`) must **never** be exposed externally; FastAPI communicates with Ollama locally via `127.0.0.1`.
> 3. Set `ORCHESTRATOR_ALLOW_PUBLIC_READ=0` when exposing the service on a LAN.

---

## 2. Fedora System Requirements & Prerequisites

On Fedora (Workstation/Server):

```bash
# 1. Install base development tools and Python 3.12+
sudo dnf install -y git curl gcc gcc-c++ make

# 2. Install Node.js (v20+ recommended)
sudo dnf install -y nodejs

# 3. Install Astral uv (Python package & environment manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# 4. Install and enable Docker (for hermetic verification runner)
sudo dnf install -y moby-engine docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# (Log out and log back in for docker group to take effect)
```

---

## 3. Cloning & Verifying Repository Integrity

To pull the project on the Fedora machine:

```bash
git clone <REPO_URL> agentIA_v2
cd agentIA_v2

# Sync backend environment and dependencies
uv sync --extra dev

# Run full test suite verification
uv run --extra dev pytest
uv run --extra dev mypy app/ contracts/ agents/
uv run --extra dev ruff check .

# Install frontend dependencies and build
cd frontend
npm install
npm test -- --run
npm run build
cd ..
```

All 163 backend tests and 40 frontend tests should pass out of the box.

---

## 4. Firewall Configuration (Fedora firewalld)

Open only ports `3000` and `8000` on your private LAN zone:

```bash
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Verify open ports:
sudo firewall-cmd --list-ports
```

Find the Fedora machine's LAN IP address:

```bash
ip -4 addr show
# Identify your local network IP (e.g., 192.168.1.42)
```

---

## 5. Starting the Backend & Frontend for Remote Access

### Option A: Separate Processes (Recommended for Debugging)

**Terminal 1 — Backend (FastAPI)**:
```bash
export ORCHESTRATOR_API_KEY='use-a-long-random-local-secret'
export ORCHESTRATOR_ALLOW_PUBLIC_READ=0
export ORCHESTRATOR_DATABASE_PATH='runs.db'

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend (Vite)**:
```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 3000
```

### Option B: Using Unified `start.sh`

In `start.sh`, ensure Vite binds to `0.0.0.0` rather than `localhost` when remote access is desired:
```bash
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}" \
ORCHESTRATOR_ALLOW_PUBLIC_READ=0 \
ORCHESTRATOR_API_KEY="use-a-long-random-local-secret" \
./start.sh
```

---

## 6. Accessing the Studio from your Laptop

1. Open your browser on the laptop:
   ```text
   http://<FEDORA_IP>:3000
   ```
2. In the Studio UI (or in API settings):
   - **Backend Base URL**: `http://<FEDORA_IP>:8000`
   - **API Key**: `use-a-long-random-local-secret` (matching `ORCHESTRATOR_API_KEY`)

Verify network connectivity from the laptop:
```bash
# Test API reachability
curl http://<FEDORA_IP>:8000/docs

# Test authenticated endpoint
curl -H "x-api-key: use-a-long-random-local-secret" \
  http://<FEDORA_IP>:8000/v1/runs
```

---

## 7. AMD Radeon RX 570 8GB GPU Setup & Verification

The Polaris-generation AMD Radeon RX 570 (8GB VRAM) provides a cost-effective platform for running local code-generation models.

### Step 1: Verify Driver & Hardware Acceleration

```bash
# Check GPU recognition and driver
lspci -nnk | grep -A3 -Ei 'vga|3d|display'
# Should display AMD Radeon RX 470/480/570/580 with kernel driver 'amdgpu'

# Check OpenGL rendering
sudo dnf install -y mesa-demos
glxinfo -B | grep "OpenGL renderer"

# Check Vulkan acceleration
sudo dnf install -y vulkan-tools mesa-vulkan-drivers
vulkaninfo --summary
```

> [!NOTE]
> Modern ROCm 6.x officially targets RDNA architectures (RX 6000/7000) and CDNA. For Polaris (RX 570), Vulkan (`llama.cpp` Vulkan backend) or optimized CPU inference are the most reliable acceleration backends.

### Step 2: Install Ollama & Pull Recommended Model

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the primary recommended model for 8GB VRAM
ollama pull qwen2.5-coder:3b
```

### Step 3: Recommended Models (by Priority)

| Priority | Model | Size | Context Target | Characteristics |
|---|---|---|---|---|
| **1 (Recommended)** | `qwen2.5-coder:3b` | ~2.0 GB | 4K–8K tokens | Fast, reliable JSON schema compliance, high Java/Quarkus accuracy. Fits comfortably in 8GB VRAM with ample room for system operations. |
| **2 (Fallback)** | `deepseek-coder:1.3b` | ~1.0 GB | 4K tokens | Extremely lightweight; ideal when system memory or GPU bandwidth is constrained. |
| **3 (Higher Capacity)** | `qwen2.5-coder:7b-instruct-q4_K_M` | ~4.7 GB | 4K tokens | Stronger reasoning, but higher VRAM footprint and lower token generation rate on Polaris. |

### Step 4: Monitor GPU Utilization During Generation

In a separate terminal on Fedora:
```bash
sudo dnf install -y radeontop
watch -n 1 radeontop
```

Test inference latency locally:
```bash
time curl http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:3b",
    "prompt": "Return only JSON: {\"status\":\"ok\"}",
    "stream": false
  }'
```

And test chat completions API:
```bash
time curl http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:3b",
    "messages": [
      {
        "role": "user",
        "content": "Return only JSON with keys service_name and package_name for a payment service."
      }
    ],
    "temperature": 0.1
  }'
```

### Step 5: Configure the Studio UI

In the AgentIA Web Studio LLM Drawer:
- **Provider**: `Local (Ollama / llama.cpp)`
- **Model**: `qwen2.5-coder:3b`
- **Endpoint**: `http://127.0.0.1:11434`
- **API Key**: *(leave blank)*

---

## 8. Readiness Checklist for Sharing with Colleagues

- [x] All 163 backend tests passing (`uv run --extra dev pytest`).
- [x] Static type checking 100% clean across 41 source files (`mypy app/ contracts/ agents/`).
- [x] Code style and linting 100% clean (`ruff check .`).
- [x] All 40 frontend integration & component tests passing (`npm test -- --run`).
- [x] Production frontend build passing (`npm run build`).
- [x] Working tree clean with zero uncommitted changes.
- [x] Hermetic Docker runner configured as default with strict non-fallback exit code 127.
- [x] Quarkus 3.15 profile with Java 21 Panache and Kafka extensions ready.
- [x] Truthful run statuses (`RUNNING`, `SUCCESS`, `NO_FIX`, `ERROR`) persisted to SQLite.
