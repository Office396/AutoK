"""
GUI Components
Reusable UI components for the application
"""

import customtkinter as ctk
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
from enum import Enum


# Color scheme
class Colors:
    """Application color scheme - Optimized"""
    # Primary colors
    PRIMARY = "#2196F3"  # Brighter blue
    PRIMARY_DARK = "#1976D2"
    PRIMARY_LIGHT = "#64B5F6"
    
    # Status colors
    SUCCESS = "#4CAF50"
    WARNING = "#FFC107"  # Brighter warning
    ERROR = "#F44336"
    INFO = "#03A9F4"
    
    # Background colors - Slightly lighter for better contrast
    BG_DARK = "#121212"
    BG_MEDIUM = "#1E1E1E"
    BG_LIGHT = "#2D2D2D"
    BG_CARD = "#252525"
    
    # Text colors
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#B3B3B3"
    TEXT_MUTED = "#808080"
    
    # Border colors
    BORDER = "#404040"
    BORDER_LIGHT = "#505050"
    
    # Accent colors
    ACCENT_BLUE = "#00BCD4"
    ACCENT_PURPLE = "#AB47BC"
    ACCENT_ORANGE = "#FF7043"
    ACCENT_GREEN = "#66BB6A"


class StatusIndicator(ctk.CTkFrame):
    """A status indicator with icon and label"""
    
    def __init__(
        self,
        parent,
        label: str,
        initial_status: str = "Disconnected",
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.label_text = label
        
        # Status dot
        self.dot_frame = ctk.CTkFrame(
            self,
            width=12,
            height=12,
            corner_radius=6,
            fg_color=Colors.ERROR
        )
        self.dot_frame.pack(side="left", padx=(0, 8))
        self.dot_frame.pack_propagate(False)
        
        # Label
        self.label = ctk.CTkLabel(
            self,
            text=f"{label}: {initial_status}",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY
        )
        self.label.pack(side="left")
    
    def set_status(self, status: str, is_good: bool = True):
        """Update status"""
        color = Colors.SUCCESS if is_good else Colors.ERROR
        self.dot_frame.configure(fg_color=color)
        self.label.configure(text=f"{self.label_text}: {status}")
    
    def set_warning(self, status: str):
        """Set warning status"""
        self.dot_frame.configure(fg_color=Colors.WARNING)
        self.label.configure(text=f"{self.label_text}: {status}")


class StatCard(ctk.CTkFrame):
    """A card displaying a statistic"""
    
    def __init__(
        self,
        parent,
        title: str,
        value: str = "0",
        icon: str = "📊",
        color: str = Colors.PRIMARY,
        **kwargs
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_CARD,
            corner_radius=10,
            **kwargs
        )
        
        self.color = color
        
        # Icon and title row
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        icon_label = ctk.CTkLabel(
            title_frame,
            text=icon,
            font=ctk.CTkFont(size=20)
        )
        icon_label.pack(side="left")
        
        title_label = ctk.CTkLabel(
            title_frame,
            text=title,
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY
        )
        title_label.pack(side="left", padx=(10, 0))
        
        # Value
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=color
        )
        self.value_label.pack(padx=15, pady=(5, 15), anchor="w")
    
    def set_value(self, value: str):
        """Update the value"""
        self.value_label.configure(text=value)
    
    def set_color(self, color: str):
        """Update the color"""
        self.value_label.configure(text_color=color)


