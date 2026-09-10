# FirstMoney Gold - Web & Mobile Unified Runner (PowerShell)
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "      FIRSTMONEY GOLD PAWNSHOP - WEB & MOBILE RUNNER (PowerShell)    " -ForegroundColor Yellow
Write-Host "=====================================================================" -ForegroundColor Cyan

$WorkspaceRoot = $PSScriptRoot
Set-Location $WorkspaceRoot

# 1. Detect Python
$PythonExe = "python"
if (Test-Path "$WorkspaceRoot\pawnshop_env\Scripts\python.exe") {
    $PythonExe = "$WorkspaceRoot\pawnshop_env\Scripts\python.exe"
    Write-Host "[OK] Using virtualenv Python: $PythonExe" -ForegroundColor Green
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py"
    Write-Host "[OK] Using Python Launcher: py" -ForegroundColor Green
} else {
    Write-Host "[OK] Using System Python" -ForegroundColor Green
}

# 2. Run Migrations
Write-Host "`n[1/4] Running database migrations..." -ForegroundColor White
& $PythonExe manage.py migrate --noinput

# 3. Start Django Server
Write-Host "`n[2/4] Starting Django Server on http://0.0.0.0:8000 ..." -ForegroundColor White
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$WorkspaceRoot'; & '$PythonExe' manage.py runserver 0.0.0.0:8000"

Start-Sleep -Seconds 3

# 4. Open Web & Swagger
Write-Host "`n[3/4] Opening Web Application & Swagger Docs..." -ForegroundColor White
Start-Process "http://127.0.0.1:8000/"
Start-Process "http://127.0.0.1:8000/api/docs/"

# 5. Launch Flutter App
Write-Host "`n[4/4] Launching Flutter Mobile App..." -ForegroundColor White
$FlutterCmd = "flutter"
$FlutterInstalled = Get-Command flutter -ErrorAction SilentlyContinue
if (-not $FlutterInstalled -and (Test-Path "C:\src\flutter\bin\flutter.bat")) {
    $FlutterCmd = "C:\src\flutter\bin\flutter.bat"
    $FlutterInstalled = $true
}

if ($FlutterInstalled) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$WorkspaceRoot\mobile_app'; & '$FlutterCmd' run -d chrome"
    Write-Host "[OK] Flutter Mobile App window launched." -ForegroundColor Green
} else {
    Write-Host "`n[NOTE] Flutter SDK was not found." -ForegroundColor Yellow
    Write-Host "You can open the 'mobile_app' directory in VS Code / Android Studio to launch the mobile app." -ForegroundColor White
}

Write-Host "`n=====================================================================" -ForegroundColor Cyan
Write-Host "  SYSTEMS RUNNING:" -ForegroundColor Green
Write-Host "  - Web App:      http://127.0.0.1:8000/" -ForegroundColor White
Write-Host "  - Swagger Docs: http://127.0.0.1:8000/api/docs/" -ForegroundColor White
Write-Host "  - Mobile APIs:  http://127.0.0.1:8000/api/v1/" -ForegroundColor White
Write-Host "=====================================================================" -ForegroundColor Cyan
