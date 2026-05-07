@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

set PYTHON_ZIP=python-3.11.9-embed-amd64.zip
set PYTHON_URL=https://www.python.org/ftp/python/3.11.9/%PYTHON_ZIP%
set PYTHON_DIR=%CD%\python_embed

if exist "%PYTHON_DIR%\python.exe" (
    echo Python portable already exists: %PYTHON_DIR%
    goto :install_libs
)

echo ============================================
echo Downloading Python 3.11 portable...
echo %PYTHON_URL%
echo ============================================

powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%' -UseBasicParsing"
if not exist "%PYTHON_ZIP%" (
    echo Failed to download Python. Check internet connection.
    pause
    exit /b 1
)

echo Extracting Python...
powershell -Command "Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
del "%PYTHON_ZIP%"

:: Enable pip in embeddable python
echo import site >> "%PYTHON_DIR%\python311._pth"

:install_libs
echo ============================================
echo Installing pip...
echo ============================================
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYTHON_DIR%\get-pip.py' -UseBasicParsing"
"%PYTHON_DIR%\python.exe" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location
del "%PYTHON_DIR%\get-pip.py" 2>nul

echo ============================================
echo Installing requirements...
echo ============================================
"%PYTHON_DIR%\python.exe" -m pip install -r requirements.txt --no-warn-script-location

echo ============================================
echo Installing Playwright browsers...
echo ============================================
"%PYTHON_DIR%\python.exe" -m playwright install chromium

echo ============================================
echo Setup complete!
echo Python: %PYTHON_DIR%\python.exe
echo ============================================
pause
