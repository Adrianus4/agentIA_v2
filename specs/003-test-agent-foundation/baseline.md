# Referencia Inicial del Proyecto (Trabajo 1 — Baseline Observacional)

Fecha de medición: 2026-10-18 (America/Lima) / 2026-10-19T03:17:49Z (UTC).
Revisión base Git: `d7a14ff` (`git status --short`: únicamente `?? specs/003-test-agent-foundation/` sin modificaciones sobre archivos rastreados del producto).
Plan de referencia: [plan.md](plan.md) | Especificación: [spec.md](spec.md) | Tareas: [tasks.md](tasks.md).

---

## 1. Entorno Observado y Huellas de Referencia (B01, B03)

### 1.1 Plataforma y herramientas detectadas

| Componente | Estado en la máquina medida | Detalle / Versión observada | Rol en este incremento |
| --- | --- | --- | --- |
| Sistema Operativo | Presente | `Windows-11-10.0.26300-SP0` (x86_64) | Plataforma principal de referencia |
| Python (sistema) | Presente | `Python 3.12.10` (`C:\Users\willi\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\python.exe`) | Intérprete base compatible (`>=3.11`, ref. `3.12`) |
| Entorno virtual de usuario (`.venv`) | Preparado | `.venv\Scripts\python.exe` (`Python 3.12.10`, 81 paquetes fijados desde `uv.lock`, sin instalar el repositorio como paquete editable) | Entorno aislado de ejecución QA |
| `uv` | Presente (opcional) | `uv 0.12.13 (0ebbd9274 2026-09-10 x86_64-pc-windows-msvc)` | Usado para sincronizar/exportar `uv.lock`; no obligatorio para el ejecutor QA |
| `git` | Presente (opcional) | `git version 2.55.0.windows.3` | Inspección de revisión (`d7a14ff`); no obligatorio para el ejecutor QA |
| `node` / `npm` | Presentes (opcionales) | `node v24.18.0` / `npm 11.16.0` | Herramientas presentes, pero `frontend/node_modules` no está instalado localmente |
| `java` / `mvn` | Ausentes en `PATH` | No encontrados por `where.exe java` / `where.exe mvn` | Capacidades opcionales; su ausencia no bloquea la suite Python |
| `docker` | Binario presente (opcional) | `C:\Users\willi\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe` | No requerido ni invocado en las pruebas Python en proceso |

### 1.2 Huellas SHA-256 de archivos clave del repositorio (`d7a14ff`)

| Archivo | SHA-256 | Observación |
| --- | --- | --- |
| `pyproject.toml` | `825db95035d799d5d927f16105d9767b275bf19d5055e45e36630ae4d36e8f50` | Declara dependencias base y extra `dev` (`pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`, `types-pyyaml`) |
| `uv.lock` | `5576cbb5e3568f460f7c77202ab0a69db267004a24d2162cee881f431c17540f` | Fuente de verdad de versiones fijadas para Python (`pydantic==2.14.1`, `fastapi==0.143.0`, `langgraph==1.2.14`, `pytest==9.1.1`, `pytest-asyncio==1.4.0`, `respx==0.23.1`) |
| `requirements.txt` | `e64e9e5af3348a1708ed08b25d3e0686aa204f4c73ab309cd848d325ccdac9fe` | Dependencias de runtime para imágenes de contenedores (no incluye `pytest`, `pytest-asyncio` ni `respx`) |
| `frontend/package.json` | `ab725d4c2041a238879b719550d2a82187641497d6e91a2b7019875fcd9f8544` | Scripts `test` (`vitest run`) y `build` (`tsc -b && vite build`) |
| `frontend/package-lock.json` | `96c7ea3e363ee70917212d9308c60171cc97e8d1eb5670b0d260154d2f98a7b0` | Lockfile de dependencias de interfaz |
| `tests/conftest.py` | `e21561d0c03e17b02023da9628094597d0b2296ea5d9cb756e2efd2bbd1bf521` | Desactiva la colección de `TestBaseline` como clase de test |

---

## 2. Inventario de Suites, Scripts y Lanzadores y Decisión de Elegibilidad (B01)

