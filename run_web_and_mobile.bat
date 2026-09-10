@echo off
setlocal enabledelayedexpansion
title FirstMoney Gold - Web & Mobile Unified Runner
cd /d "%~dp0"

echo =====================================================================
echo       FIRSTMONEY GOLD PAWNSHOP - WEB & MOBILE RUNNER
echo =====================================================================
echo.

:: 1. Detect Python Executable
set "PYTHON_CMD=python"
if exist "%~dp0pawnshop_env\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0pawnshop_env\Scripts\python.exe"
    echo [OK] Using virtual environment Python: !PYTHON_CMD!
) else (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py"
        echo [OK] Using Python Launcher: py
    ) else (
        echo [OK] Using System Python
    )
)

:: 2. Database Migrations
echo [1/3] Checking database and migrations...
"%PYTHON_CMD%" manage.py migrate --noinput >nul 2>&1

:: 3. Start Django Server in background
echo [2/3] Starting Django Backend on http://0.0.0.0:8000 ...
start "FirstMoney Django Backend" cmd /k "title FirstMoney Backend && "%PYTHON_CMD%" manage.py runserver 0.0.0.0:8000"

:: Wait 3 seconds for backend to start
timeout /t 3 /nobreak >nul

:: Launch Web App in Default Browser
start "" "http://127.0.0.1:8000/"

:: 4. Launch Flutter Mobile App
echo [3/3] Launching Flutter Mobile App in Chrome...

set "FLUTTER_CMD=flutter"
where flutter >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\src\flutter\bin\flutter.bat" (
        set "FLUTTER_CMD=C:\src\flutter\bin\flutter.bat"
    )
)

start "FirstMoney Flutter Mobile App" cmd /k "title FirstMoney Mobile App && cd /d "%~dp0mobile_app" && "!FLUTTER_CMD!" run -d chrome"

echo.
echo =====================================================================
echo  ALL SYSTEMS RUNNING!
echo  - Counter Web App:       http://127.0.0.1:8000/
echo  - Mobile App:          Running in Chrome
echo  - Swagger API Console:   http://127.0.0.1:8000/api/docs/
echo =====================================================================
echo.
echo Keep this window or the backend console open.
pause >nul
