"""Verification script to test alarm processing from existing exports"""
import sys
import os
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from alarm_processor import alarm_processor
from logger_module import logger

# Output capture
output = []

def log_print(msg):
    print(msg)
    output.append(msg)

exports_dir = "exports"
files = sorted([f for f in os.listdir(exports_dir) if f.endswith('.xlsx')], 
               key=lambda x: os.path.getctime(os.path.join(exports_dir, x)), reverse=True)

if not files:
    log_print("No files found to verify.")
else:
    # Process top 5 most recent files
    for filename in files[:5]:
        filepath = os.path.join(exports_dir, filename)
        log_print(f"\nProcessing: {filename}")
        log_print("=" * 60)
        
        try:
            alarms = alarm_processor.process_exported_excel(filepath)
            log_print(f"✅ Found {len(alarms)} valid alarms")
            
            if alarms:
                log_print("\nSnapshot of first 5 alarms:")
                for i, alarm in enumerate(alarms[:5]):
                    log_print(f"{i+1}. [{alarm.severity}] {alarm.alarm_type} @ {alarm.site_code} ({alarm.timestamp_str}) {'[TOGGLE]' if alarm.is_toggle else ''}")
            else:
                log_print("❌ No alarms extracted (might be empty or parsing failed)")
                
        except Exception as e:
            log_print(f"❌ Error processing file: {e}")
            import traceback
            traceback.print_exc()

# Write detailed output to file
with open("verification_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("\nVerification results written to verification_results.txt")
