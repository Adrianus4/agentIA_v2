# Plan de implementación: trabajos 6, 7, 8 y 9

Fecha: 2026-10-19 (America/Lima). Estado: listo para implementar; sin ejecución.
Contrato: [spec.md](spec.md). Secuencia: [tasks.md](tasks.md).

## 1. Decisiones de partida

Se amplía `qa_agent`; no se crea otro agente, una web de reportes ni un servicio
que deba permanecer encendido. El flujo será:

```text
doctor/configuración -> suites elegibles -> evidencia determinista persistida
                                              |
                                   paquete reducido y redactado
                                              |
                                   análisis IA, solo si se solicita
                                              |
                              HTML + manifiesto de entrega + resumen
```

GitHub usa este flujo y publica sus artefactos. VS Code llama a la misma CLI.
La regeneración de informes consume evidencia existente y nunca repite pruebas
o llamadas de IA implícitamente.

### Estado observado y puerta de entrada

La revisión 004 midió 229 pruebas Python aprobadas, 53 Vitest con build, 76 casos
Java positivos al usar una ruta corta y falsos positivos en Playwright. Esas
cantidades son referencias históricas, no objetivos de conteos para este plan.

La lectura actual muestra cambios posteriores en los adaptadores y en los
contratos: por ejemplo, `backend_mode="java"`, propagación de INCOMPLETE y campos
de comandos/diagnóstico. **No se han vuelto a ejecutar ni certificado aquí.**
No sobreescribir la revisión histórica ni rehacer correcciones ya aceptadas.

Antes de aceptar los trabajos 6–9, comprobar:

| Antecedente de revisión 004 | Comprobación de entrada |
| --- | --- |
| R01/R02 | Sin compilador real no hay cierre integrado; cero casos/skips/discrepancias no pasan. |
| R03/R04 | UI contrasta resultado y trace_id; ZIP coincide por contenido; negativos actúan sobre servicios propios. |
| R05/R06 | Cache parcial y builder ausente bloquean con causa; no se omiten pasos obligatorios. |
| R07/R08/R09 | Contratos preservan datos, rutas largas no rompen la entrega y adjuntos sobreviven al cleanup. |
| R10 | Matriz con los AC originales, interrupción 130 y defectos del producto declarados. |
| Brechas adicionales | Deadline incluye preparación/cierre; Node y browser corresponden al lockfile instalado. |

Guardar una nueva revisión de seguimiento de 004 con comandos y evidencia.
Puede avanzarse en contratos/maquetas del reporte mientras se corrige esta base;
ningún cierre posterior debe basarse en resultados que todavía admiten falsos
positivos. El fallo del producto GENERATED→RUNNING se conserva si sigue presente.

## 2. Arquitectura y compatibilidad

### Componentes previstos

```text
contracts/models.py                    contratos QA aditivos
qa_agent/
  cli.py, config.py                     opciones y precedencia actuales
  evidence.py                          persistencia/redacción, no renderizador IA
  reporting/
    manifest.py                        identidad y validación de artefactos
    render.py                          HTML y resumen desde evidencia
    templates/report.html.j2           estilos incluidos, autoescape
  ai/
    config.py, transport.py             credenciales por entorno y límites
    providers/{openai,gemini,deepseek}.py
    analysis.py, evidence_packet.py     inferencia separada de los tests
  adapters/llm.py                       suite LLM simulada/real optativa
qa_scenarios/llm/                       escenarios sintéticos, fuera de tests/
qa_tests/                              aceptación offline del propio agente
profiles/qa/                           fixtures/configuración declarativa del caso LLM
.github/workflows/{qa,qa-llm-live}.yml
.vscode/tasks.json                     tareas de terminal, no secretos
docs/qa-{reports,ai,ci,portability}.md
specs/005-test-agent-delivery/           trazabilidad y cierre
```

Los nombres son orientativos; ajustar a las interfaces existentes sin mover
innecesariamente los adaptadores. Reutilizar HTTPX, Pydantic, Jinja2 y pytest ya
presentes. No añadir LangChain, un servidor de IA, Postman, Karate o dependencias
Node al perfil Python del coordinador para cumplir estos trabajos.

Mantener la configuración `schema_version="1.0"` aceptando campos opcionales
aditivos. Conservar los ejemplos anteriores y sus valores predeterminados.
Los esquemas de manifiesto y análisis tendrán versiones propias; si una evolución
resulta incompatible, deberá incluir migración/lectura de evidencia antigua,
sin reinterpretarla como si tuviera campos que nunca registró.

