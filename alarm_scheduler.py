"""
Alarm Scheduler
Manages timing and scheduling for batch alarm sending
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import queue

from config import settings, AlarmTypes
from alarm_processor import ProcessedAlarm, AlarmBatch, alarm_processor
from whatsapp_handler import WhatsAppHandler, WhatsAppMessageFormatter
from logger_module import logger


@dataclass
class ScheduledBatch:
    """A scheduled batch of alarms"""
    alarm_type: str
    scheduled_time: datetime
    alarms: List[ProcessedAlarm] = field(default_factory=list)
    
    @property
    def is_due(self) -> bool:
        return datetime.now() >= self.scheduled_time


class AlarmScheduler:
    """Manages alarm scheduling and batching"""
    
    def __init__(self):
        self.pending_alarms: Dict[str, List[ProcessedAlarm]] = defaultdict(list)  # alarm_type -> list
        self.last_send_time: Dict[str, datetime] = {}  # alarm_type -> last send time
        self.send_callback: Optional[Callable] = None
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.alarm_queue = queue.Queue()
        
        # Real-time alarm types (sent immediately)
        self.realtime_types = {AlarmTypes.CSL_FAULT.lower()}
    
    def set_send_callback(self, callback: Callable):
        """Set the callback function for sending alarms"""
        self.send_callback = callback
    
    def add_alarm(self, alarm: ProcessedAlarm):
        """Add an alarm to the scheduler"""
        with self.lock:
            alarm_type = alarm.alarm_type.lower()
            
            # Check if real-time alarm
            if self._is_realtime(alarm.alarm_type):
                # Queue for immediate sending
                self.alarm_queue.put(("realtime", alarm))
            else:
                # Add to pending batch
                self.pending_alarms[alarm.alarm_type].append(alarm)
                
                # Initialize last send time if not exists
                if alarm.alarm_type not in self.last_send_time:
                    self.last_send_time[alarm.alarm_type] = datetime.now()
    
    def add_alarms(self, alarms: List[ProcessedAlarm]):
        """Add multiple alarms"""
        for alarm in alarms:
            self.add_alarm(alarm)
    
    def _is_realtime(self, alarm_type: str) -> bool:
        """Check if alarm type should be sent in real-time"""
        return alarm_type.lower() in self.realtime_types or "csl" in alarm_type.lower()
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("Alarm scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Alarm scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                # Process real-time alarms
                self._process_realtime_queue()
                
                # Check batch alarms
                self._check_batch_alarms()
                
                # Sleep briefly
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(5)
    
    def _process_realtime_queue(self):
        """Process real-time alarm queue"""
        while not self.alarm_queue.empty():
            try:
                msg_type, alarm = self.alarm_queue.get_nowait()
                if msg_type == "realtime" and self.send_callback:
                    self._send_realtime_alarm(alarm)
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error processing realtime alarm: {e}")
    
    def _send_realtime_alarm(self, alarm: ProcessedAlarm):
        """Send a real-time alarm (CSL Fault)"""
        try:
            # Use alarm processor to get all related alarms
            send_list = alarm_processor.process_csl_fault(alarm)
            
            for group_name, group_type, alarms in send_list:
                if self.send_callback and alarms:
                    if group_type == "MBU":
                        message = alarm_processor.format_mbu_message(alarms)
                    else:
                        message = alarm_processor.format_b2s_message(alarms)
                    
                    self.send_callback(group_name, message, alarm.alarm_type)
                    logger.alarm_batch_sent(alarm.alarm_type, len(alarms), group_name)
                    
        except Exception as e:
            logger.error(f"Error sending realtime alarm: {e}")
    
    def _check_batch_alarms(self):
        """Check and send batch alarms based on timing"""
        with self.lock:
            current_time = datetime.now()
            
            for alarm_type, alarms in list(self.pending_alarms.items()):
                if not alarms:
                    continue
                
                # Get timing for this alarm type
                timing_minutes = settings.get_timing_for_alarm(alarm_type)
                
                # Get last send time
                last_sent = self.last_send_time.get(alarm_type, current_time - timedelta(minutes=timing_minutes + 1))
                
                # Check if it's time to send
                time_since_last = (current_time - last_sent).total_seconds() / 60
                
                if time_since_last >= timing_minutes:
                    # Time to send!
                    self._send_batch_alarms(alarm_type, alarms)
                    
                    # Clear pending and update last send time
                    self.pending_alarms[alarm_type] = []
                    self.last_send_time[alarm_type] = current_time
    
    def _send_batch_alarms(self, alarm_type: str, alarms: List[ProcessedAlarm]):
        """Send a batch of alarms"""
        if not self.send_callback or not alarms:
            return
        
        try:
            # Group by MBU
            mbu_groups = alarm_processor.group_alarms_by_mbu(alarms)
            
            # Send to each MBU group
            for mbu, type_batches in mbu_groups.items():
                if alarm_type in type_batches:
                    batch = type_batches[alarm_type]
                    
                    # Send regular alarms
                    if batch.alarms:
                        logger.info(f"DEBUG: Processing {len(batch.alarms)} alarms for {alarm_type} in group {batch.group_name}")
                        message = WhatsAppMessageFormatter.format_mbu_alarms(batch.alarms, alarm_type)
                        logger.info(f"DEBUG: Generated MBU message for {alarm_type}: length={len(message)}, preview='{message[:100]}'")
                        if not message.strip():
                            logger.error(f"DEBUG: EMPTY MESSAGE generated for {alarm_type}!")
                        else:
                            self.send_callback(batch.group_name, message, alarm_type)
                            logger.alarm_batch_sent(alarm_type, len(batch.alarms), batch.group_name)
                    
                    # Send toggle alarms (if not skipped for this MBU)
                    if batch.toggle_alarms and not alarm_processor.should_skip_toggle_for_mbu(mbu):
                        toggle_message = WhatsAppMessageFormatter.format_toggle_alarms(batch.toggle_alarms)
                        logger.info(f"DEBUG: Generated toggle message: length={len(toggle_message)}, preview='{toggle_message[:100]}'")
                        self.send_callback(batch.group_name, toggle_message, f"{alarm_type} (Toggle)")
                        logger.alarm_batch_sent(f"{alarm_type} (Toggle)", len(batch.toggle_alarms), batch.group_name)
            
            # Group by B2S
            b2s_groups = alarm_processor.group_alarms_for_b2s(alarms)
            for company, type_batches in b2s_groups.items():
                if alarm_type in type_batches:
                    batch = type_batches[alarm_type]
                    if batch.alarms:
                        message = WhatsAppMessageFormatter.format_b2s_alarms(batch.alarms)
                        self.send_callback(batch.group_name, message, alarm_type)
                        logger.alarm_batch_sent(alarm_type, len(batch.alarms), batch.group_name)
            
            # Group by OMO
            omo_groups = alarm_processor.group_alarms_for_omo(alarms)
            for company, type_batches in omo_groups.items():
                if alarm_type in type_batches:
                    batch = type_batches[alarm_type]
                    if batch.alarms:
                        message = WhatsAppMessageFormatter.format_omo_alarms(batch.alarms)
                        self.send_callback(batch.group_name, message, alarm_type)
                        logger.alarm_batch_sent(alarm_type, len(batch.alarms), batch.group_name)
                        
        except Exception as e:
            logger.error(f"Error sending batch alarms: {e}")
    
    def force_send_all(self):
        """Force send all pending alarms immediately"""
        with self.lock:
            for alarm_type, alarms in list(self.pending_alarms.items()):
                if alarms:
                    self._send_batch_alarms(alarm_type, alarms)
                    self.pending_alarms[alarm_type] = []
                    self.last_send_time[alarm_type] = datetime.now()
    
    def force_send_type(self, alarm_type: str):
        """Force send alarms of a specific type"""
        with self.lock:
            alarms = self.pending_alarms.get(alarm_type, [])
            if alarms:
                self._send_batch_alarms(alarm_type, alarms)
                self.pending_alarms[alarm_type] = []
                self.last_send_time[alarm_type] = datetime.now()
    
    def get_pending_counts(self) -> Dict[str, int]:
        """Get count of pending alarms by type"""
        with self.lock:
            return {k: len(v) for k, v in self.pending_alarms.items()}
    
    def get_next_send_times(self) -> Dict[str, datetime]:
        """Get next scheduled send time for each alarm type"""
        result = {}
        current_time = datetime.now()
        
        with self.lock:
            for alarm_type in self.pending_alarms.keys():
                timing_minutes = settings.get_timing_for_alarm(alarm_type)
                last_sent = self.last_send_time.get(alarm_type, current_time)
                next_send = last_sent + timedelta(minutes=timing_minutes)
                result[alarm_type] = next_send
        
        return result
    
    def clear_all(self):
        """Clear all pending alarms"""
        with self.lock:
            self.pending_alarms.clear()
            self.last_send_time.clear()
            while not self.alarm_queue.empty():
                try:
                    self.alarm_queue.get_nowait()
                except:
                    break


# Global instance
alarm_scheduler = AlarmScheduler()