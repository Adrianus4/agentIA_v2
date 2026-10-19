#!/usr/bin/env bash
# ==============================================================================
# scripts/check_gpu.sh
# AMD Radeon GPU & Acceleration Diagnostics for Polaris (RX 570) and newer
# ==============================================================================
set -euo pipefail

echo "======================================================================"
echo " AgentIA v2 - GPU & Hardware Acceleration Check"
echo "======================================================================"

# 1. PCI identification
echo -e "\n[1] PCI Devices (VGA/3D/Display):"
if command -v lspci &>/dev/null; then
    lspci -nnk | grep -A3 -Ei 'vga|3d|display' || echo "No PCI display devices matched."
else
    echo "lspci not found. Install pciutils: sudo dnf install pciutils"
fi

# 2. Kernel driver
echo -e "\n[2] Loaded GPU Kernel Modules:"
lsmod | grep -E 'amdgpu|radeon|kfd' || echo "No AMD GPU kernel modules loaded."

# 3. OpenGL renderer
echo -e "\n[3] OpenGL Hardware Rendering:"
if command -v glxinfo &>/dev/null; then
    glxinfo -B 2>/dev/null | grep -E 'OpenGL renderer|OpenGL core profile version|Dedicated video memory' || glxinfo -B
else
    echo "glxinfo not found. Install mesa-demos: sudo dnf install mesa-demos"
fi

# 4. Vulkan Devices
echo -e "\n[4] Vulkan Device Support (Recommended for Polaris LLM inference):"
if command -v vulkaninfo &>/dev/null; then
    vulkaninfo --summary 2>/dev/null || echo "vulkaninfo failed or no display attached."
else
    echo "vulkaninfo not found. Install vulkan-tools: sudo dnf install vulkan-tools"
fi

# 5. ROCm status
echo -e "\n[5] ROCm Status (Note: Polaris RX 570 typically runs via Vulkan/CPU):"
if command -v rocminfo &>/dev/null; then
    rocminfo 2>/dev/null | grep -E 'Name:|Marketing Name:' || echo "ROCm installed but no devices queried."
else
    echo "rocminfo not installed (expected on non-ROCm Polaris setups)."
fi

# 6. Monitoring tool recommendation
echo -e "\n[6] Real-time GPU Monitor:"
if command -v radeontop &>/dev/null; then
    echo "radeontop is installed. Run 'watch -n 1 radeontop' in another terminal while running models."
else
    echo "radeontop not found. Install with: sudo dnf install radeontop"
fi

echo -e "\n======================================================================"

