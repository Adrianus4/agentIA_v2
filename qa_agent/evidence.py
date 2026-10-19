"""Redacción previa de secretos, acotamiento de logs y persistencia de evidencia mínima (E07)."""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

MAX_LOG_CHARS = 32000
MAX_CASE_MESSAGE_CHARS = 600

_SENSITIVE_ENV_NAME_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|credential|private[_-]?key)"
)
_PEM_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"
)
_GOOGLE_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z\-_]{12,}\b")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9\-_]{10,}\b")
_BEARER_RE = re.compile(r"(?i)\b((?:Authorization\s*:\s*)?Bearer\s+)[^\s\"',;)]+")
_KV_SECRET_RE = re.compile(
    r"(?i)\b([a-z0-9_]*(?:api[_-]?key|secret|token|password|passwd|credential)[a-z0-9_]*\s*[:=]\s*)([\"']?)[^\s\"',;)]+\2"
)


def collect_sensitive_env_values(env: dict[str, str] | None = None) -> list[str]:
    """Obtiene valores actuales de variables sensibles del entorno para redactarlos por coincidencia exacta."""
    source = env if env is not None else dict(os.environ)
    secrets: set[str] = set()
    for key, val in source.items():
        if _SENSITIVE_ENV_NAME_RE.search(key):
            cleaned = (val or "").strip()
            if len(cleaned) >= 4:
                secrets.add(cleaned)
    return sorted(secrets, key=len, reverse=True)


def redact_text(text: str, extra_secrets: list[str] | None = None) -> str:
    """Redacta secretos conocidos del entorno y patrones de credenciales antes de imprimir o persistir."""
    if not text:
        return ""
    redacted = text
    known_values = collect_sensitive_env_values()
    if extra_secrets:
        for item in extra_secrets:
            if item and len(item.strip()) >= 4:
                known_values.append(item.strip())
    known_values = sorted(set(known_values), key=len, reverse=True)

    for secret_val in known_values:
        if secret_val in redacted:
            redacted = redacted.replace(secret_val, "[REDACTED]")

    redacted = _PEM_KEY_RE.sub("[REDACTED]", redacted)
    redacted = _GOOGLE_KEY_RE.sub("[REDACTED]", redacted)
    redacted = _OPENAI_KEY_RE.sub("[REDACTED]", redacted)
    redacted = _BEARER_RE.sub(r"\1[REDACTED]", redacted)
    redacted = _KV_SECRET_RE.sub(r"\1\2[REDACTED]\2", redacted)
    return redacted


def redact_structure(data: Any, extra_secrets: list[str] | None = None) -> Any:
    """Aplica redacción recursiva sobre diccionarios y listas."""
    if isinstance(data, str):
        return redact_text(data, extra_secrets=extra_secrets)
    if isinstance(data, list):
        return [redact_structure(item, extra_secrets=extra_secrets) for item in data]
    if isinstance(data, dict):
        return {k: redact_structure(v, extra_secrets=extra_secrets) for k, v in data.items()}
    return data


def summarize_diagnostic_text(raw_text: str, extra_secrets: list[str] | None = None) -> str:
    """Extrae un diagnóstico útil y redactado sin volcar código fuente ni diffs completos."""
    redacted = redact_text(raw_text, extra_secrets=extra_secrets)
    lines: list[str] = []
    for line in redacted.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Excluir líneas de volcado de código fuente o diffs, conservando líneas E de pytest y resúmenes
        if stripped.startswith(("E ", "E\t", "FAILED ", "ERROR ", "AssertionError", "SyntaxError", "ImportError", "ModuleNotFoundError")) or not line.startswith(("    ", "\t", "> ")):
            lines.append(stripped)
    summary = "\n".join(lines) if lines else redacted.strip()
    if len(summary) > MAX_CASE_MESSAGE_CHARS:
        summary = summary[:MAX_CASE_MESSAGE_CHARS] + "... [TRUNCATED]"
    return summary


