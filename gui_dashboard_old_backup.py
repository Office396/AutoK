"""
GUI Dashboard
Main dashboard view with status, statistics, and controls
"""

import customtkinter as ctk
from typing import Optional, Callable, Dict, List, Any
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
        
        # OPTIMIZED: Track widgets and their data to update in-place, not destroy/recreate
        self.queue_widgets: Dict[int, ctk.CTkFrame] = {}  # index -> widget
        self.sent_widgets: Dict[int, ctk.CTkFrame] = {}   # index -> widget
        self._last_queue_data = []
        self._last_sent_data = []
        
        # Log buffer for batched updates
        self._log_buffer = []
        self._log_update_scheduled = False
        
        self._create_layout()
        
        # Register for logger callbacks to receive log messages
        logger.add_callback(self._on_logger_message)
    
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
        """Create modern header with status and controls"""
        header = ctk.CTkFrame(
            self,
            fg_color=Colors.SURFACE_1,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        header.grid(row=0, column=0, sticky="ew", padx=25, pady=(25, 15))
        
        # Left side - Status indicators
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.pack(side="left", padx=25, pady=20)
        
        # Title with gradient-like appearance
        title_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        title_frame.pack(anchor="w")
        
        title = ctk.CTkLabel(
            title_frame,
            text="🗼 Telecom Alarm Automation",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left")
        
        # Live indicator
        live_dot = ctk.CTkFrame(
            title_frame,
            width=8,
            height=8,
            corner_radius=4,
            fg_color=Colors.SUCCESS
        )
        live_dot.pack(side="left", padx=(10, 0))
        live_dot.pack_propagate(False)
        
        live_label = ctk.CTkLabel(
            title_frame,
            text="LIVE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=Colors.SUCCESS
        )
        live_label.pack(side="left", padx=(5, 0))
        
        # Status indicators row with better spacing
        indicators_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        indicators_frame.pack(anchor="w", pady=(15, 0))
        
        self.automation_status = StatusIndicator(
            indicators_frame,
            "Automation",
            "Stopped"
        )
        self.automation_status.pack(side="left", padx=(0, 35))
        
        self.portal_status = StatusIndicator(
            indicators_frame,
            "Portal",
            "Disconnected"
        )
        self.portal_status.pack(side="left", padx=(0, 35))
        
        self.whatsapp_status = StatusIndicator(
            indicators_frame,
            "WhatsApp",
            "Disconnected"
        )
        self.whatsapp_status.pack(side="left", padx=(0, 15))
        
        # Reset WhatsApp button with modern styling
        self.reset_wa_btn = ctk.CTkButton(
            indicators_frame,
            text="🔄 Reset WA",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=Colors.BG_LIGHT,
            hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=8,
            width=90,
            height=28,
            command=self._on_reset_wa_click
        )
        self.reset_wa_btn.pack(side="left")
        
        # Right side - Control buttons with modern design
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.pack(side="right", padx=25, pady=20)
        
        # Start/Stop button - Primary action
        self.start_btn = ActionButton(
            controls_frame,
            text="Start",
            icon="▶",
            color=Colors.SUCCESS,
            hover_color=Colors.SUCCESS_LIGHT,
            command=self._on_start_click,
            width=130,
            height=44
        )
        self.start_btn.pack(side="left", padx=6)
        
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
        """Create modern statistics cards section with better visual hierarchy"""
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", padx=25, pady=15)
        
        # Configure columns for responsive layout
        for i in range(6):
            stats_frame.grid_columnconfigure(i, weight=1, uniform="stat")
        
        # Stat cards with improved spacing and modern design
        self.uptime_card = StatCard(
            stats_frame,
            title="Uptime",
            value="00:00:00",
            icon="⏱️",
            color=Colors.PRIMARY
        )
        self.uptime_card.grid(row=0, column=0, padx=6, pady=8, sticky="ew")
        
        self.alarms_card = StatCard(
            stats_frame,
            title="Alarms Processed",
            value="0",
            icon="🔔",
            color=Colors.ACCENT_ORANGE
        )
        self.alarms_card.grid(row=0, column=1, padx=6, pady=8, sticky="ew")
        
        self.messages_card = StatCard(
            stats_frame,
            title="Messages Sent",
            value="0",
            icon="📨",
            color=Colors.SUCCESS
        )
        self.messages_card.grid(row=0, column=2, padx=6, pady=8, sticky="ew")
        
        self.queued_card = StatCard(
            stats_frame,
            title="Queued",
            value="0",
            icon="📋",
            color=Colors.ACCENT_BLUE
        )
        self.queued_card.grid(row=0, column=3, padx=6, pady=8, sticky="ew")
        
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
        """Create main content area - REMADE from scratch"""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 20))
        
        # Configure grid for responsive layout
        content.grid_columnconfigure(0, weight=2)  # Activity Log (larger)
        content.grid_columnconfigure(1, weight=1)  # Queue
        content.grid_columnconfigure(2, weight=1)  # Sent
        content.grid_rowconfigure(0, weight=1)
        
        # Left - Activity Log
        log_container = ctk.CTkFrame(
            content,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        log_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        log_container.grid_rowconfigure(1, weight=1)
        log_container.grid_columnconfigure(0, weight=1)
        
        # Log header
        log_header = ctk.CTkFrame(log_container, fg_color="transparent")
        log_header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        
        log_title = ctk.CTkLabel(
            log_header,
            text="📜 Activity Log",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        log_title.pack(side="left")
        
        # self.clear_log_btn = ctk.CTkButton(
        #     log_header,
        #     text="Clear",
        #     font=ctk.CTkFont(size=11),
        #     fg_color=Colors.BG_LIGHT,
        #     hover_color=Colors.BG_MEDIUM,
        #     width=70,
        #     height=28,
        #     command=self._clear_log
        # )
        # self.clear_log_btn.pack(side="right")
        
        # Log viewer (TextBox with manual scrollbar control)
        self.log_viewer = ctk.CTkTextbox(
            log_container,
            fg_color=Colors.BG_DARK,
            text_color=Colors.TEXT_SECONDARY,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            activate_scrollbars=True
        )
        self.log_viewer.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.log_viewer.configure(state="disabled")
        
        # Middle - In Queue
        queue_container = ctk.CTkFrame(
            content,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        queue_container.grid(row=0, column=1, sticky="nsew", padx=5)
        queue_container.grid_rowconfigure(1, weight=1)
        queue_container.grid_columnconfigure(0, weight=1)
        
        # Queue header
        queue_header = ctk.CTkFrame(queue_container, fg_color="transparent")
        queue_header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        
        queue_title = ctk.CTkLabel(
            queue_header,
            text="📋 In Queue",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        queue_title.pack(side="left")
        
        self.queue_count_label = ctk.CTkLabel(
            queue_header,
            text="0",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.ACCENT_BLUE
        )
        self.queue_count_label.pack(side="right")
        
        # Queue list (scrollable frame - scrollbar only shows when needed)
        self.queue_list = ctk.CTkScrollableFrame(
            queue_container,
            fg_color="transparent"
        )
        self.queue_list.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # Right - Recently Sent
        sent_container = ctk.CTkFrame(
            content,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        sent_container.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        sent_container.grid_rowconfigure(1, weight=1)
        sent_container.grid_columnconfigure(0, weight=1)
        
        # Sent header
        sent_header = ctk.CTkFrame(sent_container, fg_color="transparent")
        sent_header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        
        sent_title = ctk.CTkLabel(
            sent_header,
            text="✅ Recently Sent",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        sent_title.pack(side="left")
        
        self.sent_count_label = ctk.CTkLabel(
            sent_header,
            text="0",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.SUCCESS
        )
        self.sent_count_label.pack(side="right")
        
        # Sent list (scrollable frame - scrollbar only shows when needed)
        self.sent_list = ctk.CTkScrollableFrame(
            sent_container,
            fg_color="transparent"
        )
        self.sent_list.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
    
    # Button handlers
    def _on_start_click(self):
        """Handle start/stop button with protection against double clicks"""
        # Disable the button temporarily to prevent double clicks
        self.start_btn.configure(state="disabled")
        
        if self.on_start:
            self.on_start()
        
        # The button will be re-enabled when the state changes
        # through set_automation_running() or set_automation_stopped() methods
    
    def _on_pause_click(self):
        if self.on_pause:
            self.on_pause()
    
    def _on_force_check_click(self):
        """Handle force check button - only works when automation is running"""
        # Check if automation is running before allowing check
        from automation_controller import automation_controller
        if not automation_controller.is_running():
            self.log("Cannot check now - automation is not running", "WARNING")
            return
            
        # Temporarily disable the button to prevent multiple clicks
        self.check_btn.configure(state="disabled")
            
        if self.on_force_check:
            self.on_force_check()
            self.log("Manual portal check initiated", "INFO")
            
        # Re-enable after a short delay
        self.after(1000, lambda: self.check_btn.configure(state="normal"))
    
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
                    hover_color="#C62828",
                    state="normal"  # Re-enable the button
                )
                self.pause_btn.configure(state="normal")
                self.check_btn.configure(state="normal")
                self.send_btn.configure(state="normal")
                self.automation_status.set_status("Running", True)
            else:
                self.start_btn.configure(
                    text="▶ Start",
                    fg_color=Colors.SUCCESS,
                    hover_color="#388E3C",
                    state="normal"  # Re-enable the button
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
    
    def set_automation_error(self):
        """Update UI for error state - re-enable start button"""
        def _update():
            # Re-enable start button so user can try starting again
            self.start_btn.configure(
                text="▶ Start",
                fg_color=Colors.SUCCESS,
                hover_color="#388E3C",
                state="normal"  # Re-enable the button
            )
            # Disable other buttons when in error state
            self.pause_btn.configure(state="disabled")
            self.check_btn.configure(state="disabled")
            self.send_btn.configure(state="disabled")
            self.automation_status.set_status("Error", False)
        
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
    
    # Alarms table removed from dashboard - now in separate Alarms view
    
    def _on_logger_message(self, log_entry: str, level: str):
        """Callback from logger module - receives all log messages"""
        # Extract just the message part (skip timestamp and level prefix from logger)
        try:
            # Log format is: [2026-01-17 07:26:18] [INFO] message
            parts = log_entry.split('] ', 2)
            if len(parts) >= 3:
                message = parts[2].strip()
            else:
                message = log_entry
            
            # Add to buffer
            self._log_buffer.append((message, level))
            
            # Schedule batched update if not already scheduled
            if not self._log_update_scheduled:
                self._log_update_scheduled = True
                self.after(100, self._process_log_buffer)
        except:
            pass
    
    def _process_log_buffer(self):
        """Process buffered log entries in batch"""
        self._log_update_scheduled = False
        
        if not self._log_buffer:
            return
        
        # Only update if log viewer exists
        if not hasattr(self, 'log_viewer') or not self.log_viewer.winfo_exists():
            return
        
        try:
            from datetime import datetime
            
            # Get all pending logs
            pending = list(self._log_buffer)
            self._log_buffer = []
            
            # Build all log lines
            log_text = ""
            for message, level in pending:
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Color based on level
                if level == "ERROR":
                    prefix = "❌"
                elif level == "SUCCESS":
                    prefix = "✅"
                elif level == "WARNING":
                    prefix = "⚠️"
                elif level == "ALARM":
                    prefix = "🔔"
                else:
                    prefix = "ℹ️"
                
                log_text += f"[{timestamp}] {prefix} {message}\n"
            
            # Single batch insert
            self.log_viewer.configure(state="normal")
            self.log_viewer.insert("end", log_text)
            
            # Auto-scroll to bottom
            self.log_viewer.see("end")
            
            # Limit to last 500 lines
            line_count = int(self.log_viewer.index('end-1c').split('.')[0])
            if line_count > 500:
                self.log_viewer.delete("1.0", f"{line_count - 500}.0")
            
            self.log_viewer.configure(state="disabled")
        except Exception as e:
            print(f"Error processing log buffer: {e}")
    
    def log(self, message: str, level: str = "INFO"):
        """Add a log entry directly - REMADE to work with TextBox"""
        def _log():
            # Only update if log viewer exists
            if not hasattr(self, 'log_viewer') or not self.log_viewer.winfo_exists():
                return
            
            try:
                from datetime import datetime
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Color based on level
                if level == "ERROR":
                    prefix = "❌"
                elif level == "SUCCESS":
                    prefix = "✅"
                elif level == "WARNING":
                    prefix = "⚠️"
                elif level == "ALARM":
                    prefix = "🔔"
                else:
                    prefix = "ℹ️"
                
                log_line = f"[{timestamp}] {prefix} {message}\n"
                
                # Enable editing, add log, disable editing
                self.log_viewer.configure(state="normal")
                self.log_viewer.insert("end", log_line)
                
                # Auto-scroll to bottom
                self.log_viewer.see("end")
                
                # Limit to last 500 lines
                line_count = int(self.log_viewer.index('end-1c').split('.')[0])
                if line_count > 500:
                    self.log_viewer.delete("1.0", f"{line_count - 500}.0")
                
                self.log_viewer.configure(state="disabled")
            except Exception as e:
                print(f"Error logging: {e}")
        
        # Schedule the log update
        try:
            self.after(0, _log)
        except:
            pass

    def update_stats_bar_event(self, data: Dict[str, Any]):
        """Update stats bar - FIXED to only update queue/sent lists"""
        def _update():
            try:
                # Update queue/sent lists (will show empty if no data)
                queue_data = data.get('queue_preview', [])
                sent_data = data.get('sent_recent', [])
                
                # CRITICAL FIX: Ensure widgets exist before updating
                if hasattr(self, 'queue_list') and self.queue_list.winfo_exists():
                    self._update_queue_list_optimized(queue_data)
                else:
                    logger.debug("Queue list widget does not exist")
                
                if hasattr(self, 'sent_list') and self.sent_list.winfo_exists():
                    self._update_sent_list_optimized(sent_data)
                else:
                    logger.debug("Sent list widget does not exist")
                    
            except Exception as e:
                # CRITICAL FIX: Log error instead of silently failing to help debug
                logger.error(f"Error updating stats bar: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        # Schedule the update without blocking
        try:
            self.after(0, _update)
        except:
            pass
    
    def _update_queue_list_optimized(self, queue_data: List[Dict]):
        """Update queue list IN-PLACE without destroying widgets"""
        try:
            if not hasattr(self, 'queue_list') or not self.queue_list.winfo_exists():
                return
            
            # Update count label
            if hasattr(self, 'queue_count_label'):
                count = len(queue_data)
                self.queue_count_label.configure(text=f"{count} pending")
            
            # Clear existing widgets
            for widget in self.queue_list.winfo_children():
                widget.destroy()
            
            # Check if there's data to display
            if not queue_data:
                # Show empty state message
                empty_label = ctk.CTkLabel(
                    self.queue_list,
                    text="No messages queued",
                    font=ctk.CTkFont(size=11),
                    text_color=Colors.TEXT_MUTED,
                    anchor="center"
                )
                empty_label.pack(fill="both", expand=True, pady=20)
                return
            
            # Add items to the list
            for item in queue_data:
                alarm_type = item.get('alarm_type', '-')
                group_name = item.get('group_name', '-')
                text = f"{alarm_type} → {group_name}"
                
                row = ctk.CTkFrame(self.queue_list, fg_color=Colors.BG_MEDIUM, corner_radius=8)
                row.pack(fill="x", padx=0, pady=3)
                
                label = ctk.CTkLabel(
                    row,
                    text=text,
                    font=ctk.CTkFont(size=11),
                    text_color=Colors.TEXT_SECONDARY,
                    anchor="w",
                    wraplength=250
                )
                label.pack(fill="x", padx=10, pady=6)
                
                # Store reference to widget for potential future updates
                if not hasattr(self, 'queue_widgets'):
                    self.queue_widgets = {}
        except Exception as e:
            logger.error(f"Error updating queue list: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _update_sent_list_optimized(self, sent_data: List[Dict]):
        """Update sent list IN-PLACE without destroying widgets"""
        try:
            if not hasattr(self, 'sent_list') or not self.sent_list.winfo_exists():
                return
            
            # Update count label
            if hasattr(self, 'sent_count_label'):
                count = len(sent_data)
                self.sent_count_label.configure(text=f"{count} sent")
            
            # Clear existing widgets
            for widget in self.sent_list.winfo_children():
                widget.destroy()
            
            # Check if there's data to display
            if not sent_data:
                # Show empty state message
                empty_label = ctk.CTkLabel(
                    self.sent_list,
                    text="No messages sent yet",
                    font=ctk.CTkFont(size=11),
                    text_color=Colors.TEXT_MUTED,
                    anchor="center"
                )
                empty_label.pack(fill="both", expand=True, pady=20)
                return
            
            # Add items to the list
            for item in sent_data:
                ok = item.get('success', False)
                icon = "✅" if ok else "❌"
                alarm_type = item.get('alarm_type', '-')
                group_name = item.get('group_name', '-')
                text = f"{icon} {alarm_type} → {group_name}"
                text_color = Colors.SUCCESS if ok else Colors.ERROR
                
                row = ctk.CTkFrame(self.sent_list, fg_color=Colors.BG_MEDIUM, corner_radius=8)
                row.pack(fill="x", padx=0, pady=3)
                
                label = ctk.CTkLabel(
                    row,
                    text=text,
                    font=ctk.CTkFont(size=11),
                    text_color=text_color,
                    anchor="w",
                    wraplength=250
                )
                label.pack(fill="x", padx=10, pady=6)
                
                # Store reference to widget for potential future updates
                if not hasattr(self, 'sent_widgets'):
                    self.sent_widgets = {}
        except Exception as e:
            logger.error(f"Error updating sent list: {e}")
            import traceback
            logger.debug(traceback.format_exc())


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
