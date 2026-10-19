@echo off
rem AgentIA v2 - Windows local launcher: orchestrator (LangGraph) + 4 agent microservices + Web Studio.
rem   start.bat                 start everything (Ctrl+C stops all processes of this console)
rem   start.bat --no-frontend   backend only
rem For the containerized stack (same topology Openship deploys) use start_microservices.bat
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "WITH_FRONTEND=1"
if /I "%~1"=="--no-frontend" set "WITH_FRONTEND=0"
if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help

rem ---- .env (KEY=VALUE lines, # comments) --------------------------------------------
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%~A"=="" set "%%~A=%%~B"
    )
)

rem ---- Defaults -------------------------------------------------------------------------
if "%PORT%"=="" set "PORT=8000"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=3000"
if "%VERIFIER_PORT%"=="" set "VERIFIER_PORT=8001"
if "%REPAIR_PORT%"=="" set "REPAIR_PORT=8002"
if "%VALIDATOR_PORT%"=="" set "VALIDATOR_PORT=8003"
if "%GENERATOR_PORT%"=="" set "GENERATOR_PORT=8004"
if "%ORCHESTRATOR_API_KEY%"=="" set "ORCHESTRATOR_API_KEY=secret"
if "%ORCHESTRATOR_ALLOW_PUBLIC_READ%"=="" set "ORCHESTRATOR_ALLOW_PUBLIC_READ=1"
if "%AGENT_GATEWAY_API_KEY%"=="" set "AGENT_GATEWAY_API_KEY=%ORCHESTRATOR_API_KEY%"
if "%LLM_PROVIDER%"=="" (
    if not "%GEMINI_API_KEY%"=="" (set "LLM_PROVIDER=gemini") else (set "LLM_PROVIDER=local")
)
if "%LOCAL_LLM_ENDPOINT%"=="" set "LOCAL_LLM_ENDPOINT=http://127.0.0.1:11434"
if "%VERIFIER_TIMEOUT_SECONDS%"=="" set "VERIFIER_TIMEOUT_SECONDS=900"
if "%AGENT_CLIENT_TIMEOUT_SECONDS%"=="" set "AGENT_CLIENT_TIMEOUT_SECONDS=960"
if "%AGENTIA_MAX_REPAIR_ATTEMPTS%"=="" set "AGENTIA_MAX_REPAIR_ATTEMPTS=3"
set "VERIFIER_RUNNER=host"
set "VERIFIER_URL=http://127.0.0.1:%VERIFIER_PORT%"
set "REPAIR_URL=http://127.0.0.1:%REPAIR_PORT%"
set "BLUEPRINT_VALIDATOR_URL=http://127.0.0.1:%VALIDATOR_PORT%"
set "GENERATOR_URL=http://127.0.0.1:%GENERATOR_PORT%"
set "BACKEND_URL=http://127.0.0.1:%PORT%"
set "RUNTIME_DIR=%~dp0.agentia-runtime"
if "%WORKFLOW_STATE_DIR%"=="" set "WORKFLOW_STATE_DIR=%RUNTIME_DIR%\workflow-state"
if "%ORCHESTRATOR_DATABASE_PATH%"=="" set "ORCHESTRATOR_DATABASE_PATH=%RUNTIME_DIR%\runs.db"
rem Short roots keep generated Maven projects under the 260-character Windows MAX_PATH
if "%AGENTIA_WORKSPACE_ROOT%"=="" set "AGENTIA_WORKSPACE_ROOT=C:\tmp\agentia-workspace"
if "%VERIFIER_SCRATCH_DIR%"=="" set "VERIFIER_SCRATCH_DIR=C:\tmp\agentia-verify"
set "LOG_DIR=%RUNTIME_DIR%\launcher"

echo ===================================================
echo  AgentIA v2 - Windows local launcher
echo ===================================================

rem ---- JDK + Maven ----------------------------------------------------------------------
if "%JAVA_HOME%"=="" (
    for /d %%J in ("%ProgramFiles%\Eclipse Adoptium\jdk-21*") do set "JAVA_HOME=%%~fJ"
)
if not "%JAVA_HOME%"=="" set "PATH=%JAVA_HOME%\bin;%PATH%"
where mvn >nul 2>nul
if errorlevel 1 (
    if not "%MAVEN_HOME%"=="" set "PATH=%MAVEN_HOME%\bin;%PATH%"
    for /d %%M in ("%LOCALAPPDATA%\Programs\apache-maven-*") do set "PATH=%%~fM\bin;!PATH!"
)
where java >nul 2>nul || (echo [ERROR] Java no encontrado. Instala un JDK 21 ^(winget install EclipseAdoptium.Temurin.21.JDK^). & exit /b 1)
where mvn >nul 2>nul || (echo [ERROR] Maven no encontrado. Instala Maven 3.9+ y agrega su carpeta bin al PATH. & exit /b 1)

