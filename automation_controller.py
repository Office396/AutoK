"""
Automation Controller
Main controller that coordinates all automation components
"""

import threading
import time
from datetime import datetime
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass, field
from enum import Enum

from browser_manager import browser_manager, BrowserStatus
from portal_monitor import portal_monitor, MonitorStats
from portal_handler import portal_handler
from alarm_scheduler import alarm_scheduler
from alarm_processor import alarm_processor, ProcessedAlarm
from whatsapp_handler import whatsapp_handler, WhatsAppStatus, send_alarms_to_whatsapp
from message_dispatcher import message_dispatcher
from notification_manager import notification_manager
from master_data import master_data
from config import settings
from logger_module import logger


class AutomationState(Enum):
    """States of the automation system"""
    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    PAUSED = "Paused"
    ERROR = "Error"


@dataclass
class AutomationStats:
    """Overall automation statistics"""
    state: AutomationState = AutomationState.STOPPED
    start_time: Optional[datetime] = None
    uptime_seconds: int = 0
    
    # Portal stats
    portal_connected: bool = False
    portal_logged_in: bool = False
    
    # WhatsApp stats
    whatsapp_connected: bool = False
    messages_sent: int = 0
    messages_queued: int = 0
    
    # Alarm stats
    alarms_processed: int = 0
    alarms_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Errors
    error_count: int = 0
    last_error: Optional[str] = None


