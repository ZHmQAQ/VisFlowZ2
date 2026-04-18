@echo off
title VisFlowZ Backend - Build EXE
echo ============================================
echo   VisFlowZ Backend - PyInstaller Build
echo ============================================
echo.

cd /d "%~dp0backend"

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Activate venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
)

REM Check PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller -q
)

REM Check frontend dist exists
if not exist "%~dp0frontend\dist\index.html" (
    echo [WARN] Frontend dist not found. Building frontend first...
    cd /d "%~dp0frontend"
    if exist "node_modules\.bin\vite.cmd" (
        call npx vite build
    ) else (
        echo [ERROR] Frontend node_modules not found. Run: cd frontend ^&^& npm install ^&^& npx vite build
        echo [INFO] Continuing without frontend...
    )
    cd /d "%~dp0backend"
)

echo.
echo [BUILD] Running PyInstaller...
echo.
pyinstaller visflowz.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

REM Create data directories in dist
if not exist "dist\VisFlowZ-Backend\data" mkdir "dist\VisFlowZ-Backend\data"
if not exist "dist\VisFlowZ-Backend\data\weights" mkdir "dist\VisFlowZ-Backend\data\weights"

echo.
echo ============================================
echo   Build complete!
echo   Output: backend\dist\VisFlowZ-Backend\
echo   EXE:    backend\dist\VisFlowZ-Backend\VisFlowZ-Backend.exe
echo ============================================
echo.
echo [TIP] Copy .pt model files to dist\VisFlowZ-Backend\data\weights\
echo.
pause
