"""
GUI Dashboard
Main dashboard view with status, statistics, and controls
"""

import customtkinter as ctk
from typing import Optional, Callable, Dict, List
from datetime import datetime
import threading

from gui_components import (
    Colors, StatusIndicator, StatCard, AlarmTable, LogViewer,
    ActionButton, ProgressIndicator
)
from config import settings
from logger_module import logger


class DashboardView(ctk.CTkFrame):
    """Main dashboard view"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        # Callbacks
        self.on_start: Optional[Callable] = None
        self.on_stop: Optional[Callable] = None
        self.on_pause: Optional[Callable] = None
        self.on_force_check: Optional[Callable] = None
        self.on_force_send: Optional[Callable] = None
        
        self._create_layout()
    
    def _create_layout(self):
        """Create the dashboard layout"""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Header section
        self._create_header()
        
        # Stats section
        self._create_stats_section()
        
        # Main content (alarms table and log)
        self._create_main_content()
    
    def _create_header(self):
        """Create header with status and controls"""
        header = ctk.CTkFrame(self, fg_color=Colors.BG_MEDIUM, corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        
        # Left side - Status indicators
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.pack(side="left", padx=20, pady=15)
        
        # Title
        title = ctk.CTkLabel(
            status_frame,
            text="🗼 Telecom Alarm Automation",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(anchor="w")
        
        # Status indicators row
        indicators_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        indicators_frame.pack(anchor="w", pady=(10, 0))
        
        self.automation_status = StatusIndicator(
            indicators_frame,
            "Automation",
            "Stopped"
        )
        self.automation_status.pack(side="left", padx=(0, 30))
        
        self.portal_status = StatusIndicator(
            indicators_frame,
            "Portal",
            "Disconnected"
        )
        self.portal_status.pack(side="left", padx=(0, 30))
        
        self.whatsapp_status = StatusIndicator(
            indicators_frame,
            "WhatsApp",
            "Disconnected"
        )
        self.whatsapp_status.pack(side="left", padx=(0, 10))
        
        # Reset WhatsApp button
        self.reset_wa_btn = ctk.CTkButton(
            indicators_frame,
            text="🔄 Reset WA",
            font=ctk.CTkFont(size=11),
            fg_color=Colors.BG_LIGHT,
            hover_color=Colors.BG_MEDIUM,
            width=80,
            height=25,
            command=self._on_reset_wa_click
        )
        self.reset_wa_btn.pack(side="left")
        
        # Right side - Control buttons
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.pack(side="right", padx=20, pady=15)
        
        # Start/Stop button
        self.start_btn = ActionButton(
            controls_frame,
            text="Start",
            icon="▶",
            color=Colors.SUCCESS,
            hover_color="#388E3C",
            command=self._on_start_click,
            width=120,
            height=40
        )
        self.start_btn.pack(side="left", padx=5)
        
        # Pause button
        self.pause_btn = ActionButton(
            controls_frame,
            text="Pause",
            icon="⏸",
            color=Colors.WARNING,
            hover_color="#F57C00",
            command=self._on_pause_click,
            width=100,
            height=40
        )
        self.pause_btn.pack(side="left", padx=5)
        self.pause_btn.configure(state="disabled")
        
        # Force Check button
        self.check_btn = ActionButton(
            controls_frame,
            text="Check Now",
            icon="🔄",
            color=Colors.INFO,
            hover_color="#1976D2",
            command=self._on_force_check_click,
            width=120,
            height=40
        )
        self.check_btn.pack(side="left", padx=5)
        self.check_btn.configure(state="disabled")
        
        # Force Send button
        self.send_btn = ActionButton(
            controls_frame,
            text="Send All",
            icon="📤",
            color=Colors.ACCENT_PURPLE,
            hover_color="#7B1FA2",
            command=self._on_force_send_click,
            width=110,
            height=40
        )
        self.send_btn.pack(side="left", padx=5)
        self.send_btn.configure(state="disabled")
    
    def _create_stats_section(self):
        """Create statistics cards section"""
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        
        # Configure columns
        for i in range(6):
            stats_frame.grid_columnconfigure(i, weight=1)
        
        # Stat cards
        self.uptime_card = StatCard(
            stats_frame,
            title="Uptime",
            value="00:00:00",
            icon="⏱️",
            color=Colors.INFO
        )
        self.uptime_card.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.alarms_card = StatCard(
            stats_frame,
            title="Alarms Processed",
            value="0",
            icon="🔔",
            color=Colors.WARNING
        )
        self.alarms_card.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.messages_card = StatCard(
            stats_frame,
            title="Messages Sent",
            value="0",
            icon="📨",
            color=Colors.SUCCESS
        )
        self.messages_card.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        self.queued_card = StatCard(
            stats_frame,
            title="Queued",
            value="0",
            icon="📋",
            color=Colors.ACCENT_BLUE
        )
        self.queued_card.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        self.sites_card = StatCard(
            stats_frame,
            title="Sites Loaded",
            value="0",
            icon="📍",
            color=Colors.ACCENT_GREEN
        )
        self.sites_card.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        
        self.errors_card = StatCard(
            stats_frame,
            title="Errors",
            value="0",
            icon="❌",
            color=Colors.ERROR
        )
        self.errors_card.grid(row=0, column=5, padx=5, pady=5, sticky="ew")
    
    def _create_main_content(self):
        """Create main content area with alarms table and log"""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 20))
        
        content.grid_columnconfigure(0, weight=2)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)
        
        # Left - Alarms table
        alarms_container = ctk.CTkFrame(content, fg_color=Colors.BG_CARD, corner_radius=10)
        alarms_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Alarms header
        alarms_header = ctk.CTkFrame(alarms_container, fg_color="transparent")
        alarms_header.pack(fill="x", padx=15, pady=10)
        
        alarms_title = ctk.CTkLabel(
            alarms_header,
            text="📋 Recent Alarms",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        alarms_title.pack(side="left")
        
        # Clear Alarms button
        self.clear_alarms_btn = ctk.CTkButton(
            alarms_header,
            text="Clear Alarms",
            font=ctk.CTkFont(size=11),
            fg_color=Colors.BG_LIGHT,
            hover_color=Colors.BG_MEDIUM,
            width=90,
            height=25,
            command=self._clear_alarms
        )
        self.clear_alarms_btn.pack(side="right", padx=5)
        
        # Alarms table
        self.alarm_table = AlarmTable(alarms_container, height=400)
        self.alarm_table.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Right - Log viewer
        log_container = ctk.CTkFrame(content, fg_color=Colors.BG_CARD, corner_radius=10)
        log_container.grid(row=0, column=1, sticky="nsew")
        
        # Log header
        log_header = ctk.CTkFrame(log_container, fg_color="transparent")
        log_header.pack(fill="x", padx=15, pady=10)
        
        log_title = ctk.CTkLabel(
            log_header,
            text="📜 Activity Log",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        log_title.pack(side="left")
        
        self.clear_log_btn = ctk.CTkButton(
            log_header,
            text="Clear",
            font=ctk.CTkFont(size=11),
            fg_color=Colors.BG_LIGHT,
            hover_color=Colors.BG_MEDIUM,
            width=60,
            height=25,
            command=self._clear_log
        )
        self.clear_log_btn.pack(side="right")
        
        # Log viewer
        self.log_viewer = LogViewer(log_container, height=400)
        self.log_viewer.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    # Button handlers
    def _on_start_click(self):
        if self.on_start:
            self.on_start()
    
    def _on_pause_click(self):
        if self.on_pause:
            self.on_pause()
    
    def _on_force_check_click(self):
        if self.on_force_check:
            self.on_force_check()
    
    def _on_force_send_click(self):
        if self.on_force_send:
            self.on_force_send()
    
    def _on_reset_wa_click(self):
        """Handle Reset WhatsApp button click"""
        from automation_controller import automation_controller
        from CTkMessagebox import CTkMessagebox
        
        msg = CTkMessagebox(
            title="Reset WhatsApp?",
            message="This will close the WhatsApp browser and clear the current session. You will need to scan the QR code again.\n\nContinue?",
            icon="question",
            option_1="No",
            option_2="Yes"
        )
        
        if msg.get() == "Yes":
            self.log("Resetting WhatsApp session...", "WARNING")
            thread = threading.Thread(target=automation_controller.reset_whatsapp)
            thread.daemon = True
            thread.start()
    
    def _clear_alarms(self):
        from portal_monitor import portal_monitor
        from automation_controller import automation_controller
        
        self.alarm_table.clear()
        portal_monitor.reset_seen_alarms()
        automation_controller.stats.alarms_processed = 0
        self.update_stats(alarms=0)
        self.log("Alarms and seen cache cleared", "INFO")
    
    def _clear_log(self):
        self.log_viewer.clear()
    
    # Public methods for updating UI
    def set_automation_running(self, running: bool):
        """Update UI for running state"""
        def _update():
            if running:
                self.start_btn.configure(
                    text="⏹ Stop",
                    fg_color=Colors.ERROR,
                    hover_color="#C62828"
                )
                self.pause_btn.configure(state="normal")
                self.check_btn.configure(state="normal")
                self.send_btn.configure(state="normal")
                self.automation_status.set_status("Running", True)
            else:
                self.start_btn.configure(
                    text="▶ Start",
                    fg_color=Colors.SUCCESS,
                    hover_color="#388E3C"
                )
                self.pause_btn.configure(state="disabled")
                self.check_btn.configure(state="disabled")
                self.send_btn.configure(state="disabled")
                self.automation_status.set_status("Stopped", False)
        
        self.after(0, _update)
    
    def set_automation_paused(self, paused: bool):
        """Update UI for paused state"""
        def _update():
            if paused:
                self.pause_btn.configure(text="▶ Resume")
                self.automation_status.set_warning("Paused")
            else:
                self.pause_btn.configure(text="⏸ Pause")
                self.automation_status.set_status("Running", True)
        
        self.after(0, _update)
    
    def update_portal_status(self, connected: bool, logged_in: bool = False):
        """Update portal status indicator"""
        def _update():
            if connected and logged_in:
                self.portal_status.set_status("Connected", True)
            elif connected:
                self.portal_status.set_warning("Not Logged In")
            else:
                self.portal_status.set_status("Disconnected", False)
        
        self.after(0, _update)
    
    def update_whatsapp_status(self, status: str):
        """Update WhatsApp status indicator"""
        def _update():
            if status == "Connected":
                self.whatsapp_status.set_status("Connected", True)
            elif status == "QR Code Required":
                self.whatsapp_status.set_warning("Scan QR")
            else:
                self.whatsapp_status.set_status(status, False)
        
        self.after(0, _update)
    
    def update_stats(
        self,
        uptime: str = None,
        alarms: int = None,
        messages: int = None,
        queued: int = None,
        sites: int = None,
        errors: int = None
    ):
        """Update statistics cards"""
        def _update():
            if uptime is not None:
                self.uptime_card.set_value(uptime)
            if alarms is not None:
                self.alarms_card.set_value(str(alarms))
            if messages is not None:
                self.messages_card.set_value(str(messages))
            if queued is not None:
                self.queued_card.set_value(str(queued))
            if sites is not None:
                self.sites_card.set_value(str(sites))
            if errors is not None:
                self.errors_card.set_value(str(errors))
                if errors > 0:
                    self.errors_card.set_color(Colors.ERROR)
                else:
                    self.errors_card.set_color(Colors.TEXT_MUTED)
        
        self.after(0, _update)
    
    def add_alarm(self, alarm_data: Dict, source: str = None):
        """Add an alarm to the table"""
        self.after(0, lambda: self.alarm_table.add_alarm(alarm_data, source))
        
    def update_alarms(self, alarms: List[Dict], source: str):
        """Replace alarms for a specific source"""
        def _update():
            try:
                # Remove old alarms for this source
                self.alarm_table.remove_alarms_by_source(source)
                
                # Add new alarms
                for alarm_data in reversed(alarms):
                    self.alarm_table.add_alarm(alarm_data, source)
            except Exception as e:
                self.log(f"Error updating alarms: {e}", "ERROR")
                # Also print to console just in case
                print(f"Error in update_alarms: {e}")
                
        self.after(0, _update)
    
    def log(self, message: str, level: str = "INFO"):
        """Add a log entry"""
        self.after(0, lambda: self.log_viewer.log(message, level))


class AlarmTypeSummary(ctk.CTkFrame):
    """Summary of alarms by type"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_CARD, corner_radius=10, **kwargs)
        
        # Title
        title = ctk.CTkLabel(
            self,
            text="📊 Alarms by Type",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(padx=15, pady=(15, 10), anchor="w")
        
        # Content frame
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.type_labels: Dict[str, ctk.CTkLabel] = {}
    
    def update_counts(self, counts: Dict[str, int]):
        """Update alarm type counts"""
        # Clear existing
        for widget in self.content.winfo_children():
            widget.destroy()
        self.type_labels.clear()
        
        # Create new labels
        for alarm_type, count in sorted(counts.items(), key=lambda x: -x[1]):
            row = ctk.CTkFrame(self.content, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            # Type name
            type_label = ctk.CTkLabel(
                row,
                text=alarm_type,
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_SECONDARY,
                anchor="w"
            )
            type_label.pack(side="left", fill="x", expand=True)
            
            # Count
            count_label = ctk.CTkLabel(
                row,
                text=str(count),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Colors.WARNING
            )
            count_label.pack(side="right")
            
            self.type_labels[alarm_type] = count_label


class MBUSummary(ctk.CTkFrame):
    """Summary of alarms by MBU"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_CARD, corner_radius=10, **kwargs)
        
        # Title
        title = ctk.CTkLabel(
            self,
            text="🏢 Alarms by MBU",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(padx=15, pady=(15, 10), anchor="w")
        
        # Content frame (scrollable)
        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            height=150
        )
        self.content.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.mbu_labels: Dict[str, ctk.CTkLabel] = {}
    
    def update_counts(self, counts: Dict[str, int]):
        """Update MBU counts"""
        # Clear existing
        for widget in self.content.winfo_children():
            widget.destroy()
        self.mbu_labels.clear()
        
        # Create new labels
        for mbu, count in sorted(counts.items()):
            row = ctk.CTkFrame(self.content, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            # MBU name
            mbu_label = ctk.CTkLabel(
                row,
                text=mbu,
                font=ctk.CTkFont(size=11),
                text_color=Colors.ACCENT_BLUE,
                anchor="w"
            )
            mbu_label.pack(side="left", fill="x", expand=True)
            
            # Count
            count_label = ctk.CTkLabel(
                row,
                text=str(count),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Colors.SUCCESS
            )
            count_label.pack(side="right")
            
            self.mbu_labels[mbu] = count_label


class NextSendTimes(ctk.CTkFrame):
    """Display next scheduled send times"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_CARD, corner_radius=10, **kwargs)
        
        # Title
        title = ctk.CTkLabel(
            self,
            text="⏰ Next Send Times",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(padx=15, pady=(15, 10), anchor="w")
        
        # Content
        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            height=150
        )
        self.content.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.time_labels: Dict[str, ctk.CTkLabel] = {}
    
    def update_times(self, times: Dict[str, str]):
        """Update send times"""
        # Clear existing
        for widget in self.content.winfo_children():
            widget.destroy()
        self.time_labels.clear()
        
        # Create new labels
        for alarm_type, time_str in sorted(times.items()):
            row = ctk.CTkFrame(self.content, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            # Alarm type
            type_label = ctk.CTkLabel(
                row,
                text=alarm_type,
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_SECONDARY,
                anchor="w"
            )
            type_label.pack(side="left", fill="x", expand=True)
            
            # Time
            time_label = ctk.CTkLabel(
                row,
                text=time_str,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Colors.INFO
            )
            time_label.pack(side="right")
            
            self.time_labels[alarm_type] = time_label