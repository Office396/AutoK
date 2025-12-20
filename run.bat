@echo off
title Telecom Alarm Automation
echo ==========================================
echo   Telecom Alarm Automation
echo   Starting...
echo ==========================================
echo.

cd /d "%~dp0"

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

:: Check for virtual environment and activate it FIRST
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found!
    echo Please run install.bat first.
    pause
    exit /b 1
)

:: Activate the virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Verify we are using the venv Python
echo Using Python: 
where python
echo.

:: Check if key packages are installed in venv
echo Checking dependencies...
python -c "import customtkinter; import selenium; import pandas; import openpyxl" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Dependencies missing! Installing...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install requirements!
        pause
        exit /b 1
    )
    echo. > .requirements_installed
    echo.
    echo Dependencies installed successfully!
    echo.
)

:: Run the application
echo Starting application...
echo.
python main.py

pause