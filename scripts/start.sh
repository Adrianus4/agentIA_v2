#!/usr/bin/env sh
# Container entrypoint shared by every AgentIA image.
#   SERVICE_MODULE  uvicorn target, e.g. app.main:create_app or services.repair_service:app
#   UVICORN_EXTRA   extra uvicorn flags (--factory for the orchestrator app factory)
#   PORT            listen port
set -eu

mkdir -p "${WORKFLOW_STATE_DIR:-/data/workflow-state}" "${AGENTIA_WORKSPACE_ROOT:-/data/workspaces}" 2>/dev/null || true

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

SERVICE_MODULE="${SERVICE_MODULE:-app.main:create_app}"
PORT_VALUE="${PORT:-8000}"

# shellcheck disable=SC2086 # UVICORN_EXTRA is intentionally word-split
exec python -m uvicorn "$SERVICE_MODULE" ${UVICORN_EXTRA:-} --host 0.0.0.0 --port "$PORT_VALUE"
