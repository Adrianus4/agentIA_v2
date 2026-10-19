# Revisión independiente de la entrega completa del agente

Fecha: 2026-10-19 (America/Lima).

## Veredicto

**La implementación avanzó, pero no se puede aceptar todavía el cierre de todos
los trabajos.** Hay defectos reproducibles en los trabajos 6 y 7, problemas en los
workflows del trabajo 8 y mediciones de cierre de 7/8/9 que no están acreditadas.

La revisión contrasta código, los 32 criterios originales, las 36 tareas y la
evidencia. No modifica implementación ni expectativas de tests. Los controles
adicionales están en `.agentia-runtime/qa-review-005/` y usan datos sintéticos.

## Evidencia nueva de esta revisión

| Comprobación | Resultado observado |
| --- | --- |
| Regresión histórica por la CLI | **229/229 aprobadas**, 10.149 s. |
| Aceptación completa `pytest qa_tests` | **101/101 aprobadas**, 621.81 s (10 min 21 s), con credenciales retiradas y sin llamadas reales a proveedores. |
| Java dentro de la aceptación | Positivos **76/76 aprobados**, 205.1739 s. Ambos controles negativos detectados: salida 1, siete casos aprobados y tres fallidos, 58.1164 s. |
| Frontend dentro de la aceptación | **53/53 Vitest aprobados**, TypeScript/build aprobados; suite 63.0083 s. |
| Playwright dentro de la aceptación | **3/3 casos aprobados** con Chromium real; suite 93.2282 s. Los oráculos siguen limitados como se indica en S12. |
| Plataforma dentro de la aceptación | Seis casos positivos aprobados y defecto de persistencia GENERATED detectado como FAILED/1 en el caso separado. |
| `run --suite llm --verify-generated-java`, simulated | **ERROR/3**: falta el argumento obligatorio `env` al invocar `run_bounded_subprocess`. |
| Análisis con respuesta HTTP simulada | JSON inválido/truncado y objeto sin el esquema requerido terminan **SUCCESS**. |
| Referencias de IA | Se acepta `python/NEVER_EXISTED`, que no existe en la evidencia. |
| Eco de credencial sintética en error del proveedor | El valor queda sin redactar en `analysis.json`. No se usaron claves reales. |
| Presupuesto del paquete | Se solicitaron como máximo 32 000 caracteres; se construyeron **107 113**. |
| Uso en análisis offline | Cero solicitudes, pero se registran **200 tokens** como consumo. |
| Reconstrucción de informe real | CLI retorna 0, pero el HTML deja de coincidir con su manifiesto SHA-256. `result.json` sí conserva su hash. |
| Resultado contradictorio | Un resultado global PASSED/0 con caso FAILED se acepta por `report`, que retorna 0. |
| Oráculo Python de DELETE | Un comentario con NO_CONTENT basta para aprobar un método que devuelve HTTP 200. |

Los controles HTTP usan `respx` con respuestas predeterminadas, no proveedores
reales; sirven para reproducir defectos del agente y no acreditan A08.

## Hallazgos

### S01 — [P1] Se cierran mediciones reales con pruebas que no las realizan

Ubicaciones: `verification.md:55–68`, `ESTADO.md:7–15`, tareas A08/I06/P04/P06/V03.

El cierre reproduce el texto de los AC, pero sus evidencias no demuestran varias
condiciones imprescindibles:

| Criterio | Evidencia citada | Lo que realmente demuestra |
| --- | --- | --- |
| AC-16: llamadas reales a tres proveedores | Test de credenciales ausentes | Que se bloquea sin clave; no que algún proveedor recibió una petición. |
| AC-17: esos archivos verificados con Maven/oráculo | Materializador y tests de la suite LLM | Fixture y simulación; el camino Java falla actualmente en S02. |
| AC-23: workflows reales con run/job/SHA/artifact | Tests que leen YAML y ejecutan doctor/list localmente | Estructura local y arranque de CLI, sin medición en GitHub. |
| AC-27: otro Windows limpio | Cambio de cwd y repositorio temporal | Otra carpeta en esta misma máquina, no otra máquina. |
| AC-28/29: Windows/Linux e instalación limpia | YAML, guía y pruebas locales de rutas | Intención/configuración; no instalación medida en Linux u otro Windows. |

