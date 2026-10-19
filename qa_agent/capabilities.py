"""Inspección local de capacidades de Python, paquetes requeridos, toolchains y cachés por suite (E04, C03, J01, U01)."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from qa_agent import EXIT_INCOMPLETE, EXIT_PASSED, SCHEMA_VERSION

CORE_QA_PACKAGES: tuple[str, ...] = (
    "pytest",
    "pydantic",
)

PLATFORM_QA_PACKAGES: tuple[str, ...] = (
    "pytest",
    "pydantic",
    "fastapi",
    "httpx",
    "uvicorn",
    "aiosqlite",
)

PRODUCT_PYTHON_PACKAGES: tuple[str, ...] = (
    "pytest",
    "pytest-asyncio",
    "respx",
    "pydantic",
    "fastapi",
    "httpx",
    "pyyaml",
    "langgraph",
    "google-generativeai",
    "aiosqlite",
    "jinja2",
    "uvicorn",
)

OPTIONAL_TOOLS: tuple[str, ...] = (
    "node",
    "npm",
    "java",
    "mvn",
    "docker",
    "git",
    "uv",
)


def _is_full_agentia_repo(repo_root: Path) -> bool:
    return (repo_root / "app" / "main.py").is_file() and (repo_root / "agents").is_dir()


def _simulated_missing_packages() -> set[str]:
    raw = os.environ.get("QA_SIMULATE_MISSING_PACKAGES", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def resolve_toolchain_binary(
    tool_name: str,
    repo_root: Path,
    current_path: str | None = None,
) -> str | None:
    """
    Resuelve un binario de herramienta buscando primero en PATH y, si no se forzó el bloqueo de toolchains,
    en `.agentia-runtime/toolchains/` dentro del repositorio objetivo.
    """
    effective_path = os.environ.get("PATH", "") if current_path is None else current_path
    found = shutil.which(tool_name, path=effective_path)
    if found:
        return found

    if os.environ.get("QA_FORCE_NO_LOCAL_TOOLCHAINS") == "1":
        return None
    # Si el test vació PATH intencionalmente (sin System32 ni /usr/bin), no buscar fuera de PATH
    if not effective_path or ("system32" not in effective_path.lower() and "/bin" not in effective_path.lower()):
        return None

    toolchains_dir = repo_root / ".agentia-runtime" / "toolchains"
    if not toolchains_dir.is_dir():
        return None

    candidates: list[Path] = []
    if tool_name in ("java", "javac"):
        exe = f"{tool_name}.exe" if os.name == "nt" else tool_name
        candidates.extend(toolchains_dir.glob(f"jdk*/bin/{exe}"))
        candidates.extend(toolchains_dir.glob(f"jdk*/*/bin/{exe}"))
    elif tool_name == "mvn":
        names = ("mvn.cmd", "mvn.bat", "mvn") if os.name == "nt" else ("mvn",)
        for n in names:
            candidates.extend(toolchains_dir.glob(f"apache-maven*/bin/{n}"))
            candidates.extend(toolchains_dir.glob(f"maven*/bin/{n}"))

    for cand in candidates:
        if cand.is_file():
            return str(cand.resolve())
    return None


def probe_tool_version(binary_path: str | None, tool_name: str) -> str | None:
    if not binary_path:
        return None
    flag = "-version" if tool_name in ("java", "javac") else "--version"
    try:
        from qa_agent.execution import build_windows_safe_argv

        env = os.environ.copy()
        if tool_name == "mvn":
            # Asegurar JAVA_HOME si el JDK está en .agentia-runtime/toolchains
            java_bin = Path(binary_path).resolve().parents[2]
            for jdk_cand in java_bin.glob("jdk*"):
                if (jdk_cand / "bin" / ("java.exe" if os.name == "nt" else "java")).is_file():
                    env.setdefault("JAVA_HOME", str(jdk_cand.resolve()))
                    break
        argv = build_windows_safe_argv([binary_path, flag])
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            shell=False,
            env=env,
        )
        combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if not combined:
            return None
        first_line = combined.splitlines()[0].strip()
        return first_line[:120]
    except Exception:
        return None


def _parse_java_major(version_line: str | None) -> int | None:
    if not version_line:
        return None
    m = re.search(r'(?:version\s+"|javac\s+)(\d+)', version_line)
    if m:
        return int(m.group(1))
    return None


def _parse_maven_minor(version_line: str | None) -> tuple[int, int] | None:
    if not version_line:
        return None
    m = re.search(r"Apache Maven\s+(\d+)\.(\d+)", version_line)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _parse_node_major(version_line: str | None) -> int | None:
    if not version_line:
        return None
    m = re.search(r"v?(\d+)\.", version_line)
    if m:
        return int(m.group(1))
    return None


def inspect_capabilities(repo_root: Path) -> tuple[list[dict[str, Any]], bool, list[str]]:
    """Devuelve (lista de capacidades, python_suite_eligible, razones de bloqueo de python)."""
    capabilities: list[dict[str, Any]] = []
    reasons: list[str] = []

    py_ok = sys.version_info >= (3, 11)
    py_ver = platform.python_version()
    py_reason = None if py_ok else f"Se requiere Python >= 3.11; versión detectada: {py_ver}."
    if py_reason:
        reasons.append(py_reason)

    capabilities.append(
        {
            "name": "python",
            "category": "python_runtime",
            "required": True,
            "available": py_ok,
            "version": py_ver,
            "path": sys.executable,
            "reason": py_reason,
        }
    )

    required_pkgs = PRODUCT_PYTHON_PACKAGES if _is_full_agentia_repo(repo_root) else CORE_QA_PACKAGES
    simulated_missing = _simulated_missing_packages()

    for pkg in required_pkgs:
        pkg_lower = pkg.lower()
        if pkg_lower in simulated_missing:
            pkg_ok = False
            pkg_ver = None
        else:
            try:
                pkg_ver = importlib.metadata.version(pkg)
                pkg_ok = True
            except importlib.metadata.PackageNotFoundError:
                pkg_ok = False
                pkg_ver = None

        reason = (
            None
            if pkg_ok
            else (
                f"Paquete Python obligatorio ausente: '{pkg}'. "
                "Prepare el entorno virtual e instale dependencias con: "
                "python -m pip install -r requirements-qa.txt"
            )
        )
        if reason:
            reasons.append(reason)

        capabilities.append(
            {
                "name": pkg,
                "category": "python_package",
                "required": True,
                "available": pkg_ok,
                "version": pkg_ver,
                "path": None,
                "reason": reason,
            }
        )

    current_path = os.environ.get("PATH", "")
    for tool in OPTIONAL_TOOLS:
        resolved = resolve_toolchain_binary(tool, repo_root=repo_root, current_path=current_path)
        tool_ok = resolved is not None
        capabilities.append(
            {
                "name": tool,
                "category": "optional_tool",
                "required": False,
                "available": tool_ok,
                "version": None,
                "path": resolved,
                "reason": (
                    None
                    if tool_ok
                    else f"Herramienta opcional '{tool}' no encontrada en PATH (no bloquea la suite python)."
                ),
            }
        )

    python_suite_eligible = len(reasons) == 0
    return capabilities, python_suite_eligible, reasons


def evaluate_suite_eligibilities(
    repo_root: Path,
    java_cache_dir: Path | None = None,
    browser_cache_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, bool], dict[str, list[str]]]:
    """
    Evalúa la elegibilidad y razones de bloqueo de cada suite canónica:
    python, platform, java, frontend, playwright.
    """
    capabilities, py_eligible, py_reasons = inspect_capabilities(repo_root)
    simulated_missing = _simulated_missing_packages()
    current_path = os.environ.get("PATH", "")
    force_no_toolchains = os.environ.get("QA_FORCE_NO_LOCAL_TOOLCHAINS") == "1"

    eligibility: dict[str, bool] = {}
    suite_reasons: dict[str, list[str]] = {}

    # 1. python
    eligibility["python"] = py_eligible
    suite_reasons["python"] = list(py_reasons)

    # 2. platform (requiere Python + paquetes de plataforma HTTP/ASGI)
    plat_reasons = list(py_reasons)
    for pkg in PLATFORM_QA_PACKAGES:
        if pkg.lower() in simulated_missing:
            plat_reasons.append(f"Paquete requerido para suite 'platform' ausente: '{pkg}'.")
            continue
        try:
            importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            plat_reasons.append(f"Paquete requerido para suite 'platform' ausente: '{pkg}'.")
    eligibility["platform"] = len(plat_reasons) == 0
    suite_reasons["platform"] = plat_reasons

    # 3. java (requiere platform/python + JDK 21 + Maven 3.9+ + java_cache_dir preparada)
    java_reasons: list[str] = list(plat_reasons)
    if force_no_toolchains:
        java_bin = None
        javac_bin = None
        mvn_bin = None
    else:
        java_bin = resolve_toolchain_binary("java", repo_root=repo_root, current_path=current_path)
        javac_bin = resolve_toolchain_binary("javac", repo_root=repo_root, current_path=current_path)
        mvn_bin = resolve_toolchain_binary("mvn", repo_root=repo_root, current_path=current_path)

    java_ver_line = probe_tool_version(java_bin, "java") if java_bin else None
    javac_ver_line = probe_tool_version(javac_bin, "javac") if javac_bin else None
    mvn_ver_line = probe_tool_version(mvn_bin, "mvn") if mvn_bin else None

    java_major = _parse_java_major(java_ver_line)
    javac_major = _parse_java_major(javac_ver_line)
    mvn_ver = _parse_maven_minor(mvn_ver_line)

    if not java_bin or java_major is None or java_major < 21:
        java_reasons.append(
            f"JDK 21 requerido para la suite 'java' no disponible (detectado java={java_ver_line!r})."
        )
    if not javac_bin or javac_major is None or javac_major < 21:
        java_reasons.append(
            f"Compilador javac 21 requerido para la suite 'java' no disponible (detectado javac={javac_ver_line!r})."
        )
    if not mvn_bin or mvn_ver is None or mvn_ver < (3, 9):
        java_reasons.append(
            f"Maven >= 3.9 requerido para la suite 'java' no disponible (detectado mvn={mvn_ver_line!r})."
        )

    eff_java_cache = java_cache_dir or (repo_root / ".agentia-runtime" / "java-cache")
    java_cache_ready = (
        not force_no_toolchains
        and eff_java_cache.is_dir()
        and (
            (eff_java_cache / "repository" / "io" / "quarkus").is_dir()
            or (eff_java_cache / "io" / "quarkus").is_dir()
        )
    )
    if not java_cache_ready:
        java_reasons.append(
            f"Caché Maven offline de Quarkus ausente o incompleta en '{eff_java_cache}'. "
            "Ejecute primero la preparación offline (quarkus:go-offline) antes de invocar 'run --suite java'."
        )

    eligibility["java"] = len(java_reasons) == 0
    suite_reasons["java"] = java_reasons

    # 4. frontend (requiere Node >= 18 + frontend/package.json + frontend/node_modules con vitest, typescript, vite)
    fe_reasons: list[str] = []
    node_bin = None if force_no_toolchains else resolve_toolchain_binary("node", repo_root=repo_root, current_path=current_path)
    node_ver_line = probe_tool_version(node_bin, "node") if node_bin else None
    node_major = _parse_node_major(node_ver_line)
    if not node_bin or node_major is None or node_major < 18:
        fe_reasons.append(
            f"Node.js >= 18 requerido para la suite 'frontend' no disponible (detectado node={node_ver_line!r})."
        )

    fe_dir = repo_root / "frontend"
    nm_dir = fe_dir / "node_modules"
    if not (fe_dir / "package.json").is_file():
        fe_reasons.append(f"No existe 'frontend/package.json' en '{repo_root}'.")
    elif force_no_toolchains or not (
        (nm_dir / "vitest" / "vitest.mjs").is_file()
        and (nm_dir / "typescript" / "bin" / "tsc").is_file()
        and (nm_dir / "vite" / "bin" / "vite.js").is_file()
    ):
        fe_reasons.append(
            f"Dependencias y binarios CLI de frontend no instalados en '{nm_dir}' "
            "(se requieren vitest/vitest.mjs, typescript/bin/tsc y vite/bin/vite.js preparados previamente)."
        )

    eligibility["frontend"] = len(fe_reasons) == 0
    suite_reasons["frontend"] = fe_reasons

    # 5. playwright (requiere frontend + @playwright/test + navegador Chromium + java para backend verificado + Node >= 20)
    pw_reasons: list[str] = list(fe_reasons)
    if node_bin and node_major is not None and node_major < 20:
        pw_reasons.append(
            f"Playwright requiere Node.js >= 20; versión detectada: node={node_ver_line!r}."
        )
    if force_no_toolchains or not (nm_dir / "@playwright" / "test").is_dir():
        pw_reasons.append(
            f"Paquete '@playwright/test' ausente en '{nm_dir}'. Prepárelo antes de ejecutar 'playwright'."
        )

    eff_browser_cache = browser_cache_dir or Path(
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(repo_root / ".agentia-runtime" / "browser-cache"))
    )
    default_ms_pw = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" if os.name == "nt" else Path.home() / ".cache" / "ms-playwright"
    chromium_found = False
    if not force_no_toolchains:
        for b_dir in (eff_browser_cache, default_ms_pw):
            if b_dir.is_dir() and any(b_dir.glob("chromium-*")):
                chromium_found = True
                break
    if not chromium_found:
        pw_reasons.append(
            f"Navegador Chromium de Playwright no instalado en '{eff_browser_cache}'. "
            "Instale Chromium explícitamente antes de ejecutar 'run --suite playwright'."
        )

    for jr in java_reasons:
        if jr not in pw_reasons:
            pw_reasons.append(f"[Requisito backend/Java de playwright] {jr}")

    eligibility["playwright"] = len(pw_reasons) == 0
    suite_reasons["playwright"] = pw_reasons

    # 6. llm (requiere entorno Python base)
    llm_reasons: list[str] = list(py_reasons)
    eligibility["llm"] = len(llm_reasons) == 0
    suite_reasons["llm"] = llm_reasons

    return capabilities, eligibility, suite_reasons


def build_doctor_report(
    repo_root: Path,
    trace_id: str,
    duration_seconds: float = 0.0,
    java_cache_dir: Path | None = None,
    browser_cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Construye el reporte de diagnóstico doctor validado contra QADoctorReport si pydantic está presente."""
    capabilities, eligibility, suite_reasons = evaluate_suite_eligibilities(
        repo_root=repo_root,
        java_cache_dir=java_cache_dir,
        browser_cache_dir=browser_cache_dir,
    )
    py_eligible = eligibility["python"]
    py_reasons = suite_reasons["python"]
    status = "PASSED" if py_eligible else "INCOMPLETE"
    exit_code = EXIT_PASSED if py_eligible else EXIT_INCOMPLETE

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trace_id": trace_id,
        "repo_root": str(repo_root),
        "status": status,
        "exit_code": exit_code,
        "python_suite_eligible": py_eligible,
        "suite_eligibility": eligibility,
        "capabilities": capabilities,
        "selected_suites": ["python"],
        "cases": [],
        "counts": {
            "collected": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfail": 0,
        },
        "duration_seconds": round(duration_seconds, 4),
        "reasons": py_reasons,
        "evidence_files": {},
    }

    try:
        from contracts.models import QADoctorReport

        validated = QADoctorReport.model_validate(payload)
        return validated.model_dump()
    except ImportError:
        return payload
