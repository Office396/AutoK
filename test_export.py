#!/usr/bin/env python3
"""
Test script for portal alarm export functionality
"""

import sys
import os
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from portal_handler import test_export_functionality, test_export_single_portal
from logger_module import logger


def main():
    """Main test function"""
    if len(sys.argv) > 1:
        portal_type = sys.argv[1].lower()
        logger.info(f"Testing export for portal: {portal_type}")
        success = test_export_single_portal(portal_type)
    else:
        logger.info("Testing export functionality for all portals...")
        success = test_export_functionality()

    if success:
        logger.success("Test completed successfully!")
        sys.exit(0)
    else:
        logger.error("Test failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
