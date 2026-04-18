@echo off
title VModule - PLC Virtual Extension Module
echo ============================================
echo   VModule v3.1.0 - PLC Virtual Extension
echo   Port: 8100
echo   API docs: http://localhost:8100/docs
echo ============================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [WARN] No .venv found, using system Python. Run setup.bat first.
)

python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] First run, installing dependencies...
    pip install -r backend\requirements.txt -q
)

if not exist "backend\data" mkdir backend\data
if not exist "backend\data\weights" mkdir backend\data\weights

echo.
echo [START] Launching VModule backend...
echo [TIP] Press Ctrl+C to stop
echo.
cd /d "%~dp0backend"
python run.py
pause
