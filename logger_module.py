"""
Logging Module for Telecom Alarm Automation
Handles all logging functionality
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from config import LOGS_DIR
import threading


class AlarmLogger:
    """Logger for alarm activities"""
    
    def __init__(self):
        self.log_lock = threading.Lock()
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """Ensure logs directory exists"""
        LOGS_DIR.mkdir(exist_ok=True)
    
    def _get_log_file(self) -> Path:
        """Get current log file path"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return LOGS_DIR / f"alarm_log_{date_str}.txt"

    def log(self, message: str, level: str = "INFO"):
        """Log a message"""
        with self.log_lock:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [{level}] {message}"

            # Write to file
            try:
                with open(self._get_log_file(), 'a', encoding='utf-8') as f:
                    f.write(log_entry + "\n")
            except Exception as e:
                print(f"Error writing log: {e}")

            # Also print to console
            print(log_entry)

    def info(self, message: str):
        """Log info message"""
        self.log(message, "INFO")

    def error(self, message: str):
        """Log error message"""
        self.log(message, "ERROR")

    def warning(self, message: str):
        """Log warning message"""
        self.log(message, "WARNING")

    def success(self, message: str):
        """Log success message"""
        self.log(message, "SUCCESS")
    
    def debug(self, message: str):
        """Log debug message (only to file, not console to avoid spam)"""
        with self.log_lock:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [DEBUG] {message}"
            try:
                with open(self._get_log_file(), 'a', encoding='utf-8') as f:
                    f.write(log_entry + "\n")
            except:
                pass

    def alarm_sent(self, alarm_type: str, site_code: str, mbu: str, group: str):
        """Log alarm sent"""
        self.log(f"SENT: {alarm_type} | Site: {site_code} | MBU: {mbu} | Group: {group}", "ALARM")

    def alarm_batch_sent(self, alarm_type: str, count: int, group: str):
        """Log batch alarm sent"""
        self.log(f"BATCH SENT: {alarm_type} | Count: {count} | Group: {group}", "ALARM")

    def get_today_logs(self) -> List[str]:
        """Get today's log entries"""
        log_file = self._get_log_file()
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    return f.readlines()
            except:
                return []
        return []

    def get_recent_logs(self, count: int = 100) -> List[str]:
        """Get recent log entries"""
        logs = self.get_today_logs()
        return logs[-count:] if len(logs) > count else logs


# Global logger instance
logger = AlarmLogger()