class AlarmTable(ctk.CTkScrollableFrame):
    """A table displaying alarms"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_CARD,
            corner_radius=10,
            **kwargs
        )
        
        self.rows: List[ctk.CTkFrame] = []
        self.max_rows = 2000
        
        # Header
        self._create_header()
    
    def _create_header(self):
        """Create table header"""
        header = ctk.CTkFrame(self, fg_color=Colors.BG_LIGHT, corner_radius=5)
        header.pack(fill="x", padx=5, pady=5)
        
        columns = [
            ("Time", 120),
            ("Type", 150),
            ("Site Code", 100),
            ("Site Name", 200),
            ("MBU", 100),
            ("Status", 80)
        ]
        
        for col_name, width in columns:
            label = ctk.CTkLabel(
                header,
                text=col_name,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Colors.TEXT_PRIMARY,
                width=width
            )
            label.pack(side="left", padx=5, pady=8)
    
    def add_alarm(self, alarm_data: Dict, source: str = None):
        """Add an alarm row"""
        row = ctk.CTkFrame(self, fg_color="transparent", height=35)
        
        # Store source on the row widget for later filtering
        row.source = source
        
        # Insert at the top (visually)
        if self.rows:
            # Pack before the first row
            row.pack(fill="x", padx=5, pady=2, before=self.rows[0])
            # Insert at beginning of list
            self.rows.insert(0, row)
        else:
            # First row
            row.pack(fill="x", padx=5, pady=2)
            self.rows.append(row)
        
        row.pack_propagate(False)
        
        # Alternate row colors
        row.configure(fg_color=Colors.BG_MEDIUM if len(self.rows) % 2 == 0 else "transparent")
        
        # Time
        time_label = ctk.CTkLabel(
            row,
            text=alarm_data.get('time', ''),
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY,
            width=120
        )
        time_label.pack(side="left", padx=5)
        
        # Alarm Type
        alarm_type = alarm_data.get('type', '')
        type_color = self._get_alarm_color(alarm_type)
        type_label = ctk.CTkLabel(
            row,
            text=alarm_type,
            font=ctk.CTkFont(size=11),
            text_color=type_color,
            width=150
        )
        type_label.pack(side="left", padx=5)
        
        # Site Code
        code_label = ctk.CTkLabel(
            row,
            text=alarm_data.get('site_code', ''),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            width=100
        )
        code_label.pack(side="left", padx=5)
        
        # Site Name
        name_label = ctk.CTkLabel(
            row,
            text=alarm_data.get('site_name', '')[:30],
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY,
            width=200
        )
        name_label.pack(side="left", padx=5)
        
        # MBU
        mbu_label = ctk.CTkLabel(
            row,
            text=alarm_data.get('mbu', ''),
            font=ctk.CTkFont(size=11),
            text_color=Colors.ACCENT_BLUE,
            width=100
        )
        mbu_label.pack(side="left", padx=5)
        
        # Status
        status = alarm_data.get('status', 'Pending')
        status_color = Colors.SUCCESS if status == 'Sent' else Colors.WARNING
        status_label = ctk.CTkLabel(
            row,
            text=status,
            font=ctk.CTkFont(size=11),
            text_color=status_color,
            width=80
        )
        status_label.pack(side="left", padx=5)
        
        # Remove old rows if exceeding max (pop from end)
        if len(self.rows) > self.max_rows:
            old_row = self.rows.pop() # Pop last item (oldest)
            old_row.destroy()
    
    def remove_alarms_by_source(self, source: str):
        """Remove all alarms from a specific source"""
        if not source:
            return
            
        # Create new list for keeping
        keep_rows = []
        for row in self.rows:
            if hasattr(row, 'source') and row.source == source:
                row.destroy()
            else:
                keep_rows.append(row)
        
        self.rows = keep_rows
    
    def _get_alarm_color(self, alarm_type: str) -> str:
        """Get color for alarm type"""
        alarm_lower = alarm_type.lower()
        if 'csl' in alarm_lower:
            return Colors.ERROR
        elif 'voltage' in alarm_lower or 'battery' in alarm_lower:
            return Colors.WARNING
        elif 'rf unit' in alarm_lower:
            return Colors.ACCENT_PURPLE
        else:
            return Colors.INFO
    
    def clear(self):
        """Clear all rows"""
        for row in self.rows:
            row.destroy()
        self.rows.clear()


class LogViewer(ctk.CTkTextbox):
    """A log viewer with colored output"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_DARK,
            text_color=Colors.TEXT_SECONDARY,
            font=ctk.CTkFont(family="Consolas", size=11),
            **kwargs
        )
        
        self.configure(state="disabled")
        self.max_lines = 500
        self.line_count = 0
    
    def log(self, message: str, level: str = "INFO"):
        """Add a log entry"""
        self.configure(state="normal")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color based on level
        if level == "ERROR":
            prefix = "❌"
        elif level == "SUCCESS":
            prefix = "✅"
        elif level == "WARNING":
            prefix = "⚠️"
        else:
            prefix = "ℹ️"
        
        log_line = f"[{timestamp}] {prefix} {message}\n"
        
        self.insert("end", log_line)
        self.line_count += 1
        
        # Remove old lines if exceeding max
        if self.line_count > self.max_lines:
            self.delete("1.0", "2.0")
            self.line_count -= 1
        
        self.see("end")
        self.configure(state="disabled")
    
    def clear(self):
        """Clear the log"""
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.line_count = 0
        self.configure(state="disabled")


