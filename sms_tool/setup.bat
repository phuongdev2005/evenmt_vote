@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo SMS Tool Setup
echo ============================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python 3.10+ first.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Installing Playwright browsers...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo Failed to install Playwright browsers.
    pause
    exit /b 1
)

echo.
echo ============================================
echo Setup complete!
echo ============================================
pause
