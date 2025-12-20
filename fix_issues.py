"""
Fix common issues with the application
"""

import json
import os
from pathlib import Path

# Get the directory where this script is located
BASE_DIR = Path(__file__).parent.absolute()
SETTINGS_FILE = BASE_DIR / "settings.json"
CHROME_PROFILE = BASE_DIR / "chrome_profile"

def fix_settings():
    """Fix or create settings.json"""
    default_settings = {
        "credentials": {
            "username": "",
            "password": ""
        },
        "timing": {
            "csl_fault": 0,
            "rf_unit_failure": 30,
            "cell_unavailable": 30,
            "low_voltage": 30,
            "ac_main_failure": 60,
            "system_on_battery": 30,
            "battery_high_temp": 30,
            "genset_operation": 60,
            "mains_failure": 60
        },
        "mbu_groups": {
            "C1-LHR-01": "C1-LHR-MBU-01",
            "C1-LHR-02": "MBU C1-LHR-02",
            "C1-LHR-03": "C1-LHR-03",
            "C1-LHR-04": "MBU C1-LHR-04",
            "C1-LHR-05": "MBU C1 LHR-05",
            "C1-LHR-06": "MBU C1-LHR-06 Hotline",
            "C1-LHR-07": "MBU-C1-LHR-07",
            "C1-LHR-08": "MBU C1-LHR-08 Hotline"
        },
        "b2s_groups": {
            "ATL": "JAZZ ATL CA-LHR-C1",
            "Edotco": "Jazz~edotco C1 & C4",
            "Enfrashare": "Jazz Enfrashare MPL C1",
            "Tawal": "TAWAL - Jazz (Central-A)"
        },
        "omo_groups": {
            "Zong": "MPL JAZZ & CMPAK",
            "Ufone": "Ufone Jazz Sites Huawei Group",
            "Telenor": "TP JAZZ Shared Sites C1"
        },
        "master_file_path": str(BASE_DIR / "data" / "Master_Data.xlsx"),
        "check_interval_seconds": 30,
        "auto_start": False,
        "separate_browser_window": False,
        "skip_toggle_mbus": ["C1-LHR-04", "C1-LHR-05"]
    }
    
    try:
        # Delete old settings if corrupted
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    json.load(f)
                print("Settings file is valid.")
                return
            except:
                print("Settings file is corrupted. Recreating...")
                SETTINGS_FILE.unlink()
        
        # Create new settings
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=4)
        
        print("Settings file created successfully!")
        
    except Exception as e:
        print(f"Error: {e}")

def fix_chrome_profile():
    """Clear Chrome profile if corrupted"""
    import shutil
    
    if CHROME_PROFILE.exists():
        print(f"Chrome profile found at: {CHROME_PROFILE}")
        response = input("Do you want to clear it? (y/n): ")
        if response.lower() == 'y':
            try:
                shutil.rmtree(CHROME_PROFILE)
                CHROME_PROFILE.mkdir()
                print("Chrome profile cleared!")
            except Exception as e:
                print(f"Error clearing profile: {e}")
    else:
        CHROME_PROFILE.mkdir(exist_ok=True)
        print("Chrome profile directory created.")

def check_chrome():
    """Check if Chrome is installed"""
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            print(f"Chrome found at: {path}")
            return True
    
    print("Chrome NOT found! Please install Google Chrome.")
    return False

def main():
    print("=" * 50)
    print("  Telecom Alarm Automation - Fix Issues")
    print("=" * 50)
    print()
    
    print("1. Fixing settings file...")
    fix_settings()
    print()
    
    print("2. Checking Chrome installation...")
    check_chrome()
    print()
    
    print("3. Chrome profile...")
    fix_chrome_profile()
    print()
    
    print("=" * 50)
    print("  Done! Try running the application again.")
    print("=" * 50)
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()