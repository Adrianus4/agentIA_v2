# Especificación: entrega del agente de pruebas — trabajos 6, 7, 8 y 9

Fecha: 2026-10-19 (America/Lima). Estado: planificación; implementación pendiente.
Documentos: [plan.md](plan.md), [tasks.md](tasks.md).

## Objetivo y alcance

Completar la primera versión del agente local con un informe HTML consolidado,
análisis opcional por IA, pruebas opcionales con proveedores reales, ejecución
en GitHub Actions y una entrega reproducible por capacidades.

Se conserva la división acordada:

| Trabajo | Entrega |
| --- | --- |
| 6 | Informe terminal/JSON/JUnit/HTML coherente y navegable. |
| 7 | Gemini, DeepSeek y GPT/OpenAI: análisis de resultados y llamadas de prueba reales opcionales, configurados por separado. |
| 8 | GitHub Actions: campañas ordinarias sin claves y campaña real bajo activación explícita. |
| 9 | Instalación, VS Code, documentación y validación en entornos distintos. |

Antecedentes: [fundación](../003-test-agent-foundation/plan.md),
[cobertura funcional](../004-test-agent-functional-coverage/plan.md) y
[revisión independiente](../004-test-agent-functional-coverage/review.md).
Hay modificaciones posteriores a esa revisión en el árbol de trabajo: primero
se comprobarán sus correcciones, sin asumir que todos los hallazgos siguen abiertos
ni que los estados históricos de cierre acreditan el código actual.

## Condiciones de la versión

- El agente se ejecuta localmente con Python. VS Code es una interfaz opcional.
- Docker, virtualización, privilegios de administrador y modelos instalados
  localmente no son requisitos. Las extensiones no sustituyen runtimes ausentes.
- Python/plataforma funcionan con sus paquetes Python. Java, Node y Chromium
  solo condicionan las suites que los necesitan.
- Una PC limitada puede ejecutar el perfil Python y analizar resultados por API
  si tiene conectividad y una clave. No debe declarar aprobada una suite Java
  o de navegador que no pudo ejecutar.
- La IA sugiere explicaciones; los tests y sus oráculos deciden pass/fail.
- Llamadas reales y análisis están desactivados por defecto. Tener claves en el
  entorno no los activa. El coordinador local consulta APIs externas.
- Se usan datos sintéticos. La preparación explícita de dependencias puede usar
  red; la campaña ordinaria no instala paquetes ni descarga herramientas.
- Los defectos del producto quedan identificados. No se modifican expectativas
  ni se exige arreglar todos los defectos del negocio para aceptar el agente.

## Requisitos

