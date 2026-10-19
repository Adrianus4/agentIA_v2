# Plan de implementación: trabajos 3, 4 y 5

Fecha: 2026-10-18 (America/Lima). Estado: planificación; sin implementación iniciada.
Requisitos: [spec.md](spec.md). Ejecución por tareas: [tasks.md](tasks.md).

## 1. Punto de partida

El ejecutor dispone de `doctor`, `list`, `run`, contratos QA en `contracts/models.py`,
aislamiento y el adaptador pytest. La aceptación actual tiene 17 pruebas; la
referencia Python del producto tiene 229 casos. Esas cifras son referencias
históricas, no una cuota que deba mantenerse al añadir cobertura.

El catálogo declara `frontend`, `java` y `playwright` todavía no implementados.
La CLI, los conteos, la selección de dependencias y la persistencia están centrados
en Python y un solo XML. Por ello se requiere una ampliación común pequeña antes
de incorporar motores nuevos, conservando las regresiones F01–F04.

Hallazgos del código que deben reflejarse en las pruebas:

- `/v1/blueprint/run` utiliza el grafo distribuido; `/v1/solution/run` genera en el
  orquestador y verifica condicionalmente si encuentra Maven allí.
- Los agentes se comunican por HTTP. TestClient/respx prueban otros niveles, pero
  no sustituyen la medición de sockets y procesos reales de este incremento.
- El generador utiliza plantillas y un cliente LLM perezoso. Las fixtures elegidas
  deben poder generarse sin claves; los caminos que requieren LLM usarán un doble
  acotado en el proceso de prueba, sin añadir proveedores ficticios al contrato público.
- La UI activa usa `WorkspaceRouter` y `DevOpsAndDeliveryView`: esta última crea
  ZIP con JSZip y tiene un fallback de solo README si faltan archivos. La vista
  antigua `ExportPublishView` no es el punto de entrada del recorrido actual.
- Hay sesiones de demostración precargadas en `StudioContext`, y una consola REST
  de previsualización en la UI. Sus respuestas no acreditan llamadas al servicio generado.
- `frontend/vite.config.ts` usa Vitest/jsdom. Hay que excluir expresamente los
  escenarios Playwright de su recolección y del proyecto TypeScript de la aplicación.

## 2. Alcance y catálogo propuestos

| Suite | Motor/objetivo | Dependencias | Qué demuestra |
| --- | --- | --- | --- |
| `python` | pytest sobre `tests/` | Python y paquetes actuales | Regresión existente en proceso; conserva selección predeterminada. |
| `platform` | pytest + HTTPX, con procesos FastAPI reales | Paquetes Python y puertos loopback disponibles | Contratos, transporte, grafo y persistencia. LLM y compilador usan dobles declarados cuando el caso los necesita. |
| `java` | Driver pytest, Maven/Surefire y oráculos Java | Python, JDK 21, Maven 3.9+, cache preparada | Generación, compilación y aceptación reales de código Quarkus. |
| `frontend` | Vitest 3, TypeScript y Vite | Node compatible y dependencias fijadas | Componentes, estados y build; API simulada en pruebas unitarias declaradas. |
| `playwright` | Playwright Test/Chromium | Node, Chromium instalado, Python y toolchain Java preparada | UI + HTTP + generación + Maven reales para el caso positivo completo. |

Normalizar `react -> frontend` y `browser -> playwright`, deduplicar y conservar
orden estable. Añadir `platform` al catálogo. Ninguna suite seleccionada pasa a
ejecutable solo porque tenga Python: cada adaptador evalúa sus requisitos.
No depender de GitHub o Docker para cumplir este plan.

Comandos de uso previstos, disponibles después de implementar el incremento:

```text
python -m qa_agent doctor
python -m qa_agent list
python -m qa_agent run --suite python --suite platform
python -m qa_agent run --suite java
python -m qa_agent run --suite frontend
python -m qa_agent run --suite playwright
python -m qa_agent run --config qa-functional.example.json
```

## 3. Contratos comunes, configuración y arquitectura

Ampliar de forma aditiva los contratos Pydantic y la configuración 1.0. Los archivos
anteriores seguirán siendo válidos; se conserva `timeout_seconds`, y se añaden
opcionalmente `suite_timeouts`, `java_cache_dir` y `browser_cache_dir`. Las rutas
son datos validados, nunca comandos. Sin opciones nuevas, el comportamiento sigue
siendo ejecutar `python`. No renombrar ni eliminar campos existentes.

