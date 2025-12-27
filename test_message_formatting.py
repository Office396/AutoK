#!/usr/bin/env python3
"""
Test WhatsApp message formatting
"""

import sys
sys.path.append('.')

from whatsapp_handler import WhatsAppMessageFormatter
from alarm_processor import ProcessedAlarm, AlarmCategory
from datetime import datetime


class MockAlarm:
    def __init__(self, alarm_type, timestamp_str, site_name, category, mbu=None, ring_id=None, b2s_id=None, raw_data=None, cell_info=None):
        self.alarm_type = alarm_type
        self.timestamp_str = timestamp_str
        self.site_name = site_name
        self.category = category
        self.mbu = mbu
        self.ftts_ring_id = ring_id
        self.b2s_id = b2s_id
        self.raw_data = raw_data
        self.cell_info = cell_info


def test_formatting():
    print("Testing WhatsApp Message Formatting")
    print("=" * 50)

    # Test MBU formatting
    print("\n--- MBU Message Format ---")
    mbu_alarms = [
        MockAlarm("Low Voltage", "12-23-2025 07:47:26", "LTE_LHR6626__S_ChananDinHospital", AlarmCategory.POWER_ALARM),
        MockAlarm("System on Battery", "12-23-2025 07:47:26", "LTE_LHR6626__S_ChananDinHospital", AlarmCategory.POWER_ALARM),
    ]
    mbu_message = WhatsAppMessageFormatter.format_mbu_alarms(mbu_alarms, "Low Voltage")
    print("MBU Message:")
    print(mbu_message)

    # Test B2S formatting
    print("\n--- B2S Message Format ---")
    b2s_alarms = [
        MockAlarm("Low Voltage", "12-23-2025 07:47:26", "LTE_LHR6626__S_ChananDinHospital",
                 AlarmCategory.POWER_ALARM, mbu="C1-LHR-05", ring_id="LHR122", b2s_id="e.coPK015545PU"),
    ]
    b2s_message = WhatsAppMessageFormatter.format_b2s_alarms(b2s_alarms)
    print("B2S Message:")
    print(b2s_message)

    # Test OMO formatting (should be same as B2S)
    print("\n--- OMO Message Format ---")
    omo_message = WhatsAppMessageFormatter.format_omo_alarms(b2s_alarms)
    print("OMO Message:")
    print(omo_message)

    print("\n" + "=" * 50)
    print("✅ Formatting test completed!")


if __name__ == "__main__":
    test_formatting()

