"""
Telecom Alarm Automation
Main Entry Point

This application automates the monitoring of telecom alarms from MAE Portal
and sends notifications to appropriate WhatsApp groups.

Usage:
    python main.py

Requirements:
    - Python 3.8+
    - Chrome browser installed
    - All dependencies from requirements.txt
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

# Set working directory
os.chdir(PROJECT_ROOT)


def check_requirements():
    """Check if all required packages are installed"""
    required = [
        'customtkinter',
        'selenium',
        'pandas',
        'openpyxl',
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("=" * 50)
        print("ERROR: Missing required packages in current environment.")
        print(f"Current Python: {sys.executable}")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nPossible solutions:")
        print("1. If using run.bat, ensure it finished installing dependencies.")
        print("2. Try running: python -m pip install -r requirements.txt")
        print("3. If the virtual environment is corrupted, delete 'venv' folder")
        print("   and run 'install.bat' again.")
        print("=" * 50)
        return False
    
    return True


def main():
    """Main entry point"""
    print("=" * 50)
    print("  Telecom Alarm Automation")
    print("  Starting application...")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        input("Press Enter to exit...")
        sys.exit(1)
    
    try:
        # Import after checking requirements
        from main_window import MainWindow
        from config import settings, DATA_DIR, LOGS_DIR, EXPORTS_DIR
        from logger_module import logger
        
        # Ensure directories exist
        DATA_DIR.mkdir(exist_ok=True)
        LOGS_DIR.mkdir(exist_ok=True)
        EXPORTS_DIR.mkdir(exist_ok=True)
        
        # Log startup
        logger.info("Application starting...")
        
        # Create and run main window
        app = MainWindow()
        
        logger.info("Main window created, starting event loop")
        
        app.mainloop()
        
        logger.info("Application closed normally")
        
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()