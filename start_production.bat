@echo off
setlocal EnableExtensions

cd /d "%~dp0"

if not exist ".env" (
  echo .env not found. Copy .env.example to .env and change SECRET_KEY and BOOTSTRAP_SUPER_ADMIN_PASSWORD first.
  exit /b 1
)

set VENV_OK=0
if exist ".venv\Scripts\python.exe" (
  call ".venv\Scripts\python.exe" -c "exit(0)" >nul 2>&1
  if not errorlevel 1 set VENV_OK=1
)
if "%VENV_OK%"=="0" (
  if exist ".venv" rmdir /s /q ".venv"
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads

echo Starting NLS Admin on 0.0.0.0:17250
echo Local access: http://127.0.0.1:17250
echo LAN access: http://YOUR_SERVER_IP:17250
call ".venv\Scripts\python.exe" app.py

endlocal
