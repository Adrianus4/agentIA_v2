# Plan de implementación: trabajos 1 y 2 del agente de pruebas

Fecha: 2026-10-18 (America/Lima). Base inspeccionada: `d7a14ff`.
Estado: plan; todavía no se ha implementado ni ejecutado la referencia inicial.
Alcance contractual: [spec.md](spec.md). Secuencia ejecutable: [tasks.md](tasks.md).

## Resultado esperado

1. Un inventario y una referencia inicial verificable del proyecto.
2. Un ejecutor Python con `doctor`, `list` y `run`, que invoque la suite Python
   existente, detecte limitaciones y entregue evidencia mínima reproducible.

Se reutilizan las pruebas existentes. La ampliación de cobertura del producto,
los adaptadores Java/React/Playwright, el análisis con IA, el reporte HTML completo
y los workflows de GitHub pertenecen a los trabajos 3 a 8.

## Hallazgos que condicionan el diseño

| Evidencia | Consecuencia para este incremento |
| --- | --- |
| `pyproject.toml` declara pytest, pytest-asyncio y respx; hay 31 archivos `test_*.py`. | Reutilizar la suite `tests/`; contar los casos reales al recolectarlos, sin deducirlos de los archivos. |
| `frontend/package.json` y `frontend/vite.config.ts` configuran 13 archivos Vitest con jsdom. | Incluirlos en la referencia inicial cuando Node y sus dependencias estén disponibles; su adaptador del agente se implementará después. |
| Hay pruebas con `FakeLLMClient`, `SequenceRunner`, respx y `dry_run`. | Etiquetar la evidencia como simulada; no atribuirle compilación Java o servicios reales. |
| `scripts/cli.py` envía blueprints y consulta ejecuciones de negocio. | Crear una entrada de QA independiente, sin cambiar la CLI existente. |
| `scripts/verify_implementation_agent.py` y `scripts/guard_structure_agent.py` son auditorías específicas. | Revisar requisitos y efectos antes de ejecutarlas; no convertirlas automáticamente en la suite general. |
| `start.bat` y `start.sh` preparan y levantan la aplicación con otros requisitos. | El ejecutor QA no dependerá de esos lanzadores para pruebas Python en proceso. |
| `/v1/solution/run` verifica condicionalmente según Maven; `/v1/blueprint/run` usa el grafo distribuido. | Incluir ambas rutas en el catálogo de aceptación futuro; conservar la distinción GENERATED/verificado. |
| Existe `uv.lock` y `frontend/package-lock.json`. | Conservar versiones de referencia; no actualizar frameworks para implementar el ejecutor. |

Las cantidades anteriores son archivos observados, no casos ejecutados ni cobertura.

## Trabajo 1: establecer la referencia inicial

### A. Inventario y criterios de aceptación

Crear `baseline.md` junto a este plan y una matriz con estas columnas:
identificador, comportamiento esperado, prueba existente, nivel real/simulado,
dependencias, comando, estado observado, evidencia y seguimiento pendiente.

Catalogar como mínimo:

- Autenticación y validación de la API; blueprint válido e inválido.
- Envío asíncrono, `trace_id`, consulta de estado y persistencia.
- Orden del grafo, presupuesto de reparación, rechazo de parches y fallo de servicio.
- Generación de archivos y aislamiento de workspaces.
- Ruta de solución y diferencia entre GENERADO y VERIFICADO.
- Pruebas de componentes React y recorrido de generación desde la interfaz.
- Compilación/pruebas del servicio Java generado como comprobación posterior.

Marcar los recorridos sin cobertura existente como pendientes de los trabajos 3 a 5.
No crear esa cobertura durante este incremento.

### B. Preparar una ejecución observacional

- Registrar versión de Python, SO, revisión y estado del árbol cuando Git exista.
  Sin Git, registrar huellas de los archivos relevantes. Identificar expresamente
  cambios locales respecto a la revisión para no atribuirles resultados incorrectos.
- Revisar imports, mocks, subprocess, rutas de salida y posibles llamadas externas
  antes de ejecutar cada suite o auditoría. Comprobar límites de los workspaces.
- Usar entorno virtual de usuario y dependencias fijadas. Cuando no sea posible
  prepararlo, guardar el motivo como bloqueo; no instalar automáticamente herramientas.
- Trabajar sobre una copia temporal del código y los recursos necesarios, con
  huellas para relacionarla con el original; excluir claves, cachés y estado previo.
- Revisar particularmente escrituras fuera de la copia. Bloquear o aislar por caso
  las pruebas no acotables. No imponer `AGENTIA_WORKSPACE_ROOT`, `LLM_PROVIDER`
  o `VERIFIER_DRY_RUN` globalmente: pueden cambiar expectativas de pruebas existentes.
