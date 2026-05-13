@echo off
setlocal
chcp 65001 >nul
title VModule - Load Preset

cd /d "%~dp0"

echo ============================================
echo   VModule - Preset Loader
echo ============================================
echo.

if "%~1"=="" (
    echo Usage:
    echo   load_preset.bat ^<preset_file^>
    echo.
    echo Available presets:
    echo   presets\dual_usb_multiframe_baseline.json  Dual USB D60/D61 + D62/D63 baseline
    echo   presets\single_station.json                Single station
    echo   presets\dual_station.json                  Dual station
    echo   presets\dual_daheng_3frame.json            Dual Daheng 3-frame
    echo   presets\sorting_line.json                  Sorting line
    echo.
    echo Example:
    echo   load_preset.bat presets\dual_usb_multiframe_baseline.json
    pause
    exit /b 0
)

if not exist "%~1" (
    echo [ERROR] Preset file not found: %~1
    pause
    exit /b 1
)

echo [INFO] Loading preset: %~1
echo [INFO] Target API: http://localhost:8100/api/plc/preset/load
echo.

curl --fail -s -X POST http://localhost:8100/api/plc/preset/load -H "Content-Type: application/json" -d @"%~1"

if errorlevel 1 (
    echo.
    echo [ERROR] Load failed. Make sure VModule is running with start.bat.
    pause
    exit /b 1
)

echo.
echo [OK] Preset loaded.
pause
