@echo off
rem AgentIA v2 - containerized stack (the same docker-compose.yml Openship deploys).
rem   start_microservices.bat          build and start (foreground, Ctrl+C to stop)
rem   start_microservices.bat -d       build and start in the background
rem   start_microservices.bat down     stop and remove the containers
setlocal EnableExtensions
cd /d "%~dp0"

where docker >nul 2>nul || (echo [ERROR] Docker no esta instalado. Instala Docker Desktop. & exit /b 1)
docker info >nul 2>nul || (echo [ERROR] Docker no responde. Abre Docker Desktop y espera a que inicie. & exit /b 1)

set "ENV_ARGS="
if exist ".env" set "ENV_ARGS=--env-file .env"
if "%WEB_PORT%"=="" set "WEB_PORT=3000"
if "%ORCHESTRATOR_PORT%"=="" set "ORCHESTRATOR_PORT=8000"

if /I "%~1"=="down" (
    docker compose %ENV_ARGS% -f docker-compose.yml down
    exit /b %errorlevel%
)
if /I "%~1"=="-d" (
    docker compose %ENV_ARGS% -f docker-compose.yml up --build -d
    if errorlevel 1 exit /b 1
    echo Interfaz: http://localhost:%WEB_PORT%
    echo API/docs: http://localhost:%ORCHESTRATOR_PORT%/docs
    echo Estado:   docker compose ps    Logs: docker compose logs -f
    exit /b 0
)
if not "%~1"=="" (echo Uso: start_microservices.bat [-d^|down] & exit /b 1)

echo Interfaz: http://localhost:%WEB_PORT%   API/docs: http://localhost:%ORCHESTRATOR_PORT%/docs
docker compose %ENV_ARGS% -f docker-compose.yml up --build