rem ---- Python environment -----------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno .venv ...
    py -3.12 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (echo [ERROR] No se pudo crear .venv. Instala Python 3.11+. & exit /b 1)
)
set "PY=%~dp0.venv\Scripts\python.exe"
echo Instalando dependencias Python ...
"%PY%" -m pip install -q --disable-pip-version-check -r requirements.txt pytest pytest-asyncio respx
if errorlevel 1 (echo [ERROR] pip install fallo. & exit /b 1)

rem ---- Ports (never kill other programs: refuse occupied ports) ----------------------------
set "PORTS=%PORT% %VERIFIER_PORT% %REPAIR_PORT% %VALIDATOR_PORT% %GENERATOR_PORT%"
if "%WITH_FRONTEND%"=="1" set "PORTS=%PORTS% %FRONTEND_PORT%"
"%PY%" -c "import socket,sys;[socket.socket().bind(('127.0.0.1',int(p))) for p in sys.argv[1:]]" %PORTS% 2>nul
if errorlevel 1 (
    echo [ERROR] Alguno de los puertos %PORTS% esta ocupado. Deten ese proceso o cambia PORT/*_PORT en .env.
    exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%WORKFLOW_STATE_DIR%" mkdir "%WORKFLOW_STATE_DIR%"
if not exist "%AGENTIA_WORKSPACE_ROOT%" mkdir "%AGENTIA_WORKSPACE_ROOT%"
if not exist "%VERIFIER_SCRATCH_DIR%" mkdir "%VERIFIER_SCRATCH_DIR%"

rem ---- Services (same console: Ctrl+C stops all of them) ----------------------------------
call :service validator services.validator_service:app %VALIDATOR_PORT%
call :service generator services.generator_service:app %GENERATOR_PORT%
call :service verifier services.verifier_service:app %VERIFIER_PORT%
call :service repair services.repair_service:app %REPAIR_PORT%
call :service orchestrator app.main:create_app %PORT% --factory

echo Esperando el arranque de los servicios. Logs: %LOG_DIR%
"%PY%" -c "import sys,time,urllib.request as u;o=u.build_opener(u.ProxyHandler({}));p=set(sys.argv[1:]);d=time.time()+60;exec('while p and time.time()<d:\n for x in list(p):\n  try:\n   o.open(x,timeout=0.5);p.discard(x)\n  except Exception:pass\n time.sleep(0.25)');sys.exit('Sin respuesta: '+', '.join(sorted(p)) if p else 0)" http://127.0.0.1:%VALIDATOR_PORT%/health http://127.0.0.1:%GENERATOR_PORT%/health http://127.0.0.1:%VERIFIER_PORT%/health http://127.0.0.1:%REPAIR_PORT%/health http://127.0.0.1:%PORT%/health
if errorlevel 1 (echo [ERROR] Fallo de arranque; revisa los logs en %LOG_DIR%. & exit /b 1)

echo.
echo API/docs:  %BACKEND_URL%/docs
echo LLM:       proveedor=%LLM_PROVIDER% modelo=%LLM_MODEL%
echo Clave API del orquestador (configurala en la interfaz): %ORCHESTRATOR_API_KEY%

if "%WITH_FRONTEND%"=="0" (
    echo Backend en marcha. Pulsa Ctrl+C para detenerlo.
    "%PY%" -c "import time;exec('while True: time.sleep(3600)')"
    exit /b 0
)

where npm >nul 2>nul || (echo [ERROR] npm no encontrado. Instala Node.js 18+. & exit /b 1)
if not exist "frontend\node_modules" (
    echo Instalando dependencias frontend ...
    pushd frontend
    call npm ci --no-audit --no-fund
    if errorlevel 1 (popd & echo [ERROR] npm ci fallo. & exit /b 1)
    popd
)
echo Interfaz:  http://127.0.0.1:%FRONTEND_PORT%
echo Pulsa Ctrl+C para detener todos los servicios.
rem Empty VITE_API_BASE_URL would be unset by cmd; the UI then talks to %BACKEND_URL% directly (CORS enabled)
pushd frontend
call npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT% --strictPort
popd
exit /b 0

:service
set "SVC_EXTRA=%~4"
start "" /b "%PY%" -m uvicorn %2 %SVC_EXTRA% --host 127.0.0.1 --port %3 > "%LOG_DIR%\%1.log" 2>&1
exit /b 0

:help
echo Uso: start.bat [--no-frontend]
echo Requisitos: Python 3.11+, Node 18+ con npm, JDK 21 y Maven 3.9+.
echo Carga .env ^(KEY=VALUE^). Variables utiles:
echo   PORT=8000 FRONTEND_PORT=3000 VERIFIER_PORT=8001 REPAIR_PORT=8002 VALIDATOR_PORT=8003 GENERATOR_PORT=8004
echo   GEMINI_API_KEY=...               proveedor gemini
echo   LLM_PROVIDER=local               Ollama en LOCAL_LLM_ENDPOINT ^(por defecto :11434^)
echo   LLM_PROVIDER=openai OPENAI_API_KEY=...
echo   LLM_MODEL=modelo                 opcional
exit /b 0
