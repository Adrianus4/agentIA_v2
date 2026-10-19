"""Identidad, hashes, persistencia atómica y validación de integridad de artefactos (D02, AC-03, AC-06, AC-07, AC-08)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.models import (
    QAArtifact,
    QADeliveryResult,
    QAReportManifest,
    _validate_safe_relative_path_str,
)

CHUNK_SIZE = 64 * 1024


def compute_file_sha256(path: Path) -> str:
    """Calcula el hash SHA-256 en bloques de 64KB de forma determinista para archivos de texto o binarios."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_write_bytes(target_path: Path, data: bytes) -> None:
    """Escribe bytes de forma atómica usando un archivo temporal y reemplazo directo (os.replace)."""
    target_path = Path(target_path).resolve()
    parent_dir = target_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = parent_dir / f".tmp.{os.getpid()}.{uuid.uuid4().hex}"
    try:
        with open(tmp_path, "wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, target_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def atomic_write_text(target_path: Path, text: str, encoding: str = "utf-8") -> None:
    """Escribe texto codificado de forma atómica."""
    atomic_write_bytes(target_path, text.encode(encoding))


def infer_artifact_type(relative_path: str) -> str:
    """Infiere el tipo de artefacto a partir de su ruta y extensión."""
    lowered = relative_path.lower()
    if lowered == "result.json":
        return "result"
    if lowered.endswith(".html"):
        return "html"
    if lowered.endswith(".json"):
        return "json"
    if lowered.endswith(".xml"):
        return "junit"
    if lowered.endswith(".log") or lowered.endswith(".txt"):
        return "log"
    if lowered.endswith(".png"):
        return "png"
    if lowered.endswith(".zip"):
        return "zip"
    if lowered.endswith(".md"):
        return "markdown"
    return "other"


def copy_artifact_binary(
    source_path: Path,
    target_dir: Path,
    relative_name: str,
    artifact_id: str | None = None,
    provenance: str | dict[str, Any] | None = None,
) -> QAArtifact:
    """Copia un artefacto binario o de texto al directorio destino con validación de ruta y cálculo de hash."""
    source_path = Path(source_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Archivo origen no encontrado: {source_path}")

    # Valida que relative_name sea ruta relativa segura sin traversal
    safe_rel = _validate_safe_relative_path_str(relative_name, "relative_name")
    target_dir = Path(target_dir).resolve()
    destination = target_dir / safe_rel

    data = source_path.read_bytes()
    atomic_write_bytes(destination, data)

    sha256 = hashlib.sha256(data).hexdigest()
    size = len(data)
    art_type = infer_artifact_type(safe_rel)
    art_id = artifact_id or safe_rel.replace("/", "_").replace(".", "_")

    return QAArtifact(
        id=art_id,
        path=safe_rel,
        type=art_type,
        size_bytes=size,
        sha256=sha256,
        provenance=provenance,
    )


def generate_report_manifest(
    run_dir: Path,
    trace_id: str,
    warnings: list[str] | None = None,
    write_to_disk: bool = True,
) -> QAReportManifest:
    """Escanea el directorio del run y genera un QAReportManifest detallado con hashes SHA-256."""
    run_dir = Path(run_dir).resolve()
    result_json_path = run_dir / "result.json"
    if not result_json_path.is_file():
        raise FileNotFoundError(f"result.json no existe en el directorio del run: {run_dir}")

    result_sha = compute_file_sha256(result_json_path)

    artifacts: list[QAArtifact] = []

    # Recorrer todos los archivos de run_dir excluyendo temporales, el propio manifest y delivery.json
    for root, _, files in os.walk(run_dir):
        for f in files:
            if f.startswith(".tmp.") or f == "report_manifest.json" or f == "delivery.json":
                continue
            abs_p = Path(root) / f
            rel_p = abs_p.relative_to(run_dir).as_posix()

            sha = compute_file_sha256(abs_p)
            size = abs_p.stat().st_size
            art_type = infer_artifact_type(rel_p)

            # Procedencia
            if rel_p == "result.json":
                prov = "qa_agent.run"
            elif rel_p.startswith("report/"):
                prov = "qa_agent.reporting"
            elif rel_p.startswith("analysis/"):
                prov = "qa_agent.ai"
            else:
                # Si está bajo una suite (ej. python/junit.xml)
                parts = rel_p.split("/")
                prov = f"suite.{parts[0]}" if len(parts) > 1 else "qa_agent"

            art_id = rel_p.replace("/", "_").replace(".", "_")
            artifacts.append(
                QAArtifact(
                    id=art_id,
                    path=rel_p,
                    type=art_type,
                    size_bytes=size,
                    sha256=sha,
                    provenance=prov,
                )
            )

    # Ordenar artefactos por ruta para determinismo
    artifacts.sort(key=lambda a: a.path)

    manifest = QAReportManifest(
        schema_version="1.0",
        generated_utc=datetime.now(timezone.utc).isoformat(),
        test_run_trace=trace_id,
        test_result_sha256=result_sha,
        status="SUCCESS",
        artifacts=artifacts,
        warnings=warnings or [],
    )

    if write_to_disk:
        manifest_dest = run_dir / "report" / "report_manifest.json"
        atomic_write_text(manifest_dest, manifest.model_dump_json(indent=2))

    return manifest


def load_report_manifest(manifest_path: Path) -> QAReportManifest:
    """Carga y valida un QAReportManifest desde archivo."""
    p = Path(manifest_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Manifiesto no encontrado: {manifest_path}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    return QAReportManifest.model_validate(raw)


def write_delivery_result(run_dir: Path, delivery: QADeliveryResult) -> Path:
    """Persiste atómicamente el resultado de entrega delivery.json sin alterar result.json."""
    run_dir = Path(run_dir).resolve()
    dest = run_dir / "delivery.json"
    atomic_write_text(dest, delivery.model_dump_json(indent=2))
    return dest


def validate_package_integrity(run_dir: Path) -> tuple[bool, list[str]]:
    """Verifica la integridad de un paquete de evidencias verificando SHA-256 de result.json y artefactos."""
    run_dir = Path(run_dir).resolve()
    manifest_path = run_dir / "report" / "report_manifest.json"
    if not manifest_path.is_file():
        return False, [f"Manifiesto report/report_manifest.json no encontrado en {run_dir}"]

    try:
        manifest = load_report_manifest(manifest_path)
    except Exception as exc:
        return False, [f"Error al deserializar manifiesto de reporte: {exc}"]

    errors: list[str] = []

    # 1. Verificar inmutabilidad de result.json
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        errors.append("result.json missing from run directory")
    else:
        current_result_sha = compute_file_sha256(result_path)
        if current_result_sha != manifest.test_result_sha256:
            errors.append(
                f"result.json hash mismatch: expected {manifest.test_result_sha256}, got {current_result_sha}"
            )

    # 2. Verificar existencia y hashes de todos los artefactos listados
    for art in manifest.artifacts:
        art_path = run_dir / art.path
        if not art_path.is_file():
            errors.append(f"Artifact missing: {art.path}")
            continue
        curr_sha = compute_file_sha256(art_path)
        if curr_sha != art.sha256:
            errors.append(
                f"Artifact {art.path} hash mismatch: expected {art.sha256}, got {curr_sha}"
            )
        curr_size = art_path.stat().st_size
        if curr_size != art.size_bytes:
            errors.append(
                f"Artifact {art.path} size mismatch: expected {art.size_bytes}, got {curr_size}"
            )

    return len(errors) == 0, errors