Separar por suite los resultados y artefactos. Añadir metadatos de motor,
`process_exit_code`, pasos previos y procedencia; `pytest_exit_code` se conserva
para lectores existentes y vale null en motores que no sean pytest. Los casos
deben poder asociarse inequívocamente a suite, fixture y ejecución de aplicación.
Registrar revisión o huellas de las fuentes probadas, versiones y argumentos
permitidos, sin credenciales ni volcados de código.

Archivos orientativos, sujetos a las interfaces estables actuales:

```text
qa_agent/
  adapters/                # platform, java, frontend, playwright
  suite_registry.py        # selección y despacho de adaptadores
  result_normalization.py  # validación por dialecto y resultado común
  service_harness.py       # procesos propios, healthchecks y cierre
  execution.py             # conservar y reutilizar F02/F03/F04
  pytest_adapter.py        # conservar importaciones/interfaz usadas por regresiones
  evidence.py              # artefactos separados por suite, redacción existente
qa_scenarios/
  support/                 # aplicaciones de prueba y dobles en fronteras externas
  platform/                # nuevos casos HTTP, fuera de tests/ predeterminado
  java/                    # drivers de generación/Maven, fuera de tests/
  fixtures/                # blueprints, resultados esperados y oráculos independientes
qa_tests/                  # aceptación de los adaptadores y del coordinador
frontend/
  playwright.config.ts
  e2e/                     # navegador real, separado de Vitest
  src/test/                # conservar y ampliar pruebas de componentes
qa-functional.example.json
docs/qa-functional.md
```

No mover todo el ejecutor ni reescribir su interfaz para añadir estos adaptadores.
Generalizar los puntos Python-específicos indispensables: elegibilidad, despacho,
resumen, conteos y mapas de evidencia. `qa_tests/` no entra en el catálogo del
producto; Java/navegador no se agregan accidentalmente a `python`.

Cada adaptador devuelve su resultado común y referencia sus artefactos; la CLI
no reutiliza un único `sanitized_xml` para varias suites. Persistir, por ejemplo:

```text
<output>/<qa_trace>/result.json
<output>/<qa_trace>/python/...
<output>/<qa_trace>/platform/...
<output>/<qa_trace>/java/<fixture>/...
<output>/<qa_trace>/frontend/...
<output>/<qa_trace>/playwright/...
```

Para `run --suite python` conservar también las rutas históricas de evidencia
del incremento anterior. El trabajo 6 seguirá encargado del HTML consolidado.

### Política de resultados

- Se mantienen 0 aprobado, 1 fallo del producto, 2 configuración inválida,
  3 error de ejecución/evidencia, 4 incompleto y 130 interrupción.
- Validar XML/JSON según el formato real de pytest, Surefire, Vitest o Playwright.
  No quitar los controles F01 para tolerar otro dialecto: adaptar su lectura y
  probar sus invariantes. Cada ejecución usa directorios nuevos y reportes frescos.
- Fallo de compilación con diagnóstico comprobado o fallo de aserción del producto:
  FAILED/1. Dependencia/cache ausente: INCOMPLETE/4. Evidencia imposible, corrupta
  o un fallo del propio adaptador: ERROR/3. Un timeout de un caso de navegador es
  fallo del caso; el vencimiento del deadline global es un error del ejecutor.
- Un build o healthcheck son pasos verificables, no casos de prueba inventados.
  El número de casos se obtiene de los reportes, no del número de comandos.
- Omisiones, xfail y ausencia de casos seleccionados mantienen resultado incompleto.
  Desactivar reintentos automáticos de casos en el primer cierre; un caso inestable
  no se presenta como aprobado por haber pasado en un intento posterior.
- Mantener los estados propios del producto, por ejemplo GENERATED y NO_FIX,
  separados del resultado del test que comprueba ese comportamiento. Un caso que
  espera correctamente NO_FIX puede estar aprobado sin afirmar que se verificó Java.

## 4. Trabajo 3: plataforma y comunicación real

### Entorno de prueba

Crear un harness que lance orquestador, validador, generador, verificador y
reparador en procesos Python propios y sockets `127.0.0.1` con puertos asignados
por ejecución. Configurar URLs y claves sintéticas en sus entornos individuales.
Usar directorios independientes para SQLite, estado, generación y verificación.

