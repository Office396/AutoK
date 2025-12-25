#!/usr/bin/env python3
"""
Simple test for WhatsApp message formatting
"""

import sys
sys.path.append('.')

from whatsapp_handler import WhatsAppMessageFormatter
from alarm_processor import AlarmCategory

class MockAlarm:
    def __init__(self, alarm_type, timestamp_str, site_name, mbu, ring_id, b2s_id, category, cell_info=None, raw_data=None):
        self.alarm_type = alarm_type
        self.timestamp_str = timestamp_str
        self.site_name = site_name
        self.mbu = mbu
        self.ftts_ring_id = ring_id
        self.b2s_id = b2s_id
        self.category = category
        self.cell_info = cell_info
        self.raw_data = raw_data or f"{alarm_type}\t{timestamp_str}\t{site_name}"

def test_formatting():
    """Test message formatting"""
    print("Testing WhatsApp Message Formatting")
    print("=" * 50)

    # Test alarms
    alarms = [
        MockAlarm(
            alarm_type="CSL Fault",
            timestamp_str="12-24-2025 02:42:05",
            site_name="RUR5677__S_Padri",
            mbu="C1-LHR-03",
            ring_id="LHR5677",
            b2s_id="EC1-LHR-02599",
            category=AlarmCategory.CSL_FAULT
        ),
        MockAlarm(
            alarm_type="RF Unit Maintenance Link Failure",
            timestamp_str="12-23-2025 23:53:46",
            site_name="LTE_LHR9239__S_BhogiwalGridStation",
            mbu="C1-LHR-04",
            ring_id="LHR70",
            b2s_id="ATLHR142",
            category=AlarmCategory.RF_UNIT
        ),
        MockAlarm(
            alarm_type="Low Voltage",
            timestamp_str="12-23-2025 07:47:26",
            site_name="LTE_LHR6626__S_ChananDinHospital",
            mbu="C1-LHR-05",
            ring_id="LHR122",
            b2s_id="e.coPK015545PU",
            category=AlarmCategory.POWER_ALARM
        ),
        MockAlarm(
            alarm_type="Cell Unavailable",
            timestamp_str="12-23-2025 23:54:23",
            site_name="LTE_LHR9239__S_BhogiwalGridStation",
            mbu="C1-LHR-04",
            ring_id="LHR70",
            b2s_id="ATLHR142",
            category=AlarmCategory.CELL_UNAVAILABLE,
            cell_info="eNodeB Function Name=LTE_LHR9239__S_BhogiwalGridStation, Local Cell ID=23, Cell Name=L2LHR92393A, Cell FDD TDD indication=CELL_FDD"
        )
    ]

    print("\n--- MBU Message Format ---")
    mbu_message = WhatsAppMessageFormatter.format_mbu_alarms(alarms, "Test")
    print(mbu_message)

    print("\n--- B2S Message Format ---")
    b2s_message = WhatsAppMessageFormatter.format_b2s_alarms(alarms)
    print(b2s_message)

    print("\n✓ Formatting test completed")

if __name__ == "__main__":
    test_formatting()
