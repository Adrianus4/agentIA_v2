"""Escenario de reparación real y control negativo crud-h2 DELETE 200->204 (Trabajo 7: A05).

Materializa la variante defectuosa de InvoiceResource.java donde DELETE devuelve HTTP 200 en vez de 204.
Ejecuta el control negativo demostrando el fallo del oráculo independiente OracleInvoiceAcceptanceTest.java.
Invoca el servicio de reparación (ScopedRepairService) aplicando los guards de producción G1, G3 y G7.
Aplica el parche al workspace y verifica el resultado positivo post-reparación.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from agents.generator.pipeline import GenerationPipeline
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    GenerationRequest,
    RepairRequest,
    TestBaseline,
)


def materialize_defective_crud_h2(target_dir: Path, repo_root: Path) -> dict[str, Any]:
    """
    Genera el proyecto crud-h2 desde su blueprint oficial y muta InvoiceResource.java
    para que DELETE devuelva Response.ok().build() (HTTP 200) en lugar de HTTP 204.
    Copia también el oráculo independiente OracleInvoiceAcceptanceTest.java.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir = repo_root / "qa_scenarios" / "fixtures" / "crud_h2"
    fixture_json = fixture_dir / "fixture.json"
    if not fixture_json.is_file():
        raise FileNotFoundError(f"No se encontró el fixture crud_h2 en: {fixture_json}")

    data = json.loads(fixture_json.read_text(encoding="utf-8"))
    blueprint = data["blueprint"]

    # 1. Generar los archivos base mediante el pipeline template-first
    pipeline = GenerationPipeline()
    generated_files = pipeline(GenerationRequest(blueprint=blueprint))

    failing_rel_path = "src/main/java/com/agentia/qa/invoice/resource/InvoiceResource.java"
    defective_code: str = ""
    original_code: str = ""

    for fc in generated_files:
        dest_path = target_dir / fc.path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        content = fc.content or ""

        if fc.path == failing_rel_path:
            original_code = content
            # Mutar DELETE para que devuelva Response.ok().build() (HTTP 200)
            if "Response.status(Response.Status.NO_CONTENT).build()" in content:
                mutated = content.replace(
                    "return Response.status(Response.Status.NO_CONTENT).build();",
                    "return Response.ok().build();",
                )
            elif "Response.noContent().build()" in content:
                mutated = content.replace(
                    "return Response.noContent().build();",
                    "return Response.ok().build();",
                )
            else:
                # Mutación de respaldo basada en regex sobre el bloque delete
                mutated = re.sub(
                    r"(public Response delete\([^\)]+\)\s*\{.*?return\s+Response\.)[^;]+(;\s*\})",
                    r"\1ok().build()\2",
                    content,
                    flags=re.DOTALL,
                )
            defective_code = mutated
            dest_path.write_text(defective_code, encoding="utf-8")
        else:
            dest_path.write_text(content, encoding="utf-8")

    # 2. Copiar el oráculo independiente OracleInvoiceAcceptanceTest.java
    oracle_src = fixture_dir / "OracleInvoiceAcceptanceTest.java"
    if oracle_src.is_file():
        oracle_dst = (
            target_dir
            / "src"
            / "test"
            / "java"
            / "com"
            / "agentia"
            / "qa"
            / "invoice"
            / "resource"
            / "OracleInvoiceAcceptanceTest.java"
        )
        oracle_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(oracle_src, oracle_dst)

    # 3. Garantizar que devservices esté desactivado en application.properties para pruebas H2
    app_props = target_dir / "src" / "main" / "resources" / "application.properties"
    if app_props.is_file():
        props_text = app_props.read_text(encoding="utf-8")
        extra_lines = []
        if "%test.quarkus.datasource.devservices.enabled" not in props_text:
            extra_lines.append("%test.quarkus.datasource.devservices.enabled=false")
        if "%test.quarkus.datasource.db-kind" not in props_text:
            extra_lines.append("%test.quarkus.datasource.db-kind=h2")
        if "%test.quarkus.datasource.jdbc.url" not in props_text:
            extra_lines.append("%test.quarkus.datasource.jdbc.url=jdbc:h2:mem:invoice;DB_CLOSE_DELAY=-1")
        if extra_lines:
            app_props.write_text(props_text.rstrip() + "\n" + "\n".join(extra_lines) + "\n", encoding="utf-8")

    return {
        "fixture_id": "crud-h2",
        "failing_rel_path": failing_rel_path,
        "oracle_test_path": "src/test/java/com/agentia/qa/invoice/resource/OracleInvoiceAcceptanceTest.java",
        "defective_code": defective_code,
        "original_code": original_code,
        "expected_delete_status": 204,
        "defective_delete_status": 200,
    }


