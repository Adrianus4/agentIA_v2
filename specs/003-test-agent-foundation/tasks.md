# Tareas: referencia inicial y ejecutor local

Estado inicial: todas pendientes. Alcance: trabajos 1 y 2 de los nueve acordados.
Leer [spec.md](spec.md) y [plan.md](plan.md) antes de ejecutar las tareas.
La creación de estos documentos no autoriza por sí sola iniciar su implementación.

Cada tarea se cierra con evidencia y archivos afectados. Para las capacidades
nuevas, establecer primero el escenario de aceptación fallido y después implementarlo.
Los fallos del producto se registran sin cambiar sus expectativas para obtener verde.

## Trabajo 1: referencia inicial

- [x] **B01 — Inventariar suites y puntos de entrada.** Revisar `tests/`,
  `frontend/src/test/`, scripts de auditoría, lockfiles y launchers. Registrar
  requisitos, mocks y efectos laterales en `baseline.md`. Cierre: cada comando
  candidato tiene una categoría y decisión de elegibilidad. Requisitos: RF-01.
- [x] **B02 — Fijar los recorridos de referencia.** Crear matriz de autenticación,
  validación, ejecución asíncrona, estados, reparación, generación, solución,
  aislamiento, UI y Java. Vincular pruebas existentes o registrar la brecha para
  trabajos posteriores. Depende: B01. Cierre: resultado esperado explícito por fila.
- [x] **B03 — Preparar entorno y aislamiento de medición.** Comprobar Python y
  disponibilidad de instalación en usuario; establecer dependencias fijadas desde
  los lockfiles y obtener versiones. Auditar llamadas externas, retirar claves y
  preparar una copia temporal acotada sin modificar las expectativas de los tests.
  Depende: B01. Cierre: cada suite es segura de ejecutar o tiene bloqueo documentado.
- [x] **B04 — Medir la referencia.** Recolectar y ejecutar pytest con evidencia
  JUnit y timeout; medir tests/build de frontend y auditorías solo cuando sean
  elegibles. Guardar revisión/huellas, comandos, conteos y terminación real.
  Depende: B02, B03. Cierre: resultados observados, incluso si contienen fallos.
- [x] **B05 — Cerrar el diagnóstico inicial.** Separar fallos del producto,
  dependencias, restricciones y errores de medición. Registrar pendientes y recursos
  necesarios sin inventar resultados. Depende: B04. Cierre: RF-01 y RF-02 satisfechos;
  bloqueos explícitos y alcance real identificados.

## Trabajo 2: ejecutor local

- [x] **E01 — Definir contratos y casos de aceptación.** Precisar los modelos QA
  en `contracts/models.py`, esquema JSON, estados y códigos del plan. Preparar
  fixtures de procesos y repositorios mínimos en `qa_tests/`. Depende: B05.
  Cierre: escenarios CA-01 a CA-11 trazados a comprobaciones concretas.
- [x] **E02 — Resolver arranque y repositorio.** Demostrar CA-03 y el diagnóstico
  sin dependencias preparadas; implementar `qa_agent/__main__.py`, `cli.py` y
  `scripts/qa.py`. Cierre: ayuda, raíz explícita y rutas con espacios funcionan
  desde otra carpeta sin instalar el proyecto como paquete. Depende: E01.
- [x] **E03 — Validar configuración.** Establecer pruebas de precedencia y
  rechazo de configuración inválida; implementar `config.py` y el ejemplo JSON.
  Cierre: CLI > JSON > defaults, sin comandos arbitrarios ni opciones inoperantes.
  Depende: E02. Requisitos: RF-03, RF-04, RF-06.
- [x] **E04 — Detectar capacidades y publicar catálogo.** Demostrar CA-01/02/06;
  implementar `capabilities.py`, `catalog.py`, `doctor` y `list`. Cierre: Python
  funciona sin herramientas opcionales; los paquetes ausentes se explican y las
  capacidades futuras quedan identificadas como no implementadas. Depende: E03.
- [x] **E05 — Aislar y limitar los procesos.** Demostrar CA-07/08 con procesos
  controlados; implementar `execution.py`, snapshots, directorios propios y limpieza.
  Cierre: timeout/interrupción detienen hijos propios, dos ejecuciones no colisionan
  y el archivo centinela se conserva. Depende: E04; reutiliza hallazgos de B03.
- [x] **E06 — Integrar pytest.** Demostrar CA-04/05/06/10/11; implementar el
  adaptador con `sys.executable -m pytest`, selección `tests/` y XML estructurado.
  Cierre: distingue aserciones, colección, omisiones, cero casos y evidencia corrupta;
  no ejecuta recursivamente `qa_tests/`. Depende: E05.
- [x] **E07 — Persistir y presentar evidencia mínima.** Demostrar CA-09 y los
  códigos finales; implementar `evidence.py`, redacción previa, JSON, XML saneado,
  log acotado y resumen terminal. Cierre: resultados consistentes y ninguna clave
  ficticia sembrada queda en consola ni archivos. Depende: E06.
- [x] **E08 — Fijar instalación y documentar uso.** Preparar `requirements-qa.txt`
  coherente con la referencia y una guía `docs/qa-local.md` con venv/pip, VS Code,
  comandos, artefactos, limitaciones y diagnóstico. No hacer obligatorio uv, Git,
  Node, Docker o un proveedor IA. Depende: E07.
- [x] **E09 — Aceptar el incremento.** Ejecutar `qa_tests/` y después la suite
  del producto mediante el agente; comparar con B04/B05. Comprobar dependencias
  ausentes y uso desde otra carpeta. Registrar plataformas realmente medidas y
  bloqueos pendientes. Depende: E08. Cierre: escenarios de aceptación satisfechos
  y guía suficiente para una segunda instalación autorizada.

## Evidencia de cierre

- [x] `baseline.md` contiene el inventario y resultados reales o sus bloqueos.
- [x] El ejecutor funciona por módulo y por lanzador absoluto.
- [x] Las pruebas de aceptación del ejecutor pasan; los fallos previos del producto
  se reproducen y explican, sin exigir que el proyecto completo esté aprobado.
- [x] Falta de Java, Node o Docker no bloquea pruebas Python elegibles.
- [x] Ninguna suite seleccionada pendiente, vacía, omitida o bloqueada produce salida 0.
- [x] No se incorporaron adaptadores Java/React/browser, IA, HTML completo ni CI
  como si fueran parte de estos dos trabajos.
- [x] El usuario dispone de los comandos y conoce el alcance exacto del resultado.