- Retirar credenciales reales del proceso de pruebas y comprobar que los caminos
  auditados usan dobles controlados. Si esto no puede garantizarse para una prueba,
  dejarla bloqueada hasta aislarla; no depender de que falte una API key.

### C. Medir y documentar

Comandos de referencia, después de la preparación anterior y desde el directorio
adecuado de la copia temporal:

```text
python -m pytest --collect-only -q tests
python -m pytest tests --junitxml=<evidencia>/python.junit.xml
```

Si Node/npm y dependencias están disponibles, medir también `npm test` y
`npm run build` en `frontend/`. Revisar por separado la elegibilidad de los scripts
de auditoría existentes. Ninguna comprobación opcional ausente bloquea medir Python.

Guardar comando, cwd, versiones permitidas, inicio/fin UTC, duración, salida del
proceso, número de casos y referencia a evidencia redactada. Aplicar un tiempo
máximo explícito desde el principio. Si pytest imprime un resumen pero no termina,
registrar el timeout y el estado observado; el resumen no basta para declarar éxito.

Clasificar problemas como fallo previo del producto, dependencia ausente, limitación
de entorno o problema de la propia medición. No corregir fallos del producto ni
reducir sus aserciones para completar esta referencia. Una corrección necesaria
para aislar una prueba se debe identificar por separado y conservar el resultado
original; nunca modificar una expectativa de negocio para hacerlo pasar.

**Puerta de salida:** `baseline.md` contiene evidencia observada o un bloqueo
razonado por cada elemento seleccionado. Todos los resultados siguen pendientes
hasta que esa ejecución ocurra.

## Trabajo 2: construir el ejecutor local

### Arquitectura y archivos previstos

```text
qa_agent/
  __init__.py
  __main__.py         # entrada python -m qa_agent
  cli.py             # argparse; ayuda y diagnóstico de arranque con stdlib
  config.py          # JSON versionado y resolución de rutas
  capabilities.py    # Python, paquetes y herramientas opcionales
  catalog.py         # suite python y requisitos de capacidades futuras
  execution.py       # subprocess, timeout, aislamiento y ciclo de vida
  pytest_adapter.py  # comando registrado y lectura XML
  evidence.py        # resumen, persistencia mínima y redacción
scripts/qa.py        # lanzador absoluto para ejecutar desde otro directorio
qa_tests/            # aceptación del ejecutor; fuera de tests/ del producto
qa-agent.example.json
requirements-qa.txt  # dependencias fijadas, instalables con pip sin uv obligatorio
docs/qa-local.md
```

Añadir modelos Pydantic de QA en `contracts/models.py`, conforme a la constitución,
sin cambiar contratos existentes. Separar el diagnóstico de arranque de las
importaciones del producto para que la ayuda y la detección de dependencias
ausentes funcionen incluso si el entorno todavía no está preparado.

Los modelos compartirán `schema_version`, `trace_id`, capacidades, suites
seleccionadas, casos, conteos observados, estado, motivos, duración y referencias
a evidencias. Los datos del proveedor LLM no se incorporan en este incremento.

### Interfaz propuesta

```text
python -m qa_agent doctor
python -m qa_agent list
python -m qa_agent run --suite python
python -m qa_agent run --config qa-agent.example.json --timeout-seconds 600
python "C:/ruta del proyecto/scripts/qa.py" doctor --repo "C:/ruta del proyecto"
```

La entrada por módulo se usa desde la raíz; el lanzador absoluto hace accesible
el paquete desde otra ubicación sin instalar el repositorio como paquete editable.
El intérprete seleccionado ejecuta pytest mediante `sys.executable -m pytest`.

- `doctor`: inspección local, con texto o JSON; no instala, arranca servicios,
  llama proveedores ni exige Git/uv. Diferencia requisito obligatorio y opcional.
- `list`: muestra suites ejecutables y capacidades futuras identificadas como
  NO IMPLEMENTADAS. Solo `python` se puede ejecutar en este incremento.
- `run`: valida configuración, prepara aislamiento, ejecuta la suite elegida,
  verifica la evidencia y escribe el resumen final. Su selección predeterminada
  es `python`; el alcance se muestra siempre y no se presenta como validación total.
- Configuración JSON: `schema_version`, `suites`, `timeout_seconds`, `output_dir`.
  Precedencia: opciones CLI > JSON > valores predeterminados. Rechazar claves
  desconocidas, tipos inválidos, rutas problemáticas y límites no positivos.
- Una suite conocida pero todavía no implementada devuelve resultado incompleto.
  Una suite desconocida es error de configuración. Opciones de IA no implementadas
  se rechazan explícitamente, sin aparentar que están disponibles.

### Ejecución y evidencia mínima