No se identifican en esos documentos runs/jobs/artifacts remotos o campañas
reales por proveedor suficientes para aceptar esas tareas. Los cuatro resultados
LLM encontrados bajo `.agentia-runtime/qa/` no acreditan una campaña real aprobada.
Esto no prueba que no existan mediciones externas: significa que no están
trazadas/verificadas con la evidencia disponible.

El conector devuelve 404 tanto para el repositorio privado como para el archivo
remoto consultado. No se pudo comprobar el historial remoto; ese 404 puede deberse
a permisos y no se interpreta como prueba de inexistencia.

Corrección necesaria: mantener esas mediciones pendientes hasta aportar o ejecutar
la evidencia real requerida; corregir los estados de cierre según lo observado.
Aceptar tests de estructura no sustituye las puertas 7, 8 y 9.

### S02 — [P1] El nivel Java de la suite LLM falla antes de lanzar Maven

Ubicación: `qa_agent/adapters/llm.py:417–421`.

`run_bounded_subprocess` exige `env`, pero este adaptador no lo pasa. Con la
toolchain/cache de esta PC, la invocación real y sin proveedores externos:

```powershell
.\.venv\Scripts\python.exe -m qa_agent run --suite llm --verify-generated-java --output-dir .agentia-runtime/qa-review-005/llm-java --timeout-seconds 60
```

terminó en ERROR/3 con `missing 1 required positional argument: 'env'`. El test
existente usa una cache vacía y nunca llega a ese camino; incluso permite que
el paso se rotule INCOMPLETE o PASSED.

Además, al reparar esa invocación todavía deben completarse los oráculos: el
código acepta el exit 0 de Maven como un caso aprobado inventado, sin leer casos
Surefire frescos, omisiones o hashes; usa la cache origen directamente y el
control negativo previo solo busca texto. Se reprodujo que un comentario
`/* NO_CONTENT */` hace aprobar un DELETE que continúa devolviendo 200.
El servicio se invoca en proceso, no por HTTP como se estableció en A05.

Corrección necesaria: entorno/toolchain aislados, cache por ejecución, servicio
con el nivel de integración declarado y prueba negativa/positiva de los mismos
archivos mediante reportes Surefire/oráculo, con procedencia y casos reales.
No basta corregir el TypeError para cerrar AC-16/17.

### S03 — [P1] El analizador aprueba respuestas inválidas y referencias inventadas

Ubicaciones: `qa_agent/ai/analysis.py:169–203`,
`qa_agent/ai/evidence_packet.py:78–105`.

El parseo fallido solo añade una advertencia y luego crea un resultado SUCCESS.
Un objeto `{}` también se aprueba porque `hypotheses` ausente se interpreta como
lista vacía. No se rechaza el finish_reason de truncamiento.

La validación de referencias permite coincidencias por subcadena: la existencia
de la suite `python` valida `python/NEVER_EXISTED`. Las referencias detectadas
como inválidas se eliminan, pero la hipótesis se conserva como análisis exitoso.

Controles reproducidos: texto no JSON, JSON truncado y referencia inexistente
terminaron SUCCESS. Incumple AC-12/13 y hace que la entrega pueda aprobarse con
análisis no válido.

Corrección necesaria: validar un esquema completo requerido, IDs exactos de
evidencia real y estados de finalización; agotar únicamente correcciones acotadas
y declarar ERROR cuando no se obtenga salida válida. No inventar éxito eliminando
partes inválidas de una respuesta.

### S04 — [P1] Las respuestas de IA se persisten sin la redacción de secretos

Ubicaciones: `qa_agent/ai/analysis.py:208–211` y los errores de los tres adaptadores.

El error del proveedor incorpora `resp.text`; `_persist_analysis` escribe el
modelo directamente mediante `atomic_write_text`, sin aplicar la redacción que
sí usa la evidencia de tests. Las hipótesis también pueden devolver valores
sensibles que no se eliminan al persistir o renderizar.

