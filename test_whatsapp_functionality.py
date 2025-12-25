#!/usr/bin/env python3
"""
Test script for WhatsApp functionality
Tests direct group selection and message formatting
"""

import sys
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add current directory to path
sys.path.append('.')

from whatsapp_handler import WhatsAppHandler, WhatsAppMessageFormatter
from alarm_processor import AlarmProcessor, ProcessedAlarm, AlarmCategory
from master_data import master_data
from logger_module import logger


def test_group_finding():
    """Test direct group finding without search bar"""
    print("Testing WhatsApp group finding...")

    try:
        handler = WhatsAppHandler()

        # Test with a known group name - you'll need to replace with actual group name
        test_groups = [
            "Central - 1 O&M",  # Example group name
            "Test Group",       # Another example
        ]

        for group_name in test_groups:
            print(f"Testing group: {group_name}")
            result = handler.find_and_open_group_direct(group_name)
            print(f"Result for {group_name}: {result}")

            if result:
                print(f"✓ Successfully found and opened group: {group_name}")
                break
            else:
                print(f"✗ Could not find group: {group_name}")

        return True

    except Exception as e:
        print(f"Error testing group finding: {e}")
        return False


def test_message_formatting():
    """Test message formatting for different alarm types"""
    print("\nTesting message formatting...")

    try:
        # Load master data
        master_data.load()

        # Create test alarms
        test_alarms = [
            ProcessedAlarm(
                alarm_id="test_csl_1",
                alarm_type="CSL Fault",
                severity="Major",
                timestamp=datetime.now(),
                timestamp_str="12-24-2025 02:42:05",
                site_code="RUR5677",
                site_name="RUR5677__S_Padri",
                site_info=None,
                mbu="C1-LHR-03",
                is_toggle=False,
                is_b2s=True,
                is_omo=False,
                b2s_company="ATL",
                omo_company=None,
                b2s_id="EC1-LHR-02599",
                ftts_ring_id="LHR5677",
                raw_data="CSL Fault\t12-24-2025 02:42:05\tRUR5677__S_Padri",
                category=AlarmCategory.CSL_FAULT,
                cell_info=None
            ),
            ProcessedAlarm(
                alarm_id="test_rf_1",
                alarm_type="RF Unit Maintenance Link Failure",
                severity="Major",
                timestamp=datetime.now(),
                timestamp_str="12-23-2025 23:53:46",
                site_code="LHR9239",
                site_name="LTE_LHR9239__S_BhogiwalGridStation",
                site_info=None,
                mbu="C1-LHR-04",
                is_toggle=False,
                is_b2s=True,
                is_omo=False,
                b2s_company="ATL",
                omo_company=None,
                b2s_id="ATLHR142",
                ftts_ring_id="LHR70",
                raw_data="RF Unit Maintenance Link Failure\t12-23-2025 23:53:46\tLTE_LHR9239__S_BhogiwalGridStation",
                category=AlarmCategory.RF_UNIT,
                cell_info=None
            ),
            ProcessedAlarm(
                alarm_id="test_power_1",
                alarm_type="Low Voltage",
                severity="Major",
                timestamp=datetime.now(),
                timestamp_str="12-23-2025 07:47:26",
                site_code="LHR6626",
                site_name="LTE_LHR6626__S_ChananDinHospital",
                site_info=None,
                mbu="C1-LHR-05",
                is_toggle=False,
                is_b2s=True,
                is_omo=False,
                b2s_company="e.co",
                omo_company=None,
                b2s_id="e.coPK015545PU",
                ftts_ring_id="LHR122",
                raw_data="Low Voltage\t12-23-2025 07:47:26\tLTE_LHR6626__S_ChananDinHospital",
                category=AlarmCategory.POWER_ALARM,
                cell_info=None
            ),
            ProcessedAlarm(
                alarm_id="test_cell_1",
                alarm_type="Cell Unavailable",
                severity="Critical",
                timestamp=datetime.now(),
                timestamp_str="12-23-2025 23:54:23",
                site_code="LHR9239",
                site_name="LTE_LHR9239__S_BhogiwalGridStation",
                site_info=None,
                mbu="C1-LHR-04",
                is_toggle=False,
                is_b2s=True,
                is_omo=False,
                b2s_company="ATL",
                omo_company=None,
                b2s_id="ATLHR142",
                ftts_ring_id="LHR70",
                raw_data="Cell Unavailable\teNodeB Function Name=LTE_LHR9239__S_BhogiwalGridStation, Local Cell ID=23, Cell Name=L2LHR92393A, Cell FDD TDD indication=CELL_FDD",
                category=AlarmCategory.CELL_UNAVAILABLE,
                cell_info="eNodeB Function Name=LTE_LHR9239__S_BhogiwalGridStation, Local Cell ID=23, Cell Name=L2LHR92393A, Cell FDD TDD indication=CELL_FDD"
            )
        ]

        # Test MBU formatting
        print("\n--- MBU Message Formatting ---")
        mbu_message = WhatsAppMessageFormatter.format_mbu_alarms(test_alarms, "Mixed")
        print("MBU format:")
        print(mbu_message)

        # Test B2S formatting
        print("\n--- B2S Message Formatting ---")
        b2s_message = WhatsAppMessageFormatter.format_b2s_alarms(test_alarms)
        print("B2S format:")
        print(b2s_message)

        print("✓ Message formatting tests completed")
        return True

    except Exception as e:
        print(f"Error testing message formatting: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_connection():
    """Test WhatsApp connection"""
    print("\nTesting WhatsApp connection...")

    try:
        handler = WhatsAppHandler()
        status = handler.check_connection()
        print(f"Connection status: {status}")

        if status == handler.WhatsAppStatus.CONNECTED:
            print("✓ WhatsApp is connected")
            return True
        else:
            print(f"✗ WhatsApp status: {status}")
            return False

    except Exception as e:
        print(f"Error testing connection: {e}")
        return False


def main():
    """Run all tests"""
    print("WhatsApp Functionality Test")
    print("=" * 40)

    results = []

    # Test message formatting first (doesn't require browser)
    results.append(("Message Formatting", test_message_formatting()))

    # Test connection
    results.append(("WhatsApp Connection", test_connection()))

    # Test group finding (requires browser to be running)
    results.append(("Group Finding", test_group_finding()))

    # Summary
    print("\n" + "=" * 40)
    print("TEST RESULTS:")
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print("15")

    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
