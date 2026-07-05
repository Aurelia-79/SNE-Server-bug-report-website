@echo off
setlocal EnableExtensions

cd /d "%~dp0"

if not exist ".env" (
  echo .env not found. Copy .env.example to .env and change production values first.
  exit /b 1
)

if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads

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

powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 17250 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

powershell -NoProfile -Command "$p = Start-Process -WindowStyle Hidden -FilePath '.venv\Scripts\python.exe' -ArgumentList @('app.py') -WorkingDirectory (Get-Location) -RedirectStandardOutput 'logs\server.out.log' -RedirectStandardError 'logs\server.err.log' -PassThru; $p.Id | Set-Content 'logs\server.pid'"

echo Started on 0.0.0.0:17250
echo Local access: http://127.0.0.1:17250
echo LAN access: http://YOUR_SERVER_IP:17250
echo PID saved to logs\server.pid

endlocal