| ID | Requisito |
| --- | --- |
| RF-001 | Validar las correcciones de la revisión 004, completar las pendientes y conservar sus regresiones antes del cierre integral. |
| RF-002 | Mantener configuración anterior, identidad de casos, procedencia, fidelidad real/doble y códigos 0/1/2/3/4/130. |
| RF-003 | Separar resultado de pruebas, estado del análisis y estado de entrega del informe. Ningún complemento reescribe el resultado de los tests. |
| RF-601 | Construir HTML desde evidencia validada, con totales, suites, casos, bloqueos, pasos, versiones, fuentes y límites. |
| RF-602 | Permitir regenerar informes sin ejecutar pruebas ni llamar a proveedores. |
| RF-603 | Presentar datos y adjuntos escapados y redactados, con enlaces locales confinados y sin recursos externos. |
| RF-604 | Persistir evidencia mínima ante fallo/interrupción y conservar adjuntos propios con referencias válidas. |
| RF-701 | Integrar los tres proveedores mediante adaptadores explícitos, sin fallback silencioso de proveedor, modelo o modo. |
| RF-702 | Analizar únicamente un paquete de evidencia reducido, redactado y autorizado mediante activación de la opción. |
| RF-703 | Validar la salida de IA contra modelos Pydantic, exigir referencias a evidencia existente y separar hechos e hipótesis. |
| RF-704 | Acotar peticiones, tamaño, tokens y tiempo, registrar consumo disponible y manejar errores sin perder la evidencia base. |
| RF-705 | Ofrecer pruebas LLM simuladas/reales con procedencia observable y comprobar que las reales efectivamente consultan al proveedor. |
| RF-706 | Probar la integración real con el producto y, en el perfil completo, compilar los mismos archivos con Maven y oráculos independientes. |
| RF-801 | Ejecutar CI para cambios y manualmente utilizando el mismo coordinador y los mismos contratos locales. |
| RF-802 | Preparar dependencias por separado, con locks y caches identificadas; una cache ausente no modifica el veredicto para obtener verde. |
| RF-803 | Conservar evidencia y códigos en CI incluso si falla una suite; un job omitido no acredita cobertura. |
| RF-804 | Aislar los trabajos con claves, limitar permisos y evitar su ejecución sobre código de contribuciones no confiables. |
| RF-901 | Documentar perfiles mínimo/completo, requisitos reales, preparación online/offline y comandos desde cualquier directorio. |
| RF-902 | Ofrecer tareas de VS Code sin comandos arbitrarios, rutas personales ni secretos y mantener uso completo por terminal. |
| RF-903 | Comprobar el perfil mínimo en otro entorno Windows limpio y registrar las plataformas realmente medidas. |
| RF-904 | Verificar rutas con espacios/largas, ausencia de herramientas/Git/red, deadlines, limpieza, cancelación y reproducción desde clon limpio. |
| RF-905 | Entregar una matriz de aceptación trazada y una guía de transferencia, distinguiendo implementado, medido, fallido y bloqueado. |

## Criterios de aceptación

