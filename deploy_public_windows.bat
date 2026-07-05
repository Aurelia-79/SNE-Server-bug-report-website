@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo This project has been packaged as a single FastAPI production app.
echo Use run_background.bat for background production startup.
echo Use start_production.bat for foreground production startup.
echo.

call "%~dp0run_background.bat"

endlocal
