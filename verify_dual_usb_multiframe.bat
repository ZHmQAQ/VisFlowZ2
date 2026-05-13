@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title VModule - Dual USB Multi-frame Verifier

cd /d "%~dp0"
set "BASE_DIR=%~dp0"
set "BACKEND_DIR=%BASE_DIR%backend"
set "PRESET=presets\dual_usb_multiframe_baseline.json"
set "CONDA_BAT="

if not "%~1"=="" set "PRESET=%~1"

echo ============================================
echo   VModule - Dual USB Multi-frame Verifier
echo ============================================
echo   Preset: %PRESET%
echo.

where conda >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
    if defined CONDA_BASE (
        if exist "!CONDA_BASE!\condabin\conda.bat" set "CONDA_BAT=!CONDA_BASE!\condabin\conda.bat"
    )
)

if defined CONDA_BAT (
    call "!CONDA_BAT!" run -n envVModule python -c "import cv2" >nul 2>&1
    if not errorlevel 1 (
        call "!CONDA_BAT!" activate envVModule
        goto :env_ready
    )

    call "!CONDA_BAT!" run -n vmodule python -c "import cv2" >nul 2>&1
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

echo [ERROR] No Python environment found. Run setup.bat first.
pause
exit /b 1

:env_ready
python scripts\verify_dual_usb_multiframe.py --preset "%PRESET%"
if errorlevel 1 (
    echo.
    echo [ERROR] Verification failed.
    pause
    exit /b 1
)

echo.
echo [OK] Verification passed.
pause
