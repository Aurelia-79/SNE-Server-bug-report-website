@echo off
setlocal EnableExtensions
title NLS Admin - Dev Mode

cd /d "%~dp0"

echo.
echo ========================================
echo   NLS Admin - Dev Mode Startup
echo ========================================
echo.

REM === 1. Environment check ===
if not exist ".env" (
    echo [WARN]  .env not found, copying from .env.example...
    copy ".env.example" ".env" >nul
    echo [WARN]  .env created, please edit SECRET_KEY.
    echo.
)

REM === 2. Python venv ===
set VENV_PYTHON=.venv\Scripts\python.exe
REM Check if venv is valid (not copied from another machine)
set VENV_OK=0
if exist "%VENV_PYTHON%" (
    call "%VENV_PYTHON%" -c "exit(0)" >nul 2>&1
    if not errorlevel 1 set VENV_OK=1
)
if "%VENV_OK%"=="0" (
    if exist ".venv" (
        echo [INFO]  Removing broken venv...
        rmdir /s /q ".venv" >nul 2>&1
    )
    echo [INFO]  Creating Python venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Please install Python 3.
        pause
        exit /b 1
    )
)

echo [INFO]  Installing Python dependencies...
call "%VENV_PYTHON%" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Python dependencies install failed.
    pause
    exit /b 1
)

REM === 3. Runtime directories ===
if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads
if not exist "logs" mkdir logs

REM === 4. Frontend dependencies ===
if not exist "frontend\node_modules" (
    echo [INFO]  Installing frontend dependencies...
    cd frontend
    call npm install --silent
    if errorlevel 1 (
        echo [ERROR] Frontend dependencies install failed. Node.js required.
        cd ..
        pause
        exit /b 1
    )
    cd ..
)

REM === 5. Kill old backend if any ===
echo [INFO]  Checking for existing backend process...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 17250 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id `$_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host '  Stopped old process PID' `$_.OwningProcess }" 2>nul

REM === 6. Start backend ===
echo.
echo [INFO]  Starting backend on port 17250...
start "NLS-Backend" ".venv\Scripts\python.exe" app.py

REM === 7. Wait for backend ===
echo [INFO]  Waiting for backend to be ready...
:wait_backend
timeout /t 1 /nobreak >nul
curl -s http://127.0.0.1:17250/health >nul 2>&1
if errorlevel 1 goto wait_backend

echo [OK]    Backend ready: http://127.0.0.1:17250

REM === 8. Start frontend ===
echo [INFO]  Starting frontend dev server on port 5173...
start "NLS-Frontend" cmd /c "cd /d frontend && npm run dev"

REM === 9. Open browser ===
echo [INFO]  Opening browser...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:5173

echo.
echo ========================================
echo   Startup complete!
echo   Frontend : http://127.0.0.1:5173
echo   Backend  : http://127.0.0.1:17250
echo   API Docs : http://127.0.0.1:17250/docs
echo ========================================
echo.
echo Press any key to close this window (services will keep running).
pause >nul

endlocal
