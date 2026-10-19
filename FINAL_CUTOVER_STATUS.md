# Runtime status

The canonical runtime and how to start it are described in [README.md](README.md).

Canonical files:

- `app/main.py` — orchestrator API (sync and async run modes, live status)
- `app/orchestrator/graph.py` — LangGraph state machine
- `app/orchestrator/execution_nodes_microservice.py` — graph nodes calling the agents over HTTP
- `services/{validator,generator,verifier,repair}_service.py` — agent microservices
- `services/common.py` — shared gateway auth and `/health`
- `contracts/agent_api.py` — request/response envelopes (the verifier receives files, not paths)
- `docker-compose.yml` + `openship.json` — container topology (also what Openship deploys)
- `Dockerfile`, `Dockerfile.verifier`, `frontend/Dockerfile` — images
- `start.bat`, `start.sh` — local launchers; `start_microservices.bat`, `scripts/start_microservices.sh` — compose launchers

`docker-compose.microservices.yml` and `docker-compose.local.yml` were removed: the shared-volume
topology they described is replaced by request-carried files.
