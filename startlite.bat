@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title VModule - Lite Startup

cd /d "%~dp0"
set "BASE_DIR=%~dp0"
set "BACKEND_DIR=%BASE_DIR%backend"
set "FRONTEND_DIR=%BASE_DIR%frontend"
set "CONDA_BAT="
set "VMODULE_DATA_DIR=%BACKEND_DIR%\data"

echo ============================================
echo   VModule - Lite Startup
echo   Browser mode, Python backend
echo ============================================
echo.

echo [1/3] Activating Python environment...
where conda >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
    if defined CONDA_BASE (
        if exist "!CONDA_BASE!\condabin\conda.bat" set "CONDA_BAT=!CONDA_BASE!\condabin\conda.bat"
    )
)

if defined CONDA_BAT (
    rem Prefer the conda env currently active in this shell, if it has fastapi.
    if defined CONDA_DEFAULT_ENV (
        for %%E in (envVModule vmodule envVisFlowZ visf) do (
            if /i "%CONDA_DEFAULT_ENV%"=="%%E" (
                call "!CONDA_BAT!" run -n %%E python -c "import fastapi" >nul 2>&1
                if not errorlevel 1 (
                    call "!CONDA_BAT!" activate %%E
                    if /i "%%E"=="envVisFlowZ" echo   [INFO] Reusing VisFlowZ conda env: %%E
                    if /i "%%E"=="visf" echo   [INFO] Reusing VisFlowZ conda env: %%E
                    goto :env_ready
                )
            )
        )
    )

    rem Probe known env names in priority order: VModule own first, VisFlowZ as fallback.
    for %%E in (envVModule vmodule envVisFlowZ visf) do (
        call "!CONDA_BAT!" run -n %%E python -c "import fastapi" >nul 2>&1
        if not errorlevel 1 (
            call "!CONDA_BAT!" activate %%E
            if /i "%%E"=="envVisFlowZ" echo   [INFO] Reusing VisFlowZ conda env: %%E
            if /i "%%E"=="visf" echo   [INFO] Reusing VisFlowZ conda env: %%E
            goto :env_ready
        )
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

echo   [ERROR] No usable Python environment found.
echo           Looked for conda envs: envVModule, vmodule, envVisFlowZ, visf
echo           Looked for venvs: %BASE_DIR%.venv, %BACKEND_DIR%\.venv
echo           Run setuplite.bat first.
pause
exit /b 1

:env_ready
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Backend dependencies missing. Run setuplite.bat first.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo   [OK] %%i
echo.

echo [2/3] Checking frontend build...
if not exist "%FRONTEND_DIR%\dist\index.html" (
    echo   [ERROR] frontend\dist\index.html not found. Run setuplite.bat first.
    pause
    exit /b 1
)
echo   [OK] Frontend build ready.
echo.

echo [3/3] Starting backend...
if not exist "%BACKEND_DIR%\data" mkdir "%BACKEND_DIR%\data"
if not exist "%BACKEND_DIR%\data\weights" mkdir "%BACKEND_DIR%\data\weights"
if not exist "%BACKEND_DIR%\data\logs" mkdir "%BACKEND_DIR%\data\logs"

echo   Access: http://localhost:8100
echo   API:    http://localhost:8100/docs
echo   Press Ctrl+C to stop.
echo.

start "" "http://localhost:8100"
cd /d "%BACKEND_DIR%"
python run.py
pause
exit /b %errorlevel%
