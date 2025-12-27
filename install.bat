@echo off
title Telecom Alarm Automation - Setup
echo ==========================================
echo   Telecom Alarm Automation
echo   First Time Setup
echo ==========================================
echo.

cd /d "%~dp0"

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed!
    echo.
    echo Please download and install Python 3.8+ from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo Python found!
python --version
echo.

:: Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo Failed to create virtual environment!
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install requirements
echo.
echo Installing required packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements!
    pause
    exit /b 1
)

:: Create directories
echo.
echo Creating directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "exports" mkdir exports
if not exist "chrome_profile" mkdir chrome_profile

:: Create marker file
echo. > .requirements_installed

echo.
echo ==========================================
echo   Setup Complete!
echo ==========================================
echo.
echo To start the application, run: run.bat
echo.
echo IMPORTANT:
echo 1. Place your Master Data Excel file in the 'data' folder
echo 2. Configure settings in the application
echo 3. Have Chrome browser installed
echo.
pause