# Estado de ejecución: Trabajos 1 y 2 del agente de pruebas

Fecha de última actualización: 2026-10-18 (America/Lima).
Plan vigente: [plan.md](plan.md) | Especificación: [spec.md](spec.md) | Tareas: [tasks.md](tasks.md) | Referencia inicial: [baseline.md](baseline.md).

## Configuración del orquestador y subagentes

- **Orquestador activo**: Gemini 4 Argon (Medium) — prioridad 1 en la jerarquía requerida por `execute-project-plan`.
- **Política de subagentes**: por defecto Gemini 3.8 Flash (`Model: 'flash'`).

| conversationID / taskId | Role / Descripción | TypeName | Modelo objetivo / Tier pasado | Workspace | Estado |
| --- | --- | --- | --- | --- | --- |
| `ea7b85f4-4198-41ce-a1bb-4297a9c4f0aa` | Auditor de Suites y Aislamiento | `research` | Gemini 3.8 Flash (`high`) / `Model: 'flash'` | `inherit` (solo lectura) | Completado (`idle`) |

## Objetivo y alcance vigentes

Completar los Trabajos 1 y 2 del agente de pruebas (`specs/003-test-agent-foundation/`):
1. **Trabajo 1 (B01–B05)**: Inventario y referencia observacional en [baseline.md](baseline.md).
2. **Trabajo 2 (E01–E09)**: Ejecutor Python local (`qa_agent/`, `scripts/qa.py`, modelos en `contracts/models.py`, pruebas de aceptación en `qa_tests/`, `qa-agent.example.json`, `requirements-qa.txt` y `docs/qa-local.md`).

## Completado verificable

- **Trabajo 1 (B01–B05)**:
  - Inventario de 31 archivos en `tests/` (229 casos reales), 13 archivos Vitest en `frontend/src/test/` (48 bloques), scripts de auditoría y lanzadores documentado en [baseline.md](baseline.md).
  - Matriz de 7 recorridos de referencia (`R01-AUTH-VAL` a `R07-JAVA-SERVICE`) con distinción explícita entre validación en proceso, simulación y brechas pendientes para Trabajos 3–8.
  - Medición observacional en copia temporal aislada (`.agentia-runtime/qa/baseline-b04/`): `229` casos recolectados y `229` aprobados (`0` fallos, `0` errores, `0` omitidos).
- **Trabajo 2 (E01–E09) y Remediación de Revisión (`review.md`: `F01`–`F04`)**:
  - Contratos Pydantic añadidos en `contracts/models.py` (`QAConfigModel`, `QACapabilityStatus`, `QASuiteCatalogEntry`, `QACaseResult`, `QACounts`, `QASuiteExecutionResult`, `QADoctorReport`, `QAListReport`, `QARunResult`).
  - Implementación completa de `qa_agent/` (`__init__.py`, `__main__.py`, `cli.py`, `config.py`, `capabilities.py`, `catalog.py`, `execution.py`, `pytest_adapter.py`, `evidence.py`), `scripts/qa.py`, `qa-agent.example.json`, `requirements-qa.txt` y `docs/qa-local.md`.
  - **Corrección de hallazgos de [review.md](review.md)**:
    - **F01 (Consistencia interna del JUnit XML y conteo `skipped`, CA-10 / RF-07 / RF-11)**: En `qa_agent/pytest_adapter.py` se validan atributos enteros no negativos en `<testsuite>` y se exige igualdad exacta entre los atributos agregados (`tests`, `failures`, `errors`, `skipped`) y los elementos `<testcase>` reales (`len(cases)`, `failed`, `errors`, `skipped + xfail`). Cualquier discrepancia interna o con el código de salida del subproceso devuelve estado `ERROR` y código `3`. Verificado con `test_f01_internally_contradictory_xml_counts_and_skipped_returns_exit_3` y con la sonda independiente `.agentia-runtime/qa-review/xml_end_to_end.py` (`expected_exit: 3, actual_exit: 3, status: "ERROR"`).
    - **F02 (Cierre de procesos descendientes cuando el padre ya salió, CA-07 / RF-08)**: En `qa_agent/execution.py` se asigna un Job Object de Windows al proceso hijo y se rastrean periódicamente (cada `15 ms`) todos los PIDs descendientes mediante `CreateToolhelp32Snapshot`, terminando todos los descendientes registrados y cerrando el Job Object ante timeout o interrupción incluso si el proceso padre terminó antes. Verificado en `test_f02_exited_parent_leaves_no_orphan_descendants_on_timeout_or_interrupt` tanto para timeout con padre finalizado como para interrupción real (`QA_INTERRUPT_AFTER_SECONDS`).
    - **F03 (Limpieza de `scratch_root` ante fallo de snapshot y persistencia de evidencia de error, RF-09 / RF-10)**: En `qa_agent/execution.py` se envuelve la construcción de la copia temporal en `prepare_isolated_workspace()` con `try...except BaseException` que elimina `scratch_root` con `shutil.rmtree(..., ignore_errors=True)` antes de relanzar el error; y en `qa_agent/cli.py` se captura cualquier fallo de preparación o ejecución de suite persistiendo `<output_dir>/<trace_id>/result.json` y `python.log` con estado `ERROR` y código `3`. Verificado en `test_f03_snapshot_copy_failure_cleans_scratch_and_persists_error_evidence`.
    - **F04 (Captura concurrente y acotada en memoria de `stdout`/`stderr`, E05)**: En `qa_agent/execution.py` se reemplazó `proc.communicate()` sin cota por lectores en hilos `_BoundedStreamReader` que drenan `stdout` y `stderr` hasta EOF pero retienen como máximo `max_capture_chars` caracteres en memoria durante la lectura. Verificado en `test_f04_bounded_stream_capture_limits_buffer_during_read`.
    - **Aclaración en `baseline_metrics.json` y [baseline.md](baseline.md)**: Se reemplazó el campo ambiguo `c_tmp_touched` por `c_tmp_preexisting_dirs_observed: true` y `c_tmp_modified_during_run: false`, documentando que los directorios en `C:\tmp` tenían fecha previa (`2026-10-15`) y no fueron modificados durante la corrida aislada B04.
  - **Certificación final en verde**:
    - `ruff check qa_agent qa_tests scripts/qa.py contracts/models.py`: `All checks passed!`.
    - `mypy --follow-imports=silent qa_agent scripts/qa.py qa_tests contracts/models.py`: `Success: no issues found in 14 source files`.
    - `pytest qa_tests -v`: `17 passed in 33.65s` (13 pruebas iniciales + 4 contra-pruebas `F01`–`F04`, probadas primero en rojo `4 failed` y luego en verde).
    - `python -m qa_agent run --suite python`: `PASSED` (código `0`), `229` recolectados / `229` aprobados en `7.790 s` (evidencia en `.agentia-runtime/qa/qa-20261019T040551Z-0b6ddb7b/`).