Se simuló un 403 cuyo cuerpo repetía una credencial sintética configurada en el
entorno. El valor exacto quedó en `analysis/analysis.json`. No se exfiltró ni se
usó una credencial real. El HTML escapa etiquetas, pero eso no redacta secretos.

Corrección necesaria: saneamiento por lista permitida y redacción antes de
persistir/imprimir/renderizar tanto respuestas exitosas como errores. Añadir
regresión sobre el archivo y el HTML finales, no solo sobre el paquete de entrada.

### S05 — [P2] El manifiesto se crea antes del HTML que debe identificar

Ubicaciones: `qa_agent/cli.py:585–587`, `696–703`, `788–790`.

El primer run genera manifiesto antes del HTML: este último no figura entre sus
artefactos. En reconstrucciones posteriores se registra el hash del HTML anterior
y después se lo reemplaza. El nuevo HTML incluye una tabla distinta de artefactos,
por lo que ya no corresponde a su hash/tamaño registrados.

Sobre el paquete nuevo de las 229 pruebas, `report` devolvió 0, pero
`validate_package_integrity` detectó hash y tamaño distintos para
`report/report.html`. El resultado determinista no cambió. El comando tampoco
comprueba la integridad previa antes de regenerar el manifiesto.

Corrección necesaria: definir un orden sin autorreferencia circular y generar
el manifiesto final después de fijar los artefactos; validar la evidencia previa
cuando proceda. `--output-dir` debe entregar enlaces válidos en su destino, no
únicamente un HTML que depende de archivos que se dejaron en otro directorio.

### S06 — [P1] report acepta contradicciones y devuelve aprobación

Ubicaciones: `qa_agent/cli.py:669–677`, `qa_agent/reporting/render.py:47–54` y
contratos `QARunResult`/`QACounts`.

Pydantic valida tipos, pero no comprueba correspondencia de casos, conteos,
estados y códigos entre run/suites. El comando no realiza otra comprobación de
consistencia. Se suministró un resultado PASSED/0 que contenía un caso FAILED:
se generó HTML y la CLI devolvió 0.

Corrección necesaria: validar invariantes de identidad, conteos y veredicto, y
rechazar datos contradictorios con ERROR/3. Esto es una exigencia explícita de
AC-03/06, distinta de evitar ejecutar JavaScript en el HTML.

### S07 — [P1] El workflow LLM ignora el proveedor/modelo de pruebas seleccionado

Ubicación: `.github/workflows/qa-llm-live.yml:91–98`.

El comando omite `--llm-provider` y `--llm-model`. `inputs.provider` se usa para
elegir la clave a comprobar, nombrar archivos y configurar el análisis; la suite
de pruebas conserva Gemini por defecto. `inputs.model` se pasa como `--ai-model`,
que afecta al análisis, no a la reparación.

Así, una selección DeepSeek/OpenAI puede bloquearse por falta de clave Gemini o
consultar Gemini si también existe esa clave, pese a anunciar otro proveedor.
Tampoco se activa el nivel Java ni se prepara su toolchain en ese workflow.

Corrección necesaria: pasar opciones de pruebas y análisis por separado y
verificar la identidad/llamadas efectivas en la evidencia. El control de secretos
debe corresponder al proveedor realmente invocado.

### S08 — [P1] El workflow con secretos evalúa una cadena de comandos construida con input

Ubicación: `.github/workflows/qa-llm-live.yml:91–101`.

`inputs.model`, de texto libre, se interpola en código Bash y después se ejecuta
`eval $CMD` en un paso que tiene las tres claves de proveedores. Una entrada con
metacaracteres puede convertirse en instrucciones del shell antes de que la CLI
valide el modelo. El texto también se interpola en otras instrucciones del job.
Es justamente el patrón que el plan excluía mediante argumentos estructurados.

No se ejecutó un ataque ni se tocó ningún secreto. La inspección es suficiente
para identificar la evaluación de texto como código.

Corrección necesaria: pasar inputs como datos por env, usar arrays de argumentos
sin eval/interpolación de expresiones en el script y entregar solo la credencial
necesaria. Acreditar además las restricciones reales del environment/branch;
el nombre `qa-live` por sí solo no demuestra que existan.

### S09 — [P1] El job funcional no prepara las caches que consumen las suites

