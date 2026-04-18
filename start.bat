@echo off
title VModule - PLC Virtual Extension Module

echo ============================================
echo   VModule v1.0.0 - PLC Virtual Extension
echo   Port: 8100
echo   API docs: http://localhost:8100/docs
echo ============================================
echo.

cd /d "%~dp0backend"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [WARN] No virtual environment found, using system Python
)

python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] First run, installing dependencies...
    pip install -r requirements.txt -q
)

if not exist "data" mkdir data
if not exist "data\weights" mkdir data\weights

echo.
echo [START] Launching VModule backend...
echo [TIP] Press Ctrl+C to stop
echo.
python run.py
pause
