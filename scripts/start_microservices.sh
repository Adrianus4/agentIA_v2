#!/usr/bin/env sh
# AgentIA v2 - containerized stack (the same docker-compose.yml Openship deploys).
#   sh scripts/start_microservices.sh          build and start (foreground, Ctrl+C to stop)
#   sh scripts/start_microservices.sh -d       build and start in the background
#   sh scripts/start_microservices.sh down     stop and remove the containers
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker no esta instalado. Instala Docker Engine o Docker Desktop." >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "El daemon de Docker no responde. Inicia Docker y vuelve a intentarlo." >&2
    exit 1
fi

ENV_ARGS=""
if [ -f .env ]; then ENV_ARGS="--env-file .env"; fi

case "${1:-}" in
    down)
        # shellcheck disable=SC2086
        exec docker compose $ENV_ARGS -f docker-compose.yml down
        ;;
    -d|--detach)
        # shellcheck disable=SC2086
        docker compose $ENV_ARGS -f docker-compose.yml up --build -d
        echo "Interfaz: http://localhost:${WEB_PORT:-3000}"
        echo "API/docs: http://localhost:${ORCHESTRATOR_PORT:-8000}/docs"
        echo "Estado:   docker compose ps   |   Logs: docker compose logs -f"
        ;;
    "")
        echo "Interfaz: http://localhost:${WEB_PORT:-3000}  API/docs: http://localhost:${ORCHESTRATOR_PORT:-8000}/docs"
        # shellcheck disable=SC2086
        exec docker compose $ENV_ARGS -f docker-compose.yml up --build
        ;;
    *)
        echo "Uso: sh scripts/start_microservices.sh [-d|down]" >&2
        exit 1
        ;;
esac