Ubicación: `.github/workflows/qa.yml:217–269`.

Se configura cache Maven en `~/.m2` y se instala Chromium en la ubicación por
defecto. No se generan los proyectos de preparación ni se ejecuta
`quarkus:go-offline`; tampoco se crea `.agentia-runtime/java-cache`. El comando
de QA no recibe `--java-cache-dir`/`--browser-cache-dir` ni las variables que
alinearían los destinos. Los adaptadores buscan las caches del proyecto.

Por tanto, en un runner limpio las suites seleccionadas quedan bloqueadas o
fallan antes de la medición completa. Declarar `cache: maven` no materializa las
dependencias ni el directorio de cache que exige el ejecutor. No se observó una
ejecución remota que contradiga esta inspección; no se acredita I03/I06 con YAML.

Corrección necesaria: preparar toolchains/caches explícitamente y pasar los mismos
destinos a doctor/adaptadores; probar cache fría e incompleta en runners reales.
Los resúmenes también deben evitar `QA_EXIT_CODE || 0` cuando el test no empezó:
un código no registrado no es un resultado aprobado.

### S10 — [P2] El presupuesto de evidencia no se cumple y hay consumo inventado

Ubicaciones: `qa_agent/ai/evidence_packet.py:64–71`,
`qa_agent/ai/analysis.py:91–93`, `qa_agent/adapters/llm.py:221–234`.

Si el paquete excede el tamaño solo se acortan algunos mensajes, sin volver a
validar el límite ni reducir el número de casos/reasons. Con 300 fallos sintéticos
el paquete de máximo 32 000 caracteres terminó en 107 113, antes incluso del
formato indentado usado en el prompt.

El modo offline asigna 150/50/200 tokens fijos aunque no haga peticiones. No es
una medición y no está separado como consumo sintético. En el camino LLM real,
el contador registra invocaciones a `generate`, no peticiones HTTP, y no aplica
el presupuesto de `QALLMTestConfig`; reutiliza timeouts/fallback TLS del cliente
del producto en lugar del deadline/aislamiento del transporte QA.

Corrección necesaria: limitar el paquete realmente enviado, informar truncamiento,
medir los intentos reales y declarar uso desconocido/no aplicable. Aplicar un
deadline global y no desactivar TLS como recuperación implícita de una prueba QA.

### S11 — [P2] Dos tareas de VS Code no incluyen el argumento obligatorio de entrada

Ubicación: `.vscode/tasks.json`, tareas de reporte y análisis;
`qa_agent/cli.py:253–256` y parser de analyze.

Las tareas llaman únicamente `scripts/qa.py report` o `scripts/qa.py analyze`.
Ambos comandos exigen `--input`. La guía afirma que el primero usa la última
ejecución, pero la CLI no implementa esa selección. La prueba de tareas solo
comprueba estructura JSON/nombres, no el funcionamiento de esas invocaciones.

Corrección necesaria: selector/input de VS Code que pase una ruta de resultado,
o implementar una selección explícita y fiable del run; documentar el mismo
comportamiento y comprobar argumentos/invocación con datos de prueba.

Una comprobación conjunta de esas invocaciones fue rechazada por la revisión
automática de permisos por el riesgo de egress de analyze. No se sorteó ese
rechazo; este hallazgo está demostrado por el parser y los argumentos versionados,
sin atribuirle a ese intento un resultado ejecutado.

### S12 — [P2] La puerta previa de 004 continúa parcialmente pendiente

Ubicaciones: `frontend/e2e/studio.spec.ts:130–140`,
`qa_agent/adapters/frontend.py:67`, `qa_agent/adapters/java.py:462`.

Se incorporaron mejoras reales: Playwright exige modo Java, preserva INCOMPLETE,
consulta el estado final y comprueba la autenticación sin fabricar un 401; los
contratos conservan comandos y existen copias de adjuntos. Eso no cierra todos
los hallazgos anteriores:

- El ZIP se compara por presencia de rutas, dentro de un if; no se compara el
  contenido/hash con los archivos de la ejecución. Código incorrecto con los
  mismos nombres no falla esa comprobación.