| Candidato | Ubicación | Categoría | Requisitos | Dobles / Simulaciones | Efectos laterales detectados | Elegibilidad en referencia y ejecutor |
| --- | --- | --- | --- | --- | --- | --- |
| Suite Python (`python -m pytest tests`) | `tests/` (31 archivos, 229 casos recolectados) | Suite de pruebas del producto | Python `>=3.11`, dependencias fijadas en `uv.lock`, recursos estáticos del repositorio (`profiles/`, `templates/`, `fixtures/`, `blueprints/`, `examples/`, `Dockerfile`, `scripts/cli.py`) | `FakeLLMClient`, `SequenceRunner`, `respx`, `TestClient`, `unittest.mock`, `dry_run=True` | Si no se aísla: `app/main.py` abre `runs.db` y `.agentia-state/` en `cwd`; `test_solution_generation.py` escribe en `/tmp/order-service`, `/tmp/inventory-service` y `/tmp/agentia-workspace` (`C:\tmp\...` en Windows) | **ELEGIBLE (Suite `python` activa en Trabajos 1 y 2)** |
| Suite Frontend (`npm test` / `vitest run`) | `frontend/src/test/` (13 archivos, 48 bloques `it`/`test`) | Suite de componentes UI | Node.js, `npm`, `frontend/node_modules` instalado | `jsdom`, `vi.fn()`, mock de `global.fetch` y timers virtuales | Ninguno en disco durante `vitest run` | **BLOQUEADA EN B04 POR DEPENDENCIA LOCAL AUSENTE** (`frontend/node_modules` no instalado; adaptador React corresponde a trabajos posteriores) |
| Build Frontend (`npm run build`) | `frontend/` | Verificación estática / empaquetado UI | Node.js, `npm`, `frontend/node_modules` instalado (`tsc`, `vite`) | N/A | Escribe artefactos en `frontend/dist/` | **BLOQUEADA EN B04 POR DEPENDENCIA LOCAL AUSENTE** (`frontend/node_modules` no instalado) |
| CLI de negocio (`scripts/cli.py`) | `scripts/cli.py` | Herramienta operativa de usuario | Backend HTTP accesible y base SQLite | N/A (probada con mocks desde `tests/orchestrator/test_cli.py`) | Peticiones HTTP y escritura en SQLite | **EXCLUIDA como suite** (se mantiene intacta y separada de `qa_agent`, RF-12) |
| Auditoría de cutover (`scripts/verify_implementation_agent.py`) | `scripts/verify_implementation_agent.py` | Auditoría específica histórica | Entorno Python del producto | Sondas mixtas e inspección de rutas históricas (`/working_dir/...`) | Mutación temporal de `os.environ["AGENTIA_WORKSPACE_ROOT"]` y escritura en temp | **EXCLUIDA de la suite general** (auditoría específica de cutover previo, no suite general del producto) |
| Guardián estructural (`scripts/guard_structure_agent.py`) | `scripts/guard_structure_agent.py` | Auditoría estática / linter de repositorio | Python, `PyYAML`, ejecutable Unix `bash` (`bash -n`), `node_modules` para chequeos TS | N/A | Invoca subprocesos `bash -n` sobre scripts `.sh` | **EXCLUIDA de la suite general** (exige `bash` y estado específico del árbol; no es suite pytest) |
| Configuración de laboratorio (`setup_copilot_tcs.py` / `run_setup.bat`) | Raíz | Utilidad externa de IDE | Windows, VS Code del usuario | N/A | Modifica configuración global de VS Code (`state.vscdb`) y contiene claves embebidas | **EXCLUIDA Y PROHIBIDA** (modifica estado global del usuario fuera del repositorio y contiene credenciales) |
| Lanzadores de plataforma (`start.bat`, `start.sh`, `start_frontend.sh`, `start_gpu_backend.sh`, `start_microservices.bat`) | Raíz y `scripts/` | Lanzadores de servicios e infraestructura | JDK 21, Maven, Node, Docker o paquetes Linux (`dnf`) | N/A | Crean `.venv`, instalan paquetes, abren puertos y procesos en segundo plano o contenedores | **EXCLUIDOS** (el ejecutor QA no depende de lanzadores para pruebas Python en proceso) |

### 2.1 Resumen del catálogo de archivos en `tests/` (31 archivos = 229 casos reales recolectados)

