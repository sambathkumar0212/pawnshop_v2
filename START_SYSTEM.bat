@echo off
setlocal enabledelayedexpansion
title FirstMoney Gold - 1-Click System Launcher
cd /d "%~dp0"

echo =====================================================================
echo            FIRSTMONEY GOLD PAWNSHOP - 1-CLICK LAUNCHER
echo =====================================================================
echo.

:: 1. Detect Python
set "PYTHON_CMD=python"
if exist "%~dp0pawnshop_env\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0pawnshop_env\Scripts\python.exe"
    echo [OK] Using virtualenv Python.
) else (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py"
        echo [OK] Using Python Launcher.
    ) else (
        echo [OK] Using System Python.
    )
)

:: 2. Database Migrations
echo [1/3] Checking database...
"%PYTHON_CMD%" manage.py migrate --noinput >nul 2>&1

:: 3. Start Django Backend Server
echo [2/3] Starting Backend Server (0.0.0.0:8000)...
start "FirstMoney Django Backend" cmd /k "title FirstMoney Backend Server && "%PYTHON_CMD%" manage.py runserver 0.0.0.0:8000"

:: Wait 3 seconds for server to be ready
timeout /t 3 /nobreak >nul

:: Open Web Management Portal in default browser
start "" "http://127.0.0.1:8000/"

:: 4. Start Mobile / Flutter App
echo [3/3] Launching Mobile Application...

set "FLUTTER_CMD=flutter"
where flutter >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\src\flutter\bin\flutter.bat" (
        set "FLUTTER_CMD=C:\src\flutter\bin\flutter.bat"
    )
)

start "FirstMoney Mobile App" cmd /k "title FirstMoney Mobile App && cd /d "%~dp0mobile_app" && "!FLUTTER_CMD!" run -d chrome"

echo.
echo =====================================================================
echo  SUCCESS! Both apps are now launching:
echo  1. Web Management App:  http://127.0.0.1:8000/
echo  2. Mobile App:          Opening in Chrome (Mobile View)
echo =====================================================================
echo.
echo Note: Keep this window and the backend window open while using the system.
echo Press any key to close this launcher info window.
pause >nul