def sanitize_junit_tree(root: ET.Element, extra_secrets: list[str] | None = None) -> str:
    """Sanea el árbol JUnit XML redactando secretos y acotando volcados de código en nodos failure/error."""
    for elem in root.iter():
        for attr_key, attr_val in list(elem.attrib.items()):
            elem.attrib[attr_key] = redact_text(attr_val, extra_secrets=extra_secrets)
        if elem.tag in ("failure", "error", "skipped"):
            if "message" in elem.attrib:
                elem.attrib["message"] = summarize_diagnostic_text(
                    elem.attrib["message"], extra_secrets=extra_secrets
                )
            if elem.text:
                elem.text = summarize_diagnostic_text(elem.text, extra_secrets=extra_secrets)
        elif elem.tag in ("system-out", "system-err"):
            if elem.text:
                elem.text = summarize_diagnostic_text(elem.text, extra_secrets=extra_secrets)
        else:
            if elem.text:
                elem.text = redact_text(elem.text, extra_secrets=extra_secrets)
        if elem.tail:
            elem.tail = redact_text(elem.tail, extra_secrets=extra_secrets)

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return redact_text(xml_bytes.decode("utf-8", errors="replace"), extra_secrets=extra_secrets)


def build_bounded_log(
    raw_stdout: str,
    raw_stderr: str,
    extra_secrets: list[str] | None = None,
    max_chars: int = MAX_LOG_CHARS,
) -> tuple[str, bool]:
    """Construye un log de diagnóstico acotado, sin código fuente crudo ni secretos."""
    combined = (raw_stdout or "") + ("\n" + raw_stderr if raw_stderr else "")
    redacted = redact_text(combined, extra_secrets=extra_secrets)
    filtered_lines: list[str] = []
    for line in redacted.splitlines():
        # Evitar volcar líneas de código indentadas (>   o 4 espacios de código) pero conservar E   de pytest
        if line.startswith("> ") or (line.startswith("    ") and not line.lstrip().startswith("E ")):
            continue
        filtered_lines.append(line)

    bounded = "\n".join(filtered_lines).strip()
    truncated = False
    if len(bounded) > max_chars:
        bounded = bounded[:max_chars] + "\n...[SALIDA TRUNCADA POR LÍMITE DE VOLUMEN]..."
        truncated = True
    return bounded, truncated


def to_extended_path(p: Path) -> Path:
    """Convierte rutas de Windows a sintaxis extendida \\\\?\\ para superar el límite MAX_PATH (260 caracteres)."""
    if os.name == "nt":
        resolved = str(p.resolve())
        if not resolved.startswith("\\\\?\\") and not resolved.startswith("//?/"):
            return Path(f"\\\\?\\{resolved}")
    return p


def safe_write_text(p: Path, content: str, encoding: str = "utf-8") -> None:
    """Escribe texto asegurando que los directorios padres existan y soportando rutas largas en Windows."""
    ext = to_extended_path(p)
    ext.parent.mkdir(parents=True, exist_ok=True)
    ext.write_text(content, encoding=encoding)


def safe_write_bytes(p: Path, data: bytes) -> None:
    """Escribe bytes asegurando que los directorios padres existan y soportando rutas largas en Windows."""
    ext = to_extended_path(p)
    ext.parent.mkdir(parents=True, exist_ok=True)
    ext.write_bytes(data)


