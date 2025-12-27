"""
GUI Logs View
View and manage application logs
"""

import customtkinter as ctk
from typing import Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from gui_components import Colors, ActionButton, SearchBox
from config import LOGS_DIR
from logger_module import logger


class LogsView(ctk.CTkFrame):
    """View for browsing application logs"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        self._create_layout()
        self._load_logs()
        
        # Register for real-time updates
        logger.add_callback(self._on_new_log)
    
    def _on_new_log(self, entry: str, level: str):
        """Handle new log entry from logger"""
        def _update():
            # Check if it matches current filter
            current_level = self.level_var.get()
            if current_level != "All Levels" and level != current_level:
                return
            
            # Check if it's today
            current_date_filter = self.date_var.get()
            if current_date_filter != "Today" and current_date_filter != "All":
                return
            
            self.log_text.configure(state="normal")
            self._add_log_entry(entry)
            self.log_text.configure(state="disabled")
            self.log_text.see("end")
            
            # Update count
            try:
                count_text = self.stats_label.cget("text")
                count = int(count_text.split()[0])
                self.stats_label.configure(text=f"{count + 1} log entries")
            except:
                pass
                
        self.after(0, _update)
    
    def _create_layout(self):
        """Create the layout"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        self._create_header()
        
        # Content
        self._create_content()
    
    def _create_header(self):
        """Create header"""
        header = ctk.CTkFrame(self, fg_color=Colors.BG_MEDIUM, corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        
        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)
        
        # Title
        title = ctk.CTkLabel(
            inner,
            text="📜 Application Logs",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left")
        
        # Controls
        controls = ctk.CTkFrame(inner, fg_color="transparent")
        controls.pack(side="right")
        
        # Date filter
        self.date_var = ctk.StringVar(value="Today")
        date_menu = ctk.CTkOptionMenu(
            controls,
            values=["Today", "Yesterday", "Last 7 Days", "All"],
            variable=self.date_var,
            command=self._on_date_change,
            width=120,
            fg_color=Colors.BG_LIGHT,
            button_color=Colors.PRIMARY,
            button_hover_color=Colors.PRIMARY_DARK
        )
        date_menu.pack(side="left", padx=5)
        
        # Level filter
        self.level_var = ctk.StringVar(value="All Levels")
        level_menu = ctk.CTkOptionMenu(
            controls,
            values=["All Levels", "INFO", "SUCCESS", "WARNING", "ERROR", "ALARM"],
            variable=self.level_var,
            command=self._on_level_change,
            width=120,
            fg_color=Colors.BG_LIGHT,
            button_color=Colors.PRIMARY,
            button_hover_color=Colors.PRIMARY_DARK
        )
        level_menu.pack(side="left", padx=5)
        
        # Refresh button
        refresh_btn = ActionButton(
            controls,
            text="Refresh",
            icon="🔄",
            color=Colors.INFO,
            command=self._load_logs,
            width=100
        )
        refresh_btn.pack(side="left", padx=5)
        
        # Clear button
        clear_btn = ActionButton(
            controls,
            text="Clear Today",
            icon="🗑️",
            color=Colors.ERROR,
            command=self._clear_today_logs,
            width=120
        )
        clear_btn.pack(side="left", padx=5)
    
    def _create_content(self):
        """Create content area"""
        content = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=10)
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        # Log viewer
        self.log_text = ctk.CTkTextbox(
            content,
            fg_color=Colors.BG_DARK,
            text_color=Colors.TEXT_SECONDARY,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Stats bar
        stats_bar = ctk.CTkFrame(content, fg_color=Colors.BG_LIGHT, height=30)
        stats_bar.pack(fill="x", padx=10, pady=(0, 10))
        stats_bar.pack_propagate(False)
        
        self.stats_label = ctk.CTkLabel(
            stats_bar,
            text="0 log entries",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        self.stats_label.pack(side="left", padx=10, pady=5)
    
    def _load_logs(self):
        """Load log files"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        
        log_files = self._get_log_files()
        
        all_entries = []
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    entries = f.readlines()
                    all_entries.extend(entries)
            except Exception as e:
                pass
        
        # Filter by level
        level = self.level_var.get()
        if level != "All Levels":
            all_entries = [e for e in all_entries if f"[{level}]" in e]
        
        # Display
        for entry in all_entries[-1000:]:  # Last 1000 entries
            self._add_log_entry(entry)
        
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        
        self.stats_label.configure(text=f"{len(all_entries)} log entries")
    
    def _get_log_files(self) -> List[Path]:
        """Get log files based on date filter"""
        date_filter = self.date_var.get()
        today = datetime.now().date()
        
        files = []
        
        if date_filter == "Today":
            filename = f"alarm_log_{today.strftime('%Y-%m-%d')}.txt"
            path = LOGS_DIR / filename
            if path.exists():
                files.append(path)
        
        elif date_filter == "Yesterday":
            yesterday = today - timedelta(days=1)
            filename = f"alarm_log_{yesterday.strftime('%Y-%m-%d')}.txt"
            path = LOGS_DIR / filename
            if path.exists():
                files.append(path)
        
        elif date_filter == "Last 7 Days":
            for i in range(7):
                date = today - timedelta(days=i)
                filename = f"alarm_log_{date.strftime('%Y-%m-%d')}.txt"
                path = LOGS_DIR / filename
                if path.exists():
                    files.append(path)
        
        else:  # All
            files = list(LOGS_DIR.glob("alarm_log_*.txt"))
        
        return sorted(files)
    
    def _add_log_entry(self, entry: str):
        """Add a log entry with coloring"""
        entry = entry.strip()
        if not entry:
            return
        
        # Determine color based on level
        if "[ERROR]" in entry:
            color = Colors.ERROR
        elif "[SUCCESS]" in entry:
            color = Colors.SUCCESS
        elif "[WARNING]" in entry:
            color = Colors.WARNING
        elif "[ALARM]" in entry:
            color = Colors.ACCENT_ORANGE
        else:
            color = Colors.TEXT_SECONDARY
        
        self.log_text.insert("end", entry + "\n")
    
    def _on_date_change(self, value):
        """Handle date filter change"""
        self._load_logs()
    
    def _on_level_change(self, value):
        """Handle level filter change"""
        self._load_logs()
    
    def _clear_today_logs(self):
        """Clear today's logs"""
        today = datetime.now().date()
        filename = f"alarm_log_{today.strftime('%Y-%m-%d')}.txt"
        path = LOGS_DIR / filename
        
        try:
            if path.exists():
                path.unlink()
            self._load_logs()
        except Exception as e:
            pass