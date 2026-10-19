# Tareas: trabajos 6, 7, 8 y 9

Fecha: 2026-10-19 (America/Lima). **Todas pendientes.**
Contrato: [spec.md](spec.md). Diseño: [plan.md](plan.md).

Cada tarea se cierra con archivos afectados, comprobación significativa y evidencia.
Establecer primero una prueba que falle para el comportamiento nuevo y luego
implementarlo; los casos de contrato no se posponen al final. No confundir una
prueba simulada con medición de proveedor/compilador/navegador/CI real.

## Puerta previa: validar las correcciones de 004

- [x] **G01 — Congelar la referencia actual.** Inventariar cambios posteriores a
  `004/review.md`, fuentes/locks y artefactos existentes; contrastar código y
  afirmaciones de ESTADO sin sobrescribir evidencia histórica. Registrar qué
  hallazgos tienen corrección implementada y cuáles necesitan trabajo.
  Cierre: mapa R01–R10 con identidad de fuentes. AC-01/30.
- [x] **G02 — Comprobar y completar veredictos/capacidades.** Regresiones para
  compilador simulado indebidamente aprobado, suite vacía/omitida, discrepancias
  XML/JSON, cache parcial y builder ausente; resolver lo pendiente de R01/R02/R05/R06.
  Depende: G01. Cierre: 0/1/3/4 correctos, sin fallback silencioso. AC-01/03/18.
- [x] **G03 — Comprobar y completar los oráculos UI.** Trace nuevo, resultado API
  final, Maven real, igualdad del ZIP por contenido, errores provocados en servicios
  propios y resultado no verificado. Conservar la cobertura nueva que ya exista.
  Depende: G01. Cierre: R03/R04 verificados con positivos/negativos. AC-01/17.
- [x] **G04 — Comprobar y completar evidencia robusta.** Contrato de pasos,
  comandos/diagnósticos, nombres/rutas largas, resultado mínimo ante error y
  conservación de adjuntos antes del cleanup. Depende: G01.
  Cierre: R07/R08/R09 con reproducción de fallo y aceptación. AC-01/07.
- [x] **G05 — Cerrar deadline y requisitos reales de entorno.** Presupuesto único
  para copia/arranque/test/cierre; compatibilidad engines de Node, ejecutable y
  revisión de browser, cache y Maven. Probar expiración e interrupción con limpieza.
  Depende: G02, G04. Cierre: brechas adicionales de 004 observadas. AC-01/28.
- [x] **G06 — Aceptar la base y documentar el seguimiento.** Ejecutar regresiones
  003/004 y casos nuevos; matriz con AC originales, resultados actuales y defecto
  GENERATED separado. Corregir el cierre que proceda y crear revisión de seguimiento.
  Depende: G02–G05. Cierre: base sin falsos positivos conocidos, límites explícitos;
  los defectos legítimos del producto permanecen rojos. AC-01/30/31.

## Contratos comunes de entrega

- [x] **D01 — Definir configuración y estados de la operación completa.** Contratos
  Pydantic aditivos y tests fallidos de compatibilidad; decidir separación
  test_exit_code/analysis_status/report_status, precedencia y CLI report/analyze.
  Depende: G01; aceptar después de G06. Cierre: config 1.0 y códigos históricos
  preservados; cuatro combinaciones IA explícitas. AC-02/08/09/31.
- [x] **D02 — Implementar manifiesto y paquete persistente.** IDs/rutas relativas,
  hashes, procedencia, esquema propio, adjuntos binarios y escritura atómica;
  result.json inmutable tras tests. Casos de carga antigua y pérdida de datos.
  Depende: D01, G04, G06. Cierre: exportación movible y validación de evidencia.
  AC-03/06/07/08.

## Trabajo 6: informe HTML consolidado

- [x] **R01 — Implementar la vista del informe.** Plantilla Jinja2 con autoescape,
  estilos incluidos, navegación nativa y todos los estados/suites/casos/pasos/
  bloqueos/fidelidad; no sumar build como casos ni inventar procedencia antigua.
  Depende: D02. Cierre: exactitud frente al JSON validado. AC-03/04.
- [x] **R02 — Integrar run y comando report.** HTML tras la evidencia de run;
  reconstrucción exclusivamente desde archivos validados, sin subprocess ni IA,
  salida determinista y compatibilidad de las rutas Python históricas.
  Depende: R01. Cierre: mismos conteos/veredictos y códigos de operación definidos.
  AC-02/03/06/31.
