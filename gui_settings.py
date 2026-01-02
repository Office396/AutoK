"""
GUI Settings View
Settings and configuration interface
"""

import customtkinter as ctk
from typing import Optional, Callable, Dict
from tkinter import filedialog

from gui_components import (
    Colors, SettingsEntry, TimingSlider, GroupMappingEntry,
    ActionButton, TabButton
)
from config import settings


class SettingsView(ctk.CTkFrame):
    """Settings and configuration view"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        self.on_save: Optional[Callable] = None
        self.on_test_connection: Optional[Callable] = None
        
        self._create_layout()
        self._load_settings()
    
    def _create_layout(self):
        """Create settings layout"""
        # Title
        title = ctk.CTkLabel(
            self,
            text="⚙️ Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(pady=20, padx=20, anchor="w")
        
        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Credentials Section
        self._create_credentials_section(content)
        
        # Timing Settings Section
        self._create_timing_section(content)
        
        # MBU Group Mappings Section
        self._create_mbu_mappings_section(content)
        
        # B2S Group Mappings Section
        self._create_b2s_mappings_section(content)
        
        # OMO Group Mappings Section
        self._create_omo_mappings_section(content)
        
        # Other Settings Section
        self._create_other_settings_section(content)
        
        # Save button
        self._create_save_button()
    
    def _create_section_header(self, parent, title: str, icon: str = ""):
        """Create a section header"""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(20, 10))
        
        label = ctk.CTkLabel(
            header,
            text=f"{icon} {title}" if icon else title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        label.pack(side="left")
        
        # Separator line
        separator = ctk.CTkFrame(parent, fg_color=Colors.BORDER, height=1)
        separator.pack(fill="x", pady=(0, 15))
    
    def _create_credentials_section(self, parent):
        """Create credentials settings section"""
        self._create_section_header(parent, "Portal Credentials", "🔐")
        
        cred_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        cred_frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(cred_frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        
        self.username_entry = SettingsEntry(
            inner,
            label="Username:",
            width=300
        )
        self.username_entry.pack(fill="x", pady=5)
        
        self.password_entry = SettingsEntry(
            inner,
            label="Password:",
            is_password=True,
            width=300
        )
        self.password_entry.pack(fill="x", pady=5)
        
        # Test connection button
        test_btn = ActionButton(
            inner,
            text="Test Connection",
            icon="🔗",
            color=Colors.INFO,
            command=self._test_connection,
            width=150
        )
        test_btn.pack(pady=(15, 0), anchor="w")
    
    def _create_timing_section(self, parent):
        """Create timing settings section"""
        self._create_section_header(parent, "Alarm Timing Settings", "⏱️")
        
        timing_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        timing_frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(timing_frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        
        # Timing sliders container
        self.timing_sliders = {}

        # CSL Fault Slider (First in list)
        csl_slider = TimingSlider(
            inner,
            label="CSL Fault (0 = Realtime)",
            min_value=0,
            max_value=120,
            default_value=0
        )
        csl_slider.pack(fill="x", pady=5)
        self.timing_sliders["csl_fault"] = csl_slider
        
        # Other Timing sliders
        
        timing_settings = [
            ("Low Voltage", "low_voltage", 30),
            ("AC Main Failure", "ac_main_failure", 60),
            ("System on Battery", "system_on_battery", 30),
            ("Battery High Temp", "battery_high_temp", 30),
            ("RF Unit Failure", "rf_unit_failure", 30),
            ("Cell Unavailable", "cell_unavailable", 30),
            ("Genset Operation", "genset_operation", 60),
            ("Mains Failure", "mains_failure", 60),
        ]
        
        for label, key, default in timing_settings:
            slider = TimingSlider(
                inner,
                label=label,
                min_value=5,
                max_value=120,
                default_value=default
            )
            slider.pack(fill="x", pady=5)
            self.timing_sliders[key] = slider
        
        # Check interval
        self._create_section_header(inner, "Portal Check Interval", "🔄")
        
        self.check_interval_slider = TimingSlider(
            inner,
            label="Check Interval",
            min_value=0,
            max_value=120,
            default_value=30,
            unit="sec"
        )
        self.check_interval_slider.pack(fill="x", pady=5)
    
    def _create_mbu_mappings_section(self, parent):
        """Create MBU group mappings section"""
        self._create_section_header(parent, "MBU WhatsApp Group Names", "📱")
        
        mbu_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        mbu_frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(mbu_frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        
        self.mbu_mappings = {}
        
        mbu_list = [
            ("C1-LHR-01", "C1-LHR-MBU-01"),
            ("C1-LHR-02", "MBU C1-LHR-02"),
            ("C1-LHR-03", "C1-LHR-03"),
            ("C1-LHR-04", "MBU C1-LHR-04"),
            ("C1-LHR-05", "MBU C1 LHR-05"),
            ("C1-LHR-06", "MBU C1-LHR-06 Hotline"),
            ("C1-LHR-07", "MBU-C1-LHR-07"),
            ("C1-LHR-08", "MBU C1-LHR-08 Hotline"),
        ]
        
        for mbu, default_group in mbu_list:
            mapping = GroupMappingEntry(inner, mbu, default_group)
            mapping.pack(fill="x", pady=3)
            self.mbu_mappings[mbu] = mapping
    
    def _create_b2s_mappings_section(self, parent):
        """Create B2S group mappings section"""
        self._create_section_header(parent, "B2S WhatsApp Group Names", "🏗️")
        
        b2s_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        b2s_frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(b2s_frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        
        self.b2s_mappings = {}
        
        b2s_list = [
            ("ATL", "JAZZ ATL CA-LHR-C1"),
            ("Edotco", "Jazz~edotco C1 & C4"),
            ("Enfrashare", "Jazz Enfrashare MPL C1"),
            ("Tawal", "TAWAL - Jazz (Central-A)"),
        ]
        
        for company, default_group in b2s_list:
            mapping = GroupMappingEntry(inner, company, default_group)
            mapping.pack(fill="x", pady=3)
            self.b2s_mappings[company] = mapping
    
    def _create_omo_mappings_section(self, parent):
        """Create OMO group mappings section"""
        self._create_section_header(parent, "OMO WhatsApp Group Names", "📡")
        
        omo_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        omo_frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(omo_frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        
        self.omo_mappings = {}
        
        omo_list = [
            ("Zong", "MPL JAZZ & CMPAK"),
            ("Ufone", "Ufone Jazz Sites Huawei Group"),
            ("Telenor", "TP JAZZ Shared Sites C1"),
        ]
        
        for company, default_group in omo_list:
            mapping = GroupMappingEntry(inner, company, default_group)
            mapping.pack(fill="x", pady=3)
            self.omo_mappings[company] = mapping
    
    def _create_other_settings_section(self, parent):
        """Create other settings section"""
        self._create_section_header(parent, "Other Settings", "🔧")
        
        other_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_CARD, corner_radius=10)
        other_frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(other_frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        
        # Master data file
        file_frame = ctk.CTkFrame(inner, fg_color="transparent")
        file_frame.pack(fill="x", pady=5)
        
        file_label = ctk.CTkLabel(
            file_frame,
            text="Master Data File:",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY,
            width=150,
            anchor="w"
        )
        file_label.pack(side="left")
        
        self.file_path_entry = ctk.CTkEntry(
            file_frame,
            width=300,
            font=ctk.CTkFont(size=12),
            fg_color=Colors.BG_MEDIUM,
            border_color=Colors.BORDER
        )
        self.file_path_entry.pack(side="left", padx=(0, 10))
        
        browse_btn = ctk.CTkButton(
            file_frame,
            text="Browse",
            font=ctk.CTkFont(size=11),
            fg_color=Colors.BG_LIGHT,
            hover_color=Colors.BG_MEDIUM,
            width=80,
            command=self._browse_file
        )
        browse_btn.pack(side="left")
        
        # Skip toggle MBUs
        toggle_frame = ctk.CTkFrame(inner, fg_color="transparent")
        toggle_frame.pack(fill="x", pady=(15, 5))
        
        toggle_label = ctk.CTkLabel(
            toggle_frame,
            text="Skip Toggle Alarms for:",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY
        )
        toggle_label.pack(anchor="w")
        
        self.skip_toggle_vars = {}
        
        skip_mbus = ["C1-LHR-04", "C1-LHR-05"]
        for mbu in ["C1-LHR-01", "C1-LHR-02", "C1-LHR-03", "C1-LHR-04", 
                    "C1-LHR-05", "C1-LHR-06", "C1-LHR-07", "C1-LHR-08"]:
            var = ctk.BooleanVar(value=mbu in skip_mbus)
            cb = ctk.CTkCheckBox(
                toggle_frame,
                text=mbu,
                variable=var,
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_SECONDARY,
                fg_color=Colors.PRIMARY,
                hover_color=Colors.PRIMARY_DARK
            )
            cb.pack(side="left", padx=10, pady=5)
            self.skip_toggle_vars[mbu] = var

        # WhatsApp Sending Method
        method_frame = ctk.CTkFrame(inner, fg_color="transparent")
        method_frame.pack(fill="x", pady=(15, 5))
        
        method_label = ctk.CTkLabel(
            method_frame,
            text="WhatsApp Sending Method:",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY
        )
        method_label.pack(anchor="w", pady=(0, 5))
        
        self.sending_method_var = ctk.StringVar(value="JavaScript")
        self.sending_method_seg = ctk.CTkSegmentedButton(
            method_frame,
            values=["JavaScript", "Clipboard"],
            variable=self.sending_method_var,
            font=ctk.CTkFont(size=12),
            selected_color=Colors.PRIMARY,
            selected_hover_color=Colors.PRIMARY_DARK
        )
        self.sending_method_seg.pack(fill="x")

        # Instant Alarm Types
        instant_frame = ctk.CTkFrame(inner, fg_color="transparent")
        instant_frame.pack(fill="x", pady=(15, 5))
        
        self.instant_alarms_entry = SettingsEntry(
            instant_frame,
            label="Instant Alarm Types (comma separated):",
            width=300
        )
        self.instant_alarms_entry.pack(fill="x", pady=5)
        
        # Ignored Sites
        ignored_frame = ctk.CTkFrame(inner, fg_color="transparent")
        ignored_frame.pack(fill="x", pady=(15, 5))
        
        self.ignored_sites_entry = SettingsEntry(
            ignored_frame,
            label="Ignored Site IDs (comma separated):",
            width=300
        )
        self.ignored_sites_entry.pack(fill="x", pady=5)
        
        ignored_hint = ctk.CTkLabel(
            ignored_frame,
            text="e.g., LHR1670, LHR1234 - alarms from these sites will not be sent",
            font=ctk.CTkFont(size=10),
            text_color=Colors.TEXT_SECONDARY
        )
        ignored_hint.pack(anchor="w")
    
    def _create_save_button(self):
        """Create save button at bottom"""
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        save_btn = ActionButton(
            btn_frame,
            text="Save Settings",
            icon="💾",
            color=Colors.SUCCESS,
            hover_color="#388E3C",
            command=self._save_settings,
            width=150,
            height=40
        )
        save_btn.pack(side="right")
        
        reload_btn = ActionButton(
            btn_frame,
            text="Reload Master Data",
            icon="🔄",
            color=Colors.INFO,
            command=self._reload_master_data,
            width=180,
            height=40
        )
        reload_btn.pack(side="right", padx=10)
    
    def _browse_file(self):
        """Open file browser for master data"""
        filename = filedialog.askopenfilename(
            title="Select Master Data File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if filename:
            self.file_path_entry.delete(0, "end")
            self.file_path_entry.insert(0, filename)
    
    def _test_connection(self):
        """Test portal connection"""
        if self.on_test_connection:
            self.on_test_connection(
                self.username_entry.get(),
                self.password_entry.get()
            )
    
    def _save_settings(self):
        """Save all settings"""
        # Credentials
        settings.credentials.username = self.username_entry.get()
        settings.credentials.password = self.password_entry.get()
        
        # Timing settings
        settings.timing.csl_fault = self.timing_sliders["csl_fault"].get()
        settings.timing.low_voltage = self.timing_sliders["low_voltage"].get()
        settings.timing.ac_main_failure = self.timing_sliders["ac_main_failure"].get()
        settings.timing.system_on_battery = self.timing_sliders["system_on_battery"].get()
        settings.timing.battery_high_temp = self.timing_sliders["battery_high_temp"].get()
        settings.timing.rf_unit_failure = self.timing_sliders["rf_unit_failure"].get()
        settings.timing.cell_unavailable = self.timing_sliders["cell_unavailable"].get()
        settings.timing.genset_operation = self.timing_sliders["genset_operation"].get()
        settings.timing.mains_failure = self.timing_sliders["mains_failure"].get()
        
        settings.check_interval_seconds = self.check_interval_slider.get()
        
        # MBU mappings
        for mbu, mapping in self.mbu_mappings.items():
            _, group = mapping.get_mapping()
            settings.mbu_groups.mapping[mbu] = group
        
        # B2S mappings
        for company, mapping in self.b2s_mappings.items():
            _, group = mapping.get_mapping()
            settings.b2s_groups.mapping[company] = group
        
        # OMO mappings
        for company, mapping in self.omo_mappings.items():
            _, group = mapping.get_mapping()
            settings.omo_groups.mapping[company] = group
        
        # Other settings
        settings.master_file_path = self.file_path_entry.get()
        
        # Skip toggle MBUs
        settings.skip_toggle_mbus = [
            mbu for mbu, var in self.skip_toggle_vars.items() if var.get()
        ]
        
        # WhatsApp Sending Method
        settings.whatsapp_sending_method = self.sending_method_var.get()
        
        # Instant Alarm Types
        instant_types_str = self.instant_alarms_entry.get()
        settings.instant_alarms = [t.strip() for t in instant_types_str.split(",") if t.strip()]
        
        # Ignored Sites
        ignored_sites_str = self.ignored_sites_entry.get()
        settings.ignored_sites = [s.strip().upper() for s in ignored_sites_str.split(",") if s.strip()]
        
        # Save to file
        settings.save()
        
        if self.on_save:
            self.on_save()
    
    def _reload_master_data(self):
        """Reload master data"""
        from master_data import master_data
        master_data.reload()
    
    def _load_settings(self):
        """Load current settings into UI"""
        # Credentials
        self.username_entry.set(settings.credentials.username)
        self.password_entry.set(settings.credentials.password)
        
        # Timing settings
        self.timing_sliders["csl_fault"].set(settings.timing.csl_fault)
        self.timing_sliders["low_voltage"].set(settings.timing.low_voltage)
        self.timing_sliders["ac_main_failure"].set(settings.timing.ac_main_failure)
        self.timing_sliders["system_on_battery"].set(settings.timing.system_on_battery)
        self.timing_sliders["battery_high_temp"].set(settings.timing.battery_high_temp)
        self.timing_sliders["rf_unit_failure"].set(settings.timing.rf_unit_failure)
        self.timing_sliders["cell_unavailable"].set(settings.timing.cell_unavailable)
        self.timing_sliders["genset_operation"].set(settings.timing.genset_operation)
        self.timing_sliders["mains_failure"].set(settings.timing.mains_failure)
        
        self.check_interval_slider.set(settings.check_interval_seconds)
        
        # MBU mappings
        for mbu, mapping in self.mbu_mappings.items():
            group = settings.mbu_groups.mapping.get(mbu, "")
            mapping.set_group(group)
        
        # B2S mappings
        for company, mapping in self.b2s_mappings.items():
            group = settings.b2s_groups.mapping.get(company, "")
            mapping.set_group(group)
        
        # OMO mappings
        for company, mapping in self.omo_mappings.items():
            group = settings.omo_groups.mapping.get(company, "")
            mapping.set_group(group)
        
        # Other settings
        self.file_path_entry.insert(0, settings.master_file_path)
        
        # Skip toggle MBUs
        for mbu, var in self.skip_toggle_vars.items():
            var.set(mbu in settings.skip_toggle_mbus)

        # WhatsApp Sending Method
        self.sending_method_var.set(settings.whatsapp_sending_method)

        # Instant Alarm Types
        self.instant_alarms_entry.set(", ".join(settings.instant_alarms))
        
        # Ignored Sites
        self.ignored_sites_entry.set(", ".join(settings.ignored_sites))