def persist_run_evidence(
    evidence_dir: Path,
    run_result: dict[str, Any],
    sanitized_xml: str | None = None,
    bounded_log: str = "",
    extra_secrets: list[str] | None = None,
    suite_artifacts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """
    Persiste result.json global, mantiene python.junit.xml y python.log históricos en raíz,
    y escribe directorios de evidencia separados por suite (<evidence_dir>/<suite_id>/).
    Soporta rutas largas en Windows y resiste fallos individuales de artefactos sin perder result.json.
    """
    to_extended_path(evidence_dir).mkdir(parents=True, exist_ok=True)
    files_map: dict[str, str] = {}

    log_path = evidence_dir / "python.log"
    redacted_global_log = redact_text(bounded_log, extra_secrets=extra_secrets)
    safe_write_text(log_path, redacted_global_log + "\n", encoding="utf-8")
    files_map["python.log"] = str(log_path)

    redacted_py_xml: str | None = None
    if sanitized_xml is not None:
        redacted_py_xml = redact_text(sanitized_xml, extra_secrets=extra_secrets)
        xml_path = evidence_dir / "python.junit.xml"
        safe_write_text(xml_path, redacted_py_xml, encoding="utf-8")
        files_map["python.junit.xml"] = str(xml_path)

    for s in run_result.get("suites", []):
        s_id = str(s.get("suite_id", "unknown"))
        s_dir = evidence_dir / s_id
        to_extended_path(s_dir).mkdir(parents=True, exist_ok=True)
        s["evidence_dir"] = str(s_dir)
        s_files: dict[str, str] = dict(s.get("evidence_files") or {})

        if s_id == "python":
            py_sub_log = s_dir / "python.log"
            safe_write_text(py_sub_log, redacted_global_log + "\n", encoding="utf-8")
            s_files["python.log"] = str(log_path)
            s_files["python/python.log"] = str(py_sub_log)
            if redacted_py_xml is not None:
                py_sub_xml = s_dir / "junit.xml"
                safe_write_text(py_sub_xml, redacted_py_xml, encoding="utf-8")
                s_files["python.junit.xml"] = str(evidence_dir / "python.junit.xml")
                s_files["python/junit.xml"] = str(py_sub_xml)
                files_map["python/junit.xml"] = str(py_sub_xml)

        if suite_artifacts and s_id in suite_artifacts:
            for rel_name, content_val in suite_artifacts[s_id].items():
                target_file = s_dir / rel_name
                try:
                    if isinstance(content_val, bytes):
                        safe_write_bytes(target_file, content_val)
                    else:
                        safe_write_text(
                            target_file,
                            redact_text(str(content_val), extra_secrets=extra_secrets),
                            encoding="utf-8",
                        )
                    key_name = f"{s_id}/{rel_name}"
                    s_files[rel_name] = str(target_file)
                    files_map[key_name] = str(target_file)
                except Exception as write_exc:
                    err_msg = f"<write-error: {write_exc}>"
                    s_files[rel_name] = err_msg
                    files_map[f"{s_id}/{rel_name}"] = err_msg
                    s.setdefault("reasons", []).append(
                        f"Advertencia al escribir artefacto '{rel_name}': {write_exc}"
                    )

        suite_json_path = s_dir / "suite_result.json"
        s_files["suite_result.json"] = str(suite_json_path)
        files_map[f"{s_id}/suite_result.json"] = str(suite_json_path)
        s["evidence_files"] = s_files

        redacted_s = redact_structure(s, extra_secrets=extra_secrets)
        safe_write_text(
            suite_json_path,
            json.dumps(redacted_s, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    result_path = evidence_dir / "result.json"
    files_map["result.json"] = str(result_path)

    run_result["evidence_dir"] = str(evidence_dir)
    run_result["evidence_files"] = files_map

    redacted_result = redact_structure(run_result, extra_secrets=extra_secrets)
    try:
        from contracts.models import QARunResult

        validated = QARunResult.model_validate(redacted_result)
        redacted_result = validated.model_dump()
    except Exception:
        pass

    safe_write_text(
        result_path,
        json.dumps(redacted_result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return files_map


def format_terminal_summary(run_result: dict[str, Any], extra_secrets: list[str] | None = None) -> str:
    """Genera el resumen legible en español para la terminal, completamente redactado."""
    counts = run_result.get("counts", {})
    lines = [
        f"=== Resumen de Ejecución QA ({run_result.get('trace_id')}) ===",
        f"Estado final    : {run_result.get('status')} (código {run_result.get('exit_code')})",
        f"Suites elegidas : {', '.join(run_result.get('selected_suites', []))}",
        f"Alcance         : {run_result.get('scope_note')}",
        (
            f"Casos totales   : recolectados={counts.get('collected', 0)}, "
            f"aprobados={counts.get('passed', 0)}, fallidos={counts.get('failed', 0)}, "
            f"errores={counts.get('errors', 0)}, omitidos={counts.get('skipped', 0)}, "
            f"xfail={counts.get('xfail', 0)}"
        ),
        f"Duración total  : {run_result.get('duration_seconds', 0.0):.3f} s",
        f"Evidencia en    : {run_result.get('evidence_dir')}",
    ]
    for s in run_result.get("suites", []):
        s_counts = s.get("counts", {})
        lines.append(
            f"  * [{s.get('suite_id')}] motor={s.get('engine', 'pytest')} estado={s.get('status')} "
            f"(aprobados={s_counts.get('passed', 0)}/{s_counts.get('collected', 0)}, "
            f"fallidos={s_counts.get('failed', 0)}, errores={s_counts.get('errors', 0)})"
        )
    reasons = run_result.get("reasons", [])
    if reasons:
        lines.append("Motivos / Diagnóstico:")
        for r in reasons:
            lines.append(f"  - {r}")
    return redact_text("\n".join(lines), extra_secrets=extra_secrets)
