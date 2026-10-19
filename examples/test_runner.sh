#!/usr/bin/env bash
# ==============================================================================
# Script de Prueba Automatizada para Blueprints de Microservicios en AgentIA v2
# ==============================================================================
set -euo pipefail

API_BASE="${AGENTIA_API_URL:-http://127.0.0.1:8000}"
API_KEY="${ORCHESTRATOR_API_KEY:-development-secret-key}"
CATALOG_FILE="$(dirname "$0")/microservices_catalog.json"

echo "=========================================================="
echo "   AgentIA v2 - Validador y Ejecutor de Microservicios   "
echo "=========================================================="
echo "Target API: ${API_BASE}"
echo "Catálogo:   ${CATALOG_FILE}"
echo ""

# Validar que jq esté disponible
if ! command -v jq &> /dev/null; then
    echo "Aviso: 'jq' no está instalado. Se mostrarán respuestas JSON crudas."
fi

# 1. Probar conectividad con el endpoint de salud
echo "1. Comprobando estado de la API..."
STATUS_HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/health" || echo "FAIL")
if [ "$STATUS_HTTP" != "200" ]; then
    echo "ERROR: El servidor backend no responde en ${API_BASE}/health (Código: ${STATUS_HTTP})"
    echo "Inicie el servidor backend con: uv run uvicorn app.main:app --port 8000"
    exit 1
fi
echo "✓ Backend saludable (HTTP 200)"
echo ""

# 2. Iterar ejemplos del catálogo para validación y ejecución
INDEX=0
TOTAL_EXAMPLES=$(python3 -c "import json; data=json.load(open('${CATALOG_FILE}')); print(len(data['examples']))")

echo "2. Validando ${TOTAL_EXAMPLES} ejemplos de microservicios en el catálogo:"
echo "----------------------------------------------------------"

while [ "$INDEX" -lt "$TOTAL_EXAMPLES" ]; do
    SERVICE_NAME=$(python3 -c "import json; data=json.load(open('${CATALOG_FILE}')); print(data['examples'][${INDEX}]['serviceName'])")
    DATABASE=$(python3 -c "import json; data=json.load(open('${CATALOG_FILE}')); print(data['examples'][${INDEX}]['parameters']['database'])")
    MESSAGING=$(python3 -c "import json; data=json.load(open('${CATALOG_FILE}')); print(data['examples'][${INDEX}]['parameters']['messaging'])")
    
    echo "[$((INDEX+1))/$TOTAL_EXAMPLES] Validando esquema: ${SERVICE_NAME} (DB: ${DATABASE}, Messaging: ${MESSAGING})..."
    
    PAYLOAD=$(python3 -c "import json; data=json.load(open('${CATALOG_FILE}')); print(json.dumps({'workspace_dir': '/tmp/agentia-workspace/${SERVICE_NAME}', 'blueprint': data['examples'][${INDEX}]}))")
    
    RESPONSE=$(curl -s -X POST "${API_BASE}/v1/blueprint/validate" \
        -H "Content-Type: application/json" \
        -H "x-api-key: ${API_KEY}" \
        -d "${PAYLOAD}")
    
    VALID=$(python3 -c "import json, sys; res=json.loads(sys.argv[1]); val=res.get('validation', {}); print(val.get('valid', True))" "${RESPONSE}")
    
    if [ "$VALID" = "True" ]; then
        echo "   ✓ Esquema APROBADO por el Validador Real de AgentIA"
    else
        echo "   ✗ Esquema RECHAZADO: ${RESPONSE}"
    fi
    
    INDEX=$((INDEX + 1))
done

echo ""
echo "=========================================================="
echo "Para disparar una generación real de un microservicio, ejecute:"
echo ""
echo "curl -X POST '${API_BASE}/v1/blueprint/run' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'x-api-key: ${API_KEY}' \\"
echo "  -d @<(python3 -c 'import json; d=json.load(open(\"${CATALOG_FILE}\")); print(json.dumps({\"workspace_dir\": \"/tmp/agentia-workspace/task-tracker-service\", \"blueprint\": d[\"examples\"][4]}))')"
echo "=========================================================="

