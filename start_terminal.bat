@echo off
title Web Terminal Server
cd /d "%~dp0"

REM Ensure websockets is installed
python -c "import websockets" 2>nul
if %errorlevel% neq 0 (
    echo [setup] Installing websockets...
    python -m pip install websockets -q
    echo [setup] Done. Starting server...
)

echo ============================================
echo   Web Terminal Server
echo   Token and URL will be shown below.
echo   Open the URL in Chrome to connect.
echo ============================================

REM Let Python handle token generation and display
python terminal_server.py
pause
