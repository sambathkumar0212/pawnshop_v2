@echo off
cd /d "%~dp0"
title Package Pawnshop ERP for cPanel

echo =======================================================
echo     BUILDING & PACKAGING PAWNSHOP ERP FOR CPANEL
echo =======================================================
echo.

python package_for_cpanel.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Packaging failed. Please check Python installation.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Packaging complete!
pause
