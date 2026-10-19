# Revisión independiente de los trabajos 3, 4 y 5

Fecha: 2026-10-19 (America/Lima).

## Veredicto

**Hay implementación y ejecución reales, pero el incremento no satisface todavía
su criterio de cierre.** El estado «100% COMPLETADO Y ACEPTADO» de `ESTADO.md` y
`verification.md` no está respaldado por la revisión independiente.

Se compararon el código, `spec.md`, `plan.md`, las 28 tareas y los artefactos de
ejecuciones nuevas. No se modificó la implementación ni sus expectativas. Los
controles adicionales están separados en `.agentia-runtime/qa-review-004/`.

## Qué se volvió a ejecutar

| Comprobación | Resultado observado |
| --- | --- |
| Regresión histórica mediante `qa_agent run --suite python` | **229/229 aprobadas**, 10.619 s. |
| Aceptación completa: `pytest qa_tests` | **32 aprobadas, 1 fallida**, 484.93 s. El fallo es la persistencia de evidencia Java en una ruta larga de Windows. |
| Repetición focalizada Java con ruta corta | **3/3 pruebas de aceptación aprobadas**, 250.29 s: positivos **76/76 Surefire**; los dos controles negativos producen FAILED/1 como corresponde. |
| Regresiones de la fundación, incluidas F01–F04 | **17/17 aprobadas**, dentro de la aceptación completa. |
| Base compartida nueva | **7/7 aprobadas**, dentro de la aceptación completa. |
| Plataforma por HTTP | Sus seis escenarios positivos pasan. El escenario separado de persistencia GENERATED falla como se esperaba y el agente devuelve FAILED/1. |
| Frontend real | **53/53 casos Vitest aprobados**, `tsc -b` y `vite build` aprobados. El informe anterior menciona 44; esa cifra no es la medición actual. |
| Playwright con entorno preparado | **3/3 casos aprobados** con Chromium real. Esto acredita la ejecución de los casos existentes, no las aserciones que faltan. |
| Playwright con caché Java que contiene únicamente `.prepared.json` | **3/3 aprobados, salida global 0**, pese a iniciar `mode=platform` y usar compilador doble. Falso positivo reproducido con navegador real. |
| Java con caché parcial `io/quarkus/` sin artefactos | Devuelve **ERROR/3**, en lugar del **INCOMPLETE/4** exigido para dependencias ausentes. |
| Controles pequeños del veredicto de adaptadores | Reproducen aprobación con un caso omitido, cero casos, discrepancia XML/JSON y ausencia de los ejecutables de TypeScript/Vite. |

La primera invocación de pytest falló porque faltaba el padre de mi `--basetemp`.
Se preparó la carpeta y se repitió. Ese error del comando de revisión queda
excluido de los defectos atribuidos al proyecto.

## Hallazgos

### R01 — [P1] Playwright puede aprobar compilación simulada y anunciar Maven real

Ubicaciones: `qa_agent/adapters/playwright.py:119–147`,
`qa_agent/capabilities.py:323–332`, `qa_agent/cli.py:285–310`.

El diagnóstico acepta como caché Java preparada la existencia de `.prepared.json`.
El adaptador Playwright, sin embargo, decide usar `mode=platform` cuando no encuentra
`io/quarkus`, en vez de bloquear la suite. Esa modalidad sustituye el compilador.
Después, el resumen deduce «Maven real» de que la suite terminó PASSED/FAILED.

Reproducción real: se creó una carpeta vacía con solo `.prepared.json` y se ejecutó:

```powershell
.\.venv\Scripts\python.exe -m qa_agent run --suite playwright --java-cache-dir .agentia-runtime/qa-review-004/marker-only-java-cache --output-dir .agentia-runtime/qa-review-004/pw-compiler-double
```

La ejecución `qa-20261019T064113Z-dd06e76a` aprobó tres casos en 41.048 s.
`playwright/suite_result.json` registra `mode=platform`; el resultado global anuncia
verificación Maven/Quarkus real. Incumple RF-305/306/310 y la puerta del trabajo 5.

Corrección necesaria: unificar los requisitos del diagnóstico y del adaptador,
prohibir la degradación automática del caso integrado y derivar el alcance de
evidencia efectiva del compilador, no del nombre/estado de la suite.

### R02 — [P1] El adaptador Playwright convierte INCOMPLETE en PASSED

Ubicación: `qa_agent/adapters/playwright.py:308–337`.

Los normalizadores detectan INCOMPLETE, pero el adaptador solo propaga ERROR y
FAILED. Compara únicamente el total de casos entre XML y JSON. Reproducciones
controladas, ejecutando el adaptador real y sustituyendo solo sus procesos:

| XML / JSON suministrados | Veredicto real del adaptador |
| --- | --- |
| Un aprobado y un omitido, concordantes | PASSED/0, con `skipped=1`. |
| Ambos vacíos | PASSED/0, con `collected=0`. |
| XML: dos aprobados; JSON: un aprobado y un omitido | PASSED/0. |

Al combinar la suite vacía con una suite Python aprobada, la función de agregación
también devuelve PASSED/0. No se trata solo de una etiqueta interna. Incumple
RF-302/311 y AC-18; debe preservarse INCOMPLETE/4 y compararse el desglose completo.

### R03 — [P1] El recorrido positivo no comprueba el resultado final ni la identidad del ZIP

Ubicación: `frontend/e2e/studio.spec.ts:24–112`.

Aunque recibe el fixture `request`, no lo utiliza para contrastar la ejecución con
la API. Se acepta cualquier respuesta coincidente de `/v1/blueprint/run` o
`/v1/runs` con HTTP <400 y se espera que vuelva a habilitarse el botón. No se exige
`trace_id` nuevo, resultado terminal SUCCESS, `verification.success`, ni evidencia
de Maven. Un 202 solo confirma aceptación de la solicitud.

El ZIP solo debe contener `pom.xml` y algún `.java`. No se comprueban las pruebas
esperadas ni la igualdad de contenido/huellas con `generated_files`. Un paquete
de otra ejecución o con fuentes incorrectas puede satisfacer el oráculo.
El falso positivo real de R01 demuestra que los casos actuales no exigen el nivel
de verificación declarado. Incumple AC-14/15 y U05.

Corrección necesaria: capturar la solicitud de generación concreta, comprobar
su identidad y resultado final por API y comparar rutas y contenidos del ZIP con
esa ejecución. Añadir controles de resultado no verificado y paquete incorrecto.

### R04 — [P2] Los negativos del navegador no demuestran fallos del backend real

Ubicación: `frontend/e2e/studio.spec.ts:115–153`.

El caso de autenticación puede terminar sin realizar ninguna aserción: tanto la
apertura de configuración como la comprobación del error están dentro de `if
(isVisible())`. Además, intercepta `**/v1/runs/**`, que no cubre necesariamente el
listado `/v1/runs` sin barra final ni la petición de conexión real.

Ambos casos negativos fabrican respuestas con `route.fulfill`, sin provocar el
fallo en los servicios propios como exige el plan. Tampoco existe el recorrido
del resultado generado pero no verificado requerido por AC-16/U06.

Corrección necesaria: usar una clave sintética incorrecta y detener/provocar el
fallo del servicio del harness; exigir la interacción y la respuesta esperadas
sin ramas que permitan aprobar sin comprobarlas. Conservar las simulaciones como
pruebas de interfaz separadas si se consideran útiles.

### R05 — [P2] Una caché Maven parcial se clasifica como fallo del ejecutor

Ubicación: `qa_agent/adapters/java.py:354–360` y `685–693`.

La presencia del directorio `io/quarkus` basta para iniciar la suite. Cuando
Maven informa que faltan dependencias offline, el propio adaptador reconoce
«Caché Maven offline incompleta» y activa `has_execution_error`, devolviendo 3.

Se ejecutó realmente `crud-h2` con un repositorio vacío que solo contenía ese
directorio. Resultado: `qa-20261019T064300Z-dab4ebaf`, ERROR/3, cero casos y
diagnóstico de extensión Quarkus ausente. No se observó cambio a descarga online;
el defecto es la clasificación. RF-313 y AC-11 exigen INCOMPLETE/4, diferenciándolo
del código roto y de un error del ejecutor.

### R06 — [P2] Frontend puede aprobar sin ejecutar TypeScript ni build

Ubicación: `qa_agent/adapters/frontend.py:378–380` y `436–438`.

Los pasos obligatorios solo se ejecutan si existe el archivo de su CLI. Su
ausencia no produce bloqueo ni error. El diagnóstico comprueba directorios de
paquetes, no estos archivos. Un paquete incompleto o una discrepancia entre
diagnóstico y ejecución permite omitirlos silenciosamente.

Control del adaptador: con Vitest aprobado y sin `typescript/bin/tsc` ni
`vite/bin/vite.js`, devolvió PASSED/0 y únicamente los pasos de preparación/Vitest.
Incumple AC-13/U03. Validar esos ejecutables y registrar INCOMPLETE cuando falten.

### R07 — [P2] El contrato elimina comandos y diagnósticos del resultado global