### Contratos y persistencia

Definir en `contracts/models.py`, antes del código, modelos equivalentes a:

- `QAArtifact`: ID estable, ruta relativa, tipo, tamaño, SHA-256 y procedencia.
- `QAReportManifest`: run/fecha, huella del resultado base, artefactos, versiones
  de esquema, estado de generación y advertencias de evidencia ausente.
- `QAAnalysisConfig`/`QALLMTestConfig`: proveedor/modelo, modos y presupuestos,
  siempre sin valores de claves serializables.
- `QAAnalysisResult`: proveedor/modelo efectivamente usados, estado, hipótesis,
  evidencia referenciada, próximos pasos sugeridos, límites, uso y duración.
- `QAProviderRequest/Response`: transporte tipado, contenido/uso normalizados y
  error clasificado. No serializar headers de autorización ni respuesta cruda.

Los adaptadores devuelven los mismos campos que validan los modelos. Añadir una
prueba que persista y vuelva a leer comando, diagnóstico, caso, motor y procedencia.
No resolver pérdidas de datos únicamente permitiendo campos desconocidos sin
definir su significado.

`result.json` es la evidencia determinista final de los tests. Una vez validado
y persistido, analizarlo no lo modifica. Los complementos referencian su SHA-256:

```text
<output>/<qa_trace>/
  result.json                         contratos/campos históricos conservados
  <suite>/...                         JUnit, logs y artefactos propios
  analysis/analysis.json              solo si fue solicitado; incluye bloqueo/error
  report/report.html
  report/report_manifest.json
  report/assets/...                   únicamente recursos locales necesarios
  delivery.json                       test_exit_code, analysis_status, report_status
```

Enlaces relativos confinados al paquete del run; manifiesto de nombres cortos
para evitar reproducir R08. Copiar adjuntos binarios con una API de artefactos
tipada, sin pasarlos por escritura de texto. El HTML no incorpora código fuente,
diffs, archivos privados ni trazas crudas. Preservar rutas Python históricas.

Si no se puede persistir un adjunto, intentar guardar un resultado mínimo y el
diagnóstico. Si todo destino es inescribible, salida 3 y mensaje en stderr; no
prometer persistencia imposible. Escritura atómica con temporales propios.

## 3. Trabajo 6 — reporte consolidado

### Resultado visible

Un HTML estático en español, con estilos incluidos y navegación por anclas/
`details`. Debe abrir desde el explorador o VS Code sin servidor, Node, CDN,
fuentes remotas o conexión. Evitar JavaScript cuando los controles nativos basten.

Contenido mínimo:

1. Estado del run y alcance efectivamente probado, fecha y duración.
2. Totales por suite y desglose de aprobado/fallido/error/omitido/xfail/bloqueado.
3. Motor, modo real/doble, versiones, argumentos permitidos y fuentes identificadas.
4. Casos fallidos con diagnóstico, referencia al criterio y enlace al artefacto.
5. Pasos de preparación/build/typecheck separados de los casos de prueba.
6. Bloqueos por capacidad y acciones deterministas para preparar el entorno.
7. Sección de IA claramente diferenciada: desactivada, completada, bloqueada o
   fallida; hechos citados y posibles causas sin atribuirle nuevas mediciones.
8. Límites y defectos del producto identificados, sin confundirlos con el estado
   de aceptación del propio ejecutor.

Usar como fuente única el contrato validado. No recalcular éxito a partir de
mensajes como BUILD SUCCESS ni sumar pasos de build como casos. No fusionar
JUnit de distintas suites destruyendo sus identidades. Si se recibe evidencia
antigua sin procedencia, mostrar «no registrada» y conservar ese límite.

### Entradas propuestas

```text
python scripts/qa.py run --suite python
python scripts/qa.py report --input <run-dir>/result.json
```

Tras `run`, emitir HTML automáticamente con los recursos Python del perfil QA.
`report` solo reconstruye: no importa módulos del producto para ejecutar casos,
no consulta modelos y no invoca subprocess. Un modo `--output-dir` para el reporte
debe producir un paquete movible con manifest y enlaces válidos.

Renderizar HTML y análisis como texto escapado; rechazar enlaces con `javascript:`,
`data:` ejecutable, rutas fuera del paquete o traversal. Probar con marcadores de
secretos sintéticos y entradas maliciosas en todos los orígenes. No abrir el
navegador automáticamente durante CI o campañas desatendidas.