El harness ofrece inicio, healthcheck con deadline, ejecución y cierre en `finally`.
Usa el control de procesos y buffers ya corregido. Si falla un arranque, retira
solo lo iniciado por esa ejecución; nunca mata procesos para liberar puertos.
Reservar/asignar puertos con reintento acotado ante carrera, sin asumir 8000–8004.

Reutilizar las aplicaciones de producción. Los dobles se limitan al cliente LLM,
runner de compilación o fallo que necesita provocar un escenario. Inicializarlos
en una factoría de prueba separada; nunca añadir una opción de bypass de guards
ni reemplazar todas las respuestas de la API por JSON prefabricado.

Retirar claves reales y bloquear salidas a proveedores en los procesos/contextos
de prueba, permitiendo solo los endpoints loopback propios. Un intento no esperado
de LLM falla el caso. Para la ruta positiva usar plantillas; para especificación
natural y reparación controlar la frontera LLM con respuestas/errores fijos.

### Matriz mínima

| Grupo | Casos |
| --- | --- |
| Autenticación/validación | Clave válida e inválida, ausencia de configuración, JSON de esquema inválido, blueprint semánticamente inválido y rechazo del gateway de agentes. |
| Asíncrono | 202, `trace_id`, estado terminal y consulta inexistente; historial coherente. Usar un punto de sincronización de prueba si se necesita observar RUNNING. |
| Persistencia | Comparar detalle, lista y estado; reiniciar el orquestador propio y recuperar la ejecución. Cubrir GENERATED en solución, sin esconder errores SQLite. |
| Grafo/fallos | Orden de pasos, verificador fallido, parche aplicado/rechazado/sin cambios, límite de reparación, servicio 5xx, respuesta mal formada, caída y timeout. |
| Aislamiento | Dos ejecuciones simultáneas y dos harness independientes; fuentes y base de datos distintas, centinelas preservados y ningún proceso residual. |

La prueba API usará los resultados esperados de los contratos existentes; no
asumir que todo error de blueprint debe ser HTTP 422, porque la validación de
negocio puede responder con un estado ERROR en una respuesta HTTP válida.

Puerta del trabajo 3: casos HTTP reales ejecutados y evidencia etiquetada
`http=real`, `llm=double`, `compiler=double` cuando corresponda; ninguna afirmación
de compilación Java real en esa suite. Los fallos reales del producto se registran.

## 5. Trabajo 4: generación y verificación Java reales

### Fixtures y oráculos

Crear fixtures independientes del código del generador, a partir de su esquema:

1. `crud-h2`: una entidad con identificador y campos String/BigDecimal; H2 en memoria,
   sin mensajería ni servicios externos. CRUD con respuestas y valores esperados.
2. `catalog-h2`: dos entidades, reutilizando el esquema de
   `blueprints/demo_quarkus.json` y fijando expectativas de tipos/datos/campos.
3. `solution-h2`: solución mínima de dos servicios para medir la ruta distinta de
   generación, sus estados y evidencias separadas por servicio.

Versionar los blueprints, campos y criterios de aceptación. Los datos esperados y
tests adicionales vivirán en `qa_scenarios/fixtures/`, no se derivan copiando las
aserciones producidas por el generador. Añadir controles negativos de compilación
y aserción sobre copias de fixture, conservando intacto el repositorio del usuario.

### Preparación del entorno y caché

Detectar JDK 21 y Maven 3.9+ de verdad, incluyendo versión, ejecución y rutas de
wrappers de Windows. La preparación de dependencias es un paso separado, visible
y permitido por el entorno. No se instala Java ni Docker durante `run`.

Para resolver las dependencias de Quarkus usar su objetivo `quarkus:go-offline`
sobre los POM de referencia, con repositorio Maven dedicado; no asumir que
`dependency:go-offline` resuelve también todas las dependencias de deployment.
El veredicto posterior ejecuta Maven con `-o -B`, repositorio local aislado y sin
actualizaciones de snapshots. Si la caché está incompleta, informar el bloqueo.

No modificar `~/.m2` ni `settings.xml` corporativo. Preparar una caché de origen
inmutable y materializar una copia por ejecución para los metadatos que Maven
necesita escribir. Desactivar Dev Services de las fixtures y configurar H2 en
perfil de prueba para evitar dependencias implícitas de Docker/Testcontainers.

La restricción confirmada de no requerir Docker se aplica a este diseño. En host,
`mvn -o` significa resolución Maven offline, no aislamiento de red del SO equivalente
a `--network none`. Permitir HTTP local para las pruebas; declarar este límite y
no certificar hermeticidad de red que la máquina no pueda proporcionar.

