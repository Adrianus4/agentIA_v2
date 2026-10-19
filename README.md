# AgentIA v2

Generador de microservicios Java Quarkus a partir de un blueprint. Cada agente es un microservicio
FastAPI y un orquestador LangGraph los coordina por HTTP.

## Arquitectura

```
Web Studio (React, nginx) ──/v1──▶ Orquestador (FastAPI + LangGraph, :8000)
                                     │  validate ─▶ generate ─▶ verify ─┬─▶ SUCCESS
                                     │                  ▲               │ falla
                                     │                  └─ apply_patch ◀─ repair (hasta 3)
                                     ├── HTTP ──▶ validator  :8003  normaliza y valida el blueprint
                                     ├── HTTP ──▶ generator  :8004  plantillas Jinja; LLM solo como respaldo
                                     ├── HTTP ──▶ verifier   :8001  mvn test sobre los archivos recibidos (JDK 21 + Maven)
                                     └── HTTP ──▶ repair     :8002  fix determinista de imports, luego LLM + guards
```

- **Sin disco compartido.** El orquestador es dueño del workspace y del estado (`WORKFLOW_STATE_DIR`).
  El verificador recibe los archivos en cada petición y compila en su propio directorio temporal.
  El reparador recibe el archivo que falla y solo los archivos que este referencia.
- **Grafo LangGraph** (`app/orchestrator/graph.py`). Si un parche falla, no cambia nada o lo rechazan
  los guards, se vuelve al reparador con el motivo, sin relanzar Maven. Un error del LLM (429, sin
  clave) termina en `ERROR` en vez de reintentar. El presupuesto es `AGENTIA_MAX_REPAIR_ATTEMPTS`
  reparaciones (por defecto 3).
- **Reparación multiarchivo.** Los diagnósticos se agrupan por archivo (hasta 3 por intento).
  Primero se aplica un fix determinista (imports de tipos conocidos del perfil o del proyecto) y solo
  después se llama al LLM.
- **Ejecución asíncrona.** `POST /v1/blueprint/run?mode=async` responde `202` con el `trace_id`, y
  `GET /v1/blueprint/status/{trace_id}` devuelve la etapa en vivo (`stage`) y el estado final. La UI
  usa este modo, así que funciona detrás de proxies con timeout corto.
- **Operaciones:** `validate` solo valida, `verify` genera y verifica sin reparar, y `run`/`repair`
  ejecutan el ciclo completo. Cada ejecución usa su propio workspace (`<servicio>-<trace>`).

## Modo local (sin Docker)

Requisitos: Python 3.11+, Node 18+ con npm, JDK 21 y Maven 3.9+. Para el LLM necesitas una clave de
Gemini, una de OpenAI o un Ollama local. Copia `.env.example` a `.env` y ajústalo.

| Sistema | Comando | Detener |
|---|---|---|
| Windows | `start.bat` (`start.bat --no-frontend` solo levanta el backend) | Ctrl+C |
| Linux | `bash start.sh` (`--no-frontend` opcional) | Ctrl+C |

- Interfaz: `http://127.0.0.1:3000`. API: `http://127.0.0.1:8000/docs`. Clave de la UI:
  `ORCHESTRATOR_API_KEY` (por defecto `secret`).
- Si un puerto está ocupado, el script se niega a arrancar y no detiene otros programas. Puedes
  cambiar los puertos con `PORT`, `FRONTEND_PORT` y `*_PORT`.
- En Windows, los workspaces viven en `C:\tmp\agentia-workspace` para no superar el límite de
  260 caracteres de ruta.
- Los logs de cada servicio quedan en `.agentia-runtime/launcher/`.

## Modo contenedores (Docker Compose)

Es la misma topología que se despliega en Openship o en cloud:

| Sistema | Arrancar | En segundo plano | Detener |
|---|---|---|---|
| Windows | `start_microservices.bat` | `start_microservices.bat -d` | `start_microservices.bat down` |
| Linux | `sh scripts/start_microservices.sh` | `... -d` | `... down` |

Interfaz: `http://localhost:3000` (`WEB_PORT`). API: `http://localhost:8000/docs`
(`ORCHESTRATOR_PORT`). Para usar Ollama del host desde los contenedores, define
`LLM_PROVIDER=local`; el endpoint se toma de `CONTAINER_LOCAL_LLM_ENDPOINT`, por defecto
`http://host.docker.internal:11434`. Con Ollama en Windows o macOS puede hacer falta
`OLLAMA_HOST=0.0.0.0`.

Imágenes:
- `Dockerfile`: orquestador, validador, generador y reparador (Python 3.12 slim). El servicio se
  elige con `SERVICE_MODULE` y `PORT`.
- `Dockerfile.verifier`: verificador (Python, JDK 21 y Maven).
- `frontend/Dockerfile`: build de Vite servido por nginx, que reenvía `/v1` a `ORCHESTRATOR_UPSTREAM`.

## Despliegue con Openship

`openship.json` apunta a `docker-compose.yml` (`composePath`). Openship construye cada servicio con
su Dockerfile, respeta los `healthcheck` y `depends_on`, y los servicios se comunican por nombre
(`http://validator:8003`, etc.).

```bash
npm i -g openship        # Node 22+ (o la app de escritorio)
openship up              # control plane local
cd agentIA_v2
openship init
openship deploy
```

En el panel, expón solo `web` (la UI ya hace de proxy de la API) y, si lo necesitas, `orchestrator`.
Deja internos `validator`, `generator`, `verifier` y `repair`. Configura `GEMINI_API_KEY` (o el
proveedor que uses) y `ORCHESTRATOR_API_KEY` como secretos del proyecto. Los volúmenes solo guardan
el estado del orquestador y la caché de Maven, así que se pueden perder sin afectar la funcionalidad.

## Variables principales

| Variable | Uso |
|---|---|
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | Credenciales del LLM (también pueden llegar por petición desde la UI) |
| `LLM_PROVIDER`, `LLM_MODEL` | Proveedor (`gemini`, `local`, `openai`) y modelo (por defecto `gemini-flash-latest`) |
| `LOCAL_LLM_ENDPOINT` | Ollama o llama.cpp en modo local (`http://127.0.0.1:11434`) |
| `ORCHESTRATOR_API_KEY` | Clave `x-api-key` de la API del orquestador |
| `AGENTIA_MAX_REPAIR_ATTEMPTS` | Reparaciones por ejecución (0–3) |
| `VERIFIER_TIMEOUT_SECONDS` | Timeout de `mvn test` (por defecto 900) |

## Tests

```bash
.venv/bin/python -m pytest          # Windows: .venv\Scripts\python.exe -m pytest
cd frontend && npx vitest run && npm run build
python scripts/guard_structure_agent.py .
```
