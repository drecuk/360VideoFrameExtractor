@echo off
setlocal

REM   ##########################################################
REM   By Eugene Ch'ng
REM   GitHub: https://github.com/drecuk/
REM   ----------------------------------------------------------
REM   BEGINNER WINDOWS LAUNCHER
REM   ----------------------------------------------------------
REM   Starts the Streamlit web app from the local Python
REM   environment created by install_windows.bat
REM   ##########################################################

cd /d "%~dp0"

echo.
echo Starting 360VideoFrameExtractor...
echo A browser window should open at http://localhost:8501
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
if errorlevel 1 (
    echo.
    echo The application could not start.
    echo If this is your first time, double-click install_windows.bat first.
    echo.
    pause
    exit /b 1
)

pause
