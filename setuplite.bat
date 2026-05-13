@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title VModule - Lite Setup

cd /d "%~dp0"
set "BASE_DIR=%~dp0"
set "BACKEND_DIR=%BASE_DIR%backend"
set "FRONTEND_DIR=%BASE_DIR%frontend"
set "CONDA_BAT="
set "CONDA_ENV_NAME="
set "PY_ENV_MODE="
set "CONDA_REUSE_SOURCE="

echo ============================================
echo   VModule - Lite Setup
echo   Tsinghua PyPI + npmmirror
echo ============================================
echo.

echo [1/4] Detecting or creating Python environment...
where conda >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
    if defined CONDA_BASE (
        if exist "!CONDA_BASE!\condabin\conda.bat" set "CONDA_BAT=!CONDA_BASE!\condabin\conda.bat"
    )
)

if defined CONDA_BAT (
    if /i "%CONDA_DEFAULT_ENV%"=="envVModule" (
        set "CONDA_ENV_NAME=envVModule"
        set "CONDA_REUSE_SOURCE=VModule"
        goto :activate_conda
    )
    if /i "%CONDA_DEFAULT_ENV%"=="vmodule" (
        set "CONDA_ENV_NAME=vmodule"
        set "CONDA_REUSE_SOURCE=VModule"
        goto :activate_conda
    )
    if /i "%CONDA_DEFAULT_ENV%"=="envVisFlowZ" (
        set "CONDA_ENV_NAME=envVisFlowZ"
        set "CONDA_REUSE_SOURCE=VisFlowZ"
        goto :activate_conda
    )
    if /i "%CONDA_DEFAULT_ENV%"=="visf" (
        set "CONDA_ENV_NAME=visf"
        set "CONDA_REUSE_SOURCE=VisFlowZ"
        goto :activate_conda
    )

    for %%E in (envVModule vmodule envVisFlowZ visf) do (
        echo   [CHECK] Conda env: %%E
        call "!CONDA_BAT!" run -n %%E python --version >nul 2>&1
        if not errorlevel 1 (
            set "CONDA_ENV_NAME=%%E"
            if /i "%%E"=="envVisFlowZ" set "CONDA_REUSE_SOURCE=VisFlowZ"
            if /i "%%E"=="visf" set "CONDA_REUSE_SOURCE=VisFlowZ"
            if not defined CONDA_REUSE_SOURCE set "CONDA_REUSE_SOURCE=VModule"
            goto :activate_conda
        )
    )

    echo   [CREATE] Conda env envVModule with Python 3.10
    call "!CONDA_BAT!" create -n envVModule python=3.10 -y
    if errorlevel 1 (
        echo   [WARN] Conda env creation failed. Falling back to .venv.
        goto :activate_venv
    )
    set "CONDA_ENV_NAME=envVModule"
    set "CONDA_REUSE_SOURCE=VModule"
    goto :activate_conda
)

goto :activate_venv

:activate_conda
echo   [OK] Using Conda env: !CONDA_ENV_NAME!
if /i "!CONDA_REUSE_SOURCE!"=="VisFlowZ" (
    echo   [INFO] Reusing VisFlowZ Conda env: !CONDA_ENV_NAME!
    echo   [INFO] VModule requirements will be installed/updated in this env.
)
call "!CONDA_BAT!" activate "!CONDA_ENV_NAME!"
if errorlevel 1 (
    echo   [ERROR] Failed to activate Conda env: !CONDA_ENV_NAME!
    pause
    exit /b 1
)
set "PY_ENV_MODE=conda"
goto :env_ready

:activate_venv
where python >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found. Install Python 3.10+ or Conda first.
    pause
    exit /b 1
)
if not exist "%BASE_DIR%.venv\Scripts\activate.bat" (
    echo   [CREATE] .venv
    python -m venv "%BASE_DIR%.venv"
    if errorlevel 1 (
        echo   [ERROR] Failed to create .venv
        pause
        exit /b 1
    )
)
call "%BASE_DIR%.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo   [ERROR] Failed to activate .venv
    pause
    exit /b 1
)
set "PY_ENV_MODE=venv"

:env_ready
for /f "tokens=*" %%i in ('python --version') do echo   [OK] %%i
echo.

echo [2/4] Installing backend dependencies via Tsinghua mirror...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 echo   [WARN] pip upgrade failed, continuing.

python -m pip install -r "%BACKEND_DIR%\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo   [ERROR] Backend dependency installation failed.
    pause
    exit /b 1
)

python -m pip check
if errorlevel 1 (
    echo   [WARN] pip check found dependency conflicts.
) else (
    echo   [OK] Backend dependencies verified.
)
echo.

echo [3/4] Building frontend via npmmirror...
if not exist "%FRONTEND_DIR%\package.json" (
    if exist "%FRONTEND_DIR%\dist\index.html" (
        echo   [OK] Frontend dist-only package detected. Skipping npm build.
        goto :frontend_done
    )
    echo   [ERROR] frontend package.json and dist\index.html are both missing.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    if "!PY_ENV_MODE!"=="conda" (
        echo   [INFO] Node.js not found. Installing nodejs=18 via Conda...
        call "!CONDA_BAT!" install -n "!CONDA_ENV_NAME!" nodejs=18 -c conda-forge -y
        if errorlevel 1 (
            echo   [ERROR] Node.js installation failed.
            pause
            exit /b 1
        )
    ) else (
        echo   [ERROR] Node.js not found. Install Node.js 18+ or use Conda env setup.
        pause
        exit /b 1
    )
)

cd /d "%FRONTEND_DIR%"
call npm config set registry https://registry.npmmirror.com
call npm install --registry=https://registry.npmmirror.com
if errorlevel 1 (
    echo   [ERROR] npm install failed.
    pause
    exit /b 1
)

call npm run build
if errorlevel 1 (
    echo   [ERROR] Frontend build failed.
    pause
    exit /b 1
)
cd /d "%BASE_DIR%"
:frontend_done
echo   [OK] Frontend ready.
echo.

echo [4/4] Creating runtime directories...
if not exist "%BACKEND_DIR%\data" mkdir "%BACKEND_DIR%\data"
if not exist "%BACKEND_DIR%\data\weights" mkdir "%BACKEND_DIR%\data\weights"
if not exist "%BACKEND_DIR%\data\logs" mkdir "%BACKEND_DIR%\data\logs"
if not exist "%BACKEND_DIR%\data\cycles" mkdir "%BACKEND_DIR%\data\cycles"
echo   [OK] Runtime directories ready.
echo.

echo ============================================
echo   Lite setup complete
echo ============================================
echo   Start: startlite.bat
echo   API:   http://localhost:8100/docs
echo.
pause