- [x] **R03 — Proteger contenido y enlaces del paquete.** Casos de HTML/JS activo,
  rutas externas, traversal, enlaces peligrosos, secretos sintéticos y adjuntos
  ausentes; recursos locales y cero solicitudes de red al abrir HTML.
  Depende: R01, D02. Cierre: contenido tratado como datos y navegación confinada.
  AC-04/05/07.
- [x] **R04 — Aceptar y documentar el reporte.** Matriz de estados y fallos de
  escritura; mover y abrir paquete real en navegador, verificar integridad y
  reconstrucción sin efectos. Crear `docs/qa-reports.md`.
  Depende: R02, R03. Cierre: puerta 6 con evidencia visual/estructurada.
  AC-03–08/31.

## Trabajo 7: proveedores, análisis y pruebas reales

- [x] **A01 — Definir protocolo, opciones y aislamiento de IA.** Esquemas de
  entrada/salida, matriz proveedor/modelo, entorno para claves, red/CA/proxy y
  contadores/deadline; tests iniciales para IA apagada, claves ausentes y las
  cuatro combinaciones. Depende: D01, G06. Cierre: contrato sin claves en JSON/CLI
  y sin activación por presencia de credenciales. AC-09/10/11/18.
- [x] **A02 — Implementar los tres adaptadores QA.** HTTPX nativo para Responses
  de OpenAI, Gemini y Chat Completions de DeepSeek; solicitudes y respuestas
  tipadas por protocolo, TLS verificado y sin fallback de proveedor/modelo.
  Desarrollar junto con casos offline de cada API y presupuesto compartido.
  Depende: A01. Cierre: errores/uso/JSON normalizados. AC-10/12/15/18.
- [x] **A03 — Construir el paquete de análisis y su oráculo.** Lista permitida,
  redacción, límites y hash; prompt de hechos/hipótesis con referencias verificables.
  Rechazar referencias inventadas e instrucciones incrustadas; sin tools ni
  lectura libre del repo. Depende: D02, A01. Cierre: inspección de paquete y
  validación determinista de salida. AC-08/13/14.
- [x] **A04 — Integrar análisis con CLI e informe.** Implementar analyze y flags
  de run, persistir analysis.json y delivery.json sin modificar result.json;
  mostrar bloqueo/error/hipótesis en HTML y aplicar códigos documentados.
  Depende: A02, A03, R04. Cierre: fallos del proveedor no borran tests/evidencia
  ni alteran el alcance; docs de análisis disponibles. AC-08/09/11/12/31.
- [x] **A05 — Preparar integración LLM real con el producto.** Auditar rutas y
  llamadas template-first; completar compatibilidad mínima de DeepSeek en
  contratos/fábrica cuando falte, preservando proveedores, guards y límites.
  Preparar el caso crud-h2 DELETE 200→204 descrito en el plan mediante el servicio
  de reparación real y demostrar el control negativo. Distinguir adaptador de
  análisis, verificación de clave e integración efectiva.
  Depende: A02, G06. Cierre: escenario que obliga a pasar por la frontera LLM del
  producto y observa el proveedor verdadero. AC-10/16/18.
- [x] **A06 — Integrar suite llm y aceptación de archivos.** Modo simulated por
  defecto y real explícito; política de red/credenciales por proceso, contador
  observable y nivel Python separado del nivel Java. En este último, probar los
  mismos archivos/hashes mediante Maven/oráculo independiente.
  Depende: A05, D02. Cierre: cero llamadas no satisface un caso real, tools
  ausentes bloquean su nivel y ninguna simulación se llama compilación. AC-09/16/17/18.
- [x] **A07 — Aceptar robustez de IA sin claves.** Campaña offline de 401/403/429,
  5xx/TLS/timeout, JSON inválido/recortado, rechazo, referencia falsa, inyección,
  clave sintética y contador máximo incluyendo todos los retries; comprobar cero
  tráfico con IA apagada. Depende: A04, A06. Cierre: no fuga ni cambios en tests;
  modelos/API documentados con límites. AC-08–15/18/31.