class SettingsEntry(ctk.CTkFrame):
    """A settings entry with label and input"""
    
    def __init__(
        self,
        parent,
        label: str,
        default_value: str = "",
        is_password: bool = False,
        width: int = 200,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        # Label
        self.label = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY,
            width=150,
            anchor="w"
        )
        self.label.pack(side="left", padx=(0, 10))
        
        # Entry
        self.entry = ctk.CTkEntry(
            self,
            width=width,
            font=ctk.CTkFont(size=12),
            fg_color=Colors.BG_MEDIUM,
            border_color=Colors.BORDER,
            show="•" if is_password else ""
        )
        self.entry.pack(side="left")
        
        if default_value:
            self.entry.insert(0, default_value)
    
    def get(self) -> str:
        """Get the entry value"""
        return self.entry.get()
    
    def set(self, value: str):
        """Set the entry value"""
        self.entry.delete(0, "end")
        self.entry.insert(0, value)


class TimingSlider(ctk.CTkFrame):
    """A slider for timing settings"""
    
    def __init__(
        self,
        parent,
        label: str,
        min_value: int = 0,
        max_value: int = 120,
        default_value: int = 30,
        unit: str = "min",
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.unit = unit
        
        # Label
        self.label = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY,
            width=180,
            anchor="w"
        )
        self.label.pack(side="left", padx=(0, 10))
        
        # Slider
        self.slider = ctk.CTkSlider(
            self,
            from_=min_value,
            to=max_value,
            number_of_steps=max_value - min_value,
            width=200,
            progress_color=Colors.PRIMARY,
            button_color=Colors.PRIMARY_LIGHT,
            command=self._on_change
        )
        self.slider.set(default_value)
        self.slider.pack(side="left", padx=(0, 10))
        
        # Value label
        self.value_label = ctk.CTkLabel(
            self,
            text=f"{default_value} {unit}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            width=60
        )
        self.value_label.pack(side="left")
    
    def _on_change(self, value):
        """Handle slider change"""
        int_value = int(value)
        self.value_label.configure(text=f"{int_value} {self.unit}")
    
    def get(self) -> int:
        """Get the slider value"""
        return int(self.slider.get())
    
    def set(self, value: int):
        """Set the slider value"""
        self.slider.set(value)
        self.value_label.configure(text=f"{value} {self.unit}")


class GroupMappingEntry(ctk.CTkFrame):
    """Entry for group name mapping"""
    
    def __init__(
        self,
        parent,
        mbu_name: str,
        group_name: str = "",
        **kwargs
    ):
        super().__init__(parent, fg_color=Colors.BG_MEDIUM, corner_radius=5, **kwargs)
        
        # MBU Label
        self.mbu_label = ctk.CTkLabel(
            self,
            text=mbu_name,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Colors.ACCENT_BLUE,
            width=100,
            anchor="w"
        )
        self.mbu_label.pack(side="left", padx=10, pady=8)
        
        # Arrow
        arrow = ctk.CTkLabel(
            self,
            text="→",
            font=ctk.CTkFont(size=14),
            text_color=Colors.TEXT_MUTED
        )
        arrow.pack(side="left", padx=5)
        
        # Group Entry
        self.group_entry = ctk.CTkEntry(
            self,
            width=250,
            font=ctk.CTkFont(size=12),
            fg_color=Colors.BG_DARK,
            border_color=Colors.BORDER,
            placeholder_text="WhatsApp Group Name"
        )
        self.group_entry.pack(side="left", padx=10, pady=8)
        
        if group_name:
            self.group_entry.insert(0, group_name)
    
    def get_mapping(self) -> tuple:
        """Get the MBU and group name"""
        return (self.mbu_label.cget("text"), self.group_entry.get())
    
    def set_group(self, group_name: str):
        """Set the group name"""
        self.group_entry.delete(0, "end")
        self.group_entry.insert(0, group_name)


class ActionButton(ctk.CTkButton):
    """A styled action button"""
    
    def __init__(
        self,
        parent,
        text: str,
        icon: str = "",
        color: str = Colors.PRIMARY,
        hover_color: str = None,
        **kwargs
    ):
        display_text = f"{icon} {text}" if icon else text
        hover = hover_color or Colors.PRIMARY_DARK
        
        super().__init__(
            parent,
            text=display_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=color,
            hover_color=hover,
            corner_radius=8,
            **kwargs
        )


