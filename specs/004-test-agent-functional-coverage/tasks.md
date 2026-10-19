# Tareas ejecutables: trabajos 3, 4 y 5

Estado inicial: todas pendientes. Documentos: [spec.md](spec.md), [plan.md](plan.md).
La creación del plan no inicia su ejecución. Cada cierre debe registrar evidencia,
dependencias, archivos afectados y criterios AC satisfechos.

## Base compartida para los nuevos adaptadores

- [x] **C01 — Congelar la referencia del incremento anterior.** Revisar contratos,
  tareas y evidencia vigente; registrar fuentes/huellas y dependencias. Confirmar
  las regresiones F01–F04 antes del refactor y mantener separados resultados
  históricos y nuevas mediciones. Cierre: referencia reproducible y límites explícitos.
- [x] **C02 — Especificar contratos y aceptación multimotor.** Definir los modelos
  Pydantic aditivos, identidad de casos, pasos, metadatos de motor y política de
  estados. Establecer casos fallidos de AC-01/02/03/18 antes de implementar.
  Depende: C01. Cierre: configuración anterior compatible y semántica definida.
- [x] **C03 — Generalizar catálogo, configuración y despacho.** Añadir `platform`,
  adaptadores registrados, requisitos por suite, alias deduplicados y timeouts por
  suite. Mantener `python` predeterminado e interfaces de pruebas anteriores.
  Depende: C02. Cierre: AC-01/02/03 sin ejecutar suites equivocadas.
- [x] **C04 — Separar evidencia y normalización.** Implementar resultados por
  suite/motor y validadores de reportes, conservar la evidencia histórica Python
  y evitar sobrescrituras. Probar XML/JSON ausente, contradictorio y antiguo.
  Depende: C03. Cierre: RF-302/308/311, AC-02/03/12/18.
- [x] **C05 — Ampliar snapshots y ciclo de procesos.** Definir recursos por suite,
  procesos persistentes, buffers, puertos, preparación acotada y cleanup. Establecer
  aceptación de fallo de copia/arranque, hijo huérfano, interrupción y salida masiva.
  Depende: C03. Cierre: RF-312/314; F02/F03/F04 y AC-04/17 preservados.
- [x] **C06 — Preparar fixtures y política de entorno.** Versionar blueprints,
  expectativas independientes, claves sintéticas, bloqueo de proveedores y datos
  de prueba. Definir preparación Node/Chromium/Maven y capacidades necesarias,
  sin descargas dentro de `run`. Depende: C04, C05. Cierre: RF-305/307/313.

## Trabajo 3: plataforma por HTTP real

- [x] **P01 — Construir el harness local de cinco servicios.** Usar aplicaciones
  de producción, estado temporal, puertos dinámicos y healthchecks. Dobles solo en
  fronteras LLM/compilador. Demostrar primero fallo de servicio y puerto ocupado.
  Depende: C06. Cierre: AC-04 y retirada de procesos propios.
- [x] **P02 — Cubrir autenticación y entradas inválidas.** Probar claves, gateway,
  JSON/esquema y validación de negocio con contratos esperados explícitos.
  Depende: P01. Cierre: AC-05 sobre sockets, no solo TestClient.
- [x] **P03 — Cubrir ejecución asíncrona y persistencia.** Comprobar 202, identidad,
  estado terminal, detalle/listado y recuperación tras reiniciar el orquestador.
  Incluir solución GENERATED y registrar defectos de persistencia reales.
  Depende: P02. Cierre: AC-06/08.
- [x] **P04 — Cubrir fallos y reparación acotada.** Provocar 5xx, respuesta
  inválida, caída, timeout, parche rechazado/sin cambios y presupuesto agotado.
  Validar orden y efectos, con dobles externos declarados y cero llamadas LLM.
  Depende: P03. Cierre: AC-07; ningún bucle ilimitado.
- [x] **P05 — Verificar concurrencia y aislamiento.** Dos runs de aplicación y
  dos harness QA, con SQLite/workspaces separados, centinelas y cierre comprobado.
  Depende: P04. Cierre: AC-04/17.
- [x] **P06 — Integrar y aceptar `platform`.** Conectar escenarios al adaptador,
  catálogo y evidencia. Registrar niveles HTTP real/LLM doble/compilador doble;
  ejecutar la suite y documentar fallos del producto sin llamarlos verificación Java.
  Depende: P05. Cierre: puerta del trabajo 3 y RF-303/304/305.

## Trabajo 4: microservicios generados y Maven

- [x] **J01 — Preparar toolchain y cache reproducible.** Detectar versiones de
  JDK/Maven; probar ausencia y wrappers de Windows. Documentar preparación separada
  con `quarkus:go-offline`, cache dedicada e inmutabilidad del origen.
  Depende: P06. Cierre: AC-11; si faltan herramientas, dejar bloqueado el cierre real.
- [x] **J02 — Construir las fixtures y oráculos Java.** Preparar `crud-h2`,
  `catalog-h2` y `solution-h2` sin Docker/mensajería, con criterios y tests externos
  al generador. Definir controles negativos. Depende: J01. Cierre: RF-307.