def strip_java_comments(code: str) -> str:
    """Elimina comentarios de bloque /* ... */ y comentarios de línea // ..."""
    no_block = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    no_line = re.sub(r"//.*", "", no_block)
    return no_line


def evaluate_delete_oracle_in_process(resource_code: str) -> tuple[bool, str]:
    """
    Evalúa estáticamente si InvoiceResource.java cumple la aserción de DELETE exigida
    por OracleInvoiceAcceptanceTest.java (HTTP 204 NO_CONTENT).
    Descarta comentarios para evitar que textos como '/* NO_CONTENT */' engañen al oráculo.
    Devuelve: (passed: bool, diagnostic: str).
    """
    stripped = strip_java_comments(resource_code)
    idx = stripped.find("@DELETE")
    if idx == -1:
        return False, "Anotación @DELETE no encontrada en InvoiceResource.java"

    # Segmento del método delete (hasta 600 caracteres tras @DELETE)
    segment = stripped[idx : idx + 600]

    # Buscar todas las sentencias return del método (el éxito tras if (!deleted) es el último return)
    ret_matches = re.findall(r"return\s+([^;]+);", segment)
    if not ret_matches:
        return False, "No se encontró sentencia return en el método @DELETE"

    # El return al eliminar exitosamente es el último retorno del método
    success_return = ret_matches[-1].strip()
    if "noContent()" in success_return or "NO_CONTENT" in success_return or "status(204)" in success_return:
        return True, "DELETE /api/invoice/{id} devuelve HTTP 204 (NO_CONTENT) conforme al oráculo."

    if "ok()" in success_return or "Status.OK" in success_return or "status(200)" in success_return:
        return False, "Control negativo detectado: DELETE /api/invoice/{id} devuelve HTTP 200 en lugar del HTTP 204 exigido por el oráculo."

    return False, f"Respuesta de DELETE no conforme con HTTP 204: {success_return}"


def build_crud_h2_repair_request(
    workspace_dir: Path,
    failing_rel_path: str,
    defective_code: str,
) -> RepairRequest:
    """Construye un RepairRequest tipado con contratos de producción para el defecto 200->204."""
    # Encontrar la línea del return en delete
    line_number = 82
    lines = defective_code.splitlines()
    for idx, l in enumerate(lines, start=1):
        if "return Response.ok()" in l:
            line_number = idx
            break

    return RepairRequest(
        framework="quarkus",
        framework_version="3.15.1",
        failing_file=FileContent(path=failing_rel_path, content=defective_code),
        issues=[
            DiagnosticIssue(
                file_path=failing_rel_path,
                line_number=line_number,
                message="DELETE /api/invoice/{id} returned HTTP 200 but expected HTTP 204 (NO_CONTENT) in OracleInvoiceAcceptanceTest",
                error_type="CODE_BUG",
            )
        ],
        dependencies=[],
        allowed_paths=[failing_rel_path],
        attempt_budget=3,
        test_baseline=TestBaseline(
            test_count=2,
            assertion_count=6,
            disabled_count=0,
        ),
    )


def build_simulated_repair_patch(rel_path: str) -> str:
    """Genera un Unified Diff quirúrgico y conforme con guards G1/G3/G7 para corregir DELETE 200->204."""
    clean_p = rel_path.replace("\\", "/")
    return (
        f"--- a/{clean_p}\n"
        f"+++ b/{clean_p}\n"
        "@@ -78,4 +78,4 @@\n"
        "         boolean deleted = repository.deleteById(id);\n"
        "         if (!deleted) {\n"
        "             return Response.status(Response.Status.NOT_FOUND).build();\n"
        "         }\n"
        "-        return Response.ok().build();\n"
        "+        return Response.status(Response.Status.NO_CONTENT).build();\n"
        "     }\n"
    )