| ID | Comprobación necesaria |
| --- | --- |
| AC-01 | Los hallazgos R01–R10 de 004 se contrastan con el código nuevo y se cierran con evidencia o quedan pendientes explícitos. Se incluyen deadline total y compatibilidad Node/Playwright. |
| AC-02 | Configuraciones 1.0 anteriores y comandos doctor/list/run conservan su significado; las opciones nuevas no habilitan llamadas por defecto. |
| AC-03 | Terminal, JSON y HTML muestran iguales estados/conteos por suite y fidelidad; errores, omisiones y bloqueos impiden una aprobación global falsa. |
| AC-04 | HTML abre localmente sin Node/servidor/conexión; permite localizar cada fallo y su evidencia con estilos y recursos incluidos. |
| AC-05 | Logs/IA con etiquetas HTML, JavaScript, URLs peligrosas o rutas externas aparecen como datos; no ejecutan contenido ni publican secretos. |
| AC-06 | Reportes ausentes, contradictorios o de esquema no soportado se rechazan; reconstruir un informe no ejecuta subprocess ni solicitudes LLM. |
| AC-07 | Se conservan comandos, diagnósticos, hashes y adjuntos; mover el paquete completo mantiene los enlaces. Una escritura fallida produce un resultado mínimo cuando existe un destino escribible. |
| AC-08 | Análisis disponible/ausente/fallido se distingue del veredicto determinista. El hash de result.json no cambia tras analizarlo. |
| AC-09 | Las cuatro combinaciones de LLM real sí/no y análisis sí/no funcionan sin activar implícitamente la otra opción. |
| AC-10 | Gemini, DeepSeek y OpenAI tienen pruebas de contrato offline de solicitudes/respuestas y un modelo configurable sin selección de «latest» silenciosa. |
| AC-11 | Con análisis desactivado hay cero solicitudes externas aunque existan claves; sin clave, la opción solicitada queda bloqueada y las pruebas base conservan evidencia. |
| AC-12 | Timeout, 401/403, cuota/429, 5xx, rechazo, texto vacío/truncado y JSON inválido terminan dentro del presupuesto y conservan diagnóstico redactado. |
| AC-13 | La IA referencia únicamente suite/caso/artefacto existentes, no altera conteos, no afirma haber ejecutado pruebas y no dispara comandos, reparaciones o instalaciones. |
| AC-14 | Instrucciones maliciosas incluidas en logs no cambian el contrato del analizador. Solo se envía el paquete permitido; quedan fuera archivos fuente completos, .env, prompts privados y adjuntos crudos. |
| AC-15 | El número de peticiones real, reintentos incluidos, respeta el máximo; modelo, duración y uso disponible se registran. Costes desconocidos permanecen desconocidos. |
| AC-16 | Para cada proveedor se observa al menos una llamada real causada por un escenario del producto que requiere IA; cero llamadas o respuesta simulada no satisfacen el caso real. |
| AC-17 | En el perfil completo los archivos del caso real se identifican por hash y se prueban con Maven/oráculo; el éxito HTTP/LLM o la existencia de fuentes no se presenta como compilación. |
| AC-18 | La falta de claves, salida de red, herramientas o modelos accesibles bloquea solo la capacidad correspondiente, sin cambiar a otro proveedor o a simulación. |
| AC-19 | Los workflows ordinarios se ejecutan en pull_request/push y admiten ejecución manual de perfiles; no necesitan claves LLM. |
| AC-20 | Un fallo de suite se conserva como fallo del job; siempre se intenta subir evidencia y el resumen muestra los estados reales, incluidos jobs bloqueados u omitidos. |
| AC-21 | Con cache CI vacía, la fase de preparación crea las dependencias necesarias; run no descarga. Cache incompleta se invalida/prepara antes de medir o bloquea con causa. |
| AC-22 | La campaña LLM real requiere activación manual sobre una referencia confiable; no expone claves a PRs de forks ni ejecuta sus cambios con privilegios. |
| AC-23 | Se ejecutan y revisan workflows reales en GitHub con SHA/run/job/artifact identificados; un YAML creado o validado localmente no cierra el trabajo 8. |
| AC-24 | Un entorno Python preparado, sin Docker/Node/JDK/Chromium, ejecuta el perfil mínimo; seleccionar además suites ausentes devuelve INCOMPLETE/4. |
| AC-25 | Un usuario sin administrador puede preparar un venv con Python y paquetes permitidos; la guía explica cómo usar un wheelhouse compatible cuando no se permite descargar. |
| AC-26 | Las tareas de VS Code reutilizan la CLI y el intérprete del proyecto; no dependen de una extensión de IA, GitHub CLI ni rutas de esta PC. |
| AC-27 | Otro entorno Windows limpio ejecuta el perfil mínimo con evidencia; una simulación de capacidades en la PC de desarrollo no sustituye esa comprobación. |
| AC-28 | La matriz mide Windows y Linux; cubre rutas externas/con espacios/largas, red ausente, procesos huérfanos, copia fallida y deadline con limpieza. No se afirma macOS ni la PC corporativa real sin medirlos. |
| AC-29 | Desde un clon/copia limpia se reconstruyen entornos y caches siguiendo la guía, sin copiar .venv/node_modules de otro SO ni usar caches ocultas de la máquina original. |
| AC-30 | El cierre contiene matrices separadas de capacidad del agente y resultado del producto, incluyendo el defecto de persistencia GENERATED mientras siga existiendo. |
| AC-31 | Salida CLI respeta la política documentada: fallo de pruebas no queda oculto por IA/HTML, interrupción es 130 y una entrega incompleta nunca se declara completa. |
| AC-32 | Los cuatro trabajos tienen comprobaciones reales trazadas a requisitos/tareas; proveedores o plataformas bloqueados no se rotulan aceptados. |

## Fuera de alcance

Autorreparación del proyecto por IA, generación libre de nuevas suites, instalación
de servicios corporativos, modelos locales/GPU, despliegue de una web de reportes,
publicación automática de comentarios o releases, y compatibilidad universal sin
dependencias. No se modificarán permisos de organización ni protecciones de rama
como parte implícita de instalar los workflows.