- [x] **J03 — Ejecutar generación y verificador reales.** Usar las dos rutas API,
  Maven offline y H2; configurar toolchain en orquestador y verificador. Recoger
  reportes frescos antes del cleanup y correlacionarlos con las fuentes.
  Depende: J02. Cierre: AC-09 y distinción GENERATED/VERIFIED.
- [x] **J04 — Ejecutar aceptación independiente y controles negativos.** Añadir
  oráculos a copias identificadas; comprobar CRUD/datos y errores esperados de
  compilación/aserción. Conservar diagnósticos y casos; no modificar expectativas
  para acomodar fallos. Depende: J03. Cierre: AC-10/12.
- [x] **J05 — Integrar el adaptador Java.** Normalizar procesos, pasos Maven y
  Surefire; diferenciar defecto del código, cache ausente y error del ejecutor.
  Rechazar dry_run o reportes obsoletos como evidencia real. Depende: J04.
  Cierre: RF-306/308/311 y AC-09/10/11/12.
- [x] **J06 — Aceptar y documentar `java`.** Ejecutar los casos positivos y
  negativos en entorno preparado, contrastar estados/hashes e inspeccionar limpieza.
  Identificar defectos abiertos del producto. Depende: J05. Cierre: puerta real del
  trabajo 4; un bloqueo de toolchain mantiene esta tarea pendiente.

## Trabajo 5: componentes y navegador

- [x] **U01 — Preparar dependencias y separación de herramientas.** Mantener
  Vitest 3/lockfile; fijar Playwright compatible, preparar Chromium y separar
  `e2e/` de Vitest y TypeScript de aplicación. Probar que `run` no descarga nada
  cuando falta un paquete/browser. Depende: C06. Cierre: RF-309/313.
- [x] **U02 — Ampliar cobertura de componentes.** Añadir casos de polling,
  autenticación/red, ERROR/NO_FIX, restauración y exportación sin archivos. Mantener
  los tests existentes y declarar los mocks de fetch. Depende: U01.
  Cierre: primera parte de AC-13.
- [x] **U03 — Integrar Vitest y build.** Ejecutar comandos locales registrados
  mediante Node, recolectar JUnit/JSON y separar TypeScript/Vite como pasos.
  Probar fallos de aserción, build, ausencia de casos y reportes contradictorios.
  Depende: U02, C04, C05. Cierre: AC-13 y `frontend` disponible en catálogo.
- [x] **U04 — Crear el entorno Playwright integrado.** Lanzar frontend y backend
  del trabajo 4 en sandbox propio, Chromium/contexto limpio, un worker y cero
  retries. Comprobar arranque fallido e interrupción con cleanup completo.
  Depende: U03, J06. Cierre: RF-310/312 y AC-14/17.
- [x] **U05 — Probar generación y descarga reales por UI.** Crear una sesión
  nueva, comprobar `trace_id` y verificación contra API, esperar descarga y validar
  ZIP/archivos/huellas. Rechazar demo, README-only y consola de previsualización
  como evidencia de generación/CRUD. Depende: U04. Cierre: AC-14/15.
- [x] **U06 — Probar errores visibles y evidencia de navegador.** Provocar
  autenticación inválida, caída backend y estado no verificado; comprobar mensajes
  y coherencia con API. Guardar reportes y adjuntos sintéticos sin secretos.
  Depende: U05. Cierre: AC-16/17.
- [x] **U07 — Integrar y aceptar `playwright`.** Registrar el adaptador, leer
  JUnit/JSON, normalizar timeouts/omisiones y ejecutar todo el recorrido con Maven
  real. Depende: U06. Cierre: puerta del trabajo 5; sin entorno completo queda pendiente.

## Cierre conjunto

- [x] **V01 — Ejecutar la regresión completa y la aceptación del agente.**
  Comprobar las regresiones F01–F04, compatibilidad de configuración y las suites
  python/platform/java/frontend/playwright. Controles negativos deben ser
  detectados como fallos, no convertir artificialmente toda la campaña en verde.
  Depende: P06, J06, U07. Cierre: AC-01–AC-18 con evidencia observada.
- [x] **V02 — Documentar instalación y uso por capacidades.** Crear ejemplo
  funcional y guía local, presupuestos, caches, artefactos, bloqueos y ejecución
  desde otro directorio. Identificar qué puede hacer la PC Python y qué requiere
  un entorno preparado. Depende: V01. Cierre: RF-315 y reproducción por terceros.
- [x] **V03 — Elaborar el informe de cierre.** Crear `verification.md` con matriz
  de requisitos, mediciones reales, fuentes, plataformas, defectos del producto y
  pendientes. Revisar que no se adelantaron HTML/IA/GitHub ni se certificaron
  comprobaciones bloqueadas. Depende: V02. Cierre: incremento completo y límites claros.

## Orden y puertas

```text
C01 -> C02 -> C03 -> C04/C05 -> C06
                              |
                              +-> P01..P06 -> J01..J06 ----+
                              |                          |
                              +-> U01..U03 --------------+-> U04..U07 -> V01..V03
```

Los 28 elementos anteriores son tareas del plan; ninguno está marcado como
ejecutado. Se permite preparar Vitest tras la base común, pero el cierre del
navegador depende de disponer de generación y Maven realmente verificados.
