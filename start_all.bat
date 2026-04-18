@echo off
title VisFlowZ - Full Start (Backend + Frontend)
echo ============================================
echo   VisFlowZ v3.1.0 - Full Start
echo   Backend:  http://localhost:8100
echo   API docs: http://localhost:8100/docs
echo ============================================
echo.

cd /d "%~dp0"

REM ---- Start Backend ----
if exist "backend\dist\VisFlowZ-Backend\VisFlowZ-Backend.exe" (
    echo [INFO] Starting backend from EXE...
    start "VisFlowZ-Backend" "backend\dist\VisFlowZ-Backend\VisFlowZ-Backend.exe"
) else (
    echo [INFO] Starting backend from Python...
    cd /d "%~dp0backend"

    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python not found and no backend EXE available.
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

    start "VisFlowZ-Backend" python run.py
    cd /d "%~dp0"
)

echo [INFO] Waiting for backend...
timeout /t 3 /nobreak >nul

REM ---- Start Frontend (Electron) ----
set "ELECTRON_EXE="

REM Check installed Electron app
if exist "%LOCALAPPDATA%\Programs\visflowz\VisFlowZ.exe" (
    set "ELECTRON_EXE=%LOCALAPPDATA%\Programs\visflowz\VisFlowZ.exe"
)

REM Check local Electron build
if "%ELECTRON_EXE%"=="" (
    for /f "delims=" %%F in ('dir /b /s "frontend\release\*.exe" 2^>nul ^| findstr /i "VisFlowZ"') do (
        set "ELECTRON_EXE=%%F"
    )
)

if not "%ELECTRON_EXE%"=="" (
    echo [INFO] Starting Electron frontend: %ELECTRON_EXE%
    start "" "%ELECTRON_EXE%"
) else (
    echo [INFO] Electron app not found, opening browser...
    start http://localhost:8100
)

echo.
echo ============================================
echo   VisFlowZ is running!
echo   Press any key to stop all services...
echo ============================================
pause >nul

REM ---- Cleanup ----
echo [INFO] Stopping services...
taskkill /f /im VisFlowZ-Backend.exe >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq VisFlowZ-Backend" >nul 2>&1
echo [INFO] Done.
