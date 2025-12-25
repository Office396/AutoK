#!/usr/bin/env python3
"""
Debug message formatting
"""

import sys
sys.path.append('.')

from alarm_processor import alarm_processor, ProcessedAlarm, AlarmCategory
from whatsapp_handler import WhatsAppMessageFormatter
from datetime import datetime


def test_message_formatting():
    """Test what messages are being generated"""

    # Create a test alarm
    test_alarm = ProcessedAlarm(
        alarm_id="test_123",
        alarm_type="Low Voltage",
        severity="Major",
        timestamp=datetime.now(),
        timestamp_str="12-25-2025 04:14:13",
        site_code="LHR1234",
        site_name="LTE_LHR1234__S_TestSite",
        site_info=None,
        mbu="C1-LHR-01",
        is_toggle=False,
        is_b2s=False,
        is_omo=False,
        b2s_company=None,
        omo_company=None,
        b2s_id=None,
        ftts_ring_id=None,
        raw_data="Major\tLow Voltage\t12-25-2025 04:14:13\tLTE_LHR1234__S_TestSite",
        category=AlarmCategory.POWER_ALARM,  # This should format as POWER_ALARM
        cell_info=None
    )

    print("Test Alarm:")
    print(f"  Type: {test_alarm.alarm_type}")
    print(f"  Category: {test_alarm.category}")
    print(f"  Site: {test_alarm.site_name}")
    print(f"  Timestamp: {test_alarm.timestamp_str}")
    print()

    # Test MBU formatting
    mbu_message = WhatsAppMessageFormatter.format_mbu_alarms([test_alarm], "Low Voltage")
    print("MBU Message:")
    print(f"  Length: {len(mbu_message)}")
    print(f"  Content: '{mbu_message}'")
    print()

    # Test toggle formatting
    test_alarm.is_toggle = True
    toggle_message = WhatsAppMessageFormatter.format_toggle_alarms([test_alarm])
    print("Toggle Message:")
    print(f"  Length: {len(toggle_message)}")
    print(f"  Content: '{toggle_message}'")
    print()

    # Test with different categories
    test_alarm.is_toggle = False

    for category in [AlarmCategory.CSL_FAULT, AlarmCategory.RF_UNIT, AlarmCategory.CELL_UNAVAILABLE, AlarmCategory.POWER_ALARM, AlarmCategory.OTHER]:
        test_alarm.category = category
        test_alarm.alarm_type = {
            AlarmCategory.CSL_FAULT: "CSL Fault",
            AlarmCategory.RF_UNIT: "RF Unit Maintenance Link Failure",
            AlarmCategory.CELL_UNAVAILABLE: "Cell Unavailable",
            AlarmCategory.POWER_ALARM: "Low Voltage",
            AlarmCategory.OTHER: "Unknown Alarm"
        }[category]

        message = WhatsAppMessageFormatter.format_mbu_alarms([test_alarm], test_alarm.alarm_type)
        print(f"{category.name}: '{message}'")

    # Test B2S format
    test_alarm.category = AlarmCategory.CSL_FAULT
    test_alarm.alarm_type = "CSL Fault"
    test_alarm.b2s_id = "e.coPK000506PU"
    b2s_message = WhatsAppMessageFormatter.format_b2s_alarms([test_alarm])
    print(f"B2S Message: '{b2s_message}'")


if __name__ == "__main__":
    test_message_formatting()