### Flujo verificable

```text
blueprint/solución conocido
  -> API de prueba real
  -> archivos generados + manifiesto de huellas
  -> verificador con Maven real
  -> reportes Surefire propios de esa ejecución
  -> copia con oráculos independientes + Maven real
  -> casos, diagnósticos y resultado por servicio
```

En `java`, el harness reemplaza el doble Maven por el runner host real. Tanto
orquestador como verificador deben recibir la toolchain/cache adecuada, dado que
la ruta de solución verifica en el orquestador. Configurar el comando permitido
del verificador para offline y puertos de prueba dinámicos; no cambiar sus guards.

Para recoger Surefire del verificador, usar únicamente el scratch propio y su
opción existente `VERIFIER_KEEP_WORKSPACE` durante el escenario; copiar evidencia
redactada antes del cierre y retirar todos esos archivos después. Correlacionar
el workspace con fixture, `trace_id`, hashes y proceso; no buscar reportes en
directorios ajenos. La segunda ejecución del oráculo usa una copia identificada:
el origen generado se conserva y se identifica cualquier test añadido.

Además de compilar, comprobar crear/listar/consultar/actualizar/eliminar, valores
persistidos y recurso inexistente. Agregar rechazos de campos/duplicados cuando
el blueprint de referencia los exija; si el producto incumple, registrar el fallo.
No reducir expectativas para acomodar su comportamiento actual.

Un fallo de compilación puede carecer legítimamente de Surefire: conservar el
diagnóstico de compilación y marcar FAILED, no tratarlo como XML perdido después
de una supuesta ejecución de tests. Un proceso que afirma éxito de pruebas sin
reportes frescos y casos ejecutados no satisface la aceptación.

Puerta del trabajo 4: casos positivos y controles negativos ejecutados realmente,
informes separados de ambas rutas y oráculos, y distinción GENERATED/verificado.

## 6. Trabajo 5: interfaz y recorrido integrado

### Vitest y build

Conservar Vitest 3 y el lockfile; añadir solamente la dependencia Playwright
necesaria, fijando su versión compatible en implementación. Preparar paquetes y
Chromium explícitamente antes de las pruebas. `doctor` comprobará su disponibilidad;
`run` no usará `npx` para descargar herramientas faltantes.

Ejecutar las pruebas existentes y ampliar manejo de polling, fallo de autenticación,
fallo de red, fin en ERROR/NO_FIX, restauración de estado y ausencia de archivos
reales para exportar. Estas pruebas pueden simular fetch y lo deben declarar.

Producir JUnit/JSON con el reporter de Vitest instalado. Ejecutar TypeScript y
Vite como pasos separados con salidas/diagnósticos propios; el build no se cuenta
como caso unitario adicional. Excluir `frontend/e2e/` de Vitest y de los archivos
de aplicación que comprueba el build. No usar modo watch.

### Playwright

Usar Chromium, un worker y cero retries para el cierre inicial. Levantar el
frontend de prueba y la topología real del trabajo 4 en un sandbox propio. El
navegador tendrá contexto nuevo, almacenamiento vacío y datos sintéticos.

El caso positivo crea una sesión identificada por la ejecución QA y sigue la UI:
configurar datos estructurados -> generar -> observar progreso -> comprobar
resultado contrastándolo con API -> descargar ZIP. No necesita un proveedor LLM:
usar entrada estructurada y plantillas; si se prueba redacción de especificación,
la frontera LLM del backend se controla y se declara.

Comprobar una ejecución recién creada, no una sesión de demo de StudioContext.
No usar `route.fulfill` para las peticiones del backend en el caso integrado.
Los fallos de autenticación/backend se provocan sobre servicios de prueba propios.
No aceptar los resultados simulados de la consola REST visual como prueba de CRUD.

Esperar un evento de descarga real; abrir el ZIP y comprobar rutas, archivos y
huellas frente a `generated_files` de la ejecución. El fallback de solo README
debe fallar ese caso. Probar que se muestra el estado de error/no verificado,
evitando dar por buena una etiqueta de éxito inconsistente con el backend.

Capturas y trazas solo contienen datos/claves sintéticos; deshabilitar tráfico
saliente no esperado y evitar capturar secretos reales. Las trazas son adjuntos
diagnósticos; JSON/JUnit y aserciones independientes sostienen el veredicto.

