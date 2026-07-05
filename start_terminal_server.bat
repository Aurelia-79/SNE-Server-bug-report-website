@echo off
title Web Terminal Server
cd /d "%~dp0"

echo ============================================
echo   Web Terminal Server (Server Mode)
echo   Binding to 0.0.0.0 - accessible from LAN
echo ============================================

REM Ensure websockets
python -c "import websockets" 2>nul
if %errorlevel% neq 0 (
    echo [setup] Installing websockets...
    python -m pip install websockets -q
)

REM Bind to all interfaces
set TERMINAL_HOST=0.0.0.0
set TERMINAL_PORT=17252

echo Starting...
python terminal_server.py
pause