- **`tests/agents/generator/` (4 archivos, 40 casos)**: `test_entity.py` (9), `test_prompt.py` (12), `test_resource.py` (9), `test_test_writer.py` (10). Validan generación determinista con Jinja2 y prompts agnósticos de perfil con mocks de LLM.
- **`tests/agents/repair/` (4 archivos, 41 casos)**: `test_deterministic.py` (3), `test_guards.py` (24), `test_prompt.py` (9), `test_service.py` (5). Validan reparación determinista, compuertas G1–G8 (incluyendo protección de `pom.xml` y path traversal) y presupuesto de intentos.
- **`tests/agents/scaffolder/` (2 archivos, 6 casos)**: `test_extensions.py` (3), `test_runner.py` (3). Validan mapeo de extensiones Quarkus y ejecución de scaffolding con `subprocess.run` interceptado por `monkeypatch`.
- **`tests/agents/verifier/` (3 archivos, 21 casos)**: `test_parser.py` (9), `test_runner.py` (10), `test_verifier_integration.py` (2). Validan parseo de salidas Maven/Surefire desde `fixtures/` y construcción de comandos Docker/subprocess con `patch("subprocess.run")` y `dry_run=True`.
- **`tests/agents/` raíz (4 archivos, 22 casos)**: `test_blueprint_validator.py` (6), `test_profile_loader.py` (6), `test_quarkus_profile.py` (6), `test_stream_a_e2e.py` (4). Validan contratos de blueprint y perfiles YAML reales en `profiles/`.
- **`tests/contract/` (1 archivo, 2 casos)**: `test_scaffolding_contracts.py` (2). Valida modelos Pydantic de scaffolding.
- **`tests/orchestrator/` (12 archivos, 78 casos)**: `test_agent_client.py` (7), `test_cli.py` (4), `test_e2e_pipeline.py` (9), `test_execution_nodes.py` (6), `test_graph.py` (5), `test_llm_clients.py` (6), `test_microservice_workflow.py` (12), `test_patching.py` (13), `test_repository.py` (3), `test_scaffolding_pipeline.py` (1), `test_solution_generation.py` (2), `test_spec_agent.py` (10).
- **`tests/test_main.py` (1 archivo, 19 casos)**: Valida endpoints FastAPI (`/v1/blueprint/*`, `/v1/runs`, `/v1/llm/verify`, `/v1/solution/run`), autenticación `x-api-key`, modo asíncrono `202` y aislamiento de directorio centinela.

---

## 3. Matriz de Recorridos de Referencia y Criterios de Aceptación (B02)