**Puerta 6:** lectura exacta de todos los estados; HTML local funcional y seguro;
reconstrucción sin efectos; evidencia/adjuntos conservados incluso en casos rojos.

## 4. Trabajo 7 — IA optativa y pruebas reales

### Dos decisiones independientes

| Pruebas LLM | Análisis IA | Tráfico esperado |
| --- | --- | --- |
| Simuladas | Desactivado | Cero llamadas a proveedores. |
| Simuladas | Activado | Solo el analizador envía el resumen redactado. |
| Reales | Desactivado | Solo los escenarios LLM seleccionados consultan modelos. |
| Reales | Activado | Ambas capacidades, con presupuestos y evidencias separados. |

Registrar una suite adicional `llm`, optativa. Su modo predeterminado es
`simulated`. Las suites existentes conservan su fidelidad: `--llm-mode real` no
convierte silenciosamente `platform` o todo el grafo de QA en tráfico externo.
Usar modo real sin seleccionar la suite correspondiente es error de configuración.

Ejemplos de interfaz **a implementar**:

```text
python scripts/qa.py run --suite python --ai-analysis --ai-provider gemini --ai-model <modelo-configurado>
python scripts/qa.py run --suite llm --llm-mode real --llm-provider deepseek --llm-model <modelo-configurado>
python scripts/qa.py analyze --input <run-dir>/result.json --ai-provider openai --ai-model <modelo-configurado>
```

`analyze` es una operación explícita que activa esa llamada; nunca se activa por
abrir/reportar un resultado. En `run`, el análisis está desactivado por defecto.
La CLI recibe un proveedor/modelo por operación; la configuración permite una
matriz de proveedores/modelos para la campaña completa. `gpt` puede ser alias de
`openai`; GPT no es el nombre de un proveedor independiente.
`doctor` y `list` inspeccionan configuración y disponibilidad local; no hacen
peticiones facturables para comprobar una clave. Una comprobación remota requiere
seleccionar explícitamente la capacidad real.

### Proveedores y compatibilidad del producto

| Proveedor | Adaptador QA propuesto | Credencial |
| --- | --- | --- |
| OpenAI/GPT | HTTPX sobre Responses; salida con JSON Schema en modelos compatibles. | `OPENAI_API_KEY` |
| Gemini | HTTPX sobre API nativa y formato estructurado admitido por el modelo seleccionado. | `GEMINI_API_KEY` |
| DeepSeek | HTTPX sobre Chat Completions con JSON Output y validación local de esquema. | `DEEPSEEK_API_KEY` |

La documentación de OpenAI/Gemini permite estructurar salidas con un subconjunto
de JSON Schema; la de Chat Completions de DeepSeek documenta JSON Output. No se
supondrá que las tres APIs aceptan iguales campos. Véanse las fuentes de §8.
Pydantic valida siempre, incluso si el proveedor promete estructura.

Modelos explícitos y configurables; resolver una matriz pequeña compatible al
implementar y registrar los IDs efectivamente usados. No prometer disponibilidad
en todas las cuentas ni escoger «latest» o un modelo alternativo silenciosamente.
Si un modelo no soporta el formato, informar incompatibilidad o seleccionar por
configuración un protocolo documentado, sin cambiar de proveedor.

La fábrica actual del producto y `LLMConfiguration` contemplan gemini/local/openai;
`LLMVerifyRequest` también enumera deepseek. **Comprobar un endpoint de credenciales
no acredita integración completa de DeepSeek en generación/reparación.** A05
incluye la evolución mínima y explícita de esos contratos/fábrica cuando sea
necesaria para probar el caso real, conservando los proveedores anteriores y
los guards. No disfrazar DeepSeek como OpenAI en los resultados.

No reutilizar directamente la fábrica de negocio como analizador: mezcla políticas
de defaults y fallback. El transporte QA mantiene TLS verificado, CA/proxy
configurados explícitamente y ningún fallback automático que desactive TLS.
No se cambia configuración global de VS Code, certificados del sistema o servicios.

### Paquete de evidencia y análisis

1. Persistir el resultado determinista antes de cualquier llamada.
2. Construir un paquete por lista permitida: IDs, estados, conteos, causas de
   bloqueo, versiones y extractos pequeños de diagnósticos ya redactados.