Ubicaciones: `contracts/models.py:451–458`, `qa_agent/evidence.py:214–221`.

Los adaptadores emiten `kind`, `command` y `diagnostic`, pero `QASuiteStepResult`
declara `description`, `message` y otros campos diferentes. Al validar y hacer
`model_dump`, Pydantic descarta los datos adicionales. El resultado por suite se
guarda antes de esa validación y conserva los datos; el consolidado los pierde.

Comprobado sobre la ejecución real de R01: el resultado por suite conserva
`command: ["start_service_harness", "mode=platform"]`; el global tiene descripción
vacía y mensaje null. Esto oculta información material para interpretar el
alcance. Alinear el contrato y añadir una comprobación de ida y vuelta de los
datos, preservando comandos, diagnóstico y procedencia exigidos por C02/C04/V03.

### R08 — [P2] La evidencia Java falla en rutas largas y queda sin resultado mínimo

Ubicaciones: `qa_agent/evidence.py:188–192`, `qa_agent/cli.py:423–430`.

La aceptación completa falló al escribir un nombre Surefire de **262 caracteres**:

```text
.../qa-java-pos/qa-20261019T064059Z-444a0034/java/solution-h2/order-service/verifier/TEST-com.agentia.qa.orders.repository.OrderRecordRepositoryTest.xml
```

La excepción se convirtió en salida 3, pero la escritura se había detenido antes
de generar `result.json`. Quedaron artefactos parciales, sin veredicto persistido.
Es un fallo de persistencia del agente, no prueba de que las fuentes Java no
compilen. Afecta RF-312/315 y AC-17 en este Windows.

Corrección necesaria: acotar nombres/rutas de artefactos o usar un mecanismo
compatible con rutas largas, y persistir un resultado mínimo cuando la escritura
de un adjunto falla. La evidencia incompleta debe conservar su diagnóstico.

Se repitió únicamente `qa_tests/test_java_adapter.py` con
`--basetemp=.agentia-runtime/r4java`: **3 aprobadas en 250.29 s**. Los positivos
aprobaron 76 casos en 192.0448 s y la solución devolvió SUCCESS con ambos servicios
VERIFIED. Los negativos terminaron FAILED/1 en 57.5393 s: siete casos aprobados y
tres fallidos, incluyendo el control de compilación y las aserciones controladas.
La ruta equivalente del primer informe fallido se reduce de 262 a 240 caracteres.
Este cambio del lugar de evidencia permite confirmar el funcionamiento Java; no
corrige la persistencia del agente ni convierte la primera campaña en aprobada.

### R09 — [P2] Los adjuntos de fallo Playwright se borran antes de entregarlos

Ubicación: `qa_agent/adapters/playwright.py:211–213`, `247–273`, `403–409`.

La configuración genera trazas/capturas en el scratch y el JSON puede referirlas.
El adaptador solo exporta log/XML/JSON y luego elimina el workspace completo en
`finally`. No copia trazas, capturas ni otros adjuntos a la evidencia persistente.
Configurar `retain-on-failure` no acredita su conservación. Incumple U06 y parte
de AC-17. Recolectar adjuntos propios antes del cleanup y actualizar sus rutas;
comprobarlos con un caso de navegador deliberadamente fallido.

### R10 — [P2] El cierre sustituye los criterios originales y omite un defecto conocido

Ubicación: `specs/004-test-agent-functional-coverage/verification.md:24–43` y
su sección de defectos.

La matriz cambia el significado de varios identificadores: AC-08 original trata
de GENERATED/VERIFIED y persistencia tras reinicio; el cierre lo sustituye por
ejecutar Maven. AC-12 original exige procedencia de informes; el cierre lo reduce
al rechazo de dry_run. AC-17 original incluye recuperación de evidencia y cleanup;
se sustituye por workers/retries. No son comprobaciones equivalentes.

`test_platform_adapter.py` acepta correctamente como diagnóstico la detección del
defecto real GENERATED→RUNNING tras reinicio. La nueva ejecución lo confirmó,
pero el informe no lo registra entre los defectos pendientes del producto.
Además, la guía y el cierre llaman 2 a la interrupción, aunque el código y la
especificación preservan 130. La medición actual de Vitest es 53, no 44.
La repetición Java midió 76 casos positivos, frente a los 55 del informe anterior.

Corrección necesaria: conservar literalmente la identidad de los AC originales,
trazar cada comprobación real, separar capacidad del agente y estado del producto,
y corregir los estados/documentación después de resolver los hallazgos técnicos.

## Cobertura frente a los criterios originales

