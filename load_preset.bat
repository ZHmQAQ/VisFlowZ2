@echo off
title VModule - Load Preset

echo ============================================
echo   VModule Preset Loader
echo ============================================
echo.

if "%~1"=="" (
    echo Usage: load_preset.bat ^<preset_file^>
    echo.
    echo Available presets:
    echo   presets\single_station.json   Single station
    echo   presets\dual_station.json     Dual station
    echo   presets\sorting_line.json     Sorting line
    echo.
    echo Example: load_preset.bat presets\single_station.json
    pause
    exit /b 0
)

cd /d "%~dp0"

if not exist "%~1" (
    echo [ERROR] Preset file not found: %~1
    pause
    exit /b 1
)

echo [INFO] Loading preset: %~1
echo.

curl -s -X POST http://localhost:8100/api/plc/preset/load -H "Content-Type: application/json" -d @"%~1"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Load failed. Make sure VModule is running (start.bat)
) else (
    echo.
    echo [OK] Preset loaded successfully
)
pause
