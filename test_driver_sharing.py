#!/usr/bin/env python3
"""
Test script to verify driver sharing between browser_manager and portal_handler
"""

import sys
import time
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from browser_manager import browser_manager
    from portal_handler import portal_handler
    from logger_module import logger

    print("Testing driver sharing...")

    # Check if browser_manager has a driver
    bm_driver = browser_manager.get_driver()
    if bm_driver:
        print("✓ browser_manager has driver")
    else:
        print("✗ browser_manager has no driver")

    # Check if portal_handler can get the driver
    ph_driver = portal_handler._get_driver()
    if ph_driver:
        print("✓ portal_handler can access driver")
    else:
        print("✗ portal_handler cannot access driver")

    # Check if they are the same driver
    if bm_driver is ph_driver:
        print("✓ Same driver instance shared between browser_manager and portal_handler")
    else:
        print("✗ Different driver instances")

    print("Driver sharing test completed")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