3. Registrar hash, tamaño y campos incluidos. Un modo de inspección permite ver
   ese paquete antes de activar el envío. No recorrer el repositorio ni adjuntar
   automáticamente fuentes, .env, prompts completos, capturas, ZIP o trazas.
4. Tratar los logs y errores como datos no confiables, separados de las instrucciones
   del analizador. No habilitar tools, shell, navegación o ejecución de sugerencias.
5. Solicitar hechos con referencias, hipótesis con incertidumbre y próximos pasos.
6. Validar esquema y referencias; una referencia inventada invalida el análisis.
7. Persistir únicamente la salida validada/redactada y sus metadatos. No persistir
   respuesta cruda/reasoning ni headers. Renderizar sus textos sin HTML activo.

La IA no puede cambiar tests, estados o contadores ni declarar una causa como
confirmada sin evidencia. Detectar determinísticamente referencia/estado inválidos;
no afirmar que es posible garantizar semánticamente que una IA nunca se equivoca.
El informe presenta las causas propuestas como hipótesis revisables.

Presupuestos iniciales configurables: paquete máximo 32 000 caracteres; salida
máxima 1 500 tokens cuando el protocolo/modelo lo admita; deadline de análisis
120 s y timeout por petición <=60 s, siempre acotado al restante. Máximo **tres
peticiones reales totales**, incluyendo hasta dos correcciones de formato y
reintentos de transporte; no multiplicar políticas de retry.

401/403 y modelo inválido no se reintentan. 429/5xx admiten espera acotada al
deadline y al contador global. Rechazo, truncado, cuota, TLS, JSON malformado y
salida vacía tienen causas separadas. Uso desconocido es null; costes solo se
estiman si hay tarifas configuradas con fecha, nunca se inventan. Los límites
locales de peticiones/tokens no son una garantía del importe facturado por terceros.

### Casos LLM simulados y reales

Los tests de contrato de transporte usan respuestas sintéticas para los tres
proveedores, sin claves ni red. Los escenarios reales viven fuera del pytest
predeterminado, exigen activación y disponen de una política de salida limitada
al proveedor configurado. La presencia de una clave nunca activa el modo real.

Caso inicial concreto: reparación de un recurso del fixture `crud-h2` cuyo DELETE
devuelve 200 en lugar del 204 exigido por el oráculo independiente. Materializar
la variante defectuosa en un workspace propio y ejercer el servicio de reparación
real por HTTP con su contrato de estado/diagnóstico. La directiva pide corregir
ese comportamiento en el archivo Java permitido, sin alterar pom.xml ni tests.
La configuración y ubicación de archivos pertenecen al perfil/fixture; no añadir
conocimiento Quarkus dentro del coordinador Python.

Demostrar el control negativo antes de reparar, registrar el cambio aplicado por
los guards de producción y volver a ejecutar el mismo oráculo después. Para el
nivel Python se declara el compilador doble y solo se acredita contrato/patch;
para el nivel completo se exige el fallo y posterior resultado Maven real.
Un caso del producto generado sin invocar IA por su camino template-first no
sustituye esta prueba: cero peticiones no cierra AC-16. Contabilizar llamadas en
la frontera real sin registrar su contenido. La generación determinista completa
sigue cubierta por las suites existentes; no se promete generación libre de
proyectos nuevos para cada proveedor en esta primera versión.

Dos niveles explícitos:

- **Contrato/integración Python:** llamada real, flujo del producto, parseo y
  guards; compilador doble declarado cuando no hay JDK. Se puede medir en la PC
  mínima y no acredita compilación del código recibido.
- **Aceptación Java completa:** los mismos archivos recibidos, identificados por
  hash, pasan por Maven offline y los oráculos independientes existentes. Requiere
  el entorno del trabajo 4; falta de toolchain mantiene incompleto ese nivel.

La configuración `llm_tests.verify_generated_java` selecciona el segundo nivel.
El cierre completo exige medirlo para los tres proveedores. Usar un caso acotado
por proveedor, máximo seis solicitudes por proveedor/dieciocho por campaña,
incluidos retries/reparación y respetando el límite del grafo. No adaptar el
oráculo a la respuesta obtenida. Un defecto descubierto del producto es FAILED/1
y se registra; no se interpreta un rechazo/timeout del proveedor como caso aprobado.

