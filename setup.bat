@echo off
REM ============================================================
REM  VModule 一键安装脚本
REM  适用场景: 从 GitHub 下载 zip 解压后首次运行
REM  前提: 已安装 Python 3.10+ 和 Node.js 18+
REM ============================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul
title VModule - 一键安装

cd /d "%~dp0"

echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║    VModule - PLC 虚拟扩展模块  安装向导    ║
echo  ╚═══════════════════════════════════════════╝
echo.

REM ---- 检查 Python ----
echo [检查] Python ...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请安装 Python 3.10+
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo        已找到 Python %%v

REM ---- 检查 Node.js (可选) ----
echo [检查] Node.js ...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo        未找到 Node.js，将跳过前端构建
    echo        如果 frontend\dist 已存在则可正常运行
    set HAS_NODE=0
) else (
    for /f %%v in ('node --version 2^>^&1') do echo        已找到 Node.js %%v
    set HAS_NODE=1
)

echo.

REM ---- Step 1: Python 虚拟环境 ----
echo [1/4] 创建 Python 虚拟环境 ...
if not exist ".venv" (
    python -m venv .venv
    echo        .venv 已创建
) else (
    echo        .venv 已存在，跳过
)

echo [2/4] 安装后端依赖 ...
call .venv\Scripts\activate.bat
pip install -r backend\requirements.txt -q
if %errorlevel% neq 0 (
    echo [错误] pip install 失败，请检查网络或 requirements.txt
    pause
    exit /b 1
)
echo        后端依赖安装完成

REM ---- Step 3: 前端 ----
if "!HAS_NODE!"=="1" (
    echo [3/4] 安装前端依赖并构建 ...
    cd /d "%~dp0frontend"
    call npm install --silent 2>nul
    call npm run build
    if %errorlevel% neq 0 (
        echo [警告] 前端构建失败，请手动检查
    ) else (
        echo        前端构建完成
    )
    cd /d "%~dp0"
) else (
    echo [3/4] 跳过前端构建（无 Node.js）
    if exist "frontend\dist\index.html" (
        echo        已检测到预构建的前端产物，可正常运行
    ) else (
        echo [警告] frontend\dist 不存在，前端页面将不可用
        echo        请安装 Node.js 18+ 后重新运行此脚本
    )
)

REM ---- Step 4: 数据目录 ----
echo [4/4] 初始化数据目录 ...
if not exist "backend\data" mkdir backend\data
if not exist "backend\data\weights" mkdir backend\data\weights
if not exist "backend\data\logs" mkdir backend\data\logs
echo        数据目录就绪

echo.
echo ╔═══════════════════════════════════════════╗
echo ║            安装完成!                       ║
echo ╠═══════════════════════════════════════════╣
echo ║  启动: start.bat                           ║
echo ║  地址: http://localhost:8100               ║
echo ║  文档: http://localhost:8100/docs          ║
echo ╚═══════════════════════════════════════════╝
echo.
pause
