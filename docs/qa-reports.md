# Manual de Informes Consolidados y Paquetes de Evidencia QA

Este documento describe la arquitectura, generación, inspección e integridad de los informes HTML y manifiestos de evidencia producidos por el ejecutor de pruebas (`qa_agent`).

---

## 1. Estructura del Paquete de Evidencia

Cada ejecución (`run`) o reconstrucción (`report`) produce un paquete determinista y relocalizable estructurado de la siguiente forma:

```text
.agentia-runtime/qa/<qa_trace>/
  ├── result.json                     # Contrato canónico de ejecución de pruebas (inmutable)
  ├── <suite_id>/                     # Directorio de artefactos propios de cada suite
  │   ├── junit.xml                   # Reporte JUnit XML saneado y acotado
  │   └── pytest.log                  # Log acotado con redacción previa de secretos
  ├── report/
  │   ├── report.html                 # Informe HTML estático consolidado auto-contenido
  │   ├── report_manifest.json        # Manifiesto de artefactos con hashes SHA-256
  │   └── assets/                     # Recursos locales (capturas PNG, etc.), sin dependencias remotas
  ├── analysis/                       # Opcional (solo si se solicitó análisis IA)
  │   └── analysis.json               # Diagnóstico de hipótesis e inferencias deterministas
  └── delivery.json                   # Estado operacional de entrega y códigos de salida
```

---

## 2. Comandos Disponibles

### 2.1 Generación Automática en `run`

Por defecto, al finalizar la ejecución de las suites seleccionadas, `qa_agent run` genera automáticamente el informe HTML, el manifiesto y el archivo `delivery.json` en el directorio de evidencia:

```bash
python scripts/qa.py run --suite python
```

### 2.2 Reconstrucción Offline con `report`

El comando `report` reconstruye el informe HTML y valida o genera el manifiesto exclusivamente a partir del archivo `result.json` y de los archivos presentes en disco.
**Garantía determinista:** No ejecuta subprocesos, no invoca pruebas ni modelos LLM, y no altera el veredicto ni el hash de `result.json`.

```bash
python scripts/qa.py report --input .agentia-runtime/qa/<qa_trace>/result.json
```

Opciones admitidas:
- `--input <path>`: Ruta obligatoria al archivo `result.json`.
- `--output-dir <path>`: Directorio destino personalizado para el informe generado (por defecto, `report/` dentro del directorio del run).
- `--json`: Emite el manifiesto `QAReportManifest` en formato JSON estructurado por salida estándar.

---

## 3. Características de Seguridad y Autocontención del HTML

El archivo `report.html` está diseñado bajo los siguientes principios estrictos de seguridad e higiene:

1. **Cero solicitudes de red:**
   - Todo el CSS se encuentra embebido dentro de la etiqueta `<style>`.
   - No utiliza Google Fonts ni tipografías remotas (emplea el sistema de fuentes nativo del sistema operativo).
   - No incluye scripts externos ni dependencias de CDNs (`unpkg`, `cdnjs`, etc.).
   - La interactividad (plegado y despliegue de diagnósticos) se realiza mediante etiquetas HTML5 nativas (`<details>` y `<summary>`).

2. **Mitigación de XSS e inyecciones:**
   - La plantilla Jinja2 opera con `autoescape=True` estricto.
   - Cualquier contenido malicioso (por ejemplo, scripts o payloads en nombres de casos de prueba o mensajes de aserción) se renderiza como texto plano escapado (`&lt;script&gt;`).
   - Se prohíben esquemas peligrosos en enlaces (`javascript:`, `data:`).

3. **Confinamiento de enlaces y relocalización:**
   - Todos los enlaces dentro del informe son relativos al directorio del run (`../python/junit.xml`, `report_manifest.json`).
   - Se prohíbe el uso de enlaces absolutos o con navegación hacia atrás (`..`) que apunten fuera del paquete de evidencias.
   - El paquete completo puede comprimirse en ZIP o moverse a otra ruta o máquina sin que se rompan los enlaces internos.

---

## 4. Manifiesto de Artefactos e Integridad

El archivo `report/report_manifest.json` valida la correspondencia y autenticidad de cada artefacto:

- **Huella de `result.json`:** Se almacena el hash SHA-256 exacto de `result.json` (`test_result_sha256`). Si alguien altera manualmente el veredicto en `result.json`, el validador de integridad detecta la discrepancia inmediatamente.
- **Inventario exhaustivo:** Cada archivo (JUnit XML, logs, reportes, imágenes) se registra con su `id`, `path` relativo, tipo inferido, tamaño en bytes, hash SHA-256 y procedencia (`qa_agent.run`, `qa_agent.reporting`, `suite.python`, etc.).

---

## 5. Política Oficial de Códigos de Salida

El archivo `delivery.json` distingue el resultado de las pruebas (`test_exit_code`) del resultado de la entrega global (`delivery_exit_code`):

| Situación | Salida de la CLI | Significado operacional |
|---|:---:|---|
| Tests aprobados; HTML entregado; IA desactivada o completada | **0** | Éxito total de la campaña y entrega. |
| Tests fallidos; informe generado, con o sin análisis | **1** | Fallo legítimo de pruebas. Visible en consola y reporte; no se oculta. |
| Configuración inválida o argumentos erróneos | **2** | Bloqueo previo sin ejecutar capacidades inválidas. |
| Error de ejecución interna, evidencia corrupta o fallo de HTML | **3** | Error en el harness o renderizador (conserva salida de tests por separado). |
| Tests incompletos o análisis solicitado bloqueado con base aprobada | **4** | Base de pruebas aprobada, pero entrega incompleta o capacidad bloqueada. |
| Interrupción del usuario (`Ctrl+C` / SIGINT) | **130** | Cancelación controlada con preservación de centinelas y limpieza. |

> **Regla de oro:** Un reporte exitoso sobre pruebas fallidas **nunca convierte el código 1 en 0**. El último comando ejecutado no transforma un resultado rojo en verde.
