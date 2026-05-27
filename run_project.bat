@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0pawnshop_env\Scripts\python.exe"
set "APP_URL=http://127.0.0.1:8000/"

if not exist "%PYTHON_EXE%" goto missing_python

for /f %%P in ('powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)"') do set "RUNNING_PID=%%P"

if defined RUNNING_PID goto already_running

echo Starting project at %APP_URL%
start "" "%APP_URL%"
"%PYTHON_EXE%" manage.py runserver 127.0.0.1:8000

if errorlevel 1 goto start_failed
endlocal
exit /b 0

:already_running
echo Project is already running on %APP_URL% (PID %RUNNING_PID%).
start "" "%APP_URL%"
endlocal
exit /b 0

:missing_python
echo ERROR: Virtual environment Python not found at:
echo %PYTHON_EXE%
echo.
echo Run setup first, then try again.
pause
endlocal
exit /b 1

:start_failed
echo.
echo Failed to start Django server.
echo Common causes:
echo 1. Port 8000 is already in use.
echo 2. Missing dependencies in pawnshop_env.
pause
endlocal
exit /b 1