| Identificador | Comportamiento esperado | Prueba existente | Nivel real/simulado | Dependencias | Comando | Estado observado | Evidencia | Seguimiento pendiente |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **R01-AUTH-VAL** | Autenticación por `x-api-key` (401/503 cuando falta o es inválida) y validación determinista de blueprints válidos e inválidos con diagnósticos estructurados | `tests/test_main.py` (casos de auth y `/v1/blueprint/validate`), `tests/agents/test_blueprint_validator.py` (6), `tests/agents/test_stream_a_e2e.py` (4) | **Real en proceso** para validador y ASGI `TestClient`; **Simulado** para el grafo (`FakeGraph`) | Python 3.12, `fastapi`, `pydantic`, `profiles/*.yaml` | `python -m pytest tests/agents/test_blueprint_validator.py tests/agents/test_stream_a_e2e.py tests/test_main.py` | **APROBADO** (29/29 casos aprobados en los 3 módulos) | `.agentia-runtime/qa/baseline-b04/python.junit.xml` (`tests.agents.test_blueprint_validator`, `tests.agents.test_stream_a_e2e`, `tests.test_main`) | Cubierto en Python en proceso; pruebas E2E con servidor HTTP levantado en puerto real corresponden a trabajos 3–5 |
| **R02-ASYNC-TRACE** | Envío asíncrono (`?mode=async` devuelve HTTP 202), propagación de `trace_id`, consulta de estado (`/v1/blueprint/status/{trace_id}`, `/v1/runs`) y persistencia SQLite | `tests/test_main.py::test_async_mode_returns_202_and_status_reaches_terminal`, `tests/orchestrator/test_repository.py` (3), `tests/orchestrator/test_cli.py` (4) | **Real en proceso** para persistencia SQLite (`aiosqlite` sobre archivo en `tmp_path`); **Simulado** para transporte HTTP en CLI (`respx`) y grafo (`FakeGraph`) | Python 3.12, `aiosqlite`, `fastapi`, `respx` | `python -m pytest tests/orchestrator/test_repository.py tests/orchestrator/test_cli.py tests/test_main.py` | **APROBADO** (26/26 casos aprobados en los 3 módulos) | `.agentia-runtime/qa/baseline-b04/python.junit.xml` (`tests.orchestrator.test_repository`, `tests.orchestrator.test_cli`, `tests.test_main`) | Cubierto en proceso; concurrencia multi-proceso contra backend real queda para trabajos 3–5 |
| **R03-GRAPH-REPAIR** | Orden determinista de etapas del grafo, límite estricto de presupuesto de reparación (`MAX_REPAIR_ATTEMPTS = 3` → `NO_FIX`), rechazo de parches inseguros por compuertas G1–G8 (`pom.xml`, path traversal, reducción de aserciones) y manejo de fallos HTTP 500/503 de servicios | `tests/orchestrator/test_graph.py` (5), `tests/orchestrator/test_e2e_pipeline.py` (9), `tests/agents/repair/test_guards.py` (24), `tests/agents/repair/test_service.py` (5), `tests/orchestrator/test_agent_client.py` (7), `tests/orchestrator/test_microservice_workflow.py` (12) | **Real en proceso** para compuertas G1–G8 y máquina de estados LangGraph; **Simulado** para LLM (`FakeLLMClient`), verificador (`SequenceRunner`, `VERIFIER_DRY_RUN=1`) y red (`respx`) | Python 3.12, `langgraph`, `respx`, `profiles/`, `templates/`, `blueprints/demo_quarkus.json`, `Dockerfile` | `python -m pytest tests/orchestrator/test_graph.py tests/orchestrator/test_e2e_pipeline.py tests/agents/repair/ tests/orchestrator/test_agent_client.py tests/orchestrator/test_microservice_workflow.py` | **APROBADO** (79/79 casos aprobados en los módulos del recorrido) | `.agentia-runtime/qa/baseline-b04/python.junit.xml` | La invocación opcional de proveedores LLM reales por API y el análisis con IA pertenecen al Trabajo 7 |
| **R04-GEN-ISOLATION** | Generación de entidades, repositorios, recursos y pruebas desde plantillas Jinja2/perfiles y aislamiento estricto de workspaces (preservación de archivos centinela externos y bloqueo de escritura fuera del workspace) | `tests/agents/generator/` (40), `tests/orchestrator/test_patching.py` (13), `tests/test_main.py::test_blueprint_run_preserves_external_sentinel_directory_and_returns_trace_on_502`, `tests/contract/test_scaffolding_contracts.py` (2) | **Real en proceso** para motor de plantillas Jinja2, aplicación atómica de parches en `tmp_path` y preservación de centinela; **Simulado** cuando interviene LLM (`unittest.mock`) | Python 3.12, `Jinja2`, `PyYAML`, `templates/quarkus/`, `profiles/` | `python -m pytest tests/agents/generator/ tests/orchestrator/test_patching.py tests/contract/test_scaffolding_contracts.py tests/test_main.py` | **APROBADO** (74/74 casos aprobados en los módulos del recorrido) | `.agentia-runtime/qa/baseline-b04/python.junit.xml` | Sin brecha para generación Python en proceso |
| **R05-SOLUTION-VERIF** | Ruta `/v1/solution/run` y pipeline de solución multiservicio (`SolutionGenerationPipeline`), partición de artefactos por microservicio y distinción contractual entre `GENERATED` y `VERIFIED` | `tests/orchestrator/test_solution_generation.py` (2), `tests/test_main.py::test_solution_run_rejects_omitted_or_empty_services` (1) | **Simulado** (`FakeGenerationPipeline`); comprueba estructura `GENERATED` y rechazo HTTP 422 de servicios vacíos, pero **no** ejercita la rama de verificación condicional con Maven real en `/v1/solution/run` | Python 3.12, `examples/microservices_catalog.json`, `contracts/solution_models.py` | `python -m pytest tests/orchestrator/test_solution_generation.py tests/test_main.py -k "solution"` | **APROBADO PARCIAL (SOLO NIVEL SIMULADO `GENERATED`)** (3/3 casos existentes aprobados; falta prueba de transición `GENERATED` vs `VERIFIED` en `/v1/solution/run`) | `.agentia-runtime/qa/baseline-b04/python.junit.xml` (`tests.orchestrator.test_solution_generation`) | **Pendiente para Trabajos 3 a 5**: agregar pruebas de contrato e integración sobre `/v1/solution/run` que verifiquen explícitamente la diferencia entre estado `GENERATED` (sin Maven) y `VERIFIED` (con verificador) |
| **R06-UI-REACT** | Pruebas de componentes React (Web Studio: `App`, `BlueprintRunTrigger`, `CoderGraphTracker`, `LangGraphStateVisualizer`, `RequirementsGraphTracker`, `SettingsDrawer`, `useStatusPolling`) y recorrido de generación desde la interfaz | `frontend/src/test/*.test.tsx` y `*.test.ts` (13 archivos, 48 bloques de prueba en Vitest/jsdom) | **Simulado en jsdom** (`global.fetch = vi.fn()`, sin navegador real ni backend conectado) | Node.js `>=18`, `npm`, `frontend/node_modules` instalado (Vitest, Testing Library, jsdom) | `npm --prefix frontend test` y `npm --prefix frontend run build` | **BLOQUEADO EN MEDICIÓN INICIAL (DEPENDENCIA LOCAL AUSENTE)**; recorrido E2E en navegador real **NO IMPLEMENTADO** | Auditoría estática de `frontend/src/test/` y verificación de ausencia de `frontend/node_modules` | **Pendiente para Trabajos 3 a 5**: instalar dependencias Node autorizadas, integrar adaptador Vitest y construir pruebas E2E de navegador con Playwright |
| **R07-JAVA-SERVICE** | Compilación y ejecución real de pruebas JUnit/Quarkus (`mvn test`) sobre el microservicio Java generado como comprobación posterior | `tests/agents/verifier/test_parser.py` (9), `tests/agents/verifier/test_runner.py` (10), `tests/agents/verifier/test_verifier_integration.py` (2), `tests/agents/scaffolder/test_runner.py` (3) | **Simulado** (parseo sobre textos fijos en `fixtures/` y ejecución con `patch("subprocess.run")` o `dry_run=True`; no invoca `javac` ni `mvn` reales) | Para simulación: Python + `fixtures/`. Para verificación real: JDK 21 + Maven 3.9+ | `python -m pytest tests/agents/verifier/ tests/agents/scaffolder/` | **SIMULACIÓN APROBADA (24/24)**; **COMPILACIÓN JAVA REAL PENDIENTE / BLOQUEADA** (`java` y `mvn` ausentes en `PATH`) | `.agentia-runtime/qa/baseline-b04/python.junit.xml` (`tests.agents.verifier.*`, `tests.agents.scaffolder.*`) | **Pendiente para Trabajos 3 a 5**: adaptador Java/Maven real y pruebas de compilación de microservicios generados cuando JDK/Maven estén disponibles |

---

## 4. Auditoría de Seguridad y Aislamiento Pre-Ejecución (B03)

Antes de ejecutar la suite `tests/`, se auditaron los 31 archivos de prueba y el código de `app/`, `agents/` y `services/`:

1. **Llamadas externas y credenciales**:
   - Ninguno de los 31 archivos realiza llamadas reales a APIs de LLM ni a servicios remotos: los tests de clientes usan `FakeLLMClient`, `httpx.MockTransport` o `respx.mock`.
   - Se comprobó que retirar todas las variables de entorno sensibles (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `ORCHESTRATOR_API_KEY`) del proceso padre es seguro; las pruebas que requieren `ORCHESTRATOR_API_KEY` la inyectan localmente con `monkeypatch.setenv("ORCHESTRATOR_API_KEY", "secret")`.
2. **Subprocesos**:
   - `tests/agents/verifier/test_runner.py` y `tests/agents/scaffolder/test_runner.py` interceptan `subprocess.run` mediante `unittest.mock.patch` o `monkeypatch`. Ningún test de `tests/` lanza contenedores Docker ni procesos Maven reales.
3. **Escrituras en sistema de archivos y hallazgo de aislamiento por caso**:
   - **Hallazgo A (`runs.db` y `.agentia-state`)**: `app/main.py` usa por defecto `ORCHESTRATOR_DATABASE_PATH="runs.db"` y `WORKFLOW_STATE_DIR=".agentia-state"` relativos al directorio de trabajo o entorno. En una copia temporal aislada, redirigir `ORCHESTRATOR_DATABASE_PATH` y `WORKFLOW_STATE_DIR` a subdirectorios del scratch evita cualquier residuo en el árbol del usuario.
   - **Hallazgo B (`AGENTIA_WORKSPACE_ROOT` no puede imponerse globalmente)**: `app/main.py:732` evalúa `if is_real_graph or "AGENTIA_WORKSPACE_ROOT" in os.environ:`. Si se define `AGENTIA_WORKSPACE_ROOT` globalmente para toda la corrida de `pytest`, la prueba `tests/test_main.py::test_blueprint_routes_use_constant_auth_boundary_and_graph` falla porque espera que `FakeGraph` reciba `str(tmp_path)` sin reescritura.
   - **Hallazgo C (escritura fuera de la copia en `tests/orchestrator/test_solution_generation.py`)**: Cuando `AGENTIA_WORKSPACE_ROOT` no está definido, `resolve_managed_workspace()` en `app/orchestrator/solution_generation.py:73` usa el valor por defecto `"/tmp/agentia-workspace"` y `test_solution_generation.py:51` pasa `workspace_dir=str(Path("/tmp") / name)`. En Windows esto resuelve a `C:\tmp\agentia-workspace`, `C:\tmp\order-service` y `C:\tmp\inventory-service` (se observaron directorios previos en `C:\tmp` con fecha `2026-10-15 18:31`).
   - **Solución de aislamiento por caso aplicada (sin cambiar expectativas de negocio)**: En la copia temporal de medición (y en el adaptador `pytest` del ejecutor QA), se inyecta un hook `autouse` que define `AGENTIA_WORKSPACE_ROOT=<scratch>/managed-workspaces` **únicamente** cuando el nodo en ejecución pertenece a `test_solution_generation.py` y el propio test no ha definido `AGENTIA_WORKSPACE_ROOT`. De este modo:
     - `test_main.py` corre sin `AGENTIA_WORKSPACE_ROOT` global y conserva intacta su expectativa (`229/229` casos aprobados).
     - `test_solution_generation.py` materializa sus 5 workspaces (`order-service-trace123`, `inventory-service-trace123`, `order-service-*`, `payment-escrow-service-*`, `telemetry-ingestion-service-*`) exclusivamente dentro de `<scratch>/managed-workspaces`, sin escribir ni modificar `C:\tmp` durante la corrida aislada (en `baseline_metrics.json` se distingue `c_tmp_preexisting_dirs_observed: true` por los directorios previos del `2026-10-15` frente a `c_tmp_modified_during_run: false`).

