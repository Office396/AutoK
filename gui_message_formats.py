"""
GUI Handle View (Message Formats & Excel Column Mapping)
Allows users to customize WhatsApp message formats and Excel column mappings
"""

import customtkinter as ctk
from typing import Optional, Callable

from gui_components import Colors, ActionButton
from config import settings


class SettingsEntry(ctk.CTkFrame):
    """A labeled entry widget"""
    
    def __init__(self, parent, label: str, width: int = 200, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.label = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY
        )
        self.label.pack(anchor="w")
        
        self.entry = ctk.CTkEntry(
            self,
            width=width,
            height=32,
            fg_color=Colors.BG_MEDIUM,
            border_color=Colors.BORDER
        )
        self.entry.pack(fill="x", pady=(5, 0))
    
    def get(self) -> str:
        return self.entry.get()
    
    def set(self, value: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)


class MessageFormatsView(ctk.CTkFrame):
    """Handle view - message format and Excel column customization"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        self.on_save: Optional[Callable] = None
        
        self._create_layout()
        self._load_formats()
    
    def _create_layout(self):
        """Create the layout"""
        # Title
        title = ctk.CTkLabel(
            self,
            text="📝 Handle Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(pady=20, padx=20, anchor="w")
        
        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Excel Column Mapping Section
        self._create_excel_column_section(content)
        
        # Help section
        self._create_help_section(content)
        
        # Format sections
        self._create_format_section(content, "MBU Format", "mbu", 
            "Format for MBU group messages (C1-LHR-01 to C1-LHR-08)")
        
        self._create_format_section(content, "Toggle Format", "toggle",
            "Format for toggle alarm messages")
        
        self._create_format_section(content, "B2S Format", "b2s",
            "Format for B2S group messages (ATL, Edotco, Enfrashare, Tawal)")
        
        self._create_format_section(content, "OMO Format", "omo",
            "Format for OMO group messages (Ufone, Telenor, CMpak)")
        
        # Save button
        self._create_save_button()
    
    def _create_excel_column_section(self, parent):
        """Create Excel column mapping section"""
        frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        frame.pack(fill="x", pady=(0, 20))
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)
        
        title = ctk.CTkLabel(
            inner,
            text="📊 Excel Column Mapping",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(anchor="w")
        
        desc = ctk.CTkLabel(
            inner,
            text="Configure which Excel column headers to look for when processing exported alarm data",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        desc.pack(anchor="w", pady=(2, 15))
        
        # Grid for entries
        grid_frame = ctk.CTkFrame(inner, fg_color="transparent")
        grid_frame.pack(fill="x")
        grid_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Severity Column
        self.severity_col_entry = SettingsEntry(grid_frame, "Severity Column:", width=250)
        self.severity_col_entry.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")
        
        # Alarm Name Column
        self.alarm_name_col_entry = SettingsEntry(grid_frame, "Alarm Name Column:", width=250)
        self.alarm_name_col_entry.grid(row=0, column=1, padx=(10, 0), pady=5, sticky="ew")
        
        # Timestamp Column
        self.timestamp_col_entry = SettingsEntry(grid_frame, "Timestamp Column:", width=250)
        self.timestamp_col_entry.grid(row=1, column=0, padx=(0, 10), pady=5, sticky="ew")
        
        # Source Column
        self.source_col_entry = SettingsEntry(grid_frame, "Source Column (Primary):", width=250)
        self.source_col_entry.grid(row=1, column=1, padx=(10, 0), pady=5, sticky="ew")
        
        # Alternate Source Column
        self.alt_source_col_entry = SettingsEntry(grid_frame, "Source Column (Alternate):", width=250)
        self.alt_source_col_entry.grid(row=2, column=0, padx=(0, 10), pady=5, sticky="ew")
        
        hint = ctk.CTkLabel(
            inner,
            text="💡 These are the exact column header names in the exported Excel file",
            font=ctk.CTkFont(size=10),
            text_color=Colors.INFO
        )
        hint.pack(anchor="w", pady=(10, 0))
    
    def _create_help_section(self, parent):
        """Create help section with available placeholders"""
        help_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        help_frame.pack(fill="x", pady=(0, 20))
        
        inner = ctk.CTkFrame(help_frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)
        
        help_title = ctk.CTkLabel(
            inner,
            text="📋 Message Format Placeholders",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        help_title.pack(anchor="w")
        
        placeholders = [
            ("{alarm_type}", "Alarm name (e.g., Low Voltage)"),
            ("{timestamp}", "Time string (e.g., 12-30-2025 14:30:00)"),
            ("{site_name}", "Full site name (e.g., LTE_LHR1459_S_Eden)"),
            ("{site_code}", "Site code (e.g., LHR1459)"),
            ("{severity}", "Alarm severity (e.g., Major)"),
            ("{mbu}", "MBU code (e.g., C1-LHR-04)"),
            ("{ring_id}", "FTTS Ring ID"),
            ("{b2s_id}", "B2S/OMO ID"),
        ]
        
        placeholder_text = "  •  ".join([f"{p[0]}" for p in placeholders])
        
        placeholder_label = ctk.CTkLabel(
            inner,
            text=placeholder_text,
            font=ctk.CTkFont(size=11),
            text_color=Colors.INFO,
            wraplength=700
        )
        placeholder_label.pack(anchor="w", pady=(5, 0))
        
        tip_label = ctk.CTkLabel(
            inner,
            text="💡 Use \\t for tab separator between columns",
            font=ctk.CTkFont(size=11),
            text_color=Colors.WARNING
        )
        tip_label.pack(anchor="w", pady=(5, 0))
    
    def _create_format_section(self, parent, title: str, key: str, description: str):
        """Create a format input section"""
        frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)
        
        # Title
        title_label = ctk.CTkLabel(
            inner,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title_label.pack(anchor="w")
        
        # Description
        desc_label = ctk.CTkLabel(
            inner,
            text=description,
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        desc_label.pack(anchor="w", pady=(2, 8))
        
        # Entry
        entry = ctk.CTkEntry(
            inner,
            width=600,
            height=35,
            font=ctk.CTkFont(size=12, family="Consolas"),
            fg_color=Colors.BG_MEDIUM,
            border_color=Colors.BORDER
        )
        entry.pack(fill="x", pady=(0, 5))
        
        # Store reference
        setattr(self, f"{key}_entry", entry)
        
        # Preview label
        preview_frame = ctk.CTkFrame(inner, fg_color=Colors.BG_LIGHT, corner_radius=5)
        preview_frame.pack(fill="x")
        
        preview_title = ctk.CTkLabel(
            preview_frame,
            text="Preview:",
            font=ctk.CTkFont(size=10),
            text_color=Colors.TEXT_MUTED
        )
        preview_title.pack(anchor="w", padx=10, pady=(5, 0))
        
        preview_label = ctk.CTkLabel(
            preview_frame,
            text="",
            font=ctk.CTkFont(size=11, family="Consolas"),
            text_color=Colors.TEXT_SECONDARY,
            wraplength=580,
            justify="left"
        )
        preview_label.pack(anchor="w", padx=10, pady=(0, 5))
        
        setattr(self, f"{key}_preview", preview_label)
        
        # Bind entry change to update preview
        entry.bind("<KeyRelease>", lambda e, k=key: self._update_preview(k))
    
    def _update_preview(self, key: str):
        """Update the preview for a format"""
        entry = getattr(self, f"{key}_entry")
        preview = getattr(self, f"{key}_preview")
        
        template = entry.get()
        
        # Sample data for preview
        sample = {
            "alarm_type": "Low Voltage",
            "timestamp": "01-02-2026 14:30:00",
            "site_name": "LTE_LHR1459_S_Eden_Value",
            "site_code": "LHR1459",
            "severity": "Major",
            "mbu": "C1-LHR-04",
            "ring_id": "RING-123",
            "b2s_id": "B2S-456"
        }
        
        try:
            # Replace \t with actual tab for display
            formatted = template.format(**sample)
            # Show tabs as visible separator for preview
            formatted = formatted.replace("\t", "  |  ")
            preview.configure(text=formatted)
        except KeyError as e:
            preview.configure(text=f"❌ Unknown placeholder: {e}")
        except Exception as e:
            preview.configure(text=f"❌ Error: {e}")
    
    def _create_save_button(self):
        """Create save button"""
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        save_btn = ActionButton(
            btn_frame,
            text="Save Formats",
            icon="💾",
            color=Colors.SUCCESS,
            hover_color="#388E3C",
            command=self._save_formats,
            width=150,
            height=40
        )
        save_btn.pack(side="right")
        
        reset_btn = ActionButton(
            btn_frame,
            text="Reset to Defaults",
            icon="🔄",
            color=Colors.WARNING,
            command=self._reset_defaults,
            width=180,
            height=40
        )
        reset_btn.pack(side="right", padx=10)
    
    def _load_formats(self):
        """Load current formats into entries"""
        # Load Excel column mappings
        self.severity_col_entry.set(settings.excel_columns.severity_column)
        self.alarm_name_col_entry.set(settings.excel_columns.alarm_name_column)
        self.timestamp_col_entry.set(settings.excel_columns.timestamp_column)
        self.source_col_entry.set(settings.excel_columns.source_column)
        self.alt_source_col_entry.set(settings.excel_columns.alternate_source_column)
        
        # Load message formats
        self.mbu_entry.insert(0, settings.message_formats.mbu_format)
        self.toggle_entry.insert(0, settings.message_formats.toggle_format)
        self.b2s_entry.insert(0, settings.message_formats.b2s_format)
        self.omo_entry.insert(0, settings.message_formats.omo_format)
        
        # Update all previews
        for key in ["mbu", "toggle", "b2s", "omo"]:
            self._update_preview(key)
    
    def _save_formats(self):
        """Save formats to settings"""
        # Save Excel column mappings
        settings.excel_columns.severity_column = self.severity_col_entry.get()
        settings.excel_columns.alarm_name_column = self.alarm_name_col_entry.get()
        settings.excel_columns.timestamp_column = self.timestamp_col_entry.get()
        settings.excel_columns.source_column = self.source_col_entry.get()
        settings.excel_columns.alternate_source_column = self.alt_source_col_entry.get()
        
        # Save message formats
        settings.message_formats.mbu_format = self.mbu_entry.get()
        settings.message_formats.toggle_format = self.toggle_entry.get()
        settings.message_formats.b2s_format = self.b2s_entry.get()
        settings.message_formats.omo_format = self.omo_entry.get()
        
        settings.save()
        
        if self.on_save:
            self.on_save()
    
    def _reset_defaults(self):
        """Reset to default formats"""
        from config import MessageFormatSettings, ExcelColumnMapping
        defaults_fmt = MessageFormatSettings()
        defaults_col = ExcelColumnMapping()
        
        # Reset Excel column mappings
        self.severity_col_entry.set(defaults_col.severity_column)
        self.alarm_name_col_entry.set(defaults_col.alarm_name_column)
        self.timestamp_col_entry.set(defaults_col.timestamp_column)
        self.source_col_entry.set(defaults_col.source_column)
        self.alt_source_col_entry.set(defaults_col.alternate_source_column)
        
        # Reset message formats
        self.mbu_entry.delete(0, "end")
        self.mbu_entry.insert(0, defaults_fmt.mbu_format)
        
        self.toggle_entry.delete(0, "end")
        self.toggle_entry.insert(0, defaults_fmt.toggle_format)
        
        self.b2s_entry.delete(0, "end")
        self.b2s_entry.insert(0, defaults_fmt.b2s_format)
        
        self.omo_entry.delete(0, "end")
        self.omo_entry.insert(0, defaults_fmt.omo_format)
        
        # Update previews
        for key in ["mbu", "toggle", "b2s", "omo"]:
            self._update_preview(key)
