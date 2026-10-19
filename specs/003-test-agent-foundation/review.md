# Revisión independiente de los trabajos 1 y 2

Fecha: 2026-10-18 (America/Lima).
Revisión Git: `d7a14ff`, con los cambios locales de QA presentes al revisar.
Documentos de referencia: [spec.md](spec.md), [plan.md](plan.md), [tasks.md](tasks.md).

## Dictamen

**Trabajo 1: respaldado para la referencia local documentada.** Hay inventario,
matriz de recorridos, dependencias, huellas y evidencia de medición. Reproduje los
229 casos Python aprobados mediante el agente. Las comprobaciones de Java real,
frontend y navegador se identifican como pendientes de sus trabajos posteriores.

**Trabajo 2: implementado y funcional en el recorrido normal, pero pendiente de
cierre.** Las 13 pruebas de aceptación existentes pasan; las sondas independientes
reproducen defectos de integridad del reporte, limpieza de procesos y tratamiento
de errores. Además, el límite de captura de salida se aplica después de acumularla
en memoria. Las marcas de cierre de E05, E06, E07 y E09 requieren revisión.

## Comprobaciones realizadas

| Comprobación | Resultado observado | Evidencia |
| --- | --- | --- |
| Suite de aceptación `qa_tests/` | 13 aprobadas, 0 fallos, 0 errores; 26,54 s de pytest. | [acceptance.junit.xml](../../.agentia-runtime/qa-review/acceptance.junit.xml) |
| Suite del producto invocada mediante `qa_agent run` | PASSED / código 0; 229 recolectadas y aprobadas, sin fallos, errores ni omisiones; 8,9813 s del ejecutor. | [result.json](../../.agentia-runtime/qa-review/product/qa-20261019T034706Z-0efc2300/result.json) |
| `doctor` con el entorno virtual preparado | PASSED / código 0. Java y Maven ausentes; la suite Python sigue elegible. | Salida inspeccionada durante la revisión. |
| `doctor` con `python -S`, sin paquetes externos en el path de importación | INCOMPLETE / código 4; 12 dependencias requeridas ausentes. El diagnóstico funciona sin instalarlas. | [doctor-without-site-packages.json](../../.agentia-runtime/qa-review/doctor-without-site-packages.json) |
| Cinco huellas del baseline | Coinciden las de `pyproject.toml`, `uv.lock`, `requirements.txt`, `frontend/package.json` y `frontend/package-lock.json`. | Comparación SHA-256 con `baseline_metrics.json`. |
| Cambios en contratos existentes | Descartando finales de línea, `contracts/models.py` agrega 146 líneas; no elimina las definiciones previas. | `git diff --ignore-space-at-eol --numstat`. |
| Sondas adicionales de XML, copia temporal y procesos | Reproducen los hallazgos F01–F03. | [independent-probes.json](../../.agentia-runtime/qa-review/independent-probes.json) |
| Caso XML mediante CLI completa | Devuelve código 0 con conteos JUnit contradictorios. | [xml-e2e-summary.json](../../.agentia-runtime/qa-review/xml-e2e-summary.json) |

La evidencia de revisión vive en `.agentia-runtime/qa-review/`, ignorada por Git.
Las sondas usan fixtures temporales y no modifican el código del agente ni las
pruebas existentes. El hijo que quedó vivo en la contraprueba F02 fue detenido por
la propia revisión al finalizar la medición.

El primer lanzamiento de aceptación falló por faltar el directorio padre de
`--basetemp` elegido por la revisión. Se preparó ese directorio y se repitió la
comprobación. Ese problema del arnés de revisión no se atribuye a la implementación.
El intérprete WindowsApps requirió ejecución fuera del sandbox para poder iniciarse.

## Hallazgos que impiden cerrar el trabajo 2

### F01 — [P2] Se aprueba un XML con casos y omisiones inconsistentes

Ubicación: `qa_agent/pytest_adapter.py:203–259` y `:300–302`.
Requisitos afectados: RF-07, RF-11; CA-10; tareas E06 y E09.

El adaptador lee los atributos `tests`, `failures` y `errors`, pero no contrasta
todos los totales con los elementos `testcase` ni valida el atributo `skipped`.
Usa `max(xml_tests, len(cases))` para el total y concluye PASSED si encuentra un
caso aprobado y código del proceso 0.

Contraprueba por CLI completa: un fixture ejecuta una prueba aprobada y, al cerrar
pytest, produce un XML sintácticamente válido con `tests="2"` y `skipped="1"`,
manteniendo un solo `testcase` aprobado. La respuesta real fue:

```text
status=PASSED, exit_code=0
collected=2, passed=1, skipped=0, cases=1
```

Un reporte internamente contradictorio termina aprobado y oculta la omisión
declarada. El resultado esperado es ERROR / código 3 por evidencia inconsistente.

Corrección necesaria: comprobar valores no negativos, consistencia de todos los
totales y correspondencia con los casos antes de decidir el estado. Añadir una
prueba de aceptación con XML válido pero internamente contradictorio. Las
pruebas actuales solo cubren XML ausente, mal formado y un desacuerdo simple
entre código del proceso y número de fallos.

Evidencia reproducible: [xml_end_to_end.py](../../.agentia-runtime/qa-review/xml_end_to_end.py),
[resultado](../../.agentia-runtime/qa-review/xml-e2e-summary.json) y
[XML preservado](../../.agentia-runtime/qa-review/xml-e2e-python.junit.xml).

### F02 — [P2] La limpieza deja descendientes vivos si el padre ya terminó

