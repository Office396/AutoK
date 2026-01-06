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
        self.seen_alarms_timestamps: Dict[str, datetime] = {}  # Track when alarms were seen
        self.alarm_callbacks: List[Callable] = []
        self.status_callbacks: List[Callable] = []
        self.lock = threading.Lock()
        
        # Track last scan sites for Instant Alarms
        # Format: {alarm_type: {(site_code, timestamp), ...}}
        self.last_scan_sites: Dict[str, Set[tuple]] = defaultdict(set)
        # Track alarms triggered for MBU in current cycle to prevent double triggering
        self._cycle_handled_mbu_entries: Set[tuple] = set()
        self._cycle_handled_b2s_triggers: Set[tuple] = set()
        self._first_scan_done = False
        
        # Performance: TTL for seen alarms (24 hours)
        self.seen_alarms_ttl_hours = 24
        self._last_cleanup_time = datetime.now()
    
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
    
    def _process_instant_alarms(self, alarms: List[ProcessedAlarm], is_end_of_cycle: bool = False):
        """
        Process instant alarms.
        
        Args:
            alarms: List of alarms to check for instant triggers
            is_end_of_cycle: If True, performs cleanup of history and triggers B2S logic (global)
        """
        try:
            instant_types = [t.strip().lower() for t in settings.instant_alarms]
            new_instant_mbus = set() # (alarm_type, mbu)
            
            # 1. Check for NEW alarms and trigger sends
            for alarm in alarms:
                atype_lower = alarm.alarm_type.lower()
                if atype_lower in instant_types:
                    entry = (alarm.site_code, alarm.timestamp_str)
                    
                    # 2. If first scan, allow all current alarms to be processed as "new"
                    if not self._first_scan_done:
                        logger.info("First scan processing. All current instant alarms will trigger initial notifications.")
                        self._first_scan_done = True
                        # No return here - let it flow to Step 3 where it compares with empty history
                    
                    # 3. Compare with history to find NEW entries
                    if entry not in self.last_scan_sites[atype_lower]:
                        # It's new compared to history!
                        
                        # MBU Logic: Check if we already handled this MBU trigger THIS cycle
                        # We use _cycle_handled_mbu_entries to avoid re-triggering MBU send 
                        # when we re-process the same new alarm at end of cycle.
                        if entry not in self._cycle_handled_mbu_entries:
                            # Not handled this cycle yet -> Trigger MBU send
                            if alarm.mbu:
                                logger.info(f"INSTANT ALARM: New/updated site {alarm.site_code} ({alarm.timestamp_str}) found for {alarm.alarm_type} in {alarm.mbu}")
                                new_instant_mbus.add((atype_lower, alarm.mbu))
                                self._cycle_handled_mbu_entries.add(entry)
                        
                        if alarm.is_b2s and alarm.b2s_company:
                            key = (atype_lower, alarm.b2s_company)
                            if key not in self._cycle_handled_b2s_triggers:
                                new_instant_mbus.add(("B2S", atype_lower, alarm.b2s_company))
                                self._cycle_handled_b2s_triggers.add(key)

            # 4. Trigger Sending
            if new_instant_mbus:
                from whatsapp_handler import ordered_sender, whatsapp_handler, message_formatter
                
                # Separate MBU and B2S triggers
                mbu_triggers = set()
                b2s_triggers = set()
                
                for item in new_instant_mbus:
                    if len(item) == 3 and item[0] == "B2S":
                        b2s_triggers.add((item[1], item[2])) # (itype, b2s_company)
                    else:
                        mbu_triggers.add(item) # (itype, mbu)
                
                # Process MBU Triggers (Usually Immediate)
                for atype_lower, mbu in mbu_triggers:
                    # Find ALL active alarms for this MBU and Type (Old + New)
                    mbu_atype_alarms = [
                        a for a in alarms 
                        if a.alarm_type.lower() == atype_lower and a.mbu == mbu
                    ]
                    
                    if mbu_atype_alarms:
                        logger.info(f"Triggering immediate MBU send for {mbu} | {atype_lower} | Count: {len(mbu_atype_alarms)}")
                        # Use mbu_only=True to prevent double sending of B2S/OMO alarms that might be in this list
                        ordered_sender.send_all_ordered(mbu_atype_alarms, mbu_only=True)
                
                # Process B2S Triggers (Only at End of Cycle)
                for atype_lower, b2s_company in b2s_triggers:
                    # Find ALL active alarms for this B2S Company and Type - ACROSS ALL MBUs
                    b2s_atype_alarms = [
                        a for a in alarms 
                        if a.alarm_type.lower() == atype_lower 
                        and a.is_b2s 
                        and a.b2s_company == b2s_company
                    ]
                    
                    if b2s_atype_alarms:
                        group_name = settings.get_b2s_group_name(b2s_company)
                        if group_name:
                            logger.info(f"Triggering immediate B2S send for {b2s_company} | {atype_lower} | Count: {len(b2s_atype_alarms)}")
                            message = message_formatter.format_b2s_alarms(b2s_atype_alarms)
                            if message.strip():
                                # Priority: 1 for instant alarms (like CSL), 2 for others.
                                priority = 1 if atype_lower in instant_types else 2
                                whatsapp_handler.queue_message(group_name, message, atype_lower, priority)

            # 5. Cleanup History (Only at End of Cycle)
            if is_end_of_cycle:
                # 'alarms' here should contain ALL alarms from ALL portals (cycle_alarms)
                current_cycle_entries = defaultdict(set)
                for alarm in alarms:
                    atype_lower = alarm.alarm_type.lower()
                    if atype_lower in instant_types:
                        current_cycle_entries[atype_lower].add((alarm.site_code, alarm.timestamp_str))
                
                # Replace history with current cycle state
                for itype in instant_types:
                    self.last_scan_sites[itype] = current_cycle_entries.get(itype, set())
                
                # Reset cycle tracker for next cycle
                self._cycle_handled_mbu_entries.clear()
                self._cycle_handled_b2s_triggers.clear()
                
                logger.info("Instant Alarm History updated/cleaned for next cycle")
                
        except Exception as e:
            logger.error(f"Error in _process_instant_alarms: {e}")
            import traceback
            traceback.print_exc()

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
                cycle_alarms = [] # For instant logic
                cycle_success = True # Track if all checks were successful
                
                # Clear MBU tracker at start of cycle
                self._cycle_handled_mbu_entries.clear()
                
                logger.info(f"Starting portal check cycle...")
                
                for portal in portals_to_check:
                    if not self.running:
                        break
                    
                    logger.info(f"Checking portal: {portal.value}")
                    current_alarms, new_alarms = self._check_portal(portal)
                    
                    if current_alarms is None:
                        logger.error(f"Check failed for {portal.value}. Marking cycle as incomplete.")
                        cycle_success = False
                        continue
                    
                    if current_alarms:
                        count = len(current_alarms)
                        all_new_alarms.extend(new_alarms) # Track new for total stats
                        cycle_alarms.extend(current_alarms) # Collect for instant logic
                        logger.info(f"Found {count} alarms from {portal.value} ({len(new_alarms)} new)")
                        
                        # Process and notify immediately for this portal
                        if new_alarms:
                            alarm_scheduler.add_alarms(new_alarms)
                        
                        # --- Trigger Instant Alarms IMMEDIATELY ---
                        # Use ONLY the current portal snapshot to avoid including stale sites
                        # This ensures the MBU/B2S messages reflect the latest terminal view
                        snapshot_alarms = list({a.alarm_id: a for a in current_alarms}.values())
                        self._process_instant_alarms(snapshot_alarms, is_end_of_cycle=False)
                        # ------------------------------------------
                        
                        # Update GUI with ALL current alarms (snapshot view)
                        self._notify_alarms(current_alarms, source=portal.value)
                    elif new_alarms: # Should not happen if current is empty but just in case
                         all_new_alarms.extend(new_alarms)

                # --- Instant Alarm Cleanup (End of Cycle) ---
                if self.running and cycle_success:
                    # Deduplicate cycle_alarms based on alarm_id to prevent double processing
                    # Use a dictionary to keep unique alarms
                    unique_cycle_alarms = list({a.alarm_id: a for a in cycle_alarms}.values())
                    
                    # Only clean history if the cycle was fully successful
                    # If we missed a tab (e.g. CSL failed), we shouldn't assume CSL faults are gone
                    self._process_instant_alarms(unique_cycle_alarms, is_end_of_cycle=True)
                # -----------------------------------------------
                
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
        exported_file = None
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
                return None, None
            
            logger.success(f"Export completed: {exported_file}")
            
            # Process the exported Excel file
            processed_alarms = alarm_processor.process_exported_excel(exported_file)
            
            logger.info(f"Processed {len(processed_alarms)} alarms from {portal.value}")
            
            # Filter out ignored sites
            ignored_sites = [s.upper() for s in settings.ignored_sites]
            if ignored_sites:
                before_count = len(processed_alarms)
                processed_alarms = [a for a in processed_alarms if a.site_code.upper() not in ignored_sites]
                filtered_count = before_count - len(processed_alarms)
                if filtered_count > 0:
                    logger.info(f"Filtered out {filtered_count} alarms from ignored sites")
            
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
            return None, None
        finally:
            # CRITICAL: Clean up the exported file to prevent disk/memory bloat
            if exported_file and os.path.exists(exported_file):
                try:
                    os.remove(exported_file)
                    logger.debug(f"Cleaned up export file: {exported_file}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup export file {exported_file}: {cleanup_error}")
    
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
        """Mark alarm as seen with timestamp for TTL-based cleanup"""
        current_time = datetime.now()
        with self.lock:
            self.seen_alarms.add(alarm.alarm_id)
            self.seen_alarms_timestamps[alarm.alarm_id] = current_time
            
            # Perform cleanup every hour to avoid frequent operations
            if (current_time - self._last_cleanup_time).total_seconds() > 3600:
                self._cleanup_old_seen_alarms(current_time)
                self._last_cleanup_time = current_time
    
    def _cleanup_old_seen_alarms(self, current_time: datetime):
        """Remove seen alarms older than TTL (called while holding lock)"""
        cutoff_time = current_time - timedelta(hours=self.seen_alarms_ttl_hours)
        
        # Find expired alarm IDs
        expired_ids = [
            alarm_id for alarm_id, timestamp in self.seen_alarms_timestamps.items()
            if timestamp < cutoff_time
        ]
        
        # Remove expired alarms
        for alarm_id in expired_ids:
            self.seen_alarms.discard(alarm_id)
            self.seen_alarms_timestamps.pop(alarm_id, None)
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired seen alarms (older than {self.seen_alarms_ttl_hours}h)")
    
    def force_check(self) -> List[ProcessedAlarm]:
        all_alarms = []
        for portal in [TabType.CSL_FAULT, TabType.ALL_ALARMS, TabType.RF_UNIT, TabType.NODEB_CELL]:
            alarms, _ = self._check_portal(portal)
            if alarms:
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
