@echo off
chcp 65001 >nul 2>&1
title VModule - 加载预设

echo ============================================
echo   VModule 预设加载工具
echo ============================================
echo.

if "%~1"=="" (
    echo 用法: load_preset.bat ^<预设文件^>
    echo.
    echo 可用预设:
    echo   presets\single_station.json   单工位检测
    echo   presets\dual_station.json     双工位检测
    echo   presets\sorting_line.json     分拣线
    echo.
    echo 示例: load_preset.bat presets\single_station.json
    pause
    exit /b 0
)

cd /d "%~dp0"

if not exist "%~1" (
    echo [错误] 预设文件不存在: %~1
    pause
    exit /b 1
)

echo [信息] 加载预设: %~1
echo.

:: 用 curl 调用 API 加载预设
curl -s -X POST http://localhost:8100/api/plc/preset/load -H "Content-Type: application/json" -d @"%~1"

if %errorlevel% neq 0 (
    echo.
    echo [错误] 加载失败，请确认 VModule 已启动 (start.bat)
) else (
    echo.
    echo [成功] 预设已加载
)
pause
