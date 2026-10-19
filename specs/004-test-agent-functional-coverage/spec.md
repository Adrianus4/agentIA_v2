# Especificación: cobertura funcional del agente de pruebas

Fecha: 2026-10-18 (America/Lima). Estado: plan listo para implementar.
Alcance: trabajos 3, 4 y 5 de la primera versión acordada.
Antecedente: [fundación del ejecutor](../003-test-agent-foundation/plan.md) y
[revisión de sus correcciones](../003-test-agent-foundation/review-followup.md).

## Objetivo

Extender el ejecutor Python existente para comprobar la plataforma AgentIA por
HTTP real, los microservicios Quarkus generados mediante Maven y los recorridos
de la interfaz mediante Vitest y Playwright. Cada resultado debe indicar qué
componentes fueron reales, cuáles usaron dobles y qué quedó sin comprobar.

Se conservarán `doctor`, `list`, `run`, la suite `python`, los códigos de salida
y las correcciones F01–F04. Docker, virtualización, Git y una API key no serán
requisitos del ejecutor. Java, Node y Chromium serán requisitos de las suites
que efectivamente los necesiten, no de todas las comprobaciones.

## Límites del incremento

- Se implementan las suites `platform`, `java`, `frontend` y `playwright`.
- Se amplían catálogo, contratos y evidencia mínima JSON/JUnit para esas suites.
- Se preparan escenarios conocidos y oráculos independientes del generador.
- La cobertura nueva del producto se separa de la aceptación del propio agente.
- Proveedores LLM reales, análisis por IA, HTML consolidado, publicación Git y
  workflows de GitHub siguen en los trabajos posteriores.
- Las pruebas no usarán datos, claves, servidores o repositorios corporativos reales.
- Si las pruebas descubren un fallo del producto, debe quedar como fallo observado
  y reproducible. Cerrar el agente no equivale a certificar que el producto no tiene errores.
- El cierre de este grupo exige ejecuciones reales de sus cuatro suites en un
  entorno preparado; tener adaptadores que solo informan bloqueos no basta.

## Requisitos funcionales

| ID | Requisito |
| --- | --- |
| RF-301 | Evaluar capacidades y bloqueos por suite, manteniendo `python` como selección predeterminada. |
| RF-302 | Ejecutar varias suites sin sobrescribir evidencia y conservar códigos 0/1/2/3/4/130, alcance y causas. |
| RF-303 | Levantar una topología local de prueba con procesos propios, puertos dinámicos, healthchecks y estado aislado; detenerla incluso ante fallos. |
| RF-304 | Probar autenticación, entradas inválidas, ejecución asíncrona, persistencia, concurrencia, fallos HTTP y reparación acotada. |
| RF-305 | Distinguir transporte HTTP real de dobles LLM/Maven; una simulación de verificación no se rotula como compilación real. |
| RF-306 | Generar servicios mediante las dos rutas, compilar y probar realmente con JDK 21 y Maven 3.9+, sin depender de contenedores. |
| RF-307 | Evaluar el código generado contra resultados esperados mantenidos fuera del generador, incluyendo un control negativo. |
| RF-308 | Separar generación, compilación, ejecución de pruebas y aceptación; conservar procedencia, huellas y diagnósticos de cada etapa. |
| RF-309 | Ejecutar Vitest existente y la comprobación TypeScript/build sin que estas recolecten pruebas Playwright. |
| RF-310 | Ejecutar Playwright sobre la UI y backend reales y un servicio realmente verificado; comprobar progreso, errores y descarga del código correcto. |
| RF-311 | Obtener conteos de artefactos estructurados y rechazar evidencia ausente, vieja, corrupta o contradictoria según el dialecto de cada herramienta. |
| RF-312 | Mantener aislamiento, límite de salida durante la lectura, deadline, limpieza de descendientes y redacción; conservar las regresiones F01–F04. |
| RF-313 | Detectar dependencias y caches ausentes sin instalarlas o descargarlas silenciosamente durante `run`. |
| RF-314 | Ejecutar operaciones locales y comandos registrados; no admitir comandos arbitrarios ni iniciar cambios en servicios del usuario. |
| RF-315 | Conservar compatibilidad con la configuración anterior y registrar las plataformas realmente comprobadas. |