Usar argv de comandos registrados, `shell=False`, cwd explícito y plazos limitados.
No aceptar comandos arbitrarios desde JSON. Las pruebas del agente en `qa_tests/`
no se incluyen automáticamente en el catálogo del producto, evitando recursión.

Reutilizar el aislamiento auditado en el trabajo 1. Copiar exclusivamente recursos
necesarios, revisar enlaces simbólicos y no copiar `.git`, `.env`, `.venv`,
`node_modules`, cachés o evidencias previas. Cada ejecución crea su propio scratch
con marcador de propiedad. Limpiar solo esos directorios, después de guardar
evidencia redactada, incluso ante fallos o interrupciones. Nunca borrar una ruta
recibida del usuario como si fuera un scratch propio.

Cerrar procesos hijos propios con una estrategia específica para Windows y otra
para POSIX; no detener servicios o procesos ajenos. Limitar duración y volumen de
salida capturada. Una captura truncada debe señalarse en el resultado.

Guardar como mínimo en `.agentia-runtime/qa/<trace_id>/`:

- `result.json`: metadatos y resultado normalizado.
- `python.junit.xml`: evidencia estructurada redactada.
- `python.log`: diagnóstico acotado y redactado, sin volcar código, diffs o secretos.

La redacción ocurre antes de escribir o imprimir evidencia; no mantener una copia
cruda persistente. Identificar valores sensibles conocidos del entorno y patrones
de credenciales. Recoger únicamente variables técnicas permitidas, nunca el entorno
completo. Revisar también los fragmentos de código que pytest puede incluir en XML.
El HTML y la consolidación de otras herramientas se desarrollan en el trabajo 6.

Interpretar el XML junto con el código y la terminación real del proceso. No
extraer conteos buscando texto como `passed` en stdout. Si no hay XML válido o hay
inconsistencia, emitir error; no inventar cero fallos ni asumir éxito.

### Estados y códigos de salida

| Código QA | Significado |
| --- | --- |
| 0 | Alcance seleccionado completo; al menos una prueba aprobada, sin fallos, errores, pendientes ni omisiones. |
| 1 | Fallo de aserción en pruebas del producto, según el resultado real de pytest. |
| 2 | Configuración, argumentos o repositorio inválidos. |
| 3 | Error de colección, infraestructura, ejecución o evidencia; incluye timeout. |
| 4 | Ejecución incompleta: dependencia ausente, suite no implementada, ausencia de casos o pruebas omitidas/xfail. |
| 130 | Interrupción solicitada por el usuario; guardar evidencia parcial cuando sea posible. |

Registrar aparte el código original de pytest. Para resultados combinados:
ERROR > FAILED > INCOMPLETE > PASSED. Nunca ocultar casos bloqueados aunque otra
prueba ya haya fallado. `doctor` puede terminar con 0 si la suite Python es
elegible aunque falten herramientas opcionales; esto no significa que ejecutó pruebas.

### Pruebas de aceptación del ejecutor

Crear primero fixtures temporales controlados y los escenarios CA-01 a CA-11.
Usar procesos reales pequeños para probar propagación de fallo, timeout, limpieza,
rutas con espacios, selección vacía y artefactos inconsistentes. Simular únicamente
capacidades de máquinas que no estén disponibles; no llamar redes ni modelos.

Ejecutar la aceptación con `python -m pytest qa_tests`. Después, ejecutar la suite
del producto por el agente y comparar con la referencia del trabajo 1. Cuando haya
diferencias, analizar el entorno y las pruebas afectadas antes de repetir todo.
Documentar por separado qué plataformas se probaron realmente; una simulación de
PATH sin herramientas no demuestra ejecución en una segunda PC o en otro SO.

## Dependencias, riesgos y cierre

- El inventario y la elegibilidad preceden a la referencia ejecutada.
- La referencia puede contener fallos; no se exige arreglarlos para implementar QA.
- Los modelos/configuración preceden al ejecutor; el adaptador precede al cierre
  del resumen; la aceptación exige ambos trabajos completos.
- Si pip/red corporativa bloquean la preparación, registrar el impedimento y
  preparar instrucciones para una instalación autorizada; nunca asumir privilegios.
- Si una auditoría necesita archivos auxiliares ausentes o un entorno particular,
  documentar esa dependencia y no atribuirle resultados de una ejecución inexistente.
- La verificación hermética Maven y el presupuesto de reparación existentes se
  conservan: este incremento no incorpora otro compilador ni modifica esos contratos.

El incremento termina con la referencia documentada, el ejecutor aceptado, sus
dependencias reproducibles y una guía de uso local. Cualquier bloque pendiente se
mantiene visible. Este documento es planificación y no certifica resultados de pruebas.
