# Cobertura Funcional Multimotor de AgentIA (`qa_agent`)

Este documento detalla la arquitectura, toolchains, caches offline, comandos y contratos de ejecución para las 5 suites funcionales de AgentIA (`specs/004-test-agent-functional-coverage/`): **`python`**, **`platform`**, **`java`**, **`frontend`** y **`playwright`**.

---

## 1. Arquitectura de Suites y Fronteras de Medición

| Suite | Motor / Engine | Frontera HTTP | Frontera Compilador / Runtime | Toolchain Requerido | Caché Offline / Dependencias | Métricas Reales |
|---|---|---|---|---|---|:---:|
| **`python`** | `pytest` | In-process / Mock | N/A | Python `>= 3.11` | `.pytest_cache` | 229 casos aprobados |
| **`platform`** | `fastapi+httpx` | **Sockets HTTP reales** en loopback (5 microservicios) | Doble acotado en verifier (`compiler=double`) | Python `>= 3.11` | N/A | 7 escenarios (aísla defecto P-01) |
| **`java`** | `maven+surefire` | **Sockets HTTP reales** en loopback (orquestador) | **Maven 3.9+ y JDK 21 reales** (`-o -B`, H2 en memoria) | Temurin OpenJDK 21, Maven 3.9+ | `.agentia-runtime/java-cache` | 76 Surefire pos. + 2 neg. |
| **`frontend`** | `vitest+tsc+vite` | In-process (jsdom + fetch mocks) | Node.js directo (`tsc -b`, `vite build`) | Node.js `>= 20` | `frontend/node_modules` | 53 Vitest + tsc + vite build |
| **`playwright`** | `playwright+chromium` | **Sockets HTTP reales** (Vite + backend loopback) | **Chromium real hermético** + **Maven real** | Node.js `>= 20`, Chromium, JDK 21, Maven | `.agentia-runtime/browser-cache` | 3 casos (1 pos. + 2 neg.) |

---

## 2. Contrato de Códigos de Salida

El agente garantiza fidelidad estricta y trazabilidad en sus veredictos (RF-301 a RF-315, AC-18):

- **`0` (`EXIT_SUCCESS` / `PASSED`)**: Todas las suites seleccionadas fueron ejecutadas y aprobaron todas sus aserciones.
- **`1` (`EXIT_FAILED` / `FAILED`)**: Fallo legítimo de producto o aserción funcional (p. ej. compilación rota o aserción fallida en microservicio generado; defecto en base de datos; código HTTP inesperado; defecto de persistencia del producto).
- **`2` (`EXIT_CONFIG_ERROR`)**: Configuración CLI o archivo de configuración JSON sintácticamente inválido o con directivas rechazadas.
- **`3` (`EXIT_EXECUTION_ERROR`)**: Error de infraestructura o ejecución no controlada del ejecutor (p. ej. reporte JUnit corrupto, timeout de socket, proceso caído sin respuesta). Intentos de bypass como `VERIFIER_DRY_RUN=1` en suites Java reales son rechazados con código 3.
- **`4` (`EXIT_INCOMPLETE`)**: Falta de toolchain (JDK, Maven, Node) o de caché offline (`java-cache`, `browser-cache`), o suite con cero casos recolectados o pruebas omitidas (`skipped`). El ejecutor aborta de inmediato **sin intentar descargar dependencias ni navegadores por red**.
- **`130` (`EXIT_INTERRUPTED`)**: Interrupción manual del usuario (`SIGINT`/`Ctrl+C`), preservando el estándar POSIX (`128 + 2 = 130`).

---

## 3. Preparación para Nuevos Clones (Estructura de Runtimes Offline)

El agente está diseñado para operar con **100% de aislamiento de red (cero descargas en runtime)**. En un clon limpio del repositorio, la estructura requerida bajo `.agentia-runtime/` se compone de:

```text
.agentia-runtime/
├── toolchains/
│   ├── jdk-21/                 # Eclipse Temurin OpenJDK 21.0.12.1 (bin/java.exe)
│   └── apache-maven-3.9.9/      # Apache Maven 3.9.9 binario (bin/mvn.cmd)
├── java-cache/                 # Repositorio Maven local offline con Quarkus 3.15.1, H2, RestAssured
│   └── io/quarkus/...          # Artefactos Quarkus cacheados previamente
└── browser-cache/              # Binarios herméticos de Chromium para Playwright
    └── chromium_headless_shell-1248/...
```

### Requisitos del Entorno:
1. **Python**: Python 3.11 o 3.12 en virtualenv `.venv`.
2. **Node.js**: Versión `>= 20.0.0` (Playwright 1.64.1 requiere Node `>= 20`).
3. **Módulos de Frontend**: `frontend/node_modules/` presente (preparado mediante `npm ci` en fase de setup).

> [!IMPORTANT]
> **Principio de Aislamiento Hermético**: El agente nunca muta `.agentia-runtime/` ni `~/.m2`. En cada ejecución de `run`, crea copias temporales aisladas en el directorio scratch del run (`workspace.scratch_root`) con soporte para rutas extendidas en Windows (`\\?\`).

---

## 4. Archivo de Configuración (`qa-functional.example.json`)

Para reproducir la campaña completa de cobertura funcional:

```json
{
  "schema_version": "1.0",
  "suites": [
    "python",
    "platform",
    "java",
    "frontend",
    "playwright"
  ],
  "timeout_seconds": 900,
  "suite_timeouts": {
    "python": 300,
    "platform": 300,
    "java": 600,
    "frontend": 180,
    "playwright": 300
  },
  "java_cache_dir": ".agentia-runtime/java-cache",
  "browser_cache_dir": ".agentia-runtime/browser-cache",
  "output_dir": ".agentia-runtime/qa"
}
```

---

## 5. Comandos de Ejecución

### 5.1 Diagnóstico de Capacidades

```powershell
.\.venv\Scripts\python.exe -m qa_agent doctor
```

### 5.2 Ejecutar suites individuales

```powershell
# Suite python (regresión histórica: 229/229 pruebas)
.\.venv\Scripts\python.exe -m qa_agent run --suite python

# Suite platform (5 microservicios FastAPI HTTP reales en loopback)
.\.venv\Scripts\python.exe -m qa_agent run --suite platform

# Suite java (compilación y pruebas Maven offline con H2: 76 Surefire positivos + 2 negativos)
.\.venv\Scripts\python.exe -m qa_agent run --suite java

# Suite frontend (53 pruebas Vitest, chequeo de tipos TypeScript y build Vite)
.\.venv\Scripts\python.exe -m qa_agent run --suite frontend

# Suite playwright (Chromium real contra backend Maven real y controles negativos 401/down)
.\.venv\Scripts\python.exe -m qa_agent run --suite playwright
```

### 5.3 Ejecutar Regresión Completa

```powershell
.\.venv\Scripts\python.exe -m qa_agent run --config qa-functional.example.json
```

### 5.4 Ejecutar Suite de Aceptación del Agente

```powershell
.\.venv\Scripts\python.exe -m pytest qa_tests -v
```
