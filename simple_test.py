#!/usr/bin/env python3
"""
Simple test to verify the alarm processing functionality
"""

import os
import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from alarm_processor import alarm_processor
    from master_data import master_data
    print("✓ Successfully imported alarm_processor and master_data")

    # Load master data
    if master_data.load():
        print(f"✓ Loaded master data with {master_data.site_count} sites")
    else:
        print("✗ Failed to load master data")

    # Test processing a sample Excel file if it exists
    exports_dir = Path("exports")
    if exports_dir.exists():
        excel_files = list(exports_dir.glob("*.xlsx"))
        if excel_files:
            test_file = excel_files[0]
            print(f"Testing with file: {test_file}")
            try:
                alarms = alarm_processor.process_exported_excel(str(test_file))
                print(f"✓ Successfully processed {len(alarms)} alarms from Excel file")
            except Exception as e:
                print(f"✗ Error processing Excel file: {e}")
        else:
            print("No Excel files found in exports directory")
    else:
        print("Exports directory not found")

except ImportError as e:
    print(f"✗ Import error: {e}")
except Exception as e:
    print(f"✗ Unexpected error: {e}")
