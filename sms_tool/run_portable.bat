@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

set PYTHON=%CD%\python_embed\python.exe

if not exist "%PYTHON%" (
    echo Python portable not found. Please run portable_setup.bat first.
    pause
    exit /b 1
)

:: Default: run main.py
if "%~1"=="" (
    set SCRIPT=main.py
) else (
    set SCRIPT=%~1
)

"%PYTHON%" "%SCRIPT%" %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
pause
