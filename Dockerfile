# Image for the orchestrator and the Python-only agents (validator, generator, repair).
# The verifier needs a JDK and Maven and is built from Dockerfile.verifier instead.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    SERVICE_MODULE=app.main:create_app \
    UVICORN_EXTRA=--factory

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY main.py ./main.py
COPY app ./app
COPY services ./services
COPY contracts ./contracts
COPY agents ./agents
COPY profiles ./profiles
COPY templates ./templates
COPY blueprints ./blueprints
COPY scripts/start.sh ./scripts/start.sh

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/workflow-state /data/workspaces \
    && chown -R appuser:appuser /app /data \
    && chmod +x /app/scripts/start.sh

USER appuser

EXPOSE 8000

# SERVICE_MODULE / PORT select which service this container runs (see docker-compose.yml)
ENTRYPOINT ["/app/scripts/start.sh"]
