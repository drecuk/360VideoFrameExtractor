@echo off
setlocal

REM   ##########################################################
REM   By Eugene Ch'ng
REM   GitHub: https://github.com/drecuk/
REM   ----------------------------------------------------------
REM   BEGINNER WINDOWS INSTALLER
REM   ----------------------------------------------------------
REM   Automatically installs Python, FFmpeg, COLMAP and the
REM   Streamlit Python requirements by double-clicking this file
REM   ##########################################################

cd /d "%~dp0"

echo.
echo 360VideoFrameExtractor - Windows Beginner Installer
echo ---------------------------------------------------
echo This installer will try to install everything needed:
echo.
echo - Python 3.12
echo - FFmpeg and FFprobe
echo - COLMAP
echo - Streamlit and the Python packages used by the app
echo - PyYAML for frame sidecar metadata files
echo.
echo It will also add the installed tools to your user PATH.
echo.

if exist ".venv\Scripts\python.exe" (
    echo Existing Python virtual environment found.
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python is not available yet. The PowerShell installer will install Python and create .venv.
    ) else (
        echo Creating Python virtual environment before dependency installation...
        python -m venv .venv
        if errorlevel 1 (
            echo Could not create .venv with the current Python command.
            echo The PowerShell installer will try again after checking Python.
        )
    )
)
echo.

where powershell >nul 2>nul
if errorlevel 1 (
    echo Windows PowerShell was not found.
    echo Please install PowerShell or run this installer on a standard Windows 10/11 system.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -AutoInstallDependencies
if errorlevel 1 (
    echo.
    echo Installation did not complete.
    echo Check the error message above, then run this file again.
    echo.
    pause
    exit /b 1
)

echo.
echo Installation complete.
echo To open the web app, double-click run_windows.bat
echo or, in the same Windows PowerShell, run  .\run_windows.bat
echo If Windows still cannot find a newly installed tool, close this window and open it again.
echo.
pause
