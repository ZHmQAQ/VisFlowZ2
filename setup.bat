@echo off
chcp 65001 >nul 2>&1
title VModule - 环境安装

echo ============================================
echo   VModule 环境安装
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

:: 创建虚拟环境
if not exist "venv" (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
) else (
    echo [1/3] 虚拟环境已存在，跳过
)

echo [2/3] 激活虚拟环境...
call venv\Scripts\activate.bat

echo [3/3] 安装依赖...
pip install -r requirements.txt -q

:: 创建目录
if not exist "data\weights" mkdir data\weights

echo.
echo ============================================
echo   安装完成！
echo   启动命令: start.bat
echo   API 文档: http://localhost:8100/docs
echo ============================================
pause
