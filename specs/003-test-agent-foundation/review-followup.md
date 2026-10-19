# Seguimiento de revisión: correcciones F01–F04

Fecha: 2026-10-18 (America/Lima).
Estado revisado: [ESTADO.md](ESTADO.md).
Antecedente histórico: [review.md](review.md).

## Resultado

Los cuatro hallazgos anteriores están resueltos en el código y respaldados por
las pruebas de regresión ejecutadas durante esta revisión. No se identifica un
defecto pendiente de F01–F04 que impida el cierre de los trabajos 1 y 2 dentro
de su alcance local Python documentado.

La comprobación realizada combina una nueva ejecución independiente de aceptación
con la inspección de los artefactos de la suite del producto aportados en ESTADO.md.
No se presenta esa evidencia previa como una nueva ejecución independiente.

## Verificación ejecutada

```text
.venv/Scripts/python.exe -m pytest qa_tests -q
  --basetemp=.agentia-runtime/qa-review-followup/acceptance-tmp
  --junitxml=.agentia-runtime/qa-review-followup/acceptance.junit.xml
```

Resultado: **17 passed in 33.35s**, sin errores ni omisiones.
Evidencia: [acceptance.junit.xml](../../.agentia-runtime/qa-review-followup/acceptance.junit.xml).

| Hallazgo | Corrección inspeccionada | Comprobación actual |
| --- | --- | --- |
| F01: aprobación de XML contradictorio | Validación de atributos enteros no negativos y correspondencia de totales, casos, errores, fallos y omitidos. | La regresión `test_f01_internally_contradictory_xml_counts_and_skipped_returns_exit_3` pasó mediante la CLI; espera ERROR / 3. |
| F02: descendientes activos después de salir el padre | Job Object y seguimiento de descendientes en Windows; terminación ante timeout e interrupción. | La regresión `test_f02_exited_parent_leaves_no_orphan_descendants_on_timeout_or_interrupt` pasó con procesos activos, padre finalizado y comprobación de PID. |
| F03: scratch sin limpiar y ausencia de reporte al fallar la copia | Limpieza protegida durante la preparación; captura del error por la CLI y persistencia del resultado de error. | La regresión `test_f03_snapshot_copy_failure_cleans_scratch_and_persists_error_evidence` pasó; verifica ausencia de scratch y presencia del reporte ERROR / 3. |
| F04: acumulación de toda la salida antes de recortarla | Lectores concurrentes de stdout/stderr con límite aplicado durante cada lectura. | La regresión `test_f04_bounded_stream_capture_limits_buffer_during_read` pasó con salida en ambos canales y límite de 4096 caracteres por canal. |

La interrupción de la nueva prueba F02 se induce mediante un temporizador que
lanza KeyboardInterrupt con los procesos activos; no se debe describir esta
comprobación como una pulsación física de Ctrl+C en otra máquina.

## Evidencia del producto inspeccionada

Se inspeccionaron directamente los artefactos del directorio
`.agentia-runtime/qa/qa-20261019T040551Z-0b6ddb7b/`:

- [result.json](../../.agentia-runtime/qa/qa-20261019T040551Z-0b6ddb7b/result.json):
  PASSED, salida 0, 229 casos recolectados y aprobados, sin fallos, errores u
  omisiones; duración del ejecutor 7,790 s.
- [python.junit.xml](../../.agentia-runtime/qa/qa-20261019T040551Z-0b6ddb7b/python.junit.xml):
  229 casos, 0 failures, 0 errors, 0 skipped; coincide con los totales JSON.
- Los archivos fuente QA inspeccionados tienen fechas de modificación anteriores
  a esa ejecución. Este dato aporta contexto, no equivale a una firma del snapshot.

También se comprobó la aclaración del baseline: el indicador ambiguo
`c_tmp_touched` fue reemplazado por los campos diferenciados
`c_tmp_preexisting_dirs_observed` y `c_tmp_modified_during_run`, con una explicación
en `baseline.md` y en la evidencia de medición.

## Limitación de esta sesión de revisión

Se intentó volver a ejecutar la suite del producto, las sondas independientes de
la revisión original y Ruff/mypy. La revisión automática de permisos rechazó el
inicio por falta de capacidad. El reintento individual de la suite del producto
también quedó sin ejecutar al vencer el plazo del revisor. Esto es un fallo del
mecanismo de aprobación, no una determinación de que los comandos sean inseguros.
No se eludió esa revisión mediante otro mecanismo de ejecución.

Por ello, solo la suite de aceptación de 17 casos se volvió a ejecutar aquí.
Ruff/mypy siguen siendo resultados declarados en ESTADO.md; las 229 pruebas del
producto están respaldadas por los artefactos existentes inspeccionados arriba.
Las copias de sondas preparadas en `qa-review-followup/` no se presentan como
ejecutadas ni como nueva evidencia de resultados.

## Alcance de cierre

El cierre se refiere a la referencia inicial y al ejecutor Python local. Se
mantienen los trabajos posteriores de cobertura de servicios reales, Java,
frontend/navegador, reportes HTML, IA y GitHub. Tampoco se certifica todavía una
segunda PC física ni Linux/macOS.

No se modificó la implementación del agente durante esta revisión.