Ubicación: `qa_agent/execution.py:251–284`, especialmente `:258–265`.
Requisitos afectados: RF-08; CA-07; tareas E05 y E09.

En Windows, el cierre intenta `taskkill /F /T /PID <padre>` y no comprueba su código
de retorno. Si el proceso padre termina antes y un hijo conserva abiertos los
pipes heredados, `communicate()` llega al timeout; `taskkill` ya no encuentra al
padre y no elimina ese descendiente.

Contraprueba con procesos reales: un padre Python crea un hijo que espera 15 s y
termina inmediatamente. El ejecutor devuelve timeout a los 3,2177 s con límite
de 2 s, pero el hijo sigue activo. La revisión comprobó su estado y lo detuvo.

Corrección necesaria: mantener control efectivo de los descendientes durante toda
la ejecución, incluido el escenario en que el padre finaliza antes que ellos,
y comprobar que la terminación fue efectiva. Añadir este caso a la aceptación.

La prueba CA-07 existente mantiene vivo al padre durante el timeout. Su comprobación
del hijo es condicional a que se haya escrito el archivo PID. La parte de
interrupción usa `QA_SIMULATE_INTERRUPT`, que retorna antes de crear procesos;
por sí sola no prueba la limpieza ante una interrupción real.

### F03 — [P2] Un error al crear el snapshot deja scratch y omite el reporte

Ubicación: `qa_agent/execution.py:146–194` y `qa_agent/cli.py:333–348`.
Requisitos afectados: RF-09, RF-10; tareas E05, E07 y E09.

El scratch se crea antes de copiar archivos. La llamada a
`prepare_isolated_workspace()` ocurre antes del bloque `try/finally` de la CLI.
Si la copia falla, no se devuelve un workspace sobre el que ejecutar la limpieza
y el flujo tampoco alcanza `persist_run_evidence()`.

Contraprueba: inyectar `PermissionError` en `shutil.copy2` deja un directorio scratch
con su marcador. Una segunda comprobación por la entrada de la CLI devuelve
código 3 pero genera cero archivos `result.json`.

Corrección necesaria: proteger la preparación desde el momento de crear el scratch,
limpiarlo cuando falle una copia y finalizar un resultado de error con el mismo
identificador siempre que el directorio de evidencia sea escribible. Verificarlo
con un error de copia controlado y un centinela externo al scratch.

### F04 — [P2] El límite de salida no limita la memoria durante la captura

Ubicación: `qa_agent/execution.py:328` y `:345–350`.
Requisito afectado: límite de volumen de salida del plan, trabajo 2; tarea E05.

`proc.communicate()` acumula stdout y stderr completos. El recorte a
`MAX_CAPTURE_CHARS` se aplica cuando el proceso ya terminó o venció el timeout.
Por ello, un proceso muy verboso puede consumir memoria proporcional a toda su
salida antes de que el ejecutor aplique el supuesto límite.

La sonda moderada escribió 500.000 caracteres y recibió 128.000 con
`output_truncated=True`: confirma el recorte del resultado. La ausencia de límite
durante la lectura se constata en el código; no se provocó agotamiento de memoria.

Corrección necesaria: drenar ambos pipes de forma concurrente con buffers acotados
durante la lectura, conservando el indicador de truncamiento y el timeout. Probar
un flujo sostenido de salida con un límite pequeño, sin acumularlo completo.

## Estado frente a las tareas

| Tareas | Estado de revisión |
| --- | --- |
| B01–B05 | Referencia observacional local documentada y respaldada por la medición reproducida; mantener sus límites de entorno explícitos. |
| E01–E04 | Contratos, comandos, configuración y diagnóstico presentes; comportamiento principal comprobado en aceptación. |
| E05 | Pendiente por F02, F03 y F04. |
| E06 | Pendiente por F01. |
| E07 | Reportes normales y redacción de secretos ficticios comprobados; pendiente el error temprano de F03. |
| E08 | Dependencias fijadas y guía presentes. No se reprodujo una instalación limpia en otra PC. |
| E09 | Pendiente: deben incorporarse las contrapruebas y superar su aceptación antes de sostener el cierre total. |

## Límites de la comprobación

- Se midió Windows con Python 3.12.10. El PATH sin herramientas opcionales y el
  arranque sin paquetes se verificaron localmente; esto no certifica otra PC física,
  Python 3.11 ni Linux/macOS.
- Las 229 pruebas usan los dobles controlados ya documentados. No prueban Java real,
  un navegador conectado a servicios reales ni proveedores LLM.
- `ESTADO.md` declara una ejecución inicial en rojo. Esta revisión reproduce el
  estado verde actual; no certifica por sí misma el orden histórico de implementación.
- `baseline_metrics.json` incluye `c_tmp_touched: true`, mientras `baseline.md`
  explica directorios previos y aislamiento sin escrituras en `C:\tmp`. Falta
  documentar la semántica de ese indicador o su medición para eliminar esa
  ambigüedad. No se usa ese booleano aislado para afirmar una escritura nueva.

## Qué falta para cerrar

Resolver F01–F04 y añadir las contrapruebas a `qa_tests/`; repetir la aceptación y
la suite Python del producto; actualizar `tasks.md` y `ESTADO.md` con el resultado
observado y las limitaciones que sigan presentes. Estos ajustes pertenecen al
trabajo 2 y no requieren anticipar las integraciones de trabajos posteriores.

Esta revisión añade el informe y evidencia de auditoría; no corrige la implementación.
