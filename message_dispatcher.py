"""
Message Dispatcher
Coordinates sending alarm messages to appropriate WhatsApp groups
"""

import threading
from datetime import datetime
from typing import List, Dict, Optional, Callable
from collections import defaultdict
from dataclasses import dataclass, field

from alarm_processor import ProcessedAlarm, AlarmBatch, alarm_processor
from whatsapp_handler import whatsapp_handler, message_formatter
from config import settings
from logger_module import logger


@dataclass
class DispatchStats:
    """Statistics for message dispatching"""
    total_dispatched: int = 0
    by_mbu: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_alarm_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_group_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_dispatch_time: Optional[datetime] = None


class MessageDispatcher:
    """
    Coordinates sending alarm batches to appropriate WhatsApp groups
    """
    
    def __init__(self):
        self.stats = DispatchStats()
        self.lock = threading.Lock()
        self.dispatch_callbacks: List[Callable] = []
    
    def add_dispatch_callback(self, callback: Callable):
        """Add callback for dispatch events"""
        self.dispatch_callbacks.append(callback)
    
    def _notify_dispatch(self, group_name: str, alarm_type: str, count: int):
        """Notify dispatch callbacks - FIXED to prevent blocking"""
        import tkinter as tk
        for callback in self.dispatch_callbacks:
            try:
                # Check if this is a GUI callback that needs to be scheduled on the main thread
                if hasattr(callback, '__self__') and isinstance(callback.__self__, tk.Widget):
                    # Schedule GUI updates to run on the main thread
                    try:
                        callback.__self__.after(0, lambda: callback(group_name, alarm_type, count))
                    except:
                        pass
                else:
                    callback(group_name, alarm_type, count)
            except:
                pass
    
    def dispatch_alarms(self, alarms: List[ProcessedAlarm]):
        """
        Dispatch alarms to appropriate WhatsApp groups
        
        Args:
            alarms: List of processed alarms to dispatch
        """
        if not alarms:
            return
        
        with self.lock:
            # Use OrderedAlarmSender to maintain consistency across the app
            from whatsapp_handler import OrderedAlarmSender
            OrderedAlarmSender.send_all_ordered(alarms)
            
            self.stats.last_dispatch_time = datetime.now()
            # Stats update is handled inside OrderedAlarmSender indirectly? 
            # No, I should probably update stats here too for the GUI
            for a in alarms:
                group_type = "MBU" if a.mbu else ("B2S" if a.is_b2s else "OMO")
                target = a.mbu or a.b2s_company or a.omo_company or "Unknown"
                self._update_stats(target, a.alarm_type, group_type, 1)
    
    def _dispatch_mbu_alarms(self, mbu_groups: Dict[str, Dict[str, AlarmBatch]]):
        """Dispatch alarms to MBU groups"""
        for mbu, type_batches in mbu_groups.items():
            for alarm_type, batch in type_batches.items():
                if batch is None:
                    continue
                
                group_name = batch.group_name
                
                # Send regular alarms
                if batch.alarms:
                    message = message_formatter.format_mbu_alarms(batch.alarms, alarm_type)
                    if message:
                        priority = 1 if "csl" in alarm_type.lower() else 2
                        whatsapp_handler.queue_message(group_name, message, alarm_type, priority)
                        
                        self._update_stats(mbu, alarm_type, "MBU", len(batch.alarms))
                        self._notify_dispatch(group_name, alarm_type, len(batch.alarms))
                        
                        logger.info(f"Dispatched {len(batch.alarms)} {alarm_type} alarms to {group_name}")
                
                # Send toggle alarms (if not skipped for this MBU)
                if batch.toggle_alarms and not alarm_processor.should_skip_toggle_for_mbu(mbu):
                    toggle_message = message_formatter.format_toggle_alarms(batch.toggle_alarms)
                    if toggle_message:
                        whatsapp_handler.queue_message(
                            group_name, 
                            toggle_message, 
                            f"{alarm_type} (Toggle)",
                            priority=2
                        )
                        
                        self._update_stats(mbu, f"{alarm_type} (Toggle)", "MBU", len(batch.toggle_alarms))
                        logger.info(f"Dispatched {len(batch.toggle_alarms)} toggle {alarm_type} alarms to {group_name}")
    
    def _dispatch_b2s_alarms(self, b2s_groups: Dict[str, Dict[str, AlarmBatch]]):
        """Dispatch alarms to B2S groups"""
        for company, type_batches in b2s_groups.items():
            for alarm_type, batch in type_batches.items():
                if batch is None or not batch.alarms:
                    continue
                
                group_name = batch.group_name
                message = message_formatter.format_b2s_alarms(batch.alarms)
                
                if message:
                    whatsapp_handler.queue_message(group_name, message, alarm_type, priority=2)
                    
                    self._update_stats(company, alarm_type, "B2S", len(batch.alarms))
                    self._notify_dispatch(group_name, alarm_type, len(batch.alarms))
                    
                    logger.info(f"Dispatched {len(batch.alarms)} {alarm_type} alarms to B2S group {group_name}")
    
    def _dispatch_omo_alarms(self, omo_groups: Dict[str, Dict[str, AlarmBatch]]):
        """Dispatch alarms to OMO groups"""
        for company, type_batches in omo_groups.items():
            for alarm_type, batch in type_batches.items():
                if batch is None or not batch.alarms:
                    continue
                
                group_name = batch.group_name
                message = message_formatter.format_omo_alarms(batch.alarms)
                
                if message:
                    whatsapp_handler.queue_message(group_name, message, alarm_type, priority=2)
                    
                    self._update_stats(company, alarm_type, "OMO", len(batch.alarms))
                    self._notify_dispatch(group_name, alarm_type, len(batch.alarms))
                    
                    logger.info(f"Dispatched {len(batch.alarms)} {alarm_type} alarms to OMO group {group_name}")
    
    def _update_stats(self, mbu_or_company: str, alarm_type: str, group_type: str, count: int):
        """Update dispatch statistics"""
        self.stats.total_dispatched += count
        self.stats.by_mbu[mbu_or_company] += count
        self.stats.by_alarm_type[alarm_type] += count
        self.stats.by_group_type[group_type] += count
    
    def dispatch_csl_fault_realtime(self, alarm: ProcessedAlarm):
        """
        Dispatch CSL Fault alarm in real-time
        
        For CSL Fault, we need to send all current CSL alarms for the MBU
        """
        try:
            # Get all sites to send for this CSL fault
            send_list = alarm_processor.process_csl_fault(alarm)
            
            for group_name, group_type, alarms in send_list:
                if not alarms:
                    continue
                
                if group_type == "MBU":
                    message = message_formatter.format_csl_fault(alarms)
                else:
                    message = message_formatter.format_b2s_alarms(alarms)
                
                if message:
                    whatsapp_handler.queue_message(group_name, message, "CSL Fault", priority=1)
                    
                    self._update_stats(alarm.mbu, "CSL Fault", group_type, len(alarms))
                    self._notify_dispatch(group_name, "CSL Fault", len(alarms))
                    
                    logger.info(f"Dispatched CSL Fault ({len(alarms)} sites) to {group_name}")
                    
        except Exception as e:
            logger.error(f"Error dispatching CSL Fault: {e}")
    
    def dispatch_single_alarm(self, alarm: ProcessedAlarm):
        """Dispatch a single alarm"""
        self.dispatch_alarms([alarm])
    
    def get_stats(self) -> DispatchStats:
        """Get dispatch statistics"""
        return self.stats
    
    def clear_stats(self):
        """Clear dispatch statistics"""
        self.stats = DispatchStats()


# Global instance
message_dispatcher = MessageDispatcher()