No entregar claves a otros procesos: solo el cliente/proceso que las requiere.
La campaña ordinaria conserva el bloqueo de tráfico externo; la campaña real
habilita exclusivamente la frontera prevista, sin quitar globalmente los guards.
Las claves se leen del entorno al usarlas, no de JSON/CLI ni de archivos del repo.
Mantener separados los paquetes de análisis y los prompts sintéticos de pruebas.

**Puerta 7:** contratos offline completos y llamadas reales observadas para Gemini,
DeepSeek y OpenAI; cuatro combinaciones verificadas; límites, errores y redacción;
resultado determinista intacto y aceptación Java real trazada. Falta de claves/
conectividad deja pendiente la medición correspondiente, nunca «PASSED» simulado.

## 5. Trabajo 8 — GitHub Actions

### Workflows

`qa.yml`: `pull_request`, `push` a la rama de integración actualmente `master` y
`workflow_dispatch` con perfil mínimo/completo. Jobs previstos:

| Job | Entorno y alcance |
| --- | --- |
| core | Windows/Linux, Python 3.12 de referencia; aceptación QA sin suites pesadas y suite histórica Python. |
| platform | Servicios HTTP reales y resultado del producto. |
| frontend | Node fijado compatible — referencia 22 —, npm ci, Vitest/typecheck/build. |
| functional | Perfil completo: JDK 21/Maven 3.9.9, Java y Playwright con Chromium del lockfile; medir Windows y Linux. |
| summary | Siempre intenta consolidar manifiestos y subir reportes de jobs disponibles. |

No usar contenedores ni servicios Docker. Fijar etiquetas de runner soportadas y
revisiones SHA de acciones oficiales al implementar. El job core no debe ejecutar
accidentalmente `pytest qa_tests` entero sin las herramientas que exigen sus tests
Java/browser. Clasificar esos tests por requisitos y comprobar el inventario para
que ningún caso desaparezca por falta de marcador. Los escenarios LLM reales
quedan fuera de la colección ordinaria.

En PRs ejecutar core/platform/frontend. En push a master y ejecución manual con
perfil completo ejecutar también functional. Un resumen de PR no afirmará haber
medido Java/navegador. Evitar filtros que dejen un check requerido esperando sin
resultado; registrar expresamente los jobs no seleccionados. Los perfiles son
selecciones explícitas, no reinterpretaciones de suites bloqueadas.

El producto actualmente puede mantener rojo platform por la persistencia conocida.
Ese resultado no se suprime ni se convierte en xfail para dejar verde el workflow.
La aceptación del agente verifica que diagnostica ese fallo; la calidad del
producto conserva su estado separado en el resumen.

### Preparación y artefactos

- Instalación de Python/Node/JDK/Maven, paquetes y Chromium en pasos explícitos
  anteriores a `run`. El job funcional prepara fixtures y usa `quarkus:go-offline`
  para cada perfil necesario. El veredicto Maven usa `-o` y cache por ejecución.
- Claves de cache por SO, arquitectura, Python/Node/JDK/Maven, locks y huellas de
  perfiles/fixtures. No dar por preparada una cache por tener un marcador vacío.
  Un miss se prepara antes de medir; un fallo de preparación queda bloqueado/error.
- No cachear .env, claves, resultados, bases de datos ni workspaces de aplicación.
  Evitar reutilizar caches escritas por código no confiable en jobs con claves.
- Capturar el exit code del coordinador, recolectar evidencia con `always()` y
  terminar con ese fallo. No usar `continue-on-error` o un último comando de
  reporte exitoso para borrar el fallo de tests. Usar nombres por SHA/job/SO/run.
- Subir HTML, manifest, JSON/JUnit, logs y adjuntos redactados permitidos, incluso
  ante fallo. Retención inicial corta y explícita — siete días — en repo privado;
  no publicar Pages ni enlaces públicos. El resumen incluye vínculos a artefactos.

`qa-llm-live.yml`: exclusivamente `workflow_dispatch` sobre referencia confiable,
proveedor/modelo/perfil como datos validados y límites fijos. Claves en secrets de
un environment limitado a ramas confiables; aprobación del environment cuando la
política del repo lo requiera. No usar `pull_request_target` para ejecutar código
de una PR con secretos, ni pasar claves a jobs ordinarios. Sin secretos se informa
bloqueo y no se declara validado el proveedor.

