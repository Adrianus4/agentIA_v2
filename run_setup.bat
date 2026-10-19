@echo off
title TCS GenAI Lab - GitHub Copilot Setup
color 0A

echo ======================================================================
echo   TCS GenAI Lab - Configurador de GitHub Copilot para VS Code
echo ======================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] No se encontro Python en el PATH del sistema.
    echo Por favor asegurese de tener Python 3 instalado para ejecutar este asistente.
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"
python setup_copilot_tcs.py %*

echo.
pause

