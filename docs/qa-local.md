# Guía de Uso Local del Ejecutor QA (`qa_agent`)

Esta guía describe cómo preparar, diagnosticar y ejecutar localmente el agente de aseguramiento de calidad (`qa_agent`) en Windows y desde Visual Studio Code, correspondiente a los **Trabajos 1 y 2** (`specs/003-test-agent-foundation/`).

---

## 1. Requisitos del Sistema

- **Obligatorios**:
  - Sistema operativo Windows (también compatible con entornos POSIX).
  - **Python `>= 3.11`** (entorno de referencia: **Python `3.12`**).
  - Entorno virtual de usuario con las dependencias fijadas en `requirements-qa.txt`.
- **Opcionales (no requeridos para este incremento)**:
  - `uv`, `git`, `node`, `npm`, `java` (JDK), `mvn` (Maven) y `docker` son opcionales. Su ausencia se informa en `doctor`, pero **no bloquea** la ejecución de la suite Python.
  - No se requiere clave de API ni conexión a proveedores de IA (Gemini, OpenAI, DeepSeek).

---

## 2. Preparación del Entorno Virtual con `venv` y `pip`

Desde una terminal de PowerShell situada en la raíz del repositorio:

```powershell
# 1. Crear el entorno virtual de usuario
python -m venv .venv

# 2. Instalar las dependencias fijadas sin requerir uv ni instalar el proyecto como paquete editable
.\.venv\Scripts\python.exe -m pip install -r requirements-qa.txt
```

> **Nota sobre redes corporativas o entornos restringidos**: Si políticas de proxy o firewall impiden descargar paquetes desde PyPI, `python -m qa_agent doctor` identificará exactamente qué paquetes faltan sin intentar instalarlos automáticamente. En ese caso, solicite la instalación autorizada o utilice una caché de ruedas (`--find-links`) aprobada por su organización.

---

## 3. Uso desde Visual Studio Code

1. Abra la carpeta del repositorio en VS Code (`File > Open Folder...`).
2. Abra la paleta de comandos (`Ctrl+Shift+P`) y seleccione **`Python: Select Interpreter`**.
3. Elija el intérprete de `.venv`: `.\.venv\Scripts\python.exe`.
4. Abra una terminal integrada (`Ctrl+\``) y ejecute cualquiera de los comandos descritos a continuación.

---

## 4. Comandos Disponibles

### 4.1 Diagnóstico del entorno (`doctor`)

Inspecciona la versión de Python, los paquetes obligatorios para la suite `python` y las herramientas opcionales del sistema, sin instalar paquetes ni levantar servicios:

```powershell
.\.venv\Scripts\python.exe -m qa_agent doctor
.\.venv\Scripts\python.exe -m qa_agent doctor --json
```

### 4.2 Catálogo de suites (`list`)

Lista las suites registradas, indicando cuáles son ejecutables en este incremento (`python`) y cuáles corresponden a trabajos futuros (`frontend`, `java`, `playwright`, marcadas como `NO IMPLEMENTADA`):

```powershell
.\.venv\Scripts\python.exe -m qa_agent list
.\.venv\Scripts\python.exe -m qa_agent list --json
```

### 4.3 Ejecución aislada de pruebas (`run`)

Copia los recursos necesarios a un directorio temporal (`scratch`) con marcador de propiedad, limpia variables sensibles del entorno, ejecuta la suite seleccionada con tiempo máximo y guarda evidencia redactada:

```powershell
# Ejecución predeterminada (suite python)
.\.venv\Scripts\python.exe -m qa_agent run --suite python

# Ejecución usando archivo de configuración JSON y límite de tiempo explícito
.\.venv\Scripts\python.exe -m qa_agent run --config qa-agent.example.json --timeout-seconds 600
```

### 4.4 Ejecución desde otro directorio o en rutas con espacios (`scripts/qa.py`)

Puede invocar el lanzador absoluto `scripts/qa.py` desde cualquier otro directorio de trabajo sin necesidad de instalar el repositorio como paquete editable:

```powershell
C:\ruta\al\proyecto\.venv\Scripts\python.exe "C:\ruta con espacios\finalagent\scripts\qa.py" doctor --repo "C:\ruta con espacios\finalagent"
C:\ruta\al\proyecto\.venv\Scripts\python.exe "C:\ruta con espacios\finalagent\scripts\qa.py" run --repo "C:\ruta con espacios\finalagent" --suite python
```

---

## 5. Configuración JSON (`qa-agent.example.json`)

El archivo `qa-agent.example.json` define la configuración base:

```json
{
  "schema_version": "1.0",
  "suites": [
    "python"
  ],
  "timeout_seconds": 300,
  "output_dir": ".agentia-runtime/qa"
}
```

- **Precedencia**: Opciones de línea de comandos (`CLI`) > Archivo `JSON` (`--config`) > Valores predeterminados.
- **Seguridad**: Se rechazan con código `2` claves desconocidas, comandos arbitrarios (`command`, `shell`), rutas con `..`, tiempos no positivos y opciones de IA aún no implementadas (`llm_provider`, `--ai-analysis`).

---

## 6. Evidencia Generada y Redacción de Secretos

Cada ejecución de `run` crea un directorio único bajo `.agentia-runtime/qa/<trace_id>/` con tres artefactos redactados:

| Archivo | Contenido |
| --- | --- |
| `result.json` | Resultado normalizado conforme al contrato `QARunResult` (`schema_version`, `trace_id`, `status`, `exit_code`, `counts`, `cases`, `capabilities`, `reasons`, `scope_note`). |
| `python.junit.xml` | Reporte JUnit XML saneado y redactado, sin volcados extensos de código fuente. |
| `python.log` | Diagnóstico de consola acotado y redactado, sin secretos ni diffs de código. |

Antes de mostrar por pantalla o escribir en disco, el ejecutor reemplaza por `[REDACTED]` cualquier valor sensible detectado en variables de entorno (`*_API_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`) y patrones de credenciales (`AIza...`, `sk-...`, `Bearer ...`, claves privadas PEM).

---

## 7. Códigos de Salida

| Código | Estado | Significado |
| --- | --- | --- |
| `0` | `PASSED` | Alcance seleccionado completo; al menos una prueba aprobada, sin fallos, errores, pendientes ni omisiones. |
| `1` | `FAILED` | Fallo de aserción en una o más pruebas del producto. |
| `2` | Error de configuración | Argumentos inválidos, clave desconocida en JSON, suite desconocida o ruta de repositorio inválida. |
| `3` | `ERROR` | Error de colección/importación en pytest, timeout agotado, XML ausente/corrupto o desacuerdo entre proceso y XML. |
| `4` | `INCOMPLETE` | Dependencia obligatoria ausente, suite aún no implementada (`java`, `frontend`, `playwright`), 0 casos recolectados o pruebas omitidas (`skip`/`xfail`). |
| `130` | `INTERRUPTED` | Ejecución interrumpida por el usuario (`Ctrl+C`). |

Para resultados combinados rige la prioridad: `INTERRUPTED (130) > ERROR (3) > FAILED (1) > INCOMPLETE (4) > PASSED (0)`.

---

## 8. Alcance Actual y Limitaciones

- **Alcance validado en este incremento**: Suite Python en proceso (`tests/`, 31 archivos / 229 casos), que utiliza dobles controlados (`FakeLLMClient`, `SequenceRunner`, `respx`, `TestClient`).
- **Pendiente de trabajos posteriores (Trabajos 3 a 8)**:
  - Adaptador de pruebas de componentes React/Vitest (`frontend`) y navegador real (`playwright`).
  - Adaptador de compilación y pruebas reales Maven/JUnit para servicios Java generados (`java`).
  - Integración opcional con proveedores LLM por API y análisis asistido (Trabajo 7).
  - Reporte HTML consolidado (Trabajo 6) y automatización en GitHub Actions (Trabajo 8).
- **Pruebas de aceptación del propio ejecutor**: Se encuentran separadas en `qa_tests/` y se verifican mediante:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest qa_tests
  ```
