"""Catálogo de suites de QA y evaluación de elegibilidad por suite (E04, C03)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qa_agent import SCHEMA_VERSION
from qa_agent.capabilities import evaluate_suite_eligibilities

PRIMARY_SUITES: tuple[str, ...] = (
    "python",
    "platform",
    "java",
    "frontend",
    "playwright",
    "llm",
)

KNOWN_SUITES: dict[str, dict[str, Any]] = {
    "llm": {
        "suite_id": "llm",
        "description": "Suite de reparación LLM sobre el producto (simulated por defecto, real optativo con credenciales).",
        "implemented": True,
        "engine": "llm+repair",
        "aliases": [],
        "target_paths": ["qa_scenarios/llm", "qa_scenarios/fixtures"],
        "required_capabilities": ["python"],
        "optional_capabilities": ["java", "mvn", "java_cache_dir"],
    },
    "python": {
        "suite_id": "python",
        "description": "Suite de pruebas Python en proceso (tests/) ejecutada mediante pytest en copia aislada.",
        "implemented": True,
        "engine": "pytest",
        "aliases": [],
        "target_paths": ["tests"],
        "required_capabilities": ["python", "pytest", "pytest-asyncio", "respx", "pydantic", "fastapi"],
        "optional_capabilities": [],
    },
    "platform": {
        "suite_id": "platform",
        "description": "Suite HTTP real sobre los 5 procesos FastAPI en sockets loopback (qa_scenarios/platform/).",
        "implemented": True,
        "engine": "pytest+httpx",
        "aliases": [],
        "target_paths": ["qa_scenarios/platform"],
        "required_capabilities": ["python", "pytest", "httpx", "fastapi", "uvicorn", "aiosqlite"],
        "optional_capabilities": [],
    },
    "java": {
        "suite_id": "java",
        "description": "Generación, compilación Maven offline y verificación real JUnit/Quarkus con H2 y oráculos independientes.",
        "implemented": True,
        "engine": "maven+surefire",
        "aliases": [],
        "target_paths": ["qa_scenarios/java", "qa_scenarios/fixtures"],
        "required_capabilities": ["python", "java", "javac", "mvn", "java_cache_dir"],
        "optional_capabilities": ["docker"],
    },
    "frontend": {
        "suite_id": "frontend",
        "description": "Suite de componentes React/TypeScript con Vitest 3, chequeo TypeScript y build Vite (frontend/).",
        "implemented": True,
        "engine": "vitest+tsc+vite",
        "aliases": ["react"],
        "target_paths": ["frontend/src/test"],
        "required_capabilities": ["node", "frontend_node_modules"],
        "optional_capabilities": [],
    },
    "react": {
        "suite_id": "react",
        "canonical_id": "frontend",
        "description": "Alias de la suite 'frontend' (componentes React/Vitest y build).",
        "implemented": True,
        "engine": "vitest+tsc+vite",
        "aliases": [],
        "target_paths": ["frontend/src/test"],
        "required_capabilities": ["node", "frontend_node_modules"],
        "optional_capabilities": [],
    },
    "playwright": {
        "suite_id": "playwright",
        "description": "Pruebas E2E en navegador Chromium real sobre Web Studio, backend y servicio Quarkus verificado.",
        "implemented": True,
        "engine": "playwright",
        "aliases": ["browser"],
        "target_paths": ["frontend/e2e"],
        "required_capabilities": ["node", "frontend_node_modules", "chromium_browser", "java", "mvn", "java_cache_dir"],
        "optional_capabilities": [],
    },
    "browser": {
        "suite_id": "browser",
        "canonical_id": "playwright",
        "description": "Alias de la suite 'playwright' (E2E en navegador Chromium real).",
        "implemented": True,
        "engine": "playwright",
        "aliases": [],
        "target_paths": ["frontend/e2e"],
        "required_capabilities": ["node", "frontend_node_modules", "chromium_browser", "java", "mvn", "java_cache_dir"],
        "optional_capabilities": [],
    },
}


def get_known_suite_ids() -> set[str]:
    return set(KNOWN_SUITES.keys())


def build_catalog_entries(
    repo_root: Path,
    java_cache_dir: Path | None = None,
    browser_cache_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Construye las entradas del catálogo evaluando la elegibilidad actual de cada suite canónica."""
    capabilities, eligibility, suite_reasons = evaluate_suite_eligibilities(
        repo_root=repo_root,
        java_cache_dir=java_cache_dir,
        browser_cache_dir=browser_cache_dir,
    )
    entries: list[dict[str, Any]] = []

    for s_id in PRIMARY_SUITES:
        meta = KNOWN_SUITES[s_id]
        is_exec = eligibility.get(s_id, False)
        s_reasons = suite_reasons.get(s_id, [])
        if meta["implemented"]:
            status = "EXECUTABLE" if is_exec else "BLOCKED"
            reason = None if is_exec else "; ".join(s_reasons)
        else:
            status = "NOT_IMPLEMENTED"
            reason = meta.get("reason")

        entries.append(
            {
                "suite_id": meta["suite_id"],
                "description": meta["description"],
                "implemented": meta["implemented"],
                "status": status,
                "engine": meta.get("engine"),
                "aliases": list(meta.get("aliases", [])),
                "target_paths": list(meta["target_paths"]),
                "required_capabilities": list(meta["required_capabilities"]),
                "optional_capabilities": list(meta["optional_capabilities"]),
                "reason": reason,
            }
        )
    return entries, capabilities, suite_reasons.get("python", [])


def build_list_report(
    repo_root: Path,
    trace_id: str,
    duration_seconds: float = 0.0,
    java_cache_dir: Path | None = None,
    browser_cache_dir: Path | None = None,
) -> dict[str, Any]:
    entries, capabilities, reasons = build_catalog_entries(
        repo_root=repo_root,
        java_cache_dir=java_cache_dir,
        browser_cache_dir=browser_cache_dir,
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trace_id": trace_id,
        "repo_root": str(repo_root),
        "status": "PASSED",
        "exit_code": 0,
        "capabilities": capabilities,
        "selected_suites": [e["suite_id"] for e in entries if e["status"] == "EXECUTABLE"],
        "suites": entries,
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
        "reasons": reasons,
        "evidence_files": {},
    }
    try:
        from contracts.models import QAListReport

        return QAListReport.model_validate(payload).model_dump()
    except ImportError:
        return payload
