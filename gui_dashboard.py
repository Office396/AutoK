"""
GUI Dashboard - COMPLETELY REMADE
Only shows: Alarm Updates | Currently Sending | Recently Sent
"""

import customtkinter as ctk
from typing import Optional, Callable, Dict, List, Any
from datetime import datetime
import threading

from gui_components import (
    Colors, StatusIndicator, StatCard, ActionButton
)
from config import settings
from logger_module import logger


class DashboardView(ctk.CTkFrame):
    """Main dashboard view - REMADE"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        # Callbacks
        self.on_start: Optional[Callable] = None
        self.on_stop: Optional[Callable] = None
        self.on_pause: Optional[Callable] = None
        self.on_force_check: Optional[Callable] = None
        self.on_force_send: Optional[Callable] = None
        
        # Data tracking
        self._alarm_counts = {}  # alarm_type -> count
        self._current_sending = None
        self._recent_sent = []  # Last 20 sent messages
        
        # Track widgets to safely update scrollable lists without destroying scrollbars
        self.queue_widgets: List[ctk.CTkBaseClass] = []
        self.sent_widgets: List[ctk.CTkBaseClass] = []
        self.alarm_widgets: List[ctk.CTkBaseClass] = []
        
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
        
        # Main content (3 columns: Alarm Updates | Currently Sending | Recently Sent)
        self._create_main_content()
    
    def _create_header(self):
        """Create header with status and controls"""
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
        
        # Title
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
        
        # Status indicators row
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
        
        # Reset WhatsApp button
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
        
        # Right side - Control buttons
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.pack(side="right", padx=25, pady=20)
        
        # Start/Stop button
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
        """Create statistics cards section"""
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", padx=25, pady=15)
        
        # Configure columns for responsive layout
        for i in range(6):
            stats_frame.grid_columnconfigure(i, weight=1, uniform="stat")
        
        # Stat cards
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
        """Create main content area - 2 rows"""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 20))
        
        # Configure grid: 2 rows
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=0)  # Currently Sending - fixed height
        content.grid_rowconfigure(1, weight=1)  # Bottom row - expandable
        
        # ROW 1 - Currently Sending (full width, centered)
        self._create_currently_sending_section(content)
        
        # ROW 2 - Create container for 3 columns
        bottom_row = ctk.CTkFrame(content, fg_color="transparent")
        bottom_row.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        
        # Configure 3 columns for bottom row
        bottom_row.grid_columnconfigure(0, weight=1)
        bottom_row.grid_columnconfigure(1, weight=1)
        bottom_row.grid_columnconfigure(2, weight=1)
        bottom_row.grid_rowconfigure(0, weight=1)
        
        # LEFT - Alarm Updates
        self._create_alarm_updates_section(bottom_row)
        
        # MIDDLE - In Queue
        self._create_in_queue_section(bottom_row)
        
        # RIGHT - Recently Sent
        self._create_recently_sent_section(bottom_row)
    
    def _create_alarm_updates_section(self, parent):
        """Create alarm updates section"""
        container = ctk.CTkFrame(
            parent,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        
        title = ctk.CTkLabel(
            header,
            text="🔔 Alarm Updates",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left")
        
        # Scrollable frame for alarm updates
        self.alarm_updates_list = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent"
        )
        self.alarm_updates_list.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # Initial message
        self._show_alarm_empty_state()
    
    def _create_currently_sending_section(self, parent):
        """Create currently sending section - full width horizontal"""
        container = ctk.CTkFrame(
            parent,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER,
            height=100
        )
        container.grid(row=0, column=0, sticky="ew", padx=0)
        container.grid_propagate(False)
        
        # Horizontal layout
        content = ctk.CTkFrame(container, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Title on left
        title = ctk.CTkLabel(
            content,
            text="📤 Currently Sending:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left", padx=(0, 20))
        
        # Content area (horizontal)
        self.currently_sending_frame = ctk.CTkFrame(
            content,
            fg_color="transparent"
        )
        self.currently_sending_frame.pack(side="left", fill="both", expand=True)
        
        # Initial message
        self._show_sending_empty_state()
    
    def _create_recently_sent_section(self, parent):
        """Create recently sent section"""
        container = ctk.CTkFrame(
            parent,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        container.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        
        title = ctk.CTkLabel(
            header,
            text="✅ Recently Sent",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left")
        
        self.sent_count_label = ctk.CTkLabel(
            header,
            text="0",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.SUCCESS
        )
        self.sent_count_label.pack(side="right", padx=(10, 0))
        
        self.clear_sent_btn = ctk.CTkButton(
            header,
            text="Clear",
            font=ctk.CTkFont(size=11),
            fg_color=Colors.BG_LIGHT,
            hover_color=Colors.BG_MEDIUM,
            width=60,
            height=28,
            command=self._clear_recently_sent
        )
        self.clear_sent_btn.pack(side="right")
        
        # Scrollable frame for sent messages
        self.recently_sent_list = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent"
        )
        self.recently_sent_list.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # Initial message
        self._show_sent_empty_state()
    
    # Empty states
    def _show_alarm_empty_state(self):
        """Show empty state for alarm updates"""
        for widget in self.alarm_updates_list.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(
            self.alarm_updates_list,
            text="No alarm updates yet",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        ).pack(pady=50)
    
    def _show_sending_empty_state(self):
        """Show empty state for currently sending"""
        for widget in self.currently_sending_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(
            self.currently_sending_frame,
            text="Nothing sending",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_MUTED
        ).pack(side="left")
    
    def _show_sent_empty_state(self):
        """Show empty state for recently sent"""
        for widget in self.recently_sent_list.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(
            self.recently_sent_list,
            text="No messages sent yet",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        ).pack(pady=50)
    
    # Update methods
    def add_alarm_update(self, alarm_type: str, count: int = 1):
        """Add or update alarm in the updates list"""
        def _update():
            if not hasattr(self, 'alarm_updates_list'):
                return
            
            # Update count
            if alarm_type in self._alarm_counts:
                self._alarm_counts[alarm_type] += count
            else:
                self._alarm_counts[alarm_type] = count
            
            # Rebuild the list
            self._refresh_alarm_updates()
        
        try:
            self.after(0, _update)
        except:
            pass
    
    def _refresh_alarm_updates(self):
        """Refresh the alarm updates display with high-performance widget pooling"""
        if not hasattr(self, 'alarm_updates_list'):
            return
            
        if not self._alarm_counts:
            self._show_alarm_empty_state()
            # Hide all pooled widgets
            for w in self.alarm_widgets:
                w.pack_forget()
            return

        # Ensure empty state message is hidden if we have data
        for w in self.alarm_updates_list.winfo_children():
            if isinstance(w, ctk.CTkLabel) and w.cget("text") == "No new alarm updates":
                w.pack_forget()

        # Sort by count (descending)
        sorted_alarms = sorted(self._alarm_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Display limit
        data_to_show = sorted_alarms[:20]

        for i, (alarm_type, count) in enumerate(data_to_show):
            if i < len(self.alarm_widgets):
                # REUSE: Update existing widget
                item_frame = self.alarm_widgets[i]
                item_frame.pack(fill="x", padx=5, pady=4)
                
                # Update labels
                # Structure: [type_label, count_frame]
                # count_frame structure: [count_label]
                children = item_frame.winfo_children()
                if len(children) >= 2:
                    children[0].configure(text=alarm_type)
                    
                    # Inside count_frame (index 1) which is a CTkFrame
                    # But CTkLabel inside frame is accessible via children of children
                    count_children = children[1].winfo_children()
                    if count_children:
                        count_children[0].configure(text=str(count))
            else:
                # CREATE: New widget
                item_frame = ctk.CTkFrame(
                    self.alarm_updates_list,
                    fg_color=(("gray90", "gray20")),
                    corner_radius=6
                )
                item_frame.pack(fill="x", padx=5, pady=4)
                self.alarm_widgets.append(item_frame)
                
                # Alarm type
                type_label = ctk.CTkLabel(
                    item_frame,
                    text=alarm_type,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=Colors.TEXT_PRIMARY,
                    anchor="w"
                )
                type_label.pack(side="left", fill="x", expand=True, padx=12, pady=10)
                
                # Count badge
                count_frame = ctk.CTkFrame(
                    item_frame,
                    fg_color=Colors.ACCENT_ORANGE,
                    corner_radius=10,
                    width=45,
                    height=22
                )
                count_frame.pack(side="right", padx=12)
                count_frame.pack_propagate(False)
                
                count_label = ctk.CTkLabel(
                    count_frame,
                    text=str(count),
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="white"
                )
                count_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Hide excess widgets
        for i in range(len(data_to_show), len(self.alarm_widgets)):
            self.alarm_widgets[i].pack_forget()
    
    def _create_in_queue_section(self, parent):
        """Create in queue section"""
        container = ctk.CTkFrame(
            parent,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        container.grid(row=0, column=1, sticky="nsew", padx=5)
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        
        title = ctk.CTkLabel(
            header,
            text="📋 In Queue",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left")
        
        self.queue_count_label = ctk.CTkLabel(
            header,
            text="0",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.ACCENT_BLUE
        )
        self.queue_count_label.pack(side="right")
        
        # Scrollable frame for queue
        self.queue_list = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent"
        )
        self.queue_list.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # Initial message
        self._show_queue_empty_state()
    
    def _show_queue_empty_state(self):
        """Show empty state for queue"""
        for widget in self.queue_list.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(
            self.queue_list,
            text="No messages in queue",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        ).pack(pady=50)
    
    def update_currently_sending(self, alarm_type: str = None, group_name: str = None):
        """Update currently sending display - horizontal layout"""
        def _update():
            if not hasattr(self, 'currently_sending_frame'):
                return
            
            # Clear current
            for widget in self.currently_sending_frame.winfo_children():
                widget.destroy()
            
            if not alarm_type or not group_name:
                self._show_sending_empty_state()
                return
            
            # Show sending info horizontally
            # Alarm type
            type_label = ctk.CTkLabel(
                self.currently_sending_frame,
                text=f"📨 {alarm_type}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=Colors.TEXT_PRIMARY
            )
            type_label.pack(side="left", padx=(0, 10))
            
            # Arrow
            arrow_label = ctk.CTkLabel(
                self.currently_sending_frame,
                text="→",
                font=ctk.CTkFont(size=14),
                text_color=Colors.TEXT_MUTED
            )
            arrow_label.pack(side="left", padx=5)
            
            # Group name
            group_label = ctk.CTkLabel(
                self.currently_sending_frame,
                text=group_name,
                font=ctk.CTkFont(size=13),
                text_color=Colors.TEXT_SECONDARY
            )
            group_label.pack(side="left", padx=(10, 15))
            
            # Time
            time_label = ctk.CTkLabel(
                self.currently_sending_frame,
                text=datetime.now().strftime("%H:%M:%S"),
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_MUTED
            )
            time_label.pack(side="left")
        
        try:
            self.after(0, _update)
        except:
            pass
    
    def update_queue(self, queue_data: list):
        """Update queue list with high-performance widget pooling"""
        def _update():
            if not hasattr(self, 'queue_list'):
                return

            # DATA DIFFING: Skip if data hasn't changed
            if hasattr(self, '_last_queue_data') and self._last_queue_data == queue_data:
                return
            self._last_queue_data = queue_data.copy() if queue_data else []
            
            # Update count
            count = len(queue_data) if queue_data else 0
            if hasattr(self, 'queue_count_label'):
                self.queue_count_label.configure(text=str(count))
            
            if not queue_data:
                self._show_queue_empty_state()
                # Hide all pooled widgets
                for w in self.queue_widgets:
                    w.pack_forget()
                return

            # Ensure empty state message is hidden if we have data
            for w in self.queue_list.winfo_children():
                if isinstance(w, ctk.CTkLabel) and w.cget("text") == "No messages in queue":
                    w.pack_forget()

            # Process data (Max 20)
            data_to_show = queue_data[:20]
            
            # Update existing or create new widgets
            for i, item in enumerate(data_to_show):
                alarm_type = item.get('alarm_type', 'Unknown')
                group_name = item.get('group_name', 'Unknown')
                
                if i < len(self.queue_widgets):
                    # REUSE: Update existing widget
                    frame = self.queue_widgets[i]
                    frame.pack(fill="x", padx=5, pady=3)
                    
                    # Update labels (assuming they were stored as attributes or found by index)
                    # For safety, let's find them or store them next time. 
                    # For now, let's re-configure the labels by index.
                    labels = [w for w in frame.winfo_children() if isinstance(w, ctk.CTkLabel)]
                    if len(labels) >= 2:
                        labels[0].configure(text=alarm_type)
                        labels[1].configure(text=f"→ {group_name}")
                else:
                    # CREATE: New widget
                    item_frame = ctk.CTkFrame(
                        self.queue_list,
                        fg_color=(("gray90", "gray20")),
                        corner_radius=6 # Reduced for performance
                    )
                    item_frame.pack(fill="x", padx=5, pady=3)
                    
                    type_label = ctk.CTkLabel(
                        item_frame,
                        text=alarm_type,
                        font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=Colors.TEXT_PRIMARY,
                        anchor="w"
                    )
                    type_label.pack(fill="x", padx=12, pady=(6, 1))
                    
                    group_label = ctk.CTkLabel(
                        item_frame,
                        text=f"→ {group_name}",
                        font=ctk.CTkFont(size=10),
                        text_color=Colors.TEXT_MUTED,
                        anchor="w"
                    )
                    group_label.pack(fill="x", padx=12, pady=(0, 6))
                    
                    self.queue_widgets.append(item_frame)
            
            # Hide excess widgets
            for i in range(len(data_to_show), len(self.queue_widgets)):
                self.queue_widgets[i].pack_forget()
        
        try:
            self.after(0, _update)
        except:
            pass
    
    def add_recently_sent(self, alarm_type: str, group_name: str, success: bool = True):
        """Add a sent message to recently sent list"""
        def _update():
            if not hasattr(self, 'recently_sent_list'):
                return
            
            # Add to list (keep max 20)
            self._recent_sent.insert(0, {
                'alarm_type': alarm_type,
                'group_name': group_name,
                'success': success,
                'time': datetime.now().strftime("%H:%M:%S")
            })
            
            if len(self._recent_sent) > 20:
                self._recent_sent = self._recent_sent[:20]
            
            # Update count
            self.sent_count_label.configure(text=str(len(self._recent_sent)))
            
            # Rebuild list
            self._refresh_recently_sent()
        
        try:
            self.after(0, _update)
        except:
            pass
    
    def _refresh_recently_sent(self):
        """Refresh recently sent display with high-performance widget pooling"""
        if not hasattr(self, 'recently_sent_list'):
            return
            
        if not self._recent_sent:
            self._show_sent_empty_state()
            # Hide all pooled widgets
            for w in self.sent_widgets:
                w.grid_forget() # or pack_forget depending on what was used
                w.pack_forget()
            return

        # Ensure empty state message is hidden if we have data
        for w in self.recently_sent_list.winfo_children():
            if isinstance(w, ctk.CTkLabel) and w.cget("text") == "No messages sent yet":
                w.pack_forget()

        # Update existing or create new widgets
        for i, item in enumerate(self._recent_sent):
            # Status icon
            icon = "✅" if item['success'] else "❌"
            
            if i < len(self.sent_widgets):
                # REUSE: Update existing widget
                item_frame = self.sent_widgets[i]
                item_frame.pack(fill="x", padx=5, pady=3)
                
                # Update sub-widgets
                # Success Icon (index 0)
                # Info container (index 1) which has two labels
                # Time label (index 2)
                children = item_frame.winfo_children()
                if len(children) >= 3:
                    # Icon
                    children[0].configure(text=icon)
                    
                    # Info Labels
                    info_children = children[1].winfo_children()
                    if len(info_children) >= 2:
                        info_children[0].configure(text=item['alarm_type'])
                        info_children[1].configure(text=f"→ {item['group_name']}")
                    
                    # Time
                    children[2].configure(text=item['time'])
            else:
                # CREATE: New widget
                item_frame = ctk.CTkFrame(
                    self.recently_sent_list,
                    fg_color=(("gray90", "gray20")),
                    corner_radius=6
                )
                item_frame.pack(fill="x", padx=5, pady=3)
                self.sent_widgets.append(item_frame)
                
                # Status icon
                icon_label = ctk.CTkLabel(
                    item_frame,
                    text=icon,
                    font=ctk.CTkFont(size=14)
                )
                icon_label.pack(side="left", padx=(10, 5), pady=8)
                
                # Info container
                info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
                info_frame.pack(side="left", fill="x", expand=True, padx=(5, 10), pady=8)
                
                # Alarm type
                type_label = ctk.CTkLabel(
                    info_frame,
                    text=item['alarm_type'],
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=Colors.TEXT_PRIMARY,
                    anchor="w"
                )
                type_label.pack(anchor="w", fill="x")
                
                # Group name
                group_label = ctk.CTkLabel(
                    info_frame,
                    text=f"→ {item['group_name']}",
                    font=ctk.CTkFont(size=10),
                    text_color=Colors.TEXT_MUTED,
                    anchor="w"
                )
                group_label.pack(anchor="w", fill="x")
                
                # Time
                time_label = ctk.CTkLabel(
                    item_frame,
                    text=item['time'],
                    font=ctk.CTkFont(size=9),
                    text_color=Colors.TEXT_MUTED
                )
                time_label.pack(side="right", padx=10)
        
        # Hide excess widgets
        for i in range(len(self._recent_sent), len(self.sent_widgets)):
            self.sent_widgets[i].pack_forget()
    
    def _clear_recently_sent(self):
        """Clear recently sent messages"""
        self._recent_sent.clear()
        self._refresh_recently_sent()
        if hasattr(self, 'sent_count_label'):
            self.sent_count_label.configure(text="0")
    
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
        """Handle reset WhatsApp button"""
        from automation_controller import automation_controller
        success = automation_controller.reset_whatsapp()
        if success:
            print("WhatsApp session reset successfully")
    
    # State management
    def set_automation_running(self, running: bool):
        """Update UI for automation running state"""
        if running:
            self.automation_status.set_status("Running", Colors.SUCCESS)
            self.start_btn.configure(text="⏹ Stop")
            self.pause_btn.configure(state="normal")
            self.check_btn.configure(state="normal")
            self.send_btn.configure(state="normal")
        else:
            self.automation_status.set_status("Stopped", Colors.ERROR)
            self.start_btn.configure(text="▶ Start")
            self.pause_btn.configure(state="disabled")
            self.check_btn.configure(state="disabled")
            self.send_btn.configure(state="disabled")
    
    def set_automation_paused(self, paused: bool):
        """Update UI for paused state"""
        if paused:
            self.automation_status.set_status("Paused", Colors.WARNING)
            self.pause_btn.configure(text="▶ Resume")
        else:
            self.automation_status.set_status("Running", Colors.SUCCESS)
            self.pause_btn.configure(text="⏸ Pause")
    
    def set_automation_error(self):
        """Update UI for error state"""
        self.automation_status.set_status("Error", Colors.ERROR)
        self.start_btn.configure(state="normal")
    
    def update_portal_status(self, connected: bool, logged_in: bool):
        """Update portal status"""
        if logged_in:
            self.portal_status.set_status("Logged In", Colors.SUCCESS)
        elif connected:
            self.portal_status.set_status("Connected", Colors.WARNING)
        else:
            self.portal_status.set_status("Disconnected", Colors.ERROR)
    
    def update_whatsapp_status(self, status: str):
        """Update WhatsApp status"""
        if status == "Connected":
            self.whatsapp_status.set_status("Connected", Colors.SUCCESS)
        else:
            self.whatsapp_status.set_status("Disconnected", Colors.ERROR)
    
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
    
    # Compatibility with old dashboard methods
    def log(self, message: str, level: str = "INFO"):
        """Compatibility - does nothing in new dashboard"""
        pass
    
    def update_stats_bar_event(self, data: Dict[str, Any]):
        """Handle stats update with current sending info"""
        def _update():
            try:
                # DATA DIFFING: Skip if data hasn't changed
                if hasattr(self, '_last_stats_event_data') and self._last_stats_event_data == data:
                    return
                self._last_stats_event_data = data.copy() if data else {}

                # Update currently sending
                current = data.get('current')
                if current:
                    alarm_type = current.get('alarm_type', 'Unknown')
                    group_name = current.get('group_name', 'Unknown')
                    print(f"DEBUG: Currently sending - {alarm_type} -> {group_name}")
                    self.update_currently_sending(alarm_type, group_name)
                else:
                    self.update_currently_sending(None, None)
                
                # Update queue
                queue_data = data.get('queue_preview', [])
                if queue_data:
                    print(f"DEBUG: Received {len(queue_data)} queue items")
                    self.update_queue(queue_data)
                
                # Replace entire sent list with new data
                sent_data = data.get('sent_recent', [])
                if sent_data:
                    print(f"DEBUG: Received {len(sent_data)} sent items")
                    # Clear and rebuild
                    self._recent_sent = []
                    for item in sent_data:
                        alarm_type = item.get('alarm_type', 'Unknown')
                        group_name = item.get('group_name', 'Unknown')
                        success = item.get('success', True)
                        timestamp = item.get('timestamp')
                        
                        # Format time
                        if timestamp:
                            try:
                                from datetime import datetime
                                if isinstance(timestamp, str):
                                    dt = datetime.fromisoformat(timestamp)
                                else:
                                    dt = timestamp
                                time_str = dt.strftime("%H:%M:%S")
                            except:
                                time_str = datetime.now().strftime("%H:%M:%S")
                        else:
                            time_str = datetime.now().strftime("%H:%M:%S")
                        
                        self._recent_sent.append({
                            'alarm_type': alarm_type,
                            'group_name': group_name,
                            'success': success,
                            'time': time_str
                        })
                    
                    # Refresh display
                    self._refresh_recently_sent()
                    self.sent_count_label.configure(text=str(len(self._recent_sent)))
            except Exception as e:
                print(f"Error updating stats bar: {e}")
                import traceback
                traceback.print_exc()
        
        try:
            self.after(0, _update)
        except:
            pass