Permiso ordinario `contents: read`, checkout sin persistencia de credenciales y
permisos adicionales solo si la acción oficial realmente los requiere. El plan
no incluye comentarios automáticos en PRs, creación de issues, push o cambios de
protección de ramas. Ejecutar workflows reales requiere que estos archivos estén
publicados en una referencia accesible y que Actions tenga cuota/permisos: si no
se puede, dejar I06 pendiente, no reemplazar la medición por inspección de YAML.

**Puerta 8:** ejecuciones reales de los perfiles ordinario/completo y campaña LLM
manual, con run/job/SHA/artifact identificados; probar un fallo controlado de suite
que deje el job rojo y el reporte descargable. Registrar consumo/retención y
limitaciones de acceso observadas sin prometer cuota de GitHub para el repo privado.

## 6. Trabajo 9 — portabilidad, documentación y entrega

### Perfiles para el usuario

| Perfil | Puede hacer | Necesita |
| --- | --- | --- |
| Python | doctor/list, pruebas Python y plataforma, reportes; pruebas LLM de contrato/integración Python. | Python compatible y paquetes QA preparados. |
| Python + API | Lo anterior más análisis o casos reales optativos. | Conectividad, CA/proxy válidos, clave/modelo configurados. |
| Completo | Java, frontend y navegador; aceptación de código producido con LLM real. | JDK/Maven/cache, Node/node_modules y Chromium compatibles. |

Usar Python 3.12 como versión de referencia observada. Auditar las dependencias
antes de prometer todo el rango `>=3.11` del proyecto; añadir medición de 3.11 o
declarar el rango QA realmente soportado sin cambiar silenciosamente el del producto.

Una extensión de VS Code no instala Python, Java, Node o Chromium de forma
equivalente a tenerlos disponibles. Si la empresa no permite preparar paquetes,
explicar el bloqueo y el procedimiento con entorno aprobado; no pedir privilegios
ni eludir controles de instalación.

### Instalación reproducible

Conservar CLI por `python scripts/qa.py` y `python -m qa_agent`. Preparar un venv
por usuario con pip; uv es opcional, nunca requisito para la PC mínima. Mantener
requirements/locks coherentes y separar, si hace falta, las dependencias de
operación del coordinador de las necesarias para probar el producto.

Crear documentación y scripts de preparación registrados, con pasos visibles:

1. Copiar/clonar el proyecto; Git no es requisito de ejecución. Sin Git se usan hashes.
2. Comprobar versión/arquitectura Python y crear venv local sin administrador.
3. Instalar dependencias fijadas; para red restringida preparar un wheelhouse
   compatible en una máquina autorizada y usar pip `--no-index --find-links`.
4. Ejecutar doctor/list y seleccionar perfil; no seleccionar automáticamente todo.
5. Solo para perfil completo, instalar runtimes autorizados en rutas de usuario
   o utilizar los ya disponibles; preparar Maven/npm/Chromium explícitamente.
6. Configurar claves mediante entorno de terminal o entorno de CI; guardar solo
   ejemplos vacíos de nombres de variables. Configurar CA/proxy sin desactivar TLS.
7. Ejecutar, abrir HTML local y transferir el paquete de evidencia redactado.

Wheelhouses/caches son específicos de SO, arquitectura, Python y versiones.
Registrar inventario y checksums; comprobar que no incluyen credenciales. No
copiar .venv o node_modules desde otro SO como método de instalación. Maven y
Chromium se preparan para el SO de destino; no asumir las carpetas ignoradas de
esta máquina. Los scripts de setup no son llamados dentro de `run`.

Añadir `.vscode/tasks.json` usando el intérprete configurado/venv y argumentos
estructurados: QA doctor, perfil Python, completo, generar reporte y analizar
opcionalmente. No shell concatenada, rutas `C:/Users/willi`, claves en settings
o dependencia de una extensión de IA. Incluir comandos equivalentes para
PowerShell y terminal POSIX.

### Validación real de portabilidad

- Reproducir desde copia limpia con usuario sin privilegios en otro entorno
  Windows: otro PC disponible o un runner Windows independiente. Medir perfil
  mínimo con herramientas opcionales fuera del alcance del perfil y comprobar
  que no se usan rutas/caches/servicios del PC original.
- Medir perfil completo en Windows y Linux de CI. Ensayar instalación en frío
  y ejecución caliente sin descargas; analizar bloqueos de red por separado.
- Probar cwd externo, espacios/caracteres Unicode, rutas largas, destino sin
  escritura, paquetes/browser incompletos, ausencia de Git, clave errónea, proxy/
  CA incorrectos, copia interrumpida, deadline e hijos huérfanos. Confirmar cleanup
  y centinelas externos sin matar servicios ajenos.
