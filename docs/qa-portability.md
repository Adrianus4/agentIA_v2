# Guía de Portabilidad, Instalación y Entrega (`docs/qa-portability.md`)

Esta guía describe cómo desplegar, configurar y ejecutar el Agente de Aseguramiento de Calidad (QA) de AgentIA en cualquier estación de trabajo Windows o Linux, sin requerir privilegios de administrador, virtualización ni Docker.

---

## 1. Perfiles de Ejecución

El Agente de QA organiza sus capacidades en tres perfiles explícitos para adaptarse a los recursos disponibles en el equipo:

| Perfil | Alcance de Pruebas | Herramientas Requeridas | Casos de Uso Recomendados |
| :--- | :--- | :--- | :--- |
| **Python (Mínimo)** | Diagnóstico (`doctor`, `list`), pruebas unitarias del producto (`tests/`), microservicios HTTP (`platform`), pruebas LLM simuladas (`llm`) y reportes HTML interactivos. | Python `>=3.11` (3.12 de referencia) y dependencias de `requirements-qa.txt`. | Estaciones de desarrollo estándar, laptops corporativas restringidas, validación rápida de cambios. |
| **Python + API** | Todo lo del perfil Python más análisis post-ejecución IA (`--ai-analysis`) y/o pruebas LLM reales sobre el servicio de reparación del producto (`--llm-mode real`). | Lo anterior más conectividad de red y claves de API configuradas en variables de entorno. | Auditoría de calidad asistida por IA y medición empírica de proveedores LLM. |
| **Completo** | Todas las suites: Python, microservicios, compilación offline Quarkus JUnit/H2 (`java`) y pruebas E2E en navegador Chromium real (`playwright`). | Lo anterior más JDK 21 (Temurin), Apache Maven 3.9.x, Node.js 22 y binarios de Chromium. | Estaciones de integración, servidores CI/CD o equipos de desarrollo full-stack. |

---

## 2. Instalación Paso a Paso (Sin Administrador)

### Paso 1: Clonar o Copiar el Repositorio
No se requiere Git para la ejecución del agente; si el código se transfiere en formato ZIP o carpeta compartida, el agente degrada limpiamente a cálculo de hashes SHA-256 para trazabilidad.

### Paso 2: Crear el Entorno Virtual Python
Abra una terminal en la raíz del repositorio (`cd finalagent`):