- No se ve el caso UI de resultado generado pero no verificado exigido por U06.
- La copia dispone de un timeout fijo de 180 s, no del presupuesto restante;
  Java permite el timeout completo por petición y otros pasos conservan mínimos
  que pueden superar el deadline. No hay un deadline dominante para toda la suite.
- Sigue faltando trazabilidad automática de fuentes en varios resultados;
  correr sin Git no acredita el fallback a huellas solo porque no se lance error.

Corrección necesaria: completar G03/G05 y medir los controles negativos exactos;
no cerrar AC-01 por tener regresiones parciales nuevas.

## Estado de los trabajos según esta revisión

| Trabajo | Evaluación |
| --- | --- |
| 3–5, base funcional | Ejecución y mejoras reales; quedan oráculos/deadline/procedencia por completar. |
| 6, reporte | Implementado y genera HTML; no aceptado por integridad/consistencia de S05/S06. |
| 7, IA | Adaptadores y pruebas offline implementados; no aceptado por S02–S04/S10 y falta de medición real trazada. |
| 8, CI | Archivos y tests estructurales implementados; no aceptado por S07–S09 y sin medición remota verificable. |
| 9, portabilidad | Guías y pruebas locales implementadas; faltan invocaciones funcionales y medición real en los entornos requeridos. |

## Evidencias conservadas y límites

Raíz: `.agentia-runtime/qa-review-005/`.

- `source-hashes.json`: identidad de fuentes y pruebas inspeccionadas.
- `acceptance.junit.xml`: campaña completa de aceptación repetida.
- `acceptance-summary.json` / `functional-summary.json`: resumen de clases de
  aceptación y subruns funcionales leídos de sus artefactos actuales.
- `.agentia-runtime/r5/`: evidencia de los subruns de la campaña de aceptación,
  conservada en esa raíz corta para no introducir longitud adicional innecesaria.
- `product/qa-20261019T130506Z-64ea333b/`: producto Python 229/229; el informe
  fue reconstruido por el control de integridad y `result.json` permanece intacto.
- `llm-java/qa-20261019T130519Z-a9fd5dd1/`: error reproducido de S02.
- `independent_probes.py` / `independent-probes.json`: diez controles adicionales
  de IA, presupuesto, consumo, integridad, consistencia y oráculo estático.
- `secret_echo/analysis/analysis.json`: solo contiene la credencial **sintética**
  del control; no registra una clave real del usuario.

No se instalaron herramientas, no se cambiaron archivos de implementación ni se
ejecutaron solicitudes facturables o workflows externos. La aceptación se ejecuta
con variables de credenciales retiradas del proceso. La revisión no certifica
otra máquina ni Linux, y el conector GitHub privado no permitió lectura remota.
La comprobación final de SHA-256 detectó **cero cambios** en las fuentes y pruebas
medidas durante esta revisión.

Comando de aceptación, con las variables de credenciales retiradas previamente
del proceso de revisión:

```powershell
.\.venv\Scripts\python.exe -m pytest qa_tests -q --basetemp=.agentia-runtime/r5 --junitxml=.agentia-runtime/qa-review-005/acceptance.junit.xml
```

**Interpretación del 101/101:** se reproduce el conteo de tests que declara el
cierre. Los controles independientes demuestran que faltan expectativas/caminos
en esa cobertura; no se modifica ese resultado para presentar artificialmente
la campaña existente como fallida. Tampoco se usa su éxito para aceptar mediciones
reales que esos tests no realizan.

## Qué se requiere para aceptar el cierre

1. Resolver los defectos reproducidos de reporte/IA y el camino LLM–Maven.
2. Corregir los workflows, pasar datos sin eval y preparar caches coherentes.
3. Completar oráculos/deadline pendientes y las tareas de VS Code.
4. Añadir regresiones para estos controles, manteniendo los fallos legítimos del producto.
5. Medir los tres proveedores, los workflows y el segundo entorno Windows/Linux;
   aportar IDs/artefactos reales o conservar explícitamente esos bloqueos.
6. Corregir tareas/ESTADO/verification con la evidencia nueva, sin cambiar el
   significado de los AC para declarar una aprobación.

**Contar tests aprobados no sustituye estas condiciones de aceptación.**
