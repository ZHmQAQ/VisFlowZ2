@echo off
title VisFlowZ - Lite Mode (Browser)
echo ============================================
echo   VisFlowZ v3.1.0 - Lite Mode
echo   Port: 8100
echo   URL:  http://localhost:8100
echo ============================================
echo.

cd /d "%~dp0"

REM Try backend exe first
if exist "backend\dist\VisFlowZ-Backend\VisFlowZ-Backend.exe" (
    echo [INFO] Starting backend from EXE...
    start "" "backend\dist\VisFlowZ-Backend\VisFlowZ-Backend.exe"
    goto :wait_and_open
)

REM Fallback to Python
echo [INFO] Backend EXE not found, using Python...
cd /d "%~dp0backend"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found and no backend EXE available.
    echo [TIP]   Run build_backend.bat to build the backend EXE,
    echo         or install Python 3.10+
    pause
    exit /b 1
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
)

python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt -q
)

if not exist "data" mkdir data
if not exist "data\weights" mkdir data\weights

start "" python run.py

:wait_and_open
echo.
echo [INFO] Waiting for backend to start...
timeout /t 3 /nobreak >nul

REM Open browser
echo [INFO] Opening browser at http://localhost:8100
start http://localhost:8100
echo.
echo [TIP] Press any key to stop the server
pause >nul
taskkill /f /im VisFlowZ-Backend.exe >nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq VModule*" >nul 2>&1