| Criterios | Evaluación de esta revisión |
| --- | --- |
| AC-01/02 | Implementados; aceptación de capacidades y alias aprobada. |
| AC-03 | Despacho/configuración compatibles; contrato de pasos incompleto (R07). |
| AC-04/05/06/07 | Cobertura HTTP sustancial ejecutada; escenarios positivos y negativos del harness observados. |
| AC-08 | Defecto real de persistencia detectado correctamente. Debe constar en la matriz del producto; no certifica que la persistencia funcione. |
| AC-09/10/12 | Compilación y oráculos reales ejecutados: 76 positivos y controles negativos detectados. Persistencia de evidencia y procedencia aún requieren correcciones; la repetición con ruta corta no resuelve R07/R08. |
| AC-11 | Ausencia total cubierta; caché parcial mal clasificada (R01/R05). |
| AC-13 | Vitest y build reales aprobados; omisión silenciosa de builders aún posible (R06). |
| AC-14/15/16 | Parciales; faltan los oráculos completos e integración negativa exigidos (R01/R03/R04). |
| AC-17 | Limpieza/buffers previos aprobados; falta robustez de persistencia y conservación de adjuntos (R08/R09). |
| AC-18 | Regresiones Python aprobadas; falsos positivos nuevos impiden el cierre (R02). |

Otra brecha por inspección: no hay un deadline que domine toda la suite. La copia
de dependencias usa `subprocess.run` sin timeout; Java usa un timeout completo
por petición y mínimos de 15 s por paso; Playwright concede al menos 30 s incluso
si su presupuesto terminó. La guía debe explicar cómo preparar dependencias y
caches desde un clon nuevo, no solo enumerar las carpetas de esta PC. Estas
comprobaciones deben incorporarse al cierre de C05/J01/U04/V02.
También debe alinearse la detección de Node con `engines` del paquete fijado:
el Playwright instalado/registrado en el lockfile es 1.64.1 y exige Node >=20,
mientras el diagnóstico y la guía aceptan >=18.

## Evidencias y reproducción

Raíz de evidencia local: `.agentia-runtime/qa-review-004/`.

- `source-hashes.json`: huellas de código, pruebas y especificación revisados.
- `acceptance.junit.xml`: 33 casos de aceptación; 32 aprobados y un fallo.
- `acceptance-runs-summary.json`: resultados de los subruns de aceptación.
- `product/qa-20261019T064015Z-f8c57582/result.json`: regresión Python 229/229.
- `pw-compiler-double/qa-20261019T064113Z-dd06e76a/`: falso positivo real R01.
- `java-partial-cache/qa-20261019T064300Z-dab4ebaf/`: control real R05.
- `java-short-path.junit.xml`: repetición focalizada Java, tres aprobadas.
- `.agentia-runtime/r4java/test_j03_j04_j06_real_java_sui0/`: evidencia Java de
  la repetición con ruta corta, conservada en esa ubicación para evitar R08:
  `qa-java-pos/qa-20261019T064730Z-1c9bd367/` y
  `qa-java-neg/qa-20261019T065043Z-e0516302/`.
- `independent_probes.py` y `independent-probes.json`: controles reproducibles
  de R02/R06. Usan reportes/procesos sintéticos y se identifican como tales; no
  se contabilizan como pruebas reales del producto.

Comando de aceptación completa:

```powershell
.\.venv\Scripts\python.exe -m pytest qa_tests -q --basetemp=.agentia-runtime/qa-review-004/acceptance-tmp --junitxml=.agentia-runtime/qa-review-004/acceptance.junit.xml
```

Repetición focalizada:

```powershell
.\.venv\Scripts\python.exe -m pytest qa_tests/test_java_adapter.py -q --basetemp=.agentia-runtime/r4java --junitxml=.agentia-runtime/qa-review-004/java-short-path.junit.xml
```

Las huellas de los archivos de implementación y pruebas no cambiaron entre el
inicio de la medición y la comprobación final de integridad.

## Qué falta para cerrar

1. Corregir los falsos positivos y completar los oráculos de Playwright (U05–U07).
2. Corregir cachés parciales, builders ausentes, contrato de evidencia y rutas largas.
3. Conservar adjuntos de fallos y aplicar un presupuesto total a cada suite.
4. Añadir regresiones que fallen con esos defectos y repetir la aceptación completa.
5. Actualizar V02/V03 con los AC originales, la evidencia nueva y el defecto del
   producto separado. Solo entonces cambiar el estado del incremento a aceptado.

La comprobación se hizo en este Windows. No acredita otra PC ni Linux/macOS.
No se instalaron herramientas, no se llamaron proveedores LLM reales y no se
implementaron correcciones durante esta revisión.
