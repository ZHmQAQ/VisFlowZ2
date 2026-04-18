@echo off
title VModule - Setup

echo ============================================
echo   VModule Environment Setup
echo ============================================
echo.

cd /d "%~dp0backend"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

if not exist "venv" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
) else (
    echo [1/3] Virtual environment exists, skipping
)

echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/3] Installing dependencies...
pip install --upgrade pip -q
pip install -r requirements.txt -q

if not exist "data\weights" mkdir data\weights

echo.
echo ============================================
echo   Setup complete!
echo   Run: start.bat
echo   API docs: http://localhost:8100/docs
echo ============================================
pause
