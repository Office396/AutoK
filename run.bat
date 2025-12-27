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
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found!
    echo Please run install.bat first.
    pause
    exit /b 1
)

:: Verify we are using the venv Python
echo Using Python: 
where python
echo.

:: Check if key packages are installed in venv
echo Checking dependencies...
python -c "import customtkinter; import selenium; import pandas; import openpyxl" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Dependencies missing or venv corrupted! 
    echo Attempting to install requirements into virtual environment...
    echo.
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    
    :: Re-check after installation
    python -c "import customtkinter; import selenium; import pandas; import openpyxl" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ==================================================
        echo ERROR: Could not install dependencies in venv!
        echo This often happens if the 'venv' folder is corrupted
        echo or has permission issues.
        echo.
        echo SOLUTION: 
        echo 1. Close this window
        echo 2. Delete the 'venv' folder
        echo 3. Run 'install.bat' again
        echo ==================================================
        pause
        exit /b 1
    )
    echo. > .requirements_installed
    echo Dependencies installed successfully!
)

:: Run the application
echo Starting application...
echo.
python main.py

pause