## Decisiones técnicas relevantes

1. **Aislamiento por caso para `test_solution_generation.py`**: `app/main.py` modifica el comportamiento de `/v1/blueprint/run` si `AGENTIA_WORKSPACE_ROOT` se define globalmente en `os.environ`, rompiendo `tests/test_main.py::test_blueprint_routes_use_constant_auth_boundary_and_graph`. En cambio, si no se define, `test_solution_generation.py` escribe en `/tmp` (`C:\tmp\...` en Windows). Tanto en B04 como en `qa_agent/execution.py` se inyecta un hook `autouse` en `tests/conftest.py` de la copia temporal que aplica `AGENTIA_WORKSPACE_ROOT` exclusivamente a `test_solution_generation.py`, logrando aislamiento total sin modificar el código del producto ni sus expectativas.
2. **Diagnóstico de arranque con stdlib**: `qa_agent/capabilities.py`, `config.py`, `catalog.py` y `cli.py` usan la biblioteca estándar y validan contra `contracts/models.py` cuando `pydantic` está disponible, permitiendo que `--help`, `doctor`, `list` y `run` funcionen e informen ausencias incluso en un intérprete sin dependencias instaladas.

## Plataformas medidas y bloqueos / pendientes reales

- **Plataforma realmente medida**: `Windows-11-10.0.26300-SP0` (x86_64) con `Python 3.12.10`. No se ha ejecutado en una segunda máquina física ni en Linux/macOS (las pruebas sin herramientas opcionales simulan `PATH` vacío localmente).
- **Bloqueos locales de herramientas opcionales (no bloquean Python)**:
  - `java` y `mvn` no están instalados en `PATH` en esta máquina.
  - `frontend/node_modules` no está instalado en el árbol local (aunque `node v24.18.0` y `npm 11.16.0` están presentes).
- **Backlog aplazado a Trabajos 3 a 8**:
  - Adaptadores React/Vitest, Java/Maven real y Playwright; ampliación de cobertura de `/v1/solution/run` (`GENERATED` vs `VERIFIED`); proveedores e informe con IA (Trabajo 7); reporte HTML completo (Trabajo 6) y GitHub Actions (Trabajo 8).

## Próximo paso

Incremento (Trabajos 1 y 2) y remediación íntegra de [review.md](review.md) (`F01`–`F04`) completados y certificados. Listo para cierre o inicio del Trabajo 3 cuando se autorice.
