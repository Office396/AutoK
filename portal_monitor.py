"""
Portal Monitor
Monitors Huawei MAE Portal for alarms using EXPORT functionality.
Uses the built-in export feature to get all alarms without scrolling limitations.
"""

import time
import threading
import inspect
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib
import os

from browser_manager import browser_manager, TabType
from alarm_processor import alarm_processor, ProcessedAlarm
from alarm_scheduler import alarm_scheduler
from site_code_extractor import SiteCodeExtractor
from master_data import master_data
from config import settings, AlarmTypes
from logger_module import logger
from portal_handler import portal_handler, PortalType


@dataclass
class MonitorStats:
    """Monitoring statistics"""
    total_checks: int = 0
    total_alarms_found: int = 0
    total_alarms_processed: int = 0
    last_check_time: Optional[datetime] = None
    alarms_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    alarms_by_mbu: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class PortalMonitor:
    """
    Monitors portal tabs for new alarms.
    Handles Huawei MAE Portal with fm_virtual_scrollbar mechanism.
    """
    
    def __init__(self):
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stats = MonitorStats()
        self.seen_alarms: Set[str] = set()
        self.alarm_callbacks: List[Callable] = []
        self.status_callbacks: List[Callable] = []
        self.lock = threading.Lock()
    
    def add_alarm_callback(self, callback: Callable):
        self.alarm_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable):
        self.status_callbacks.append(callback)
    
    def _notify_alarms(self, alarms: List[ProcessedAlarm], source: str = None):
        """Notify listeners of new alarms"""
        for callback in self.alarm_callbacks:
            try:
                # Handle callbacks that support source argument
                sig = inspect.signature(callback)
                if 'source' in sig.parameters:
                    callback(alarms, source=source)
                else:
                    callback(alarms)
            except Exception as e:
                logger.error(f"Error in alarm callback: {e}") 
    
    def _notify_status(self):
        for callback in self.status_callbacks:
            try:
                callback(self.stats)
            except:
                pass
    
    def start(self, check_interval: int = None):
        if self.running:
            return
        
        interval = check_interval or settings.check_interval_seconds
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Portal monitor started (interval: {interval}s)")
    
    def stop(self):
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logger.info("Portal monitor stopped")
    
    def _monitor_loop(self, interval: int):
        """Main monitoring loop"""
        portals_to_check = [
            TabType.CSL_FAULT,
            TabType.ALL_ALARMS,
            TabType.RF_UNIT,
            TabType.NODEB_CELL,
        ]
        
        while self.running:
            try:
                # No pause needed with dual browsers!
                # if whatsapp_handler.sending_active: ...
                
                all_new_alarms = []
                
                logger.info(f"Starting portal check cycle...")
                
                for portal in portals_to_check:
                    if not self.running:
                        break
                    
                    logger.info(f"Checking portal: {portal.value}")
                    current_alarms, new_alarms = self._check_portal(portal)
                    
                    if current_alarms:
                        count = len(current_alarms)
                        all_new_alarms.extend(new_alarms) # Track new for total stats
                        logger.info(f"Found {count} alarms from {portal.value} ({len(new_alarms)} new)")
                        
                        # Process and notify immediately for this portal
                        if new_alarms:
                            alarm_scheduler.add_alarms(new_alarms)
                        
                        # Update GUI with ALL current alarms (snapshot view)
                        self._notify_alarms(current_alarms, source=portal.value)
                
                self.stats.total_checks += 1
                self.stats.last_check_time = datetime.now()
                
                if all_new_alarms:
                    self.stats.total_alarms_processed += len(all_new_alarms)
                    logger.info(f"Total new alarms this cycle: {len(all_new_alarms)}")
                else:
                    logger.info("No new alarms found this cycle")
                
                self._notify_status()
                
                logger.info(f"Waiting {interval}s for next check...")
                self._interruptible_sleep(interval)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
    
    def _interruptible_sleep(self, seconds: int):
        for _ in range(seconds):
            if not self.running:
                break
            time.sleep(1)
    
    def _check_portal(self, portal: TabType) -> List[ProcessedAlarm]:
        """Check a specific portal for new alarms using export functionality"""
        try:
            # Map TabType to PortalType
            portal_type_map = {
                TabType.ALL_ALARMS: PortalType.ALL_ALARMS,
                TabType.CSL_FAULT: PortalType.CSL_FAULT,
                TabType.RF_UNIT: PortalType.RF_UNIT,
                TabType.NODEB_CELL: PortalType.NODEB_CELL,
            }

            portal_type = portal_type_map.get(portal)
            if not portal_type:
                logger.error(f"No mapping for portal {portal.value}")
                return [], []
            
            logger.info(f"Exporting alarms from {portal.value}...")

            # Export alarms to Excel file
            exported_file = portal_handler.export_alarms(portal_type)

            if not exported_file or not os.path.exists(exported_file):
                logger.error(f"Export failed for {portal.value}")
                return [], []
            
            logger.success(f"Export completed: {exported_file}")
            
            # Process the exported Excel file
            processed_alarms = alarm_processor.process_exported_excel(exported_file)
            
            logger.info(f"Processed {len(processed_alarms)} alarms from {portal.value}")
            
            self.stats.total_alarms_found += len(processed_alarms)
            
            # Filter for new alarms only (for scheduler) - but still return ALL for display
            new_alarms = []
            for alarm in processed_alarms:
                if self._is_new_alarm(alarm):
                    new_alarms.append(alarm)
                    self._mark_alarm_seen(alarm)
                    
                    self.stats.alarms_by_type[alarm.alarm_type] += 1
                    if alarm.mbu:
                        self.stats.alarms_by_mbu[alarm.mbu] += 1
            
            # Return BOTH all current alarms (for GUI display) and true new alarms (for scheduler)
            return processed_alarms, new_alarms
            
        except Exception as e:
            logger.error(f"Error checking portal {portal.value}: {e}")
            import traceback
            traceback.print_exc()
            return [], []
    
    def clear_seen_alarms(self):
        """Clear the seen alarms cache - useful for testing or fresh start"""
        with self.lock:
            count = len(self.seen_alarms)
            self.seen_alarms.clear()
            logger.info(f"Cleared {count} seen alarms from cache")
    
    # Removed _extract_all_alarms method - now using export functionality
    
    # Export functionality replaces all old scrolling and table extraction methods
    
    def _create_alarm_id(self, alarm_type: str, site_code: str, timestamp: str) -> str:
        raw = f"{alarm_type}_{site_code}_{timestamp}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        formats = [
            "%m-%d-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str.strip(), fmt)
            except:
                continue
        return datetime.now()
    
    def _is_new_alarm(self, alarm: ProcessedAlarm) -> bool:
        return alarm.alarm_id not in self.seen_alarms
    
    def _mark_alarm_seen(self, alarm: ProcessedAlarm):
        with self.lock:
            self.seen_alarms.add(alarm.alarm_id)
            if len(self.seen_alarms) > 10000:
                self.seen_alarms = set(list(self.seen_alarms)[5000:])
    
    def force_check(self) -> List[ProcessedAlarm]:
        all_alarms = []
        for portal in [TabType.CSL_FAULT, TabType.ALL_ALARMS, TabType.RF_UNIT, TabType.NODEB_CELL]:
            alarms, _ = self._check_portal(portal)
            all_alarms.extend(alarms)
        return all_alarms
    
    def get_stats(self) -> MonitorStats:
        return self.stats
    
    def reset_seen_alarms(self):
        with self.lock:
            self.seen_alarms.clear()
    
    def clear_stats(self):
        self.stats = MonitorStats()


# Global instance
portal_monitor = PortalMonitor()