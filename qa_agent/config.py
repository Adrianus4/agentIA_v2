"""Validación de configuración JSON/CLI, normalización de alias y resolución segura del repositorio (E02, E03, C03)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class QAConfigError(Exception):
    """Error de configuración, argumentos o repositorio inválido (código de salida 2)."""


SUITE_ALIASES: dict[str, str] = {
    "react": "frontend",
    "browser": "playwright",
}


def normalize_suite_id(suite_id: str) -> str:
    cleaned = suite_id.strip().lower()
    return SUITE_ALIASES.get(cleaned, cleaned)


FORBIDDEN_AI_KEYS = {
    "llm",
    "llm_provider",
    "ai_provider",
    "ai_analysis",
    "ai_model",
    "model",
    "api_key",
    "openai_api_key",
    "gemini_api_key",
    "deepseek_api_key",
}

FORBIDDEN_COMMAND_KEYS = {
    "command",
    "cmd",
    "shell",
    "args",
    "argv",
    "script",
}

ALLOWED_CONFIG_KEYS = {
    "schema_version",
    "suites",
    "timeout_seconds",
    "output_dir",
    "suite_timeouts",
    "java_cache_dir",
    "browser_cache_dir",
    "analysis",
    "llm_test",
    "report_enabled",
}

FORBIDDEN_AI_SECRETS = {
    "api_key",
    "openai_api_key",
    "gemini_api_key",
    "deepseek_api_key",
}


@dataclass
class ResolvedQAConfig:
    repo_root: Path
    schema_version: str = "1.0"
    suites: list[str] = field(default_factory=lambda: ["python"])
    timeout_seconds: int = 300
    output_dir: str = ".agentia-runtime/qa"
    suite_timeouts: dict[str, int] = field(default_factory=dict)
    java_cache_dir: str | None = None
    browser_cache_dir: str | None = None
    llm_mode: str = "simulated"
    llm_provider: str = "gemini"
    llm_model: str | None = None
    verify_generated_java: bool = False
    output_path: Path = field(init=False)
    java_cache_path: Path | None = field(init=False, default=None)
    browser_cache_path: Path | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.output_path = self._resolve_dir_path(self.output_dir)
        if self.java_cache_dir is not None:
            self.java_cache_path = self._resolve_dir_path(self.java_cache_dir)
        if self.browser_cache_dir is not None:
            self.browser_cache_path = self._resolve_dir_path(self.browser_cache_dir)

    def _resolve_dir_path(self, raw_dir: str) -> Path:
        p = Path(raw_dir)
        return p.resolve() if p.is_absolute() else (self.repo_root / p).resolve()

    def get_suite_timeout(self, suite_id: str) -> int:
        canonical = normalize_suite_id(suite_id)
        return int(self.suite_timeouts.get(canonical, self.timeout_seconds))


def resolve_repo_root(explicit_repo: str | None = None) -> Path:
    """Resuelve y valida la raíz del repositorio objetivo."""
    if explicit_repo is not None:
        raw = explicit_repo.strip()
        if not raw or "\x00" in raw:
            raise QAConfigError("La ruta del repositorio (--repo) no puede estar vacía.")
        candidate = Path(raw).expanduser().resolve()
    else:
        candidate = Path(__file__).resolve().parents[1]

    if not candidate.exists() or not candidate.is_dir():
        raise QAConfigError(f"El directorio del repositorio no existe: {candidate}")

    pyproject = candidate / "pyproject.toml"
    tests_dir = candidate / "tests"
    if not pyproject.is_file() or not tests_dir.is_dir():
        raise QAConfigError(
            f"El directorio '{candidate}' no es un repositorio válido del proyecto "
            "(se requieren 'pyproject.toml' y la carpeta 'tests/')."
        )
    return candidate


def _validate_safe_path(value: Any, param_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise QAConfigError(f"El parámetro '{param_name}' debe ser una cadena de ruta no vacía.")
    normalized = value.strip()
    if any(tok in normalized for tok in (";", "&&", "||", "|", "`", "$(")):
        raise QAConfigError(f"El parámetro '{param_name}' no puede contener fragmentos de comandos de shell.")
    parts = re.split(r"[\\/]+", normalized)
    if ".." in parts:
        raise QAConfigError(f"El parámetro '{param_name}' no puede contener navegación hacia atrás ('..').")
    return normalized


def _validate_suites_list(value: Any, known_suites: set[str]) -> list[str]:
    if not isinstance(value, list) or len(value) == 0:
        raise QAConfigError("La lista 'suites' debe ser un arreglo no vacío de identificadores.")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise QAConfigError("Cada elemento de 'suites' debe ser una cadena no vacía.")
        raw_id = item.strip().lower()
        if raw_id not in known_suites:
            raise QAConfigError(
                f"Suite desconocida: '{item}'. Suites registradas en catálogo: {sorted(known_suites)}."
            )
        canonical_id = normalize_suite_id(raw_id)
        if canonical_id not in cleaned:
            cleaned.append(canonical_id)
    return cleaned


def _validate_timeout(value: Any, max_seconds: int = 3600) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > max_seconds:
        raise QAConfigError(
            f"El tiempo máximo debe ser un entero positivo entre 1 y {max_seconds} segundos."
        )
    return value


def _validate_suite_timeouts(value: Any, known_suites: set[str]) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise QAConfigError("El parámetro 'suite_timeouts' debe ser un objeto JSON de suite -> segundos.")
    cleaned: dict[str, int] = {}
    for k, v in value.items():
        if not isinstance(k, str) or not k.strip():
            raise QAConfigError("Las claves de 'suite_timeouts' deben ser cadenas no vacías.")
        raw_id = k.strip().lower()
        if raw_id not in known_suites:
            raise QAConfigError(f"Suite desconocida en 'suite_timeouts': '{k}'.")
        canonical_id = normalize_suite_id(raw_id)
        cleaned[canonical_id] = _validate_timeout(v, max_seconds=7200)
    return cleaned


def load_and_merge_config(
    repo_root: Path,
    known_suites: set[str],
    config_file: str | None = None,
    cli_suites: list[str] | None = None,
    cli_timeout_seconds: int | None = None,
    cli_output_dir: str | None = None,
    cli_java_cache_dir: str | None = None,
    cli_browser_cache_dir: str | None = None,
    cli_llm_mode: str | None = None,
    cli_llm_provider: str | None = None,
    cli_llm_model: str | None = None,
    cli_verify_java: bool | None = None,
) -> ResolvedQAConfig:
    """Carga JSON opcional y aplica precedencia estricta: CLI > JSON > valores predeterminados."""
    raw_data: dict[str, Any] = {
        "schema_version": "1.0",
        "suites": ["python"],
        "timeout_seconds": 300,
        "output_dir": ".agentia-runtime/qa",
        "suite_timeouts": {},
        "java_cache_dir": None,
        "browser_cache_dir": None,
    }

    if config_file is not None:
        cfg_candidate = Path(config_file).expanduser()
        if not cfg_candidate.is_absolute() and not cfg_candidate.exists():
            cfg_candidate = repo_root / cfg_candidate
        if not cfg_candidate.is_file():
            raise QAConfigError(f"No se encontró el archivo de configuración: {config_file}")
        try:
            parsed = json.loads(cfg_candidate.read_text(encoding="utf-8"))
        except Exception as exc:
            raise QAConfigError(f"Archivo JSON de configuración inválido ({config_file}): {exc}") from exc

        if not isinstance(parsed, dict):
            raise QAConfigError("El archivo de configuración debe contener un objeto JSON en la raíz.")

        # Rechazo explícito de credenciales en JSON (D01, A01)
        for sec in FORBIDDEN_AI_SECRETS:
            if sec in parsed or any(isinstance(v, dict) and sec in v for v in parsed.values()):
                raise QAConfigError(
                    "Las credenciales de API no están permitidas en archivos de configuración JSON. "
                    "Use variables de entorno del sistema (GEMINI_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY)."
                )

        unknown_keys = set(parsed.keys()) - ALLOWED_CONFIG_KEYS
        if unknown_keys:
            ai_found = unknown_keys & FORBIDDEN_AI_KEYS
            cmd_found = unknown_keys & FORBIDDEN_COMMAND_KEYS
            if ai_found:
                raise QAConfigError(
                    f"Las opciones de IA no estructuradas ({sorted(ai_found)}) no están permitidas en la raíz. "
                    "Use los bloques 'analysis' o 'llm_test'."
                )
            if cmd_found:
                raise QAConfigError(
                    f"No se permiten comandos arbitrarios en la configuración ({sorted(cmd_found)})."
                )
            raise QAConfigError(f"Claves desconocidas en configuración JSON: {sorted(unknown_keys)}.")

        for k, v in parsed.items():
            raw_data[k] = v

    # Precedencia: CLI > JSON > defaults
    if cli_suites is not None and len(cli_suites) > 0:
        flattened: list[str] = []
        for s in cli_suites:
            for part in s.split(","):
                if part.strip():
                    flattened.append(part.strip())
        raw_data["suites"] = flattened

    if cli_timeout_seconds is not None:
        raw_data["timeout_seconds"] = cli_timeout_seconds

    if cli_output_dir is not None:
        raw_data["output_dir"] = cli_output_dir

    if cli_java_cache_dir is not None:
        raw_data["java_cache_dir"] = cli_java_cache_dir

    if cli_browser_cache_dir is not None:
        raw_data["browser_cache_dir"] = cli_browser_cache_dir

    if raw_data.get("schema_version") != "1.0":
        raise QAConfigError(
            f"Versión de esquema no soportada: {raw_data.get('schema_version')!r}. Se requiere '1.0'."
        )

    validated_suites = _validate_suites_list(raw_data.get("suites"), known_suites)
    validated_timeout = _validate_timeout(raw_data.get("timeout_seconds"), max_seconds=3600)
    validated_output_dir = _validate_safe_path(raw_data.get("output_dir"), "output_dir")
    validated_suite_timeouts = _validate_suite_timeouts(raw_data.get("suite_timeouts"), known_suites)

    # Si se pasó --timeout-seconds explícito en CLI, sobrescribe también cualquier suite_timeout individual
    if cli_timeout_seconds is not None:
        for s_key in list(validated_suite_timeouts.keys()):
            validated_suite_timeouts[s_key] = validated_timeout

    raw_java_cache = raw_data.get("java_cache_dir")
    validated_java_cache = (
        _validate_safe_path(raw_java_cache, "java_cache_dir") if raw_java_cache is not None else None
    )
    raw_browser_cache = raw_data.get("browser_cache_dir")
    validated_browser_cache = (
        _validate_safe_path(raw_browser_cache, "browser_cache_dir") if raw_browser_cache is not None else None
    )

    try:
        from contracts.models import QAConfigModel

        QAConfigModel(
            schema_version="1.0",
            suites=validated_suites,
            timeout_seconds=validated_timeout,
            output_dir=validated_output_dir,
            suite_timeouts=validated_suite_timeouts,
            java_cache_dir=validated_java_cache,
            browser_cache_dir=validated_browser_cache,
        )
    except ImportError:
        pass
    except Exception as exc:
        raise QAConfigError(f"Configuración rechazada por el contrato QAConfigModel: {exc}") from exc

    llm_test_cfg = raw_data.get("llm_test") if isinstance(raw_data.get("llm_test"), dict) else {}
    eff_llm_mode = cli_llm_mode or llm_test_cfg.get("mode", "simulated")
    eff_llm_provider = cli_llm_provider or llm_test_cfg.get("provider", "gemini")
    eff_llm_model = cli_llm_model or llm_test_cfg.get("model")
    eff_verify_java = (
        cli_verify_java if cli_verify_java is not None else llm_test_cfg.get("verify_generated_java", False)
    )

    return ResolvedQAConfig(
        repo_root=repo_root,
        schema_version="1.0",
        suites=validated_suites,
        timeout_seconds=validated_timeout,
        output_dir=validated_output_dir,
        suite_timeouts=validated_suite_timeouts,
        java_cache_dir=validated_java_cache,
        browser_cache_dir=validated_browser_cache,
        llm_mode=eff_llm_mode,
        llm_provider=eff_llm_provider,
        llm_model=eff_llm_model,
        verify_generated_java=eff_verify_java,
    )