- La simulación de capacidades tiene valor como regresión, pero no sustituye la
  segunda máquina. No se requiere activar virtualización en la PC del usuario.
- Una máquina de CI no prueba las políticas específicas de la empresa. Si no se
  accede a la PC del trabajo, registrar esa validación como no realizada; no
  certificarla ni afirmar soporte de macOS sin ejecución.

**Puerta 9:** instalación repetible por terceros, perfiles medidos en entornos
identificados, tareas VS Code/terminal verificadas y guía con fallos/bloqueos
esperados. La restricción «cualquier PC» se cumple por requisitos explícitos y
degradación honesta, no mediante prometer ejecutar Java sin JDK.

## 7. Estados, orden y aceptación final

### Política de salida

`result.json` conserva su `status` y `exit_code` de tests. `delivery.json` distingue
esa salida de la de la operación completa:

| Situación | Salida de la CLI |
| --- | --- |
| Tests aprobados; HTML entregado; IA desactivada o completada | 0. |
| Tests fallidos; informe generado, con o sin análisis | 1; fallo de tests visible. |
| Configuración inválida | 2, sin ejecutar la capacidad inválida. |
| Error de ejecución/evidencia/HTML | 3; conservar por separado la salida de tests. |
| Tests incompletos o análisis solicitado que queda bloqueado/fallido con base aprobada | 4; base conservada, entrega parcial declarada. |
| Interrupción del usuario | 130. |

Si los tests fallaron y también falla el análisis, conservar salida 1; un error
del informe/ejecutor sigue teniendo prioridad 3 y muestra el fallo de tests en
su campo propio. No activar una política alternativa de silenciamiento por defecto.
`report`/`analyze` sobre un run fallido preservan esa salida de pruebas, aunque
consigan generar sus archivos: un último comando no transforma rojo en verde.
Un histórico sin datos verificables se describe como limitado, no se «completa»
inventando campos. Añadir regresiones de todas las combinaciones.

### Orden

```text
G01..G06 -> D01..D02 -> R01..R04 ---------> A03..A04 ----+
                 |                     /              |
                 +-> A01..A02 -> A05..A08 --------------+-> V01..V03
                 |                                    |
                 +-> I01..I04 -> I05..I06 -------------+
                 |                                    |
                 +-> P01..P03 -> P04..P07 -------------+
```

Contratos primero; aceptar el reporte antes de integrar sus secciones IA. CI
ordinario no depende de claves ni de cerrar el proveedor real; el cierre final
sí exige la medición real pendiente. Documentación/instalación se elaboran desde
el inicio y se validan con el artefacto final.

Antes de implementar cada comportamiento establecer su comprobación fallida.
Medir mediante casos significativos, no fijar como éxito los números históricos.
Al cerrar, ejecutar regresiones 003/004, nuevas pruebas QA, suites del producto,
casos LLM y perfiles CI/portabilidad. Mantener matrices separadas de aceptación
del agente y fallos del producto. No declarar cierre con proveedores/plataformas
pendientes, una PR sin ejecutar, o una prueba que solo fue simulada.

Crear `verification.md` y actualizar `ESTADO.md` de esta feature únicamente con
evidencia observada al ejecutar: requisito, tarea, comando, versión, revisión/
huella, caso, salida, artefacto y limitación. El plan actual no crea esos resultados.

## 8. Fuentes primarias consultadas

Consultadas el 2026-10-19. Revalidar API/modelos/acciones al implementar:

- [OpenAI: Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses): Responses permite pedir una salida estructurada; validar igualmente el contrato local.
- [Gemini: Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output): esquema y capacidades específicas de su API/modelos.
- [DeepSeek: Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/): JSON Output con instrucción JSON y manejo de truncamiento; no asumir JSON Schema estricto en este protocolo.
- [GitHub: Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax): eventos, jobs, condiciones y permisos.
- [GitHub: Workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts): artefactos descargables de campañas.
- [GitHub: Dependency caching](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching): preparación/caches separadas de la evidencia.
- [GitHub: Secure use](https://docs.github.com/en/actions/reference/security/secure-use): revisión de acciones y separación del código no confiable respecto a secretos.

Las APIs respaldan las opciones de transporte; los límites, perfiles, gates y
política de entrega anteriores son decisiones de este proyecto.