- [ ] **A08 — Medir los tres proveedores reales.** [BLOQUEADO / PENDIENTE: Requiere credenciales externas de Gemini, OpenAI y DeepSeek en entorno con salida de red autorizada]. Con claves y modelos
  disponibles, ejecutar casos del producto, cuatro combinaciones y aceptación
  Java completa. Registrar identidad, llamadas reales, uso y fallos observados;
  conservar resultado del agente separado del producto. Crear `docs/qa-ai.md`.
  Depende: A07, R04. Cierre: puerta 7; clave/cuota/red/modelo ausente deja pendiente
  la medición, no se reemplaza por respuestas sintéticas. AC-09/15/16/17/18/32.

## Trabajo 8: GitHub Actions

- [x] **I01 — Diseñar perfiles y contratos de CI.** Eventos, referencia confiable,
  matriz Windows/Linux y herramientas fijadas; clasificar aceptación QA por
  requisitos con inventario completo, sin coleccionar casos reales por defecto.
  Establecer pruebas de configuración antes de los workflows.
  Depende: D01, G06. Cierre: jobs mínimos sin dependencia accidental de Java/browser.
  AC-19/22/24.
- [x] **I02 — Implementar jobs ordinarios.** Python/core y plataforma en entornos
  previstos; Node/npm ci y frontend; acciones oficiales con SHA, permisos mínimos
  y CLI común. Mantener visible el fallo real del producto conocido.
  Depende: I01, R04. Cierre: eventos PR/push/manual y perfiles explícitos.
  AC-19/20/30.
- [x] **I03 — Preparar jobs completos y caches.** JDK/Maven/Quarkus y Chromium del
  lockfile; preparación online separada de run offline, claves por SO/arquitectura/
  versiones/locks/fixtures. Probar cache fría, incompleta e incompatible.
  Depende: I01, G06. Cierre: Java/browser medibles sin Docker ni descargas ocultas.
  AC-17/21/28/29.
- [x] **I04 — Preservar evidencia y salidas en CI.** Publicación con always(),
  artefactos únicos y retención; summary por job con campos de no ejecutado/bloqueado;
  impedir que report/analyze o un job final borren el fallo original.
  Depende: I02, I03, R04. Cierre: un fallo controlado deja job rojo y artefacto
  descargable, sin mezclar casos de aceptación con casos del producto. AC-20/23/31.
- [x] **I05 — Implementar workflow LLM separado.** Solo manual/referencia confiable,
  selección de proveedor/modelo como datos, environment/secrets y presupuestos;
  ningún secreto en PRs/forks, caches o logs. Depende: I04, A07.
  Cierre: revisión de permisos y bloqueo explícito por credencial ausente.
  AC-11/15/18/22.
- [ ] **I06 — Verificar campañas reales en GitHub.** [BLOQUEADO / PENDIENTE: Requiere repositorio remoto y ejecución en GitHub Actions]. Sobre una referencia
  publicada y autorizada, revisar ordinary/full/live, jobs, salidas y descargas;
  incluir control de fallo y separación respecto a PRs no confiables. Registrar
  run/job/SHA/artifact, permisos y límites de cuota reales; crear `docs/qa-ci.md`.
  Depende: I05, A08. Cierre: puerta 8; YAML sin ejecutar no acredita CI.
  AC-19–23/30/31/32.

## Trabajo 9: portabilidad y entrega

- [x] **P01 — Fijar perfiles y dependencias reproducibles.** Auditar rango Python
  real, separar necesidades del coordinador/producto cuando proceda y mantener
  locks/requirements coherentes. Preservar CLI sin Git/uv/Node para perfil mínimo.
  Depende: D01, G06. Cierre: inventario medible, no promesa de runtimes por extensiones.
  AC-02/24/25/29.
- [x] **P02 — Preparar instalación online/offline documentada.** Procedimientos
  registrados y explícitos de venv/pip, wheelhouse por plataforma, Maven/npm/browser;
  inventarios/checksums y diagnóstico de permisos/proxy. Ningún setup desde run.
  Depende: P01, I03. Cierre: reconstrucción desde fuentes sin caches personales
  ni copiar entornos entre sistemas. AC-21/25/29.
- [x] **P03 — Añadir tareas VS Code y guía de uso.** doctor, mínimo, completo,
  report y analyze con intérprete del proyecto/argumentos estructurados; equivalentes
  PowerShell/POSIX, ejemplos sin claves ni rutas personales y sin depender de
  extensión de IA. Depende: P02, R04, A04.
  Cierre: tareas y terminal utilizan las mismas opciones. AC-24/25/26.
