@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title VModule - Backend Exe Build

cd /d "%~dp0"
set "BASE_DIR=%~dp0"
set "BACKEND_DIR=%BASE_DIR%backend"
set "FRONTEND_DIR=%BASE_DIR%frontend"
set "CONDA_BAT="

echo ============================================
echo   VModule - Backend PyInstaller Build
echo ============================================
echo.

if not exist "%FRONTEND_DIR%\dist\index.html" (
    echo [ERROR] frontend\dist\index.html not found.
    echo Run setup.bat or setuplite.bat before building the exe.
    pause
    exit /b 1
)

echo [1/3] Activating Python environment...
where conda >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
    if defined CONDA_BASE (
        if exist "!CONDA_BASE!\condabin\conda.bat" set "CONDA_BAT=!CONDA_BASE!\condabin\conda.bat"
    )
)

if defined CONDA_BAT (
    call "!CONDA_BAT!" run -n envVModule python -c "import fastapi" >nul 2>&1
    if not errorlevel 1 (
        call "!CONDA_BAT!" activate envVModule
        goto :env_ready
    )

    call "!CONDA_BAT!" run -n vmodule python -c "import fastapi" >nul 2>&1
    if not errorlevel 1 (
        call "!CONDA_BAT!" activate vmodule
        goto :env_ready
    )
)

if exist "%BASE_DIR%.venv\Scripts\activate.bat" (
    call "%BASE_DIR%.venv\Scripts\activate.bat"
    goto :env_ready
)

if exist "%BACKEND_DIR%\.venv\Scripts\activate.bat" (
    call "%BACKEND_DIR%\.venv\Scripts\activate.bat"
    goto :env_ready
)

echo   [ERROR] No Python environment found. Run setup.bat first.
pause
exit /b 1

:env_ready
for /f "tokens=*" %%i in ('python --version') do echo   [OK] %%i
echo.

echo [2/3] Installing PyInstaller if needed...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    python -m pip install "pyinstaller>=6.0"
    if errorlevel 1 (
        echo   [ERROR] PyInstaller installation failed.
        pause
        exit /b 1
    )
)
echo   [OK] PyInstaller ready.
echo.

echo [3/3] Building backend exe...
cd /d "%BACKEND_DIR%"
pyinstaller pyinstaller.spec --distpath "%BACKEND_DIR%\dist" --workpath "%BASE_DIR%build" --clean
if errorlevel 1 (
    echo.
    echo [ERROR] Exe build failed. Python startup still works with startlite.bat.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build success
echo ============================================
echo   Exe: %BACKEND_DIR%\dist\VModule-Backend.exe
echo   Start with: start.bat
echo.
pause