class TabButton(ctk.CTkButton):
    """A tab navigation button"""
    
    def __init__(
        self,
        parent,
        text: str,
        icon: str = "",
        is_active: bool = False,
        command: Callable = None,
        **kwargs
    ):
        self.is_active = is_active
        display_text = f"{icon}  {text}" if icon else text
        
        super().__init__(
            parent,
            text=display_text,
            font=ctk.CTkFont(size=13),
            fg_color=Colors.PRIMARY if is_active else "transparent",
            hover_color=Colors.PRIMARY_DARK,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=8,
            anchor="w",
            command=command,
            **kwargs
        )
    
    def set_active(self, active: bool):
        """Set active state"""
        self.is_active = active
        self.configure(fg_color=Colors.PRIMARY if active else "transparent")


class ConfirmDialog(ctk.CTkToplevel):
    """A confirmation dialog"""
    
    def __init__(
        self,
        parent,
        title: str,
        message: str,
        on_confirm: Callable = None,
        on_cancel: Callable = None
    ):
        super().__init__(parent)
        
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        
        self.title(title)
        self.geometry("400x150")
        self.resizable(False, False)
        
        # Center on parent
        self.transient(parent)
        self.grab_set()
        
        # Configure
        self.configure(fg_color=Colors.BG_MEDIUM)
        
        # Message
        msg_label = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color=Colors.TEXT_PRIMARY,
            wraplength=350
        )
        msg_label.pack(pady=30)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        cancel_btn = ActionButton(
            btn_frame,
            text="Cancel",
            color=Colors.BG_LIGHT,
            hover_color=Colors.BG_CARD,
            command=self._cancel,
            width=100
        )
        cancel_btn.pack(side="left", padx=10)
        
        confirm_btn = ActionButton(
            btn_frame,
            text="Confirm",
            color=Colors.PRIMARY,
            command=self._confirm,
            width=100
        )
        confirm_btn.pack(side="left", padx=10)
    
    def _confirm(self):
        if self.on_confirm:
            self.on_confirm()
        self.destroy()
    
    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.destroy()


class ProgressIndicator(ctk.CTkFrame):
    """A progress indicator"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.progress = ctk.CTkProgressBar(
            self,
            width=200,
            height=10,
            progress_color=Colors.PRIMARY,
            fg_color=Colors.BG_DARK
        )
        self.progress.pack(side="left", padx=(0, 10))
        self.progress.set(0)
        
        self.label = ctk.CTkLabel(
            self,
            text="0%",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY
        )
        self.label.pack(side="left")
    
    def set_progress(self, value: float, text: str = None):
        """Set progress (0-1)"""
        self.progress.set(value)
        if text:
            self.label.configure(text=text)
        else:
            self.label.configure(text=f"{int(value * 100)}%")
    
    def set_indeterminate(self, running: bool):
        """Set indeterminate mode"""
        if running:
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")


class ToastNotification(ctk.CTkFrame):
    """A toast notification that appears and disappears"""
    
    def __init__(
        self,
        parent,
        message: str,
        notification_type: str = "info",
        duration: int = 3000
    ):
        # Color based on type
        if notification_type == "success":
            bg_color = Colors.SUCCESS
            icon = "✅"
        elif notification_type == "error":
            bg_color = Colors.ERROR
            icon = "❌"
        elif notification_type == "warning":
            bg_color = Colors.WARNING
            icon = "⚠️"
        else:
            bg_color = Colors.INFO
            icon = "ℹ️"
        
        super().__init__(
            parent,
            fg_color=bg_color,
            corner_radius=8
        )
        
        # Content
        content = ctk.CTkLabel(
            self,
            text=f"{icon}  {message}",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_PRIMARY
        )
        content.pack(padx=15, pady=10)
        
        # Auto-destroy after duration
        self.after(duration, self.destroy)


class SearchBox(ctk.CTkFrame):
    """A search box with icon"""
    
    def __init__(
        self,
        parent,
        placeholder: str = "Search...",
        on_search: Callable = None,
        **kwargs
    ):
        super().__init__(parent, fg_color=Colors.BG_MEDIUM, corner_radius=8, **kwargs)
        
        self.on_search = on_search
        
        # Search icon
        icon = ctk.CTkLabel(
            self,
            text="🔍",
            font=ctk.CTkFont(size=14)
        )
        icon.pack(side="left", padx=(10, 5))
        
        # Entry
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_width=0,
            width=200
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=5)
        
        # Bind enter key
        self.entry.bind("<Return>", self._on_enter)
    
    def _on_enter(self, event):
        if self.on_search:
            self.on_search(self.entry.get())
    
    def get(self) -> str:
        return self.entry.get()
    
    def clear(self):
        self.entry.delete(0, "end")