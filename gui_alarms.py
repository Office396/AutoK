"""
GUI Alarms View
Dedicated view for browsing recent alarms
"""

import customtkinter as ctk
from typing import Optional, Callable, Dict, List
from datetime import datetime

from gui_components import Colors, AlarmTable, ActionButton
from logger_module import logger


class AlarmsView(ctk.CTkFrame):
    """View for browsing recent alarms"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        self._create_layout()
    
    def _create_layout(self):
        """Create the alarms view layout"""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header section
        self._create_header()
        
        # Alarms table
        self._create_alarms_section()
    
    def _create_header(self):
        """Create header with title and controls"""
        header = ctk.CTkFrame(
            self,
            fg_color=Colors.SURFACE_1,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        header.grid(row=0, column=0, sticky="ew", padx=25, pady=(25, 15))
        
        # Content
        content = ctk.CTkFrame(header, fg_color="transparent")
        content.pack(fill="x", padx=25, pady=20)
        
        # Left side - Title
        title_frame = ctk.CTkFrame(content, fg_color="transparent")
        title_frame.pack(side="left")
        
        title = ctk.CTkLabel(
            title_frame,
            text="🔔 Recent Alarms",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left")
        
        subtitle = ctk.CTkLabel(
            title_frame,
            text="  •  View all processed alarms",
            font=ctk.CTkFont(size=14),
            text_color=Colors.TEXT_MUTED
        )
        subtitle.pack(side="left", padx=(10, 0))
        
        # Right side - Controls
        controls = ctk.CTkFrame(content, fg_color="transparent")
        controls.pack(side="right")
        
        # Refresh button
        self.refresh_btn = ActionButton(
            controls,
            text="Refresh",
            icon="🔄",
            color=Colors.INFO,
            hover_color="#1976D2",
            command=self._on_refresh,
            width=100,
            height=40
        )
        self.refresh_btn.pack(side="left", padx=5)
    
    def _create_alarms_section(self):
        """Create the alarms table section"""
        # Container
        container = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        container.grid(row=1, column=0, sticky="nsew", padx=25, pady=(0, 25))
        
        # Configure grid
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # Alarms table
        self.alarm_table = AlarmTable(container, height=600)
        self.alarm_table.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
    
    def _on_refresh(self):
        """Handle refresh button"""
        # Refresh will happen automatically through callbacks
        logger.info("Alarms view refreshed")
    
    # Public methods for adding/updating alarms
    def add_alarm(self, alarm_data: Dict):
        """Add an alarm to the table"""
        self.alarm_table.add_alarm(alarm_data)
    
    def update_alarms(self, alarms: List[Dict], source: str):
        """Update alarms from a specific source"""
        self.alarm_table._batch_update_alarms(alarms, source)