---

## 5. Resultados Observados de la Medición de Referencia (B04)

### 5.1 Recolección de casos (`--collect-only`)

- **Comando**: `C:\Users\willi\Downloads\finalagent\.venv\Scripts\python.exe -m pytest --collect-only -q tests`
- **Directorio de trabajo (`cwd`)**: `C:\Users\willi\AppData\Local\Temp\qa-baseline-b04-nxyxkblt\repo` (copia temporal aislada de 124 archivos requeridos)
- **Inicio UTC**: `2026-10-19T03:17:49.311184+00:00`
- **Fin UTC**: `2026-10-19T03:17:57.917050+00:00`
- **Duración total**: `8.606 s` (tiempo interno de colección reportado por pytest: `2.73 s`)
- **Timeout aplicado**: `120 s`
- **Código de salida**: `0`
- **Resultado observado**: `229 tests collected in 2.73s` distribuidos en 31 archivos `test_*.py`.
- **Evidencia**: `.agentia-runtime/qa/baseline-b04/collect_only.log`.

### 5.2 Ejecución completa de la suite Python (`pytest tests`)

- **Comando**:
  ```text
  C:\Users\willi\Downloads\finalagent\.venv\Scripts\python.exe -m pytest tests --basetemp=C:\Users\willi\AppData\Local\Temp\qa-baseline-b04-nxyxkblt\pytest-tmp --junitxml=C:\Users\willi\Downloads\finalagent\.agentia-runtime\qa\baseline-b04\python.junit.xml
  ```