## Casos mínimos de aceptación

Las afirmaciones de aprobación se refieren a una prueba ejecutada sobre un resultado
esperado explícito, no a un mensaje de éxito o a un conteo prefijado.

| ID | Comprobación de aceptación |
| --- | --- |
| AC-01 | Sin Java, Maven, Node y navegador, `python` y `platform` siguen siendo elegibles con sus paquetes Python; las otras suites seleccionadas devuelven INCOMPLETE y explican el requisito. |
| AC-02 | Alias `react`/`frontend` y `browser`/`playwright` se normalizan sin ejecutar dos veces la misma suite; ninguna evidencia se sobrescribe. |
| AC-03 | La configuración anterior sigue funcionando; varias suites producen resultados por motor, pasos y alcance, conservando los códigos acordados. |
| AC-04 | Los cinco procesos Python de prueba responden por sockets loopback reales; un puerto ocupado, un arranque fallido o dos ejecuciones concurrentes no afectan procesos ajenos. |
| AC-05 | Las claves de prueba correctas/incorrectas, blueprint inválido y errores de esquema producen los resultados del contrato existente, con trazabilidad. |
| AC-06 | Un `run?mode=async` devuelve 202, llega a estado terminal y concuerda con detalle/historial/estado persistido; no se depende de observar una etapa tan breve que el polling pueda perderla. |
| AC-07 | Verificación fallida, servicio caído, timeout, parche rechazado y presupuesto agotado producen el desenlace esperado, sin contactos reales a LLM ni reintentos ilimitados. |
| AC-08 | La ruta de solución permite distinguir GENERATED de VERIFIED/SUCCESS, y recuperar el resultado tras reiniciar únicamente el orquestador de prueba. Un defecto detectado se registra sin simular persistencia. |
| AC-09 | Blueprints positivos de una y varias entidades generan código, compilan y ejecutan casos reales con H2; `dry_run`, informes antiguos o BUILD SUCCESS sin casos no sirven como prueba. |
| AC-10 | Un servicio con un error de compilación controlado y otro con una aserción de aceptación deliberadamente falsa terminan FAILED, conservando diagnósticos y códigos de proceso. |
| AC-11 | Falta de JDK, Maven o cache offline se diferencia de un defecto de compilación; la suite no cambia automáticamente a simulación ni descarga dependencias durante el veredicto. |
| AC-12 | Los informes Surefire y los del oráculo corresponden a fuentes, fixture y ejecución identificadas; cero casos, omisiones o evidencia inconsistente no producen aprobación. |
| AC-13 | Las pruebas Vitest existentes, los nuevos casos de errores/estados y el build TypeScript se ejecutan con resultados estructurados y salidas diferenciadas. |
| AC-14 | Playwright parte de un contexto limpio, crea una ejecución nueva por la interfaz y contrasta su `trace_id` y resultados con la API real. No acepta sesiones de demostración. |
| AC-15 | El navegador descarga un ZIP real con `pom.xml`, fuentes y pruebas esperadas; sus contenidos corresponden a la ejecución. Un ZIP de solo README o vacío falla el caso. |
| AC-16 | La UI muestra correctamente el rechazo de autenticación, un fallo backend y un resultado no verificado; el mensaje de éxito por sí solo no satisface el oráculo. |
| AC-17 | Se recupera evidencia mínima incluso ante timeout, fallo de snapshot o herramienta inválida; se detienen servicios, navegador y descendientes propios y se conservan centinelas externos. |
| AC-18 | Las regresiones anteriores siguen pasando; los casos históricos del producto conservan sus expectativas. Una suite seleccionada bloqueada, vacía u omitida impide salida global 0. |

## Criterio de cierre

Se necesitan adaptadores aceptados, cobertura trazada y ejecuciones reales de
`platform`, `java`, `frontend` y `playwright`, además de la regresión Python.
El informe de cierre separará defectos pendientes del producto de defectos del
agente y dependencias bloqueadas. Mientras falte una toolchain para medir Java
o navegador, el grupo se mantendrá parcialmente implementado o bloqueado.