- **En Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\activate
  ```

- **En Linux / macOS (Bash):**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### Paso 3: Instalar Dependencias Fijadas
El archivo `requirements-qa.txt` contiene versiones congeladas y probadas con Python 3.12:

```bash
python -m pip install --upgrade pip
pip install -r requirements-qa.txt
```

> [!NOTE]
> `uv` es totalmente opcional. La instalación estándar mediante `pip` satisface al 100% los requisitos sin depender de herramientas externas.

### Paso 4: Verificar el Entorno con `doctor`
```bash
python scripts/qa.py doctor
```
El agente inspeccionará el sistema y mostrará una tabla con las capacidades detectadas. Las herramientas ausentes (como Java o Node) se marcarán como opcionales sin generar errores en el perfil mínimo.

---

## 3. Despliegue en Redes Restringidas / Modo Offline (Wheelhouse)

Para operar en entornos corporativos sin acceso a internet o tras proxies restrictivos:

1. **En una máquina autorizada con salida a internet**, descargue las ruedas (`wheels`) compatibles con el SO y arquitectura destino:
   ```bash
   pip download -r requirements-qa.txt -d ./wheelhouse
   ```
2. **Transfiera la carpeta `./wheelhouse`** junto con el repositorio a la máquina de destino.
3. **Instale localmente sin conexión a internet**:
   ```bash
   pip install --no-index --find-links=./wheelhouse -r requirements-qa.txt
   ```
4. **Caches offline para suites pesadas (opcional para perfil Completo)**:
   - **Maven**: Copie el directorio de dependencias precargadas a `~/.m2/repository` o use `--java-cache-dir <ruta>`.
   - **Playwright**: Copie los binarios del navegador Chromium a `~/.cache/ms-playwright` (Linux) o `%LOCALAPPDATA%\ms-playwright` (Windows) o use `--browser-cache-dir <ruta>`.

---

## 4. Tareas de VS Code y Comandos de Terminal

El repositorio incluye `.vscode/tasks.json` con tareas estructuradas accesibles desde el menú **Terminal > Run Task...** en VS Code:

| Tarea en VS Code | Comando Equivalente en Terminal | Propósito |
| :--- | :--- | :--- |
| **QA: Doctor (Diagnóstico de Entorno)** | `python scripts/qa.py doctor` | Inspecciona runtimes, paquetes y caches disponibles. |
| **QA: Listar Suites y Elegibilidad** | `python scripts/qa.py list` | Muestra el catálogo de suites y su estado de ejecución. |
| **QA: Ejecutar Perfil Mínimo (Python)** | `python scripts/qa.py run --suite python` | Corre la suite de pruebas Python en aislamiento. |
| **QA: Ejecutar Perfil Plataforma** | `python scripts/qa.py run --suite platform` | Levanta los 5 microservicios FastAPI en sockets loopback y evalúa su API. |
| **QA: Ejecutar Perfil Frontend** | `python scripts/qa.py run --suite frontend` | Corre Vitest, chequeo de tipos TypeScript y build Vite. |
| **QA: Ejecutar Perfil Completo** | `python scripts/qa.py run --suite python,platform,frontend,java,playwright` | Ejecuta todas las suites funcionales del producto. |
| **QA: Generar Reporte HTML Consolidado** | `python scripts/qa.py report` | Renderiza el informe Jinja2 auto-contenido de la última ejecución. |
| **QA: Analizar con IA (Optativo)** | `python scripts/qa.py analyze` | Envía el paquete de evidencia redactado al proveedor configurado. |

---

## 5. Configuración de Variables de Entorno y Claves

> [!IMPORTANT]
> Está terminantemente prohibido incluir claves de API en archivos JSON o en la línea de comandos. El agente lee credenciales exclusivamente desde variables de entorno del sistema.

### Configuración de Claves para Modo Real
- **Windows (PowerShell):**
  ```powershell
  $env:GEMINI_API_KEY = "tu_clave_de_gemini"
  $env:OPENAI_API_KEY = "tu_clave_de_openai"
  $env:DEEPSEEK_API_KEY = "tu_clave_de_deepseek"
  ```
- **Linux / macOS (Bash):**
  ```bash
  export GEMINI_API_KEY="tu_clave_de_gemini"
  export OPENAI_API_KEY="tu_clave_de_openai"
  export DEEPSEEK_API_KEY="tu_clave_de_deepseek"
  ```

### Proxies Corporativos y Certificados TLS
El agente utiliza el transporte estándar de HTTPX respetando las variables de entorno del sistema:
- `HTTPS_PROXY="http://proxy.corporativo.com:8080"`
- `SSL_CERT_FILE="/ruta/al/certificado-ca-corporativo.crt"`

La verificación TLS se encuentra siempre activa para prevenir ataques Man-in-the-Middle; nunca se desactiva `verify=False`.

---

## 6. Resolución de Problemas Frecuentes (Troubleshooting)

### A. Rutas Largas en Windows (`WinError 206: The filename or extension is too long`)
- **Causa**: Limitación histórica de la API Win32 (260 caracteres MAX_PATH) al compilar proyectos Java/Maven con estructuras de paquetes profundas.
- **Solución implementada**: El arnés de ejecución del Agente de QA utiliza prefijos `\\?\` en rutas absolutas y genera directorios de trabajo temporales con nombres compactos (`tmp_ws_...`). Además, se recomienda habilitar el soporte de rutas largas en Windows:
  `reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v "LongPathsEnabled" /t REG_DWORD /d 1 /f`

### B. Rutas con Espacios o Caracteres Acentuados / Unicode
- **Comportamiento**: El agente admite sin inconvenientes directorios que contengan espacios o caracteres acentuados (p. ej. `C:\Proyectos\Agente IA v2\`).
- **Recomendación**: Al pasar rutas por línea de comandos, asegúrese de entrecomillarlas:
  `python scripts/qa.py doctor --repo "C:\Proyectos\Agente IA v2"`

### C. Puertos y Conflictos de Red en Suite `platform`
- **Comportamiento**: Los microservicios HTTP no utilizan puertos fijos (como 8000 u 8080) que pudieran chocar con servicios locales del desarrollador. El arnés reserva sockets efímeros en `127.0.0.1:0` y enlaza cada microservicio a su puerto dinámico exclusivo.
- **Resultado**: Cero interferencia con aplicaciones preexistentes y cero requerimiento de privilegios de administrador para abrir puertos.

### D. Diagnóstico del Fallo Conocido en Suite `platform`
- **Observación**: Al correr `python scripts/qa.py run --suite platform`, la suite puede finalizar con código de salida 1 (`FAILED`).
- **Explicación**: El producto AgentIA presenta un comportamiento conocido en su capa de persistencia de flujos. El Agente de QA no enmascara este fallo ni altera los veredictos; documenta con precisión la traza del error en `platform.log` y `result.json` para facilitar la corrección por parte del equipo de ingeniería.
