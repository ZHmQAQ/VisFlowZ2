@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title VModule - Detect Business Path

cd /d "%~dp0"
set "BASE_DIR=%~dp0"
set "BACKEND_DIR=%BASE_DIR%backend"
set "SCRIPT=%BASE_DIR%scripts\detect_path.py"
set "CONDA_BAT="

echo ============================================
echo   VModule - Detect Business Path
echo ============================================
echo.

rem --- detect conda ---
where conda >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
    if defined CONDA_BASE (
        if exist "!CONDA_BASE!\condabin\conda.bat" set "CONDA_BAT=!CONDA_BASE!\condabin\conda.bat"
    )
)

if defined CONDA_BAT (
    for %%E in (envVModule vmodule envVisFlowZ visf) do (
        call "!CONDA_BAT!" run -n %%E python -c "import urllib.request" >nul 2>&1
        if not errorlevel 1 (
            echo   [INFO] Using conda env: %%E
            call "!CONDA_BAT!" run -n %%E python "%SCRIPT%" %*
            set "RC=!ERRORLEVEL!"
            goto :report
        )
    )
)

if exist "%BASE_DIR%.venv\Scripts\python.exe" (
    echo   [INFO] Using venv: %BASE_DIR%.venv
    "%BASE_DIR%.venv\Scripts\python.exe" "%SCRIPT%" %*
    set "RC=!ERRORLEVEL!"
    goto :report
)

if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    echo   [INFO] Using venv: %BACKEND_DIR%\.venv
    "%BACKEND_DIR%\.venv\Scripts\python.exe" "%SCRIPT%" %*
    set "RC=!ERRORLEVEL!"
    goto :report
)

where python >nul 2>&1
if not errorlevel 1 (
    echo   [INFO] Using system python
    python "%SCRIPT%" %*
    set "RC=!ERRORLEVEL!"
    goto :report
)

echo   [ERROR] Python not found. Run setuplite.bat first.
pause
exit /b 1

:report
echo.
pause
exit /b !RC!
