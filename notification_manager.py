"""
Notification Manager
Handles desktop notifications and alerts
"""

import threading
from datetime import datetime
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

try:
    from plyer import notification as desktop_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

from logger_module import logger


class NotificationType(Enum):
    """Types of notifications"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    ALARM = "alarm"


@dataclass
class Notification:
    """A notification"""
    title: str
    message: str
    notification_type: NotificationType
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class NotificationManager:
    """
    Manages desktop notifications and alerts
    """
    
    APP_NAME = "Telecom Alarm Automation"
    
    def __init__(self):
        self.enabled = True
        self.notification_history: List[Notification] = []
        self.max_history = 100
        self.callbacks: List[Callable] = []
        self.lock = threading.Lock()
    
    def add_callback(self, callback: Callable):
        """Add callback for notifications"""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, notification: Notification):
        """Notify all callbacks"""
        for callback in self.callbacks:
            try:
                callback(notification)
            except:
                pass
    
    def notify(self, title: str, message: str, notification_type: NotificationType = NotificationType.INFO):
        """
        Show a notification
        
        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification
        """
        notification = Notification(
            title=title,
            message=message,
            notification_type=notification_type
        )
        
        with self.lock:
            # Add to history
            self.notification_history.append(notification)
            
            # Trim history if needed
            if len(self.notification_history) > self.max_history:
                self.notification_history = self.notification_history[-self.max_history:]
        
        # Notify callbacks
        self._notify_callbacks(notification)
        
        # Show desktop notification
        if self.enabled and PLYER_AVAILABLE:
            try:
                desktop_notification.notify(
                    title=f"{self.APP_NAME} - {title}",
                    message=message[:256],  # Limit message length
                    app_name=self.APP_NAME,
                    timeout=5
                )
            except Exception as e:
                logger.error(f"Desktop notification error: {e}")
    
    def info(self, title: str, message: str):
        """Show info notification"""
        self.notify(title, message, NotificationType.INFO)
    
    def success(self, title: str, message: str):
        """Show success notification"""
        self.notify(title, message, NotificationType.SUCCESS)
    
    def warning(self, title: str, message: str):
        """Show warning notification"""
        self.notify(title, message, NotificationType.WARNING)
    
    def error(self, title: str, message: str):
        """Show error notification"""
        self.notify(title, message, NotificationType.ERROR)
    
    def alarm(self, alarm_type: str, count: int, group: str):
        """Show alarm notification"""
        self.notify(
            f"Alarm Sent: {alarm_type}",
            f"{count} alarm(s) sent to {group}",
            NotificationType.ALARM
        )
    
    def whatsapp_disconnected(self):
        """Notify WhatsApp disconnection"""
        self.warning(
            "WhatsApp Disconnected",
            "Please check WhatsApp Web connection and scan QR code if needed."
        )
    
    def portal_error(self, message: str):
        """Notify portal error"""
        self.error("Portal Error", message)
    
    def get_recent_notifications(self, count: int = 20) -> List[Notification]:
        """Get recent notifications"""
        with self.lock:
            return self.notification_history[-count:]
    
    def clear_history(self):
        """Clear notification history"""
        with self.lock:
            self.notification_history.clear()
    
    def enable(self):
        """Enable notifications"""
        self.enabled = True
    
    def disable(self):
        """Disable notifications"""
        self.enabled = False


# Global instance
notification_manager = NotificationManager()