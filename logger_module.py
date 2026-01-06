"""  
Logging Module for Telecom Alarm Automation
Handles all logging functionality with performance tracking
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from contextlib import contextmanager
from config import LOGS_DIR
import threading


class AlarmLogger:
    """Logger for alarm activities with performance monitoring"""
    
    def __init__(self):
        self.log_lock = threading.Lock()
        self._ensure_log_dir()
        self.callbacks = []
        
        # Performance tracking (lightweight)
        self.perf_stats: Dict[str, List[float]] = {}
        self.perf_lock = threading.Lock()
    
    def add_callback(self, callback):
        """Add a callback for new log entries"""
        self.callbacks.append(callback)
    
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

            # Notify callbacks
            for callback in self.callbacks:
                try:
                    callback(log_entry, level)
                except:
                    pass

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
    
    @contextmanager
    def performance_track(self, operation_name: str):
        """Context manager for tracking operation performance"""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start_time
            with self.perf_lock:
                if operation_name not in self.perf_stats:
                    self.perf_stats[operation_name] = []
                self.perf_stats[operation_name].append(elapsed)
                
                # Keep only last 100 measurements per operation
                if len(self.perf_stats[operation_name]) > 100:
                    self.perf_stats[operation_name] = self.perf_stats[operation_name][-100:]
            
            # Log if operation takes longer than 5 seconds
            if elapsed > 5.0:
                self.warning(f"SLOW OPERATION: {operation_name} took {elapsed:.2f}s")
    
    def get_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for all tracked operations"""
        stats = {}
        with self.perf_lock:
            for op_name, measurements in self.perf_stats.items():
                if measurements:
                    stats[op_name] = {
                        'count': len(measurements),
                        'avg_ms': (sum(measurements) / len(measurements)) * 1000,
                        'max_ms': max(measurements) * 1000,
                        'min_ms': min(measurements) * 1000,
                    }
        return stats


# Global logger instance
logger = AlarmLogger()