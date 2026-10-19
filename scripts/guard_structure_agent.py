#!/usr/bin/env python3
"""
Code Structure & Constitutional Guard Agent (guard_structure_agent.py).

Audits the AgentIA v2 repository across 6 structural gates:
1. Python AST syntax & Ruff hygiene (no E741 ambiguous names, no E402 late module imports).
2. Constitutional Principle V / Rule 8: Zero hardcoded framework literals in generator modules.
3. Profiles & Jinja2 templates integrity.
4. Docker, JDK/Maven toolchain, Entrypoint & Volume permissions for UID 10001.
5. Frontend TypeScript & Zero-Secret localStorage hygiene (LlmContext + StudioContext).
6. Shell Launcher Scripts (.sh) syntax & 2-PC Qwen Backend/Frontend readiness.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import yaml


def check_python_syntax_and_lint(repo_root: Path) -> list[str]:
    errors: list[str] = []
    py_dirs = ["app", "agents", "services", "contracts", "tests", "scripts"]
    py_files: list[Path] = []
    for d in py_dirs:
        p = repo_root / d
        if p.is_dir():
            py_files.extend(sorted(p.rglob("*.py")))
    if (repo_root / "main.py").is_file():
        py_files.append(repo_root / "main.py")

    for pf in py_files:
        rel = pf.relative_to(repo_root)
        source = pf.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(rel))
        except SyntaxError as exc:
            errors.append(f"SyntaxError in {rel}:{exc.lineno}: {exc.msg}")
            continue

        # Check E741 ambiguous variable names (l, O, I)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in {"l", "O", "I"}:
                errors.append(f"E741 ambiguous variable name '{node.id}' in {rel}:{node.lineno}")

        # Check E402 module-level imports after non-import statements
        non_import_seen = False
        for stmt in tree.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                if non_import_seen:
                    errors.append(f"E402 module level import not at top of file in {rel}:{stmt.lineno}")
            else:
                non_import_seen = True

    return errors


def check_constitution_zero_hardcoded_literals(repo_root: Path) -> list[str]:
    errors: list[str] = []
    checks = {
        "agents/generator/entity.py": [
            "@Entity", "@Table", "@Id", "@GeneratedValue",
            "jakarta.persistence", "javax.persistence", "org.springframework",
        ],
        "agents/generator/resource.py": [
            "@Path", "@GET", "@POST", "@PUT", "@DELETE", "@Transactional",
            "jakarta.ws.rs", "javax.ws.rs", "PanacheRepository",
        ],
        "agents/generator/test_writer.py": [
            "@QuarkusTest", "@SpringBootTest", "@InjectMock", "@MockBean",
            "io.quarkus.test", "org.springframework.boot.test",
        ],
    }
    for rel_path, forbidden in checks.items():
        fpath = repo_root / rel_path
        if not fpath.is_file():
            errors.append(f"Missing generator module: {rel_path}")
            continue
        text = fpath.read_text(encoding="utf-8")
        for lit in forbidden:
            if lit in text:
                errors.append(f"Constitution violation in {rel_path}: hardcoded literal '{lit}'")
    return errors


def check_profiles_and_templates(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for profile_name in ("quarkus-3.15.yaml", "quarkus-3.yaml"):
        p = repo_root / "profiles" / profile_name
        if not p.is_file():
            errors.append(f"Missing profile: {profile_name}")
            continue
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        scaffold = data.get("scaffold", {})
        ext_map = scaffold.get("extension_map", {})
        allowed = set(scaffold.get("allowed_extensions", []))
        for req_key in ("rest", "persistence", "postgresql", "mysql", "h2", "validation", "kafka", "health", "metrics", "otel", "security_jwt", "security_oidc"):
            if req_key not in ext_map:
                errors.append(f"{profile_name} missing extension_map key '{req_key}'")
            else:
                for coord in ext_map[req_key]:
                    if coord not in allowed:
                        errors.append(f"{profile_name} extension '{coord}' not in allowed_extensions")
        for tmpl_key, tmpl_rel in data.get("templates", {}).items():
            if not (repo_root / tmpl_rel).is_file():
                errors.append(f"{profile_name} template '{tmpl_key}' -> '{tmpl_rel}' does not exist")
    return errors


def check_docker_and_entrypoint(repo_root: Path) -> list[str]:
    errors: list[str] = []
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    for required in (
        "COPY requirements.txt",
        "COPY app",
        "COPY services",
        "COPY contracts",
        "COPY agents",
        "COPY profiles",
        "COPY templates",
        "/data/workflow-state",
    ):
        if required not in dockerfile:
            errors.append(f"Dockerfile missing '{required}'")

    verifier_dockerfile = (repo_root / "Dockerfile.verifier").read_text(encoding="utf-8")
    for required in (
        "COPY --from=jdk_maven /opt/java/openjdk",
        "COPY --from=jdk_maven /usr/share/maven",
        "services.verifier_service:app",
    ):
        if required not in verifier_dockerfile:
            errors.append(f"Dockerfile.verifier missing '{required}'")

    start_sh = (repo_root / "scripts" / "start.sh").read_text(encoding="utf-8")
    if 'exec "$@"' not in start_sh:
        errors.append('scripts/start.sh does not forward container command arguments via exec "$@"')
    if "SERVICE_MODULE" not in start_sh:
        errors.append("scripts/start.sh does not select the service through SERVICE_MODULE")

    dc = yaml.safe_load((repo_root / "docker-compose.yml").read_text(encoding="utf-8"))
    services = dc.get("services", {})
    for svc_name in ("orchestrator", "verifier", "repair", "validator", "generator", "web"):
        if svc_name not in services:
            errors.append(f"docker-compose.yml missing service '{svc_name}'")
            continue
        if "healthcheck" not in services[svc_name]:
            errors.append(f"docker-compose.yml service '{svc_name}' has no healthcheck")
    # Decoupled topology: agents must not share a workspace/state volume with the orchestrator
    shared = {
        str(v).split(":", 1)[0]
        for name, svc in services.items()
        if name != "orchestrator"
        for v in svc.get("volumes", [])
    } & {str(v).split(":", 1)[0] for v in services.get("orchestrator", {}).get("volumes", [])}
    if shared:
        errors.append(f"docker-compose.yml shares volumes between orchestrator and agents: {sorted(shared)}")
    if not (repo_root / "openship.json").is_file():
        errors.append("openship.json is missing")
    return errors


def check_frontend_structure(repo_root: Path) -> list[str]:
    errors: list[str] = []
    bg_ts = (repo_root / "frontend/src/types/blueprintGraph.ts").read_text(encoding="utf-8")
    if "apiKey?: string;" not in bg_ts:
        errors.append("frontend/src/types/blueprintGraph.ts LlmConfig missing 'apiKey?: string;'")

    spec_view = (repo_root / "frontend/src/views/SpecIngestionView.tsx").read_text(encoding="utf-8")
    if "Partial<LlmSettings>" not in spec_view or "normalizedProvider" not in spec_view:
        errors.append("frontend/src/views/SpecIngestionView.tsx not aligned with LlmSettings / normalizedProvider")

    llm_ctx = (repo_root / "frontend/src/context/LlmContext.tsx").read_text(encoding="utf-8")
    if "JSON.stringify({ provider, apiKey," in llm_ctx:
        errors.append("frontend/src/context/LlmContext.tsx still persists plaintext apiKey in localStorage")
    if "throw new Error('useLlm must be used within an LlmProvider')" in llm_ctx:
        errors.append("frontend/src/context/LlmContext.tsx useLlm() lacks fallback context for isolated component tests")

    studio_ctx = (repo_root / "frontend/src/context/StudioContext.tsx").read_text(encoding="utf-8")
    if "stripSecretsFromValue" not in studio_ctx:
        errors.append("frontend/src/context/StudioContext.tsx missing stripSecretsFromValue sanitizer for agentia_v2_sessions")
    if "apiKey: llmApiKey || undefined" in studio_ctx:
        errors.append("frontend/src/context/StudioContext.tsx still embeds apiKey inside resolvedLlm / session.blueprint")
    return errors


def check_shell_launchers(repo_root: Path) -> list[str]:
    errors: list[str] = []
    sh_files = [
        repo_root / "start.sh",
        repo_root / "start_frontend.sh",
        repo_root / "start_gpu_backend.sh",
        *sorted((repo_root / "scripts").glob("*.sh")),
    ]
    for sh in sh_files:
        if not sh.is_file():
            errors.append(f"Missing shell script: {sh.relative_to(repo_root)}")
            continue
        res = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
        if res.returncode != 0:
            errors.append(f"bash -n failed for {sh.relative_to(repo_root)}: {res.stderr.strip()}")

    gpu_sh = (repo_root / "scripts/start_backend_gpu.sh").read_text(encoding="utf-8")
    for req_svc in (
        "services.validator_service",
        "services.generator_service",
        "services.verifier_service",
        "services.repair_service",
        "AGENT_GATEWAY_API_KEY",
    ):
        if req_svc not in gpu_sh:
            errors.append(f"scripts/start_backend_gpu.sh missing '{req_svc}' for 2-PC backend startup")

    vulkan_sh = (repo_root / "scripts/start_vulkan_llm.sh").read_text(encoding="utf-8")
    if 'LLAMA_SERVER="${LLAMA_SERVER:-' not in vulkan_sh:
        errors.append("scripts/start_vulkan_llm.sh does not initialize LLAMA_SERVER before set -u check")

    return errors


def main() -> None:
    repo_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    gates: list[tuple[str, list[str]]] = [
        ("Gate 1: Python AST Syntax & Ruff Lint Hygiene", check_python_syntax_and_lint(repo_root)),
        ("Gate 2: Constitution Zero Hardcoded Literals", check_constitution_zero_hardcoded_literals(repo_root)),
        ("Gate 3: Profiles & Jinja2 Templates Integrity", check_profiles_and_templates(repo_root)),
        ("Gate 4: Container Images, Compose Topology & Openship", check_docker_and_entrypoint(repo_root)),
        ("Gate 5: Frontend TypeScript & Zero-Secret Storage Hygiene", check_frontend_structure(repo_root)),
        ("Gate 6: Shell Launchers (.sh) & 2-PC Qwen Backend/Frontend Topology", check_shell_launchers(repo_root)),
    ]

    total_errors = 0
    print("=== STRUCTURE GUARD AGENT REPORT ===")
    for gate_name, errs in gates:
        if not errs:
            print(f"[PASS] {gate_name}")
        else:
            print(f"[FAIL] {gate_name} ({len(errs)} issues)")
            for e in errs:
                print(f"       - {e}")
            total_errors += len(errs)

    if total_errors > 0:
        sys.exit(1)
    print("=== ALL 6 STRUCTURE GUARD GATES PASSED (0 VIOLATIONS) ===")


if __name__ == "__main__":
    main()
