# Informe de Verificación y Cierre Conjunto (004-test-agent-functional-coverage)

**Fecha:** 2026-10-19  
**Plan:** [plan.md](file:///c:/Users/willi/Downloads/finalagent/specs/004-test-agent-functional-coverage/plan.md)  
**Especificación:** [spec.md](file:///c:/Users/willi/Downloads/finalagent/specs/004-test-agent-functional-coverage/spec.md)  
**Tareas:** [tasks.md](file:///c:/Users/willi/Downloads/finalagent/specs/004-test-agent-functional-coverage/tasks.md)  
**Revisión Independiente Atendida:** [review.md](file:///c:/Users/willi/Downloads/finalagent/specs/004-test-agent-functional-coverage/review.md)  
**Estado:** **PASSED** (Incremento completado, verificado, corregido y aceptado)

---

## 1. Resumen Ejecutivo y Métricas Reales

El objetivo de este incremento ha sido elevar la capacidad del agente de pruebas `qa_agent` desde una base de infraestructura a una **cobertura funcional profunda y multimotor** sobre las 5 áreas clave del producto, garantizando cero falsos positivos, dobles transparentes y observabilidad determinista sin descargas en tiempo de ejecución.

Tras la revisión independiente ([review.md](file:///c:/Users/willi/Downloads/finalagent/specs/004-test-agent-functional-coverage/review.md)), se subsanaron los 10 hallazgos técnicos (`R01` a `R10`), logrando una campaña de verificación 100% exitosa con mediciones reales:

1. **`python`**: **229/229 pruebas aprobadas** en 10.6 s (`qa_agent run --suite python`). Regresiones históricas intactas.
2. **`platform`**: **7 escenarios HTTP reales** en loopback sobre los 5 microservicios FastAPI con persistencia SQLite y ciclo de vida acotado. Detección aislada del defecto de producto en persistencia `GENERATED`→`RUNNING`, retornando FAILED (código 1).
3. **`java`**: **76 casos de prueba Surefire positivos aprobados** en 192 s sobre microservicios Quarkus 3.15 con Apache Maven 3.9.9, Eclipse Temurin OpenJDK 21, base de datos H2 en memoria y 100% caché offline (sin Docker ni red). Ambos servicios de `solution-h2` alcanzaron estado `VERIFIED`. Los dos controles negativos (`crud-h2-negative-compile` y `crud-h2-negative-assertion`) producen FAILED (código 1).
4. **`frontend`**: **53/53 casos Vitest aprobados**, verificación estricta de tipos TypeScript (`tsc -b`) y compilación de producción Vite (`vite build`) aislados de E2E.
5. **`playwright`**: **3 casos en navegador Chromium real** headless shell 1248:
   - **Recorrido positivo (AC-14/AC-15/U05)**: Sesión limpia, aprobación en LangGraph con backend Maven real, verificación por API de estado terminal `SUCCESS` y `verification.success == true`, descarga de ZIP real conteniendo `pom.xml`, fuentes Java, pruebas `@QuarkusTest` y coincidencia exacta con `generated_files` (rechazo de solo README).
   - **Controles negativos (AC-16/U06)**: Rechazo visible de autenticación 401 contra backend real (`invalid-secret-key-that-fails-auth`) y detección en el header de backend caído (puerto loopback 59999 inalcanzable), sin mocks `route.fulfill`.
6. **Aceptación Completa del Agente (`pytest qa_tests`)**: **40/40 pruebas de integración aprobadas** (100%) en 657.90 s (~10.9 min), incluyendo todas las regresiones R01–R09 y las históricas CA01–CA11, F01–F04.

---

## 2. Matriz de Trazabilidad de Criterios de Aceptación (AC-01 a AC-18)

> [!NOTE]
> Las comprobaciones de aceptación conservan la redacción y alcance literal de [spec.md](file:///c:/Users/willi/Downloads/finalagent/specs/004-test-agent-functional-coverage/spec.md).

| ID | Comprobación de Aceptación (Definición Literal de `spec.md`) | Evidencia de Verificación | Estado |
|---|---|---|:---:|
| **AC-01** | Sin Java, Maven, Node y navegador, `python` y `platform` siguen siendo elegibles con sus paquetes Python; las otras suites seleccionadas devuelven INCOMPLETE y explican el requisito. | [`qa_tests/test_shared_base_c02_to_c05.py::test_ac01...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_shared_base_c02_to_c05.py) | **PASSED** |
| **AC-02** | Alias `react`/`frontend` y `browser`/`playwright` se normalizan sin ejecutar dos veces la misma suite; ninguna evidencia se sobrescribe. | [`qa_tests/test_shared_base_c02_to_c05.py::test_ac02...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_shared_base_c02_to_c05.py) | **PASSED** |
| **AC-03** | La configuración anterior sigue funcionando; varias suites producen resultados por motor, pasos y alcance, conservando los códigos acordados. | [`qa_tests/test_shared_base_c02_to_c05.py::test_ac03_and_ac18...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_shared_base_c02_to_c05.py) | **PASSED** |
| **AC-04** | Los cinco procesos Python de prueba responden por sockets loopback reales; un puerto ocupado, un arranque fallido o dos ejecuciones concurrentes no afectan procesos ajenos. | [`qa_tests/test_shared_base_c02_to_c05.py::test_c05...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_shared_base_c02_to_c05.py) | **PASSED** |
| **AC-05** | Las claves de prueba correctas/incorrectas, blueprint inválido y errores de esquema producen los resultados del contrato existente, con trazabilidad. | [`qa_tests/test_platform_adapter.py`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_platform_adapter.py) | **PASSED** |
| **AC-06** | Un `run?mode=async` devuelve 202, llega a estado terminal y concuerda con detalle/historial/estado persistido; no se depende de observar una etapa tan breve que el polling pueda perderla. | [`qa_tests/test_platform_adapter.py`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_platform_adapter.py) | **PASSED** |
| **AC-07** | Verificación fallida, servicio caído, timeout, parche rechazado y presupuesto agotado producen el desenlace esperado, sin contactos reales a LLM ni reintentos ilimitados. | [`qa_tests/test_platform_adapter.py`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_platform_adapter.py) | **PASSED** |
| **AC-08** | La ruta de solución permite distinguir GENERATED de VERIFIED/SUCCESS, y recuperar el resultado tras reiniciar únicamente el orquestador de prueba. Un defecto detectado se registra sin simular persistencia. | [`qa_tests/test_platform_adapter.py::test_p06...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_platform_adapter.py) | **PASSED** |
| **AC-09** | Blueprints positivos de una y varias entidades generan código, compilan y ejecutan casos reales con H2; `dry_run`, informes antiguos o BUILD SUCCESS sin casos no sirven como prueba. | [`qa_tests/test_java_adapter.py::test_j03_j04_j06...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_java_adapter.py) | **PASSED** |
| **AC-10** | Un servicio con un error de compilación controlado y otro con una aserción de aceptación deliberadamente falsa terminan FAILED, conservando diagnósticos y códigos de proceso. | [`qa_tests/test_java_adapter.py::test_j03_j04_j06...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_java_adapter.py) | **PASSED** |
| **AC-11** | Falta de JDK, Maven o cache offline se diferencia de un defecto de compilación; la suite no cambia automáticamente a simulación ni descarga dependencias durante el veredicto. | [`qa_tests/test_java_adapter.py::test_j01...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_java_adapter.py), [`test_r05...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_java_adapter.py) | **PASSED** |
| **AC-12** | Los informes Surefire y los del oráculo corresponden a fuentes, fixture y ejecución identificadas; cero casos, omisiones o evidencia inconsistente no producen aprobación. | [`qa_tests/test_java_adapter.py::test_j05...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_java_adapter.py) | **PASSED** |
| **AC-13** | Las pruebas Vitest existentes, los nuevos casos de errores/estados y el build TypeScript se ejecutan con resultados estructurados y salidas diferenciadas. | [`qa_tests/test_frontend_adapter.py::test_u03...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_frontend_adapter.py), [`test_r06...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_frontend_adapter.py) | **PASSED** |
| **AC-14** | Playwright parte de un contexto limpio, crea una ejecución nueva por la interfaz y contrasta su `trace_id` y resultados con la API real. No acepta sesiones de demostración. | [`qa_tests/test_playwright_adapter.py::test_u04_u05_u06...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_playwright_adapter.py) | **PASSED** |
| **AC-15** | El navegador descarga un ZIP real con `pom.xml`, fuentes y pruebas esperadas; sus contenidos corresponden a la ejecución. Un ZIP de solo README o vacío falla el caso. | [`qa_tests/test_playwright_adapter.py::test_u04_u05_u06...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_playwright_adapter.py) | **PASSED** |
| **AC-16** | La UI muestra correctamente el rechazo de autenticación, un fallo backend y un resultado no verificado; el mensaje de éxito por sí solo no satisface el oráculo. | [`qa_tests/test_playwright_adapter.py::test_u04_u05_u06...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_playwright_adapter.py) | **PASSED** |
| **AC-17** | Se recupera evidencia mínima incluso ante timeout, fallo de snapshot o herramienta inválida; se detienen servicios, navegador y descendientes propios y se conservan centinelas externos. | [`qa_tests/test_java_adapter.py::test_r08...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_java_adapter.py), [`qa_tests/test_acceptance_ca01_to_ca11.py`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_acceptance_ca01_to_ca11.py) | **PASSED** |
| **AC-18** | Las regresiones anteriores siguen pasando; los casos históricos del producto conservan sus expectativas. Una suite seleccionada bloqueada, vacía u omitida impide salida global 0. | [`qa_tests/test_shared_base_c02_to_c05.py::test_ac03_and_ac18...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_shared_base_c02_to_c05.py), [`qa_tests/test_playwright_adapter.py::test_r02...`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_playwright_adapter.py) | **PASSED** |

---

## 3. Resolución de los 10 Hallazgos de la Revisión Independiente (R01 a R10)

| Ref | Severidad | Descripción del Defecto Identificado | Corrección Implementada y Verificación |
|---|:---:|---|---|
| **R01** | **P1** | Playwright podía degradar a `mode=platform` (compilador doble) ante ausencia de `io/quarkus` y anunciar falsamente Maven real. | Se eliminó la degradación automática. Si falta JDK, Maven o la carpeta real `io/quarkus`, el adaptador retorna inmediatamente `INCOMPLETE` (código 4). El alcance de evidencia deriva dinámicamente de `compiler=maven-real`. Probado en [`test_r01_marker_only_java_cache_returns_incomplete_without_compiler_double`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_playwright_adapter.py). |
| **R02** | **P1** | Adaptador Playwright convertía `INCOMPLETE` en `PASSED` y comparaba solo conteos totales, ignorando casos omitidos o vacíos. | Se propaga `INCOMPLETE` (código 4) si `xml_norm` o `json_norm` reportan `INCOMPLETE`, si `collected == 0` o si `skipped > 0`. Se compara el desglose completo por categorías (`collected`, `passed`, `failed`, `errors`, `skipped`, `xfail`). Probado en [`test_r02_playwright_preserves_incomplete_on_skipped_or_zero_cases`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_playwright_adapter.py) y [`test_r02_playwright_flags_error_on_xml_json_category_mismatch`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_playwright_adapter.py). |
| **R03** | **P1** | Recorrido positivo E2E no contrastaba el resultado terminal con la API ni verificaba la identidad/pruebas del ZIP. | Se captura la respuesta de run, se extrae el `trace_id` dinámico, se consulta `/v1/blueprint/status/{trace_id}` requiriendo `SUCCESS` y `verification.success == true`. Se valida que el ZIP descargado contenga `pom.xml`, archivos fuente `.java`, pruebas `@QuarkusTest` y coincida con `generated_files`. |
| **R04** | **P2** | Casos negativos de navegador usaban mocks `route.fulfill` y condicionales permisivos sin probar fallos del backend real. | Se eliminaron todos los mocks `route.fulfill`. Se prueba autenticación real inválida contra el backend (`invalid-secret-key-that-fails-auth`), validando el error 401 sin condicionales, y se prueba la caída real contra un puerto loopback no disponible (59999), validando el estado `DOWN`. |
| **R05** | **P2** | Caché Maven parcial con `io/quarkus` vacío se clasificaba como fallo del ejecutor (`ERROR`/3) en vez de dependencia ausente (`INCOMPLETE`/4). | Se clasifica como `INCOMPLETE` (código 4) la ausencia de artefactos/plugins durante compilación offline de Maven en el oráculo y el verificador. La falta de reportes Surefire downstream no activa `has_execution_error` cuando la caché está incompleta. Probado en [`test_r05_partial_java_cache_returns_incomplete_4_not_error_3`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_java_adapter.py). |
| **R06** | **P2** | El adaptador de frontend podía omitir silenciosamente TypeScript (`tsc -b`) y build (`vite build`) si faltaban sus ejecutables. | Se valida la presencia de `typescript/bin/tsc` y `vite/bin/vite.js` en el diagnóstico de capacidades y al inicio del adaptador. Si faltan, la suite retorna `INCOMPLETE` (código 4). Probado en [`test_r06_missing_tsc_or_vite_returns_incomplete_4`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_frontend_adapter.py). |
| **R07** | **P2** | `QASuiteStepResult` descartaba campos adicionales (`kind`, `command`, `diagnostic`), perdiendo trazabilidad en el `result.json` consolidado. | Se agregaron los campos `kind: str = "test"`, `command: list[str] | str | None = None` y `diagnostic: str | None = None` al modelo Pydantic, con `ConfigDict(extra="allow")`. Probado en [`test_r07_pydantic_round_trip_preserves_step_command_and_diagnostic`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_shared_base_c02_to_c05.py). |
| **R08** | **P2** | Escritura de artefactos Surefire con rutas largas (> 260 caracteres en Windows) provocaba `FileNotFoundError` sin persistir `result.json` mínimo. | Se implementó `to_extended_path(p)` con prefijo `\\?\` para Windows, `safe_write_text`, `safe_write_bytes`, y salvaguarda con bloque `try...except` por archivo. Además, `_handle_run` persiste un `result.json` de emergencia ante cualquier excepción fatal. Probado en [`test_r08_long_windows_paths_persistence`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_java_adapter.py). |
| **R09** | **P2** | Los adjuntos de fallo en Playwright (trazas, screenshots) se eliminaban en el `finally` del workspace antes de copiarse a la evidencia persistente. | Se recolectan los adjuntos de `test_results_dir` hacia `artifacts["playwright-results/..."]` antes de la limpieza del workspace en el adaptador. |
| **R10** | **P2** | El informe de cierre anterior sustituyó criterios originales, citó métricas desactualizadas y omitió el defecto conocido del producto. | Se reescribió `verification.md` manteniendo la literalidad de AC-01–AC-18, actualizando las métricas reales (53 Vitest, 76 Surefire), registrando el código 130 de interrupción y documentando formalmente el defecto de persistencia del producto. |

---

## 4. Defectos de Producto Identificados vs Capacidades del Agente

El agente de pruebas funcional aisló y diagnosticó de manera precisa el siguiente defecto real en el producto:

### Defecto P-01: Estado de Persistencia `GENERATED` se reinicia a `RUNNING` tras reinicio del Orquestador
- **Comportamiento observado:** Cuando un microservicio o solución se encuentra en estado `GENERATED` y se reinicia el servicio orquestador FastAPI, una consulta posterior a `/v1/runs/{trace_id}` o `/v1/blueprint/status/{trace_id}` reporta erróneamente `status: "RUNNING"` en la base de datos SQLite en lugar de preservar el estado terminal `GENERATED`.
- **Comportamiento del Agente:** El adaptador `platform` y la prueba de integración [`qa_tests/test_platform_adapter.py::test_p06_platform_adapter_runs_real_http_and_detects_sqlite_generated_defect`](file:///c:/Users/willi/Downloads/finalagent/qa_tests/test_platform_adapter.py) identifican correctamente este fallo del producto sin simular éxito:
  ```python
  assert res["status"] == "FAILED"
  assert res["exit_code"] == 1
  assert any("defecto de persistencia" in r.lower() for r in res["reasons"])
  ```
- **Conclusión de Aceptación:** El agente de pruebas cumple cabalmente con su propósito de observar, aislar y reportar fallos del producto con código de salida `1 (FAILED)`, sin que el defecto del producto invalide la aceptación del arnés de pruebas.

---

## 5. Códigos de Salida del Agente (Fidelidad Estricta)

El agente garantiza fidelidad estricta y sin ambigüedades sobre los códigos de salida del proceso:

- `0` (`EXIT_SUCCESS` / `PASSED`): Todas las suites seleccionadas fueron ejecutadas y aprobaron todas sus aserciones.
- `1` (`EXIT_FAILED` / `FAILED`): Se detectó al menos un fallo de aserción o defecto de compilación en el código bajo prueba.
- `2` (`EXIT_CONFIG_ERROR`): Error de configuración de línea de comandos o directivas inválidas en archivo de configuración.
- `3` (`EXIT_EXECUTION_ERROR`): Fallo irrecuperable del arnés o discrepancia/corrupción en los reportes de prueba normalizados.
- `4` (`EXIT_INCOMPLETE`): Herramientas o cachés requeridas ausentes sin conexión a internet disponible para descargarlas; o suite con cero casos recolectados o pruebas omitidas (`skipped`).
- `130` (`EXIT_INTERRUPTED`): Ejecución interrumpida externamente por el usuario (`SIGINT` / `Ctrl+C`), preservando el estándar POSIX (`128 + 2`).

---

## 6. Veredicto Final

El incremento `004-test-agent-functional-coverage` ha alcanzado todos los requisitos de diseño, implementación y verificación de los trabajos 3, 4 y 5. Cumple con los principios constitucionales de aislamiento hermético, soporte offline 100%, paridad de reportes y observabilidad determinista en entornos Windows, dejando el agente de pruebas listo para el cierre oficial.
