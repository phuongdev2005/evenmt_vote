@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo Building Docker image for SMS Tool
echo ============================================

docker build -t sms_tool .

if %errorlevel% neq 0 (
    echo Failed to build Docker image.
    pause
    exit /b 1
)

echo.
echo ============================================
echo Build complete!
echo Run scripts using run_*.bat files
echo ============================================
pause
