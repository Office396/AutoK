"""
GUI Handle View (Message Formats & Master Data Column Mapping)
Allows users to customize WhatsApp message formats and Master Data Excel column mappings
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


class NumberEntry(ctk.CTkFrame):
    """A labeled number entry widget for column indices"""
    
    def __init__(self, parent, label: str, width: int = 80, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.label = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY
        )
        self.label.pack(anchor="w")
        
        self.entry = ctk.CTkEntry(
            self,
            width=width,
            height=28,
            fg_color=Colors.BG_MEDIUM,
            border_color=Colors.BORDER
        )
        self.entry.pack(fill="x", pady=(3, 0))
    
    def get(self) -> int:
        try:
            return int(self.entry.get())
        except ValueError:
            return 0
    
    def set(self, value: int):
        self.entry.delete(0, "end")
        self.entry.insert(0, str(value))


class MessageFormatsView(ctk.CTkFrame):
    """Handle view - message format and Master Data column customization"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        self.on_save: Optional[Callable] = None
        
        self._create_layout()
        self._load_formats()
    
    def _create_layout(self):
        """Create the layout"""
        title = ctk.CTkLabel(
            self,
            text="📝 Handle Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(pady=20, padx=20, anchor="w")
        
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self._create_master_column_section(content)
        
        self._create_help_section(content)
        
        self._create_format_section(content, "MBU Format", "mbu", 
            "Format for MBU group messages (C1-LHR-01 to C1-LHR-08)")
        
        self._create_format_section(content, "Toggle Format", "toggle",
            "Format for toggle alarm messages")
        
        self._create_format_section(content, "B2S Format", "b2s",
            "Format for B2S group messages (ATL, Edotco, Enfrashare, Tawal)")
        
        self._create_format_section(content, "OMO Format", "omo",
            "Format for OMO group messages (Ufone, Telenor, CMpak)")
        
        self._create_save_button()
    
    def _create_master_column_section(self, parent):
        """Create Master Data Excel column mapping section"""
        frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        frame.pack(fill="x", pady=(0, 20))
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)
        
        title = ctk.CTkLabel(
            inner,
            text="📊 Master Data Excel Column Mapping",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(anchor="w")
        
        desc = ctk.CTkLabel(
            inner,
            text="Configure which column index (0-based) in the Master_Data.xlsx contains each field",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        desc.pack(anchor="w", pady=(2, 15))
        
        grid_frame = ctk.CTkFrame(inner, fg_color="transparent")
        grid_frame.pack(fill="x")
        grid_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        
        self.master_entries = {}
        
        column_fields = [
            ("site_id", "Site ID"),
            ("site_code", "Site Code"),
            ("technology", "Technology"),
            ("old_mbu", "Old MBU"),
            ("site_name", "Site Name"),
            ("site_type", "Site Type"),
            ("dependent_sites", "Dependent Sites"),
            ("power_status", "Power Status"),
            ("latitude", "Latitude"),
            ("longitude", "Longitude"),
            ("new_mbu", "New MBU"),
            ("dg_capacity", "DG Capacity"),
            ("dg_count", "DG Count"),
            ("share_holder", "Share Holder"),
            ("remarks", "Remarks"),
            ("site_status", "Site Status"),
            ("omo_b2s_name", "OMO/B2S Name"),
            ("omo_b2s_id", "OMO/B2S ID"),
            ("hw_mbu_lead", "HW MBU Lead"),
            ("day_tech", "Day Tech"),
            ("night_tech", "Night Tech"),
            ("jazz_mbu_tech", "Jazz MBU Tech"),
            ("jazz_mbu_lead", "Jazz MBU Lead"),
            ("dependency_count", "Dependency Count"),
            ("connectivity", "Connectivity"),
            ("ftts_ring_id", "FTTS Ring ID"),
            ("site_type_new", "Site Type New"),
            ("dependent", "Dependent"),
            ("new_dependent", "New Dependent"),
        ]
        
        cols_per_row = 6
        for i, (key, label) in enumerate(column_fields):
            row = i // cols_per_row
            col = i % cols_per_row
            
            entry = NumberEntry(grid_frame, f"{label}:", width=60)
            entry.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            self.master_entries[key] = entry
        
        hint = ctk.CTkLabel(
            inner,
            text="💡 Column indices start from 0. Example: If Site Code is in column B, set it to 1",
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
        
        title_label = ctk.CTkLabel(
            inner,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title_label.pack(anchor="w")
        
        desc_label = ctk.CTkLabel(
            inner,
            text=description,
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        desc_label.pack(anchor="w", pady=(2, 8))
        
        entry = ctk.CTkEntry(
            inner,
            width=600,
            height=35,
            font=ctk.CTkFont(size=12, family="Consolas"),
            fg_color=Colors.BG_MEDIUM,
            border_color=Colors.BORDER
        )
        entry.pack(fill="x", pady=(0, 5))
        
        setattr(self, f"{key}_entry", entry)
        
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
        
        entry.bind("<KeyRelease>", lambda e, k=key: self._update_preview(k))
    
    def _update_preview(self, key: str):
        """Update the preview for a format"""
        entry = getattr(self, f"{key}_entry")
        preview = getattr(self, f"{key}_preview")
        
        template = entry.get()
        
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
            formatted = template.format(**sample)
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
        
        change_pass_btn = ActionButton(
            btn_frame,
            text="Change Password",
            icon="🔑",
            color=Colors.INFO,
            command=self._show_change_password,
            width=180,
            height=40
        )
        change_pass_btn.pack(side="left")
    
    def _show_change_password(self):
        """Show change password dialog"""
        from gui_password import ChangePasswordDialog
        ChangePasswordDialog(self.winfo_toplevel())
    
    def _load_formats(self):
        """Load current formats into entries"""
        for key, entry in self.master_entries.items():
            value = getattr(settings.master_columns, key, 0)
            entry.set(value)
        
        self.mbu_entry.insert(0, settings.message_formats.mbu_format)
        self.toggle_entry.insert(0, settings.message_formats.toggle_format)
        self.b2s_entry.insert(0, settings.message_formats.b2s_format)
        self.omo_entry.insert(0, settings.message_formats.omo_format)
        
        for key in ["mbu", "toggle", "b2s", "omo"]:
            self._update_preview(key)
    
    def _save_formats(self):
        """Save formats to settings"""
        for key, entry in self.master_entries.items():
            setattr(settings.master_columns, key, entry.get())
        
        settings.message_formats.mbu_format = self.mbu_entry.get()
        settings.message_formats.toggle_format = self.toggle_entry.get()
        settings.message_formats.b2s_format = self.b2s_entry.get()
        settings.message_formats.omo_format = self.omo_entry.get()
        
        settings.save()
        
        if self.on_save:
            self.on_save()
    
    def _reset_defaults(self):
        """Reset to default formats"""
        from config import MessageFormatSettings, MasterDataColumnMapping
        defaults_fmt = MessageFormatSettings()
        defaults_col = MasterDataColumnMapping()
        
        for key, entry in self.master_entries.items():
            value = getattr(defaults_col, key, 0)
            entry.set(value)
        
        self.mbu_entry.delete(0, "end")
        self.mbu_entry.insert(0, defaults_fmt.mbu_format)
        
        self.toggle_entry.delete(0, "end")
        self.toggle_entry.insert(0, defaults_fmt.toggle_format)
        
        self.b2s_entry.delete(0, "end")
        self.b2s_entry.insert(0, defaults_fmt.b2s_format)
        
        self.omo_entry.delete(0, "end")
        self.omo_entry.insert(0, defaults_fmt.omo_format)
        
        for key in ["mbu", "toggle", "b2s", "omo"]:
            self._update_preview(key)