class AutomationController:
    """
    Main controller for the automation system
    Coordinates all components and manages the automation lifecycle
    """
    
    def __init__(self):
        self.state = AutomationState.STOPPED
        self.stats = AutomationStats()
        self.lock = threading.Lock()
        
        # Callbacks
        self.state_callbacks: List[Callable] = []
        self.stats_callbacks: List[Callable] = []
        self.alarm_callbacks: List[Callable] = []
        
        # Connect component callbacks
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """Setup callbacks between components"""
        # Alarm scheduler sends via WhatsApp
        alarm_scheduler.set_send_callback(send_alarms_to_whatsapp)
        
        # Portal monitor notifies of new alarms
        portal_monitor.add_alarm_callback(self._on_new_alarms)
        
        # WhatsApp status changes
        whatsapp_handler.add_status_callback(self._on_whatsapp_status)
        
        # Message sent notifications
        whatsapp_handler.add_message_sent_callback(self._on_message_sent)
        
        # Browser status
        browser_manager.add_status_callback(self._on_browser_status)
    
    def set_popup_callback(self, callback: Callable):
        """Set callback for showing error popups (usually from GUI)"""
        whatsapp_handler.set_popup_callback(callback)
    
    def add_state_callback(self, callback: Callable):
        """Add callback for state changes"""
        self.state_callbacks.append(callback)
    
    def add_stats_callback(self, callback: Callable):
        """Add callback for stats updates"""
        self.stats_callbacks.append(callback)
    
    def add_alarm_callback(self, callback: Callable):
        """Add callback for new alarms"""
        self.alarm_callbacks.append(callback)
    
    def _notify_state(self):
        """Notify state callbacks - FIXED to prevent blocking"""
        import tkinter as tk
        for callback in self.state_callbacks:
            try:
                # Check if this is a GUI callback that needs to be scheduled on the main thread
                if hasattr(callback, '__self__') and isinstance(callback.__self__, tk.Widget):
                    # Schedule GUI updates to run on the main thread
                    try:
                        callback.__self__.after(0, lambda: callback(self.state))
                    except:
                        pass
                else:
                    callback(self.state)
            except:
                pass
    
    def _notify_stats(self):
        """Notify stats callbacks - FIXED to prevent blocking"""
        self._update_stats()
        for callback in self.stats_callbacks:
            try:
                # Check if this is a GUI callback that needs to be scheduled on the main thread
                import tkinter as tk
                # If callback is bound to a tkinter widget, schedule it properly
                if hasattr(callback, '__self__') and isinstance(callback.__self__, tk.Widget):
                    # Schedule GUI updates to run on the main thread
                    try:
                        callback.__self__.after(0, lambda: callback(self.stats))
                    except:
                        pass
                else:
                    callback(self.stats)
            except:
                pass
    
    def _notify_alarms(self, alarms: List[ProcessedAlarm], source: str = None):
        """Notify alarm callbacks - FIXED to prevent blocking"""
        for callback in self.alarm_callbacks:
            try:
                # Support both signatures for backward compatibility
                import inspect
                import tkinter as tk
                    
                # Check if this is a GUI callback that needs to be scheduled on the main thread
                if hasattr(callback, '__self__') and isinstance(callback.__self__, tk.Widget):
                    # Schedule GUI updates to run on the main thread
                    try:
                        callback.__self__.after(0, lambda: self._call_alarm_callback(callback, alarms, source))
                    except:
                        pass
                else:
                    # Call directly for non-GUI callbacks
                    self._call_alarm_callback(callback, alarms, source)
            except Exception as e:
                logger.error(f"Error in alarm callback {callback}: {e}")
                import traceback
                traceback.print_exc()
        
    def _call_alarm_callback(self, callback, alarms, source):
        """Helper method to call alarm callback with proper signature handling"""
        import inspect
        sig = inspect.signature(callback)
        if 'source' in sig.parameters:
            callback(alarms, source=source)
        else:
            callback(alarms)
    
    def _update_stats(self):
        """Update statistics"""
        with self.lock:
            self.stats.state = self.state
            
            if self.stats.start_time:
                self.stats.uptime_seconds = int((datetime.now() - self.stats.start_time).total_seconds())
            
            # Browser/Portal stats
            browser_status = browser_manager.get_status()
            self.stats.portal_connected = browser_status.is_open
            self.stats.portal_logged_in = portal_handler.status.is_logged_in
            
            # WhatsApp stats - check both browser_manager and whatsapp_handler
            wa_stats = whatsapp_handler.get_stats()
            # Consider connected if EITHER browser_manager says ready OR whatsapp_handler says connected
            self.stats.whatsapp_connected = (
                browser_status.whatsapp_ready or 
                wa_stats['status'] == WhatsAppStatus.CONNECTED.value
            )
            self.stats.messages_sent = wa_stats['messages_sent']
            self.stats.messages_queued = wa_stats['queue_size']
            
            # Alarm stats
            monitor_stats = portal_monitor.get_stats()
            self.stats.alarms_processed = monitor_stats.total_alarms_processed
            self.stats.alarms_by_type = dict(monitor_stats.alarms_by_type)
    
    def _on_new_alarms(self, alarms: List[ProcessedAlarm], source: str = None):
        """Handle new alarms from portal monitor (updates GUI)"""
        self._notify_alarms(alarms, source)
        self._notify_stats()
    
    def _on_whatsapp_status(self, status: WhatsAppStatus):
        """Handle WhatsApp status change"""
        logger.info(f"WhatsApp status changed to: {status.value}")
        if status == WhatsAppStatus.QR_REQUIRED:
            notification_manager.warning(
                "WhatsApp QR Required",
                "Please scan the QR code in WhatsApp Web"
            )
        elif status == WhatsAppStatus.ERROR:
            notification_manager.error(
                "WhatsApp Error",
                "WhatsApp connection error occurred"
            )
            self.stats.error_count += 1
        elif status == WhatsAppStatus.CONNECTED:
            logger.success("WhatsApp is now connected!")
        
        self._notify_stats()
    
    def _on_message_sent(self, result):
        """Handle message sent notification"""
        if result.success:
            notification_manager.success(
                "Message Sent",
                f"Sent to {result.group_name}"
            )
        else:
            notification_manager.error(
                "Message Failed",
                f"Failed to send to {result.group_name}: {result.error}"
            )
            self.stats.error_count += 1
            self.stats.last_error = result.error
        
        self._notify_stats()
    
    def _on_browser_status(self, status: BrowserStatus):
        """Handle browser status change"""
        self._notify_stats()
    
    def start(self, username: str = None, password: str = None) -> bool:
        """
        Start the automation system
        
        Args:
            username: Portal username (optional, uses saved)
            password: Portal password (optional, uses saved)
            
        Returns:
            True if started successfully
        """
        try:
            with self.lock:
                if self.state == AutomationState.RUNNING:
                    logger.warning("Automation already running")
                    return True
                
                self.state = AutomationState.STARTING
                self._notify_state()
            
            logger.info("=" * 50)
            logger.info("Starting Telecom Alarm Automation")
            logger.info("=" * 50)
            
            # Load master data
            logger.info("Loading master data...")
            if not master_data.load():
                raise Exception("Failed to load master data")
            logger.success(f"Loaded {master_data.site_count} sites")
            
            # Start browser
            logger.info("Starting browser...")
            if not browser_manager.start():
                raise Exception("Failed to start browser")
            
            # Portal login will happen automatically when portal monitor tries to access portals
            # No need to wait here - let it happen naturally during first portal access
            
            # Wait for WhatsApp
            logger.info("Checking WhatsApp connection...")
            if not browser_manager.is_whatsapp_ready():
                logger.info("Waiting for WhatsApp QR scan...")
                notification_manager.info(
                    "Scan QR Code",
                    "Please scan WhatsApp QR code to continue"
                )
                if not browser_manager.wait_for_whatsapp_scan(timeout=120):
                    raise Exception("WhatsApp connection timeout")
            
            # Initialize WhatsApp handler status by checking connection
            logger.info("Initializing WhatsApp handler status...")
            wa_status = whatsapp_handler.check_connection()
            logger.info(f"WhatsApp handler status: {wa_status.value}")
            
            # Start WhatsApp sender
            logger.info("Starting WhatsApp message sender...")
            whatsapp_handler.start_sender()
            
            # Start alarm scheduler
            logger.info("Starting alarm scheduler...")
            alarm_scheduler.start()
            
            # Start portal monitor
            logger.info("Starting portal monitor...")
            portal_monitor.start(settings.check_interval_seconds)
            
            # Update state
            with self.lock:
                self.state = AutomationState.RUNNING
                self.stats.start_time = datetime.now()
                self.stats.error_count = 0
                self.stats.last_error = None
            
            self._notify_state()
            self._notify_stats()
            
            logger.success("Automation started successfully!")
            notification_manager.success(
                "Automation Started",
                "Telecom Alarm Automation is now running"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start automation: {e}")
            self.state = AutomationState.ERROR
            self.stats.last_error = str(e)
            self._notify_state()
            
            notification_manager.error(
                "Startup Failed",
                str(e)
            )
            
            return False
    
    def stop(self):
        """Stop the automation system"""
        try:
            logger.info("Stopping automation...")
            
            with self.lock:
                self.state = AutomationState.STOPPED
            
            # Stop components in reverse order
            portal_monitor.stop()
            alarm_scheduler.stop()
            whatsapp_handler.stop_sender()
            browser_manager.close()
            
            self._notify_state()
            self._notify_stats()
            
            logger.success("Automation stopped")
            notification_manager.info(
                "Automation Stopped",
                "Telecom Alarm Automation has been stopped"
            )
            
        except Exception as e:
            logger.error(f"Error stopping automation: {e}")
    
    def pause(self):
        """Pause the automation (stop monitoring but keep browser open)"""
        with self.lock:
            if self.state != AutomationState.RUNNING:
                return
            
            self.state = AutomationState.PAUSED
        
        portal_monitor.stop()
        alarm_scheduler.stop()
        
        self._notify_state()
        logger.info("Automation paused")
    
    def resume(self):
        """Resume paused automation"""
        with self.lock:
            if self.state != AutomationState.PAUSED:
                return
            
            self.state = AutomationState.RUNNING
        
        alarm_scheduler.start()
        portal_monitor.start(settings.check_interval_seconds)
        
        self._notify_state()
        logger.info("Automation resumed")
    
    def force_check(self):
        """Force an immediate check of all portals"""
        if self.state not in [AutomationState.RUNNING, AutomationState.PAUSED]:
            return
        
        logger.info("Forcing portal check...")
        alarms = portal_monitor.force_check()
        
        if alarms:
            logger.info(f"Found {len(alarms)} alarms")
            self._on_new_alarms(alarms)
    
    def force_send_all(self):
        """Force send all pending alarms (Runs in background thread)"""
        logger.info("Forcing send of all pending alarms...")
        
        def _force_send():
            try:
                alarm_scheduler.force_send_all()
                logger.success("Force send cycle completed and queued to WhatsApp")
            except Exception as e:
                logger.error(f"Error in force_send_all: {e}")
                
        thread = threading.Thread(target=_force_send, daemon=True)
        thread.start()
    
    def get_state(self) -> AutomationState:
        """Get current automation state"""
        return self.state
    
    def get_stats(self) -> AutomationStats:
        """Get current statistics"""
        self._update_stats()
        return self.stats
    
    def is_running(self) -> bool:
        """Check if automation is running"""
        return self.state == AutomationState.RUNNING
    
    def reset_whatsapp(self) -> bool:
        """Reset WhatsApp session by deleting profile and restarting browser"""
        logger.warning("User requested WhatsApp session reset")
        success = browser_manager.reset_whatsapp_session()
        if success:
            # Re-check status
            self._on_whatsapp_status(whatsapp_handler.check_connection())
        return success

    def reload_master_data(self) -> bool:
        """Reload master data from Excel"""
        logger.info("Reloading master data...")
        success = master_data.reload()
        if success:
            logger.success(f"Reloaded {master_data.site_count} sites")
        else:
            logger.error("Failed to reload master data")
        return success


# Global instance
automation_controller = AutomationController()


# Convenience functions
def start_automation(username: str = None, password: str = None) -> bool:
    """Start the automation"""
    return automation_controller.start(username, password)


def stop_automation():
    """Stop the automation"""
    automation_controller.stop()


def get_automation_state() -> AutomationState:
    """Get automation state"""
    return automation_controller.get_state()


def get_automation_stats() -> AutomationStats:
    """Get automation stats"""
    return automation_controller.get_stats()