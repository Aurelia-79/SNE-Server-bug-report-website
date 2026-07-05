@echo off
setlocal EnableExtensions

cd /d "%~dp0"

powershell -NoProfile -Command "if (Test-Path 'logs\server.pid') { $id = Get-Content 'logs\server.pid' -ErrorAction SilentlyContinue; if ($id) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }; Get-NetTCPConnection -LocalPort 17250 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo Stopped.

endlocal