- **Directorio de trabajo (`cwd`)**: `C:\Users\willi\AppData\Local\Temp\qa-baseline-b04-nxyxkblt\repo`
- **Inicio UTC**: `2026-10-19T03:17:57.918047+00:00`
- **Fin UTC**: `2026-10-19T03:18:07.435683+00:00`
- **Duración observada (proceso)**: `9.517 s` (tiempo reportado por pytest: `6.61 s`)
- **Timeout aplicado**: `300 s`
- **Código de salida**: `0`
- **Conteos verificados desde JUnit XML (`.agentia-runtime/qa/baseline-b04/python.junit.xml`)**:
  - **Total recolectados / ejecutados**: `229`
  - **Aprobados (`passed`)**: `229`
  - **Fallidos (`failures`)**: `0`
  - **Errores (`errors`)**: `0`
  - **Omitidos (`skipped` / `xfail`)**: `0`
- **Evidencia generada**:
  - `.agentia-runtime/qa/baseline-b04/python.junit.xml`
  - `.agentia-runtime/qa/baseline-b04/python.log`
  - `.agentia-runtime/qa/baseline-b04/baseline_metrics.json`

---

## 6. Clasificación del Diagnóstico Inicial (B05)

Conforme a la puerta de salida del Trabajo 1 (`plan.md`), los hallazgos observados se clasifican en cuatro categorías sin alterar expectativas de negocio:

1. **Fallos previos del producto (en suites ejecutables)**:
   - **Ninguno observado en la suite `python` (`229/229` aprobados)** cuando se ejecuta con las dependencias fijadas en `uv.lock`.
2. **Dependencias ausentes en el entorno local**:
   - **Intérprete global de Windows vs `.venv`**: El Python global del sistema (`Python 3.12.10` en `WindowsApps`) carecía de `aiosqlite`, `google-generativeai`, `pytest-asyncio` y `respx`, y tenía versiones distintas de `pydantic` (`2.13.4` vs `2.14.1`) y `fastapi` (`0.140.0` vs `0.143.0`). Esto confirma el requisito RF-02/RF-05 y CA-02: el ejecutor QA debe diagnosticar paquetes requeridos (`doctor`) y usar el entorno virtual configurado.
   - **Frontend (`frontend/node_modules`)**: Aunque `node v24.18.0` y `npm 11.16.0` están instalados, `frontend/node_modules` no existe en el árbol de trabajo. Conforme al plan, no se ejecutó `npm install` automáticamente y las comprobaciones de `frontend/` quedan registradas como bloqueadas por dependencia local ausente hasta el trabajo correspondiente.
   - **Toolchain Java (`java` y `mvn`)**: No están presentes en el `PATH` de la máquina actual. No bloquean la suite Python (CA-01), pero bloquean cualquier verificación Maven real fuera de modo simulado (`dry_run`).
3. **Limitaciones de entorno y scripts auxiliares**:
   - `scripts/guard_structure_agent.py` invoca `subprocess.run(["bash", "-n", ...])`, lo cual depende de un shell Unix externo y no forma parte de la suite portable de Windows.
   - `scripts/verify_implementation_agent.py` contiene sondas acopladas a rutas de un cutover previo y no es una suite general de regresión.
4. **Problemas propios de la medición / aislamiento**:
   - `tests/orchestrator/test_solution_generation.py` escribe en `/tmp` (`C:\tmp\...` en Windows) cuando `AGENTIA_WORKSPACE_ROOT` no está definido, pero definir `AGENTIA_WORKSPACE_ROOT` globalmente rompe `tests/test_main.py::test_blueprint_routes_use_constant_auth_boundary_and_graph`. El aislamiento por caso (`AGENTIA_WORKSPACE_ROOT` inyectado solo para `test_solution_generation.py` dentro del scratch de la corrida) resuelve el efecto lateral sin modificar el código del producto ni las aserciones de las pruebas, y se reutiliza en el Trabajo 2 (`qa_agent`).
