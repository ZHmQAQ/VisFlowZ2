@echo off
chcp 65001 >nul 2>&1
title VModule - PLC 虚拟扩展模块

echo ============================================
echo   VModule v1.0.0 - PLC 虚拟扩展模块
echo   端口: 8100
echo   API 文档: http://localhost:8100/docs
echo ============================================
echo.

cd /d "%~dp0backend"

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo [信息] 激活虚拟环境...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [信息] 激活虚拟环境...
    call .venv\Scripts\activate.bat
) else (
    echo [警告] 未检测到虚拟环境，使用系统 Python
)

:: 检查依赖
python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 首次运行，安装依赖...
    pip install -r requirements.txt -q
)

:: 创建数据目录
if not exist "data" mkdir data
if not exist "data\weights" mkdir data\weights

echo.
echo [启动] 正在启动 VModule 后端服务...
echo [提示] Ctrl+C 停止服务
echo.
python run.py
pause