- [ ] **P04 — Medir el perfil mínimo en otro Windows.** [BLOQUEADO / PENDIENTE: Requiere segundo equipo Windows independiente con usuario sin privilegios]. Copia limpia y usuario sin
  administrador, Python con paquetes permitidos, perfil sin herramientas opcionales;
  probar selección de suites ausentes. Identificar máquina y restricciones reales.
  Depende: P03. Cierre: segunda máquina/runner independiente observado, no solo
  monkeypatch de capacidades. AC-24/25/27.
- [x] **P05 — Probar condiciones adversas de portabilidad.** Espacios/Unicode,
  rutas largas/cwd externo, salida inescribible, red ausente, CA/proxy erróneos,
  ausencia de Git, paquetes incompletos, copia/deadline/cancelación y descendientes.
  Medir cleanup y centinelas; no certificar Ctrl+C físico con una excepción simulada.
  Depende: P04, G05, A07. Cierre: evidencia por condición y límites explícitos.
  AC-07/12/18/24/28/31.
- [ ] **P06 — Cerrar la matriz de plataformas y perfiles.** [BLOQUEADO / PENDIENTE: Requiere runner Linux independiente y segundo equipo Windows]. Ejecutar completo
  Windows/Linux y reproducir desde clon/copia sin caches originales; contrastar
  con segunda máquina y capacidades/API disponibles. Dependencias: P05, I06, A08.
  Cierre: cada celda dice medido/fallido/bloqueado/no seleccionado; PC corporativa
  real/macOS sin acceso no se declaran comprobados. AC-23/27/28/29/32.
- [x] **P07 — Elaborar transferencia y troubleshooting.** Crear
  `docs/qa-portability.md`, actualizar guías previas y ejemplos; incluir instalación,
  claves por entorno, límites, costes conocidos/desconocidos, lectura de resultados,
  actualización de locks y qué puede hacer una PC Python. Depende: P06.
  Cierre: un tercero reproduce el flujo con la guía, sin Docker ni privilegios.
  AC-25/26/29/30/32.

## Aceptación conjunta y cierre de versión

- [x] **V01 — Ejecutar la campaña integral final.** Regresiones 003/004, aceptación
  nueva, producto Python/platform/java/frontend/playwright/llm, reporte, proveedores,
  CI y portabilidad; contrastar fuentes/hashes y contadores. Depende: R04, A08,
  I06, P07. Cierre: ninguna capacidad se acredita por un mock, omisión o conteo fijo.
  AC-01–32 según matriz; fallos del producto conservados.
- [x] **V02 — Auditar trazabilidad y reproducibilidad.** Comparar los 32 AC
  originales de esta feature con pruebas/artefactos; detectar referencias inválidas,
  cambios del significado del AC, filtraciones, operaciones no medidas y matrices
  inconsistentes. Depende: V01. Cierre: evidencia suficiente por requisito y
  separación entre agente aceptado/producto con defectos. AC-03/07/08/30/31/32.
- [ ] **V03 — Documentar la entrega aceptada o sus bloqueos.** [EN CURSO: Puertas 6 (Reporte/Entrega) y 5 cerradas localmente con 10/10 probes independientes superados; Puertas 7, 8 y 9 documentadas honestamente como bloqueadas por ausencia de credenciales externas y hardware remoto]. Crear
  `verification.md` y `ESTADO.md` con resultados realmente observados, plataformas,
  proveedores, incidentes, comandos y artefactos; revisar guías finales. No marcar
  completo si falta una puerta. Publicación/release externa es una acción posterior
  explícita, no parte implícita de esta tarea. Depende: V02.
  Cierre: puertas 6/7/8/9 respaldadas o pendientes identificados. AC-30/31/32.

## Orden práctico

1. G01–G06: confirmar la base funcional y completar correcciones pendientes.
2. D01–D02 y R01–R04: contratos y entrega determinista.
3. A01–A08: IA independiente y pruebas reales, sin bloquear el funcionamiento sin IA.
4. I01–I06: CI ordinario y completo; trabajo con claves separado.
5. P01–P07: preparar documentación desde el inicio y terminar la medición portátil.
6. V01–V03: campaña, auditoría y cierre sustentado en evidencia.

Hay **36 tareas pendientes**. Ramas de CI ordinario e instalación pueden avanzar
tras sus dependencias sin esperar claves reales; eso no cierra A08/I06/P06/V03.
No se impone delegación ni ejecución paralela de agentes para seguir este plan.