Puerta del trabajo 5: Vitest y build ejecutados, casos Playwright reales sobre
backend/Maven real, ZIP validado y errores visibles comprobados. Sin toolchain,
registrar bloqueo y mantener pendiente este cierre integral.

## 7. Aislamiento, procesos y compatibilidad

- Ejecutar suites secuencialmente inicialmente. Probar concurrencia con dos
  ejecuciones QA para confirmar separación sin compartir estado mutable.
- Derivar snapshots por suite: `python` conserva sus recursos; `platform`/`java`
  añaden escenarios y soporte necesarios; frontend añade su código y dependencias
  preparadas. `qa_tests/`, claves y estado previo siempre quedan fuera.
- Materializar dependencias Node y Maven en el scratch sin escribir en el origen;
  usar copia convencional si no hay reflinks, sin exigir privilegios de symlink o
  junction. Registrar tiempo/espacio de preparación y detectar fallos de copia.
- Añadir un administrador de procesos persistentes al harness, reutilizando los
  buffers acotados y el control de descendientes; no usar el lanzador completo del
  usuario ni dejar que Playwright mate servidores que no le pertenecen.
- Los presupuestos incluyen arranque, pruebas y cierre acotado; un deadline por
  suite domina los timeouts internos. `suite_timeouts` permite, por ejemplo,
  `platform=180`, `java=1200`, `frontend=300`, `playwright=1500` segundos.
- Invocar CLI JavaScript locales mediante Node para evitar depender de `npm.cmd`
  en la ejecución. Para Maven/wrappers de Windows, implementar y probar un
  adaptador registrado con escape correcto: `shell=False` por sí solo no elimina
  las reglas de batch. Incluir rutas con espacios y metacaracteres en su aceptación;
  no aceptar fragmentos de shell en configuración o blueprints.
- Separar defecto del producto de defecto del agente: conservar los casos rojos
  legítimos y abrir un registro de incidencias con fixture y reproducción. Las
  correcciones de negocio descubiertas constituyen un seguimiento identificado,
  sin alterar tests para obtener verde ni ampliar funcionalidades silenciosamente.

## 8. Orden, aceptación y evidencia de cierre

Secuencia: base compartida -> trabajo 3 -> trabajo 4 -> trabajo 5 -> aceptación
conjunta. El adaptador Vitest puede prepararse después de la base compartida,
pero el cierre Playwright depende de las puertas 3 y 4.

Antes de cada capacidad nueva establecer la aceptación fallida; después ejecutar
sus pruebas focalizadas. Al integrar, volver a comprobar las 17 regresiones
históricas, la suite Python y la nueva aceptación. Añadir casos por comportamiento
significativo y fallos reales, sin tests que solo repitan la implementación.

Crear `verification.md` al ejecutar este plan, con dos matrices: capacidades del
agente y comportamiento del producto. Registrar comandos, versiones, identidad de
fuentes, suites, casos, pasos, evidencia y plataformas medidas. Un producto con
fallos puede ser diagnosticado correctamente por un agente aceptado; un motor
que nunca llegó a ejecutarse no acredita su cobertura.

Los problemas de permisos, instalación o revisión automática se documentan como
bloqueos de la medición. Las ejecuciones declaradas, las inspeccionadas y las
repetidas independientemente deben distinguirse. No crear workflows GitHub ni
activar proveedores para sustituir una comprobación local que quedó bloqueada.

## 9. Documentación primaria consultada

- [Reporters de Vitest 3](https://v3.vitest.dev/guide/reporters): salida JUnit/JSON
  en archivos y configuración correspondiente a la versión ya usada.
- [Reporters de Playwright](https://playwright.dev/docs/test-reporters): reportes
  estructurados y destino explícito del JUnit.
- [Quarkus 3.15 y Maven](https://quarkus.io/version/3.15/guides/maven-tooling/):
  preparación offline con conocimiento de dependencias de deployment.
- [Pruebas de Quarkus 3.15](https://quarkus.io/version/3.15/guides/getting-started-testing/):
  integración de pruebas Java/HTTP utilizada por el proyecto.
- [Opciones Maven 3.9](https://maven.apache.org/ref/3.9.9/maven-embedder/cli.html):
  ejecución offline explícita.
- [Subprocess de Python 3.12](https://docs.python.org/3.12/library/subprocess.html):
  tratamiento de argumentos y particularidades de archivos batch en Windows.

Este documento define trabajo futuro. No representa nuevas pruebas ejecutadas ni
implementa los adaptadores descritos.
