"""Renderizador del informe HTML estático y autocontenido (R01, R03, AC-03, AC-04, AC-05, AC-07)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jinja2

from contracts.models import (
    QAAnalysisResult,
    QAReportManifest,
    QARunResult,
    validate_run_result_consistency,
)
from qa_agent.reporting.manifest import atomic_write_text

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_jinja_env() -> jinja2.Environment:
    """Crea un entorno Jinja2 con autoescape estricto activado para mitigar inyecciones XSS."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "xml", "j2"]),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html_report(
    result: QARunResult | dict[str, Any] | str | Path,
    manifest: QAReportManifest | dict[str, Any] | str | Path | None = None,
    analysis: QAAnalysisResult | dict[str, Any] | str | Path | None = None,
    output_path: Path | str | None = None,
) -> str:
    """Renderiza el informe HTML consolidado a partir de la evidencia validada.

    No realiza peticiones de red, no invoca subprocess ni altera los conteos del contrato.
    """
    # 1. Normalizar QARunResult
    if isinstance(result, (str, Path)):
        p = Path(result).resolve()
        raw = json.loads(p.read_text(encoding="utf-8"))
        typed_result = QARunResult.model_validate(raw)
    elif isinstance(result, dict):
        typed_result = QARunResult.model_validate(result)
    else:
        typed_result = result

    # Validar consistencia invariante
    consistency_errors = validate_run_result_consistency(typed_result)
    if consistency_errors:
        raise ValueError(
            "Resultado de pruebas contradictorio o inconsistente:\n" + "\n".join(consistency_errors)
        )

    # 2. Normalizar QAReportManifest si fue provisto
    typed_manifest: QAReportManifest | None = None
    if manifest is not None:
        if isinstance(manifest, (str, Path)):
            p_man = Path(manifest).resolve()
            if p_man.is_file():
                raw_man = json.loads(p_man.read_text(encoding="utf-8"))
                typed_manifest = QAReportManifest.model_validate(raw_man)
        elif isinstance(manifest, dict):
            typed_manifest = QAReportManifest.model_validate(manifest)
        else:
            typed_manifest = manifest

    # 3. Normalizar QAAnalysisResult si fue provisto
    typed_analysis: QAAnalysisResult | None = None
    if analysis is not None:
        if isinstance(analysis, (str, Path)):
            p_an = Path(analysis).resolve()
            if p_an.is_file():
                raw_an = json.loads(p_an.read_text(encoding="utf-8"))
                typed_analysis = QAAnalysisResult.model_validate(raw_an)
        elif isinstance(analysis, dict):
            typed_analysis = QAAnalysisResult.model_validate(analysis)
        else:
            typed_analysis = analysis

    env = _get_jinja_env()
    template = env.get_template("report.html.j2")

    context = {
        "result": typed_result,
        "manifest": typed_manifest,
        "analysis": typed_analysis,
    }

    rendered_html = template.render(**context)

    if output_path is not None:
        out = Path(output_path).resolve()
        atomic_write_text(out, rendered_html, encoding="utf-8")

    return rendered_html
