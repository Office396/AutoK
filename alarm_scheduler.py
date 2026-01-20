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
from whatsapp_handler import WhatsAppHandler, WhatsAppMessageFormatter, OrderedAlarmSender
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
        self.batch_start_times: Dict[str, datetime] = {}  # alarm_type -> time when first alarm in batch arrived
        self.last_send_time: Dict[str, datetime] = {}  # Kept for compatibility but unused in new logic
        self.send_callback: Optional[Callable] = None
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.alarm_queue = queue.Queue()
        self.last_sent_buckets: Dict[str, set] = {}
        
        # Real-time alarm types (sent immediately)
        # CSL Fault is now handled as a regular alarm with 0 min delay
        # This allows it to be batched if needed and ensures consistent handling
        self.realtime_types = set()
    
    def set_send_callback(self, callback: Callable):
        """Set the callback function for sending alarms"""
        self.send_callback = callback
    
    def add_alarm(self, alarm: ProcessedAlarm):
        """Add an alarm to the scheduler"""
        alarm_type = alarm.alarm_type.lower()
        
        # Check if real-time alarm (no lock needed for read-only check)
        if self._is_realtime(alarm.alarm_type):
            # Queue for immediate sending
            self.alarm_queue.put(("realtime", alarm))
            return
        
        # Only lock when modifying shared state
        with self.lock:
            # Add to pending batch - allow duplicates
            # Start batch timer if this is the first alarm in the batch
            if not self.pending_alarms[alarm.alarm_type]:
                self.batch_start_times[alarm.alarm_type] = datetime.now()
                logger.info(f"Started batch timer for {alarm.alarm_type}")
            
            # Add to pending batch
            self.pending_alarms[alarm.alarm_type].append(alarm)
            
            # Initialize last send time if not exists (legacy)
            if alarm.alarm_type not in self.last_send_time:
                self.last_send_time[alarm.alarm_type] = datetime.now()
    
    def add_alarms(self, alarms: List[ProcessedAlarm]):
        """Add multiple alarms"""
        for alarm in alarms:
            self.add_alarm(alarm)
    
    def _is_realtime(self, alarm_type: str) -> bool:
        """Check if alarm type should be sent in real-time"""
        return alarm_type.lower() in self.realtime_types
    
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
                    if group_type != "MBU":
                        continue
                    message = alarm_processor.format_mbu_message(alarms)
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
                
                minutes_of_hour = settings.get_hourly_minutes_for_alarm(alarm_type)
                if minutes_of_hour is not None and len(minutes_of_hour) > 0:
                    bucket_hour = current_time.strftime("%Y-%m-%d %H")
                    # Initialize bucket set for this alarm type
                    sent_set = self.last_sent_buckets.get(alarm_type)
                    if sent_set is None:
                        sent_set = set()
                        self.last_sent_buckets[alarm_type] = sent_set
                    # Prune previous hour entries to avoid growth
                    if sent_set:
                        to_remove = [k for k in sent_set if not k.startswith(bucket_hour)]
                        for k in to_remove:
                            sent_set.discard(k)
                    # Check each configured minute
                    for minute_of_hour in minutes_of_hour:
                        if current_time.minute == minute_of_hour:
                            bucket_key = f"{bucket_hour}:{minute_of_hour:02d}"
                            if bucket_key not in sent_set:
                                self._send_batch_alarms(alarm_type, alarms)
                                self.pending_alarms[alarm_type] = []
                                self.batch_start_times.pop(alarm_type, None)
                                self.last_send_time[alarm_type] = current_time
                                sent_set.add(bucket_key)
                            break
                    continue
                
                timing_minutes = settings.get_timing_for_alarm(alarm_type)
                
                # Check batch aging using start time
                start_time = self.batch_start_times.get(alarm_type)
                if start_time is None:
                    # Should not happen if logic is correct, but self-heal
                    start_time = current_time
                    self.batch_start_times[alarm_type] = start_time
                
                # Check how long we've been buffering this batch
                batch_age_minutes = (current_time - start_time).total_seconds() / 60
                
                if batch_age_minutes >= timing_minutes:
                    # Time to send!
                    # Create a defensive copy of the list to ensure stability during sending
                    alarms_to_send = list(alarms)
                    
                    # Clear pending and reset timer immediately
                    self.pending_alarms[alarm_type] = []
                    self.batch_start_times.pop(alarm_type, None)
                    self.last_send_time[alarm_type] = current_time
                    
                    logger.info(f"Sending batch for {alarm_type}. Buffered for {batch_age_minutes:.1f} min. Count: {len(alarms_to_send)}")
                    self._send_batch_alarms(alarm_type, alarms_to_send)
    
    def _send_batch_alarms(self, alarm_type: str, alarms: List[ProcessedAlarm]):
        """Send a batch of alarms using ordered sending"""
        if not self.send_callback or not alarms:
            return
        
        try:
            # Use OrderedAlarmSender to handle correct grouping and ordering
            OrderedAlarmSender.send_all_ordered(alarms)
            
        except Exception as e:
            logger.error(f"Error sending batch alarms: {e}")
    
    def force_send_all(self):
        """Force send all pending alarms immediately using ordered sending"""
        with self.lock:
            all_alarms = []
            for alarm_type, alarms in list(self.pending_alarms.items()):
                if alarms:
                    all_alarms.extend(alarms)
                    self.pending_alarms[alarm_type] = []
                    self.last_send_time[alarm_type] = datetime.now()
            
            if all_alarms:
                logger.info(f"Force sending {len(all_alarms)} alarms in ordered manner...")
                OrderedAlarmSender.send_all_ordered(all_alarms)
    
    def force_send_type(self, alarm_type: str):
        """Force send alarms of a specific type"""
        with self.lock:
            alarms = self.pending_alarms.get(alarm_type, [])
            if alarms:
                self._send_batch_alarms(alarm_type, alarms)
                self.pending_alarms[alarm_type] = []
                self.batch_start_times.pop(alarm_type, None)
                self.last_send_time[alarm_type] = datetime.now()
    
    def get_pending_for_type(self, alarm_type: str) -> List[ProcessedAlarm]:
        """Get a copy of pending alarms for a specific type"""
        with self.lock:
            return list(self.pending_alarms.get(alarm_type, []))
    
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
                minutes_of_hour = settings.get_hourly_minutes_for_alarm(alarm_type)
                if minutes_of_hour is not None and len(minutes_of_hour) > 0:
                    sorted_minutes = sorted(minutes_of_hour)
                    next_minute = None
                    for m in sorted_minutes:
                        if current_time.minute < m:
                            next_minute = m
                            break
                    if next_minute is None:
                        # Wrap to next hour at the first minute
                        next_hour = current_time + timedelta(hours=1)
                        next_send = next_hour.replace(minute=sorted_minutes[0], second=0, microsecond=0)
                    else:
                        next_send = current_time.replace(minute=next_minute, second=0, microsecond=0)
                    result[alarm_type] = next_send
                else:
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
