"""
Configuration Management for Telecom Alarm Automation
Handles all settings, credentials, and mappings
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"
PROFILES_DIR = BASE_DIR / "browser_profiles"
SETTINGS_FILE = BASE_DIR / "settings.json"

# Create directories if not exist
for dir_path in [DATA_DIR, LOGS_DIR, EXPORTS_DIR, PROFILES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class PortalConfig:
    """Portal URLs and settings"""
    base_url: str = "https://10.226.101.71:31943/ossfacewebsite/index.html"
    
    main_topology: str = "https://10.226.101.71:31943/ossfacewebsite/index.html#Access/Access_MainTopoTitle?switch"
    
    csl_fault: str = "https://10.226.101.71:31943/ossfacewebsite/index.html#Access/fmAlarmView?switch"
    
    rf_unit: str = ("https://10.226.101.71:31943/ossfacewebsite/index.html#Access/"
                    "fmAlarmView@@fmAlarmApp_alarmView_templateId835%26tabTitle%3DRF-Unit%20AR?switch=undefined"
                    "&maeUrl=%2Feviewwebsite%2Findex.html%23path%3D%2FfmAlarmApp%2FfmAlarmView%26templateId%3D835"
                    "%26fmPage%3Dtrue%26_t%3D1765394552105&maeTitle=Current%20Alarms%20-%20%5BRF-Unit%20AR%5D&loadType=iframe")
    
    nodeb_cell: str = ("https://10.226.101.71:31943/ossfacewebsite/index.html#Access/"
                       "fmAlarmView@@fmAlarmApp_alarmView_templateId803%26tabTitle%3DC1%20NodeB%20UMTS%20Cell%20Unavailable%20.?"
                       "switch=undefined&maeUrl=%2Feviewwebsite%2Findex.html%23path%3D%2FfmAlarmApp%2FfmAlarmView%26templateId%3D803"
                       "%26fmPage%3Dtrue%26_t%3D1765394556232&maeTitle=Current%20Alarms%20-%20%5BC1%20NodeB%20UMTS%20Cell%20Unavailable%20.%5D&loadType=iframe")
    
    all_alarms: str = ("https://10.226.101.71:31943/ossfacewebsite/index.html#Access/"
                       "fmAlarmView@@fmAlarmApp_alarmView_templateId592%26tabTitle%3Dc1-c2%20All%20Alarm?switch=undefined"
                       "&maeUrl=%2Feviewwebsite%2Findex.html%23path%3D%2FfmAlarmApp%2FfmAlarmView%26templateId%3D592"
                       "%26fmPage%3Dtrue%26_t%3D1765394587633&maeTitle=Current%20Alarms%20-%20%5Bc1-c2%20All%20Alarm%5D&loadType=iframe")


@dataclass
class Credentials:
    """Portal login credentials"""
    username: str = ""
    password: str = ""


@dataclass
class AlarmTimingSettings:
    """Timing settings for each alarm type (in minutes)"""
    csl_fault: int = 0  # 0 means real-time
    rf_unit_failure: int = 30
    cell_unavailable: int = 30
    low_voltage: int = 30
    ac_main_failure: int = 60
    system_on_battery: int = 30
    battery_high_temp: int = 30
    genset_operation: int = 60
    mains_failure: int = 60


@dataclass
class ExcelColumnMapping:
    """Excel column header mappings for alarm data extraction"""
    severity_column: str = "Severity"
    alarm_name_column: str = "Name"
    timestamp_column: str = "Last Occurred (NT)"
    source_column: str = "Alarm Source"
    alternate_source_column: str = "MO Name"


@dataclass
class MessageFormatSettings:
    """Custom message format templates using placeholders"""
    # Available placeholders: {alarm_type}, {timestamp}, {site_name}, {site_code}, 
    # {severity}, {mbu}, {ring_id}, {b2s_id}
    
    # MBU format (for regular MBU group messages)
    mbu_format: str = "{alarm_type}\t{timestamp}\t{site_name}"
    
    # Toggle alarm format
    toggle_format: str = "Toggle alarm\t{severity}\t{alarm_type}\t{timestamp}\t{site_name}"
    
    # B2S format (includes ring_id and b2s_id)
    b2s_format: str = "{mbu}\t{ring_id}\t{alarm_type}\t{site_name}\t{timestamp}\t{b2s_id}"
    
    # OMO format (same structure as B2S)
    omo_format: str = "{mbu}\t{ring_id}\t{alarm_type}\t{site_name}\t{timestamp}\t{b2s_id}"


@dataclass 
class MBUGroupMapping:
    """MBU to WhatsApp Group Name Mapping"""
    mapping: Dict[str, str] = field(default_factory=lambda: {
        "C1-LHR-01": "C1-LHR-MBU-01",
        "C1-LHR-02": "MBU C1-LHR-02",
        "C1-LHR-03": "C1-LHR-03",
        "C1-LHR-04": "MBU C1-LHR-04",
        "C1-LHR-05": "MBU C1 LHR-05",
        "C1-LHR-06": "MBU C1-LHR-06 Hotline",
        "C1-LHR-07": "MBU-C1-LHR-07",
        "C1-LHR-08": "MBU C1-LHR-08 Hotline"
    })


@dataclass
class B2SGroupMapping:
    """B2S Company to WhatsApp Group Name Mapping"""
    mapping: Dict[str, str] = field(default_factory=lambda: {
        "ATL": "JAZZ ATL CA-LHR-C1",
        "Edotco": "Jazz~edotco C1 & C4",
        "Enfrashare": "Jazz Enfrashare MPL C1",
        "Tawal": "TAWAL - Jazz (Central-A)"
    })


@dataclass
class OMOGroupMapping:
    """OMO Company to WhatsApp Group Name Mapping"""
    mapping: Dict[str, str] = field(default_factory=lambda: {
        "Zong": "MPL JAZZ & CMPAK",
        "CM-PAK": "MPL JAZZ & CMPAK",
        "CMPAK": "MPL JAZZ & CMPAK",
        "Ufone": "Ufone Jazz Sites Huawei Group",
        "UFONE": "Ufone Jazz Sites Huawei Group",
        "Telenor": "TP JAZZ Shared Sites C1",
        "TELENOR": "TP JAZZ Shared Sites C1"
    })


class PowerStatusClassifier:
    """Classify sites based on Power Status column"""
    
    # B2S patterns (case-insensitive matching)
    B2S_PATTERNS = {
        "ATL": ["guest/atl", "atl"],
        "Edotco": ["guest/edotco", "edotco"],
        "Enfrashare": ["guest/enfrashare", "enfrashare"],
        "Tawal": ["guest/tawal", "tawal"]
    }
    
    # OMO patterns (case-insensitive matching)
    OMO_PATTERNS = {
        "Zong": ["guest/zong", "cm-pak", "cmpak", "jazz guest/cm-pak", "jazz host/cm-pak"],
        "Ufone": ["guest/ufone", "jazz guest/ufone", "jazz host/ufone"],
        "Telenor": ["guest/telenor", "jazz guest/telenor"]
    }
    
    @classmethod
    def get_b2s_company(cls, power_status: str) -> Optional[str]:
        """Get B2S company from power status"""
        if not power_status:
            return None
        power_status_lower = power_status.lower().strip()
        for company, patterns in cls.B2S_PATTERNS.items():
            for pattern in patterns:
                if pattern in power_status_lower:
                    return company
        return None
    
    @classmethod
    def get_omo_company(cls, power_status: str) -> Optional[str]:
        """Get OMO company from power status"""
        if not power_status:
            return None
        power_status_lower = power_status.lower().strip()
        for company, patterns in cls.OMO_PATTERNS.items():
            for pattern in patterns:
                if pattern in power_status_lower:
                    return company
        return None
    
    @classmethod
    def is_b2s_site(cls, power_status: str) -> bool:
        """Check if site belongs to B2S"""
        return cls.get_b2s_company(power_status) is not None
    
    @classmethod
    def is_omo_site(cls, power_status: str) -> bool:
        """Check if site belongs to OMO"""
        return cls.get_omo_company(power_status) is not None


# Alarm type definitions
class AlarmTypes:
    """All alarm types handled by the system"""
    CSL_FAULT = "CSL Fault"
    RF_UNIT_FAILURE = "RF Unit Maintenance Link Failure"
    CELL_UNAVAILABLE = "Cell Unavailable"
    LOCAL_CELL_UNUSABLE = "Local Cell Unusable"  # Skip this
    LOW_VOLTAGE = "Low Voltage"
    AC_MAIN_FAILURE = "AC Main Failure"
    SYSTEM_ON_BATTERY = "System on Battery"
    BATTERY_HIGH_TEMP = "Battery High Temp"
    GENSET_OPERATION = "Genset Operation"
    GENSET_RUNNING = "Genset Running"
    MAINS_FAILURE = "Mains Failure"
    
    # List of all valid alarms (excluding skipped ones)
    VALID_ALARMS = [
        CSL_FAULT, RF_UNIT_FAILURE, CELL_UNAVAILABLE,
        LOW_VOLTAGE, AC_MAIN_FAILURE, SYSTEM_ON_BATTERY,
        BATTERY_HIGH_TEMP, GENSET_OPERATION, GENSET_RUNNING,
        MAINS_FAILURE
    ]
    
    # Alarms to skip
    SKIP_ALARMS = [LOCAL_CELL_UNUSABLE]
    
    # Real-time alarms (sent immediately)
    REALTIME_ALARMS = [CSL_FAULT]
    
    # Batch alarms (sent at intervals)
    BATCH_ALARMS = [
        RF_UNIT_FAILURE, CELL_UNAVAILABLE, LOW_VOLTAGE,
        AC_MAIN_FAILURE, SYSTEM_ON_BATTERY, BATTERY_HIGH_TEMP,
        GENSET_OPERATION, GENSET_RUNNING, MAINS_FAILURE
    ]


class Settings:
    """Main settings manager"""
    
    def __init__(self):
        self.portal = PortalConfig()
        self.credentials = Credentials()
        self.timing = AlarmTimingSettings()
        self.excel_columns = ExcelColumnMapping()
        self.message_formats = MessageFormatSettings()
        self.mbu_groups = MBUGroupMapping()
        self.b2s_groups = B2SGroupMapping()
        self.omo_groups = OMOGroupMapping()
        
        # Additional settings
        self.master_file_path: str = str(DATA_DIR / "Master_Data.xlsx")
        self.check_interval_seconds: int = 30  # How often to check for new alarms
        self.auto_start: bool = False
        self.separate_browser_window: bool = False
        self.skip_toggle_mbus: List[str] = ["C1-LHR-04", "C1-LHR-05"]
        self.whatsapp_sending_method: str = "JavaScript"  # Options: "JavaScript", "Clipboard"
        self.instant_alarms: List[str] = ["CSL Fault"]
        self.ignored_sites: List[str] = []  # Site IDs to ignore (e.g., ["LHR1670", "LHR1234"])
        
        # Load saved settings
        self.load()
    
    def load(self):
        if SETTINGS_FILE.exists():
            try:
                # Check if file is empty
                if SETTINGS_FILE.stat().st_size == 0:
                    logger.warning("Settings file is empty, using defaults")
                    self.save()  # Save default settings
                    return
                
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        logger.warning("Settings file is empty, using defaults")
                        self.save()
                        return
                    
                    data = json.loads(content)
                
                # Load credentials
                if 'credentials' in data:
                    self.credentials.username = data['credentials'].get('username', '')
                    self.credentials.password = data['credentials'].get('password', '')
                
                # Load timing settings
                if 'timing' in data:
                    for key, value in data['timing'].items():
                        if hasattr(self.timing, key):
                            setattr(self.timing, key, value)
                
                # Load MBU group mappings
                if 'mbu_groups' in data:
                    self.mbu_groups.mapping.update(data['mbu_groups'])
                
                # Load B2S group mappings
                if 'b2s_groups' in data:
                    self.b2s_groups.mapping.update(data['b2s_groups'])
                
                # Load OMO group mappings
                if 'omo_groups' in data:
                    self.omo_groups.mapping.update(data['omo_groups'])
                
                # Load other settings
                self.master_file_path = data.get('master_file_path', self.master_file_path)
                self.check_interval_seconds = data.get('check_interval_seconds', 30)
                self.auto_start = data.get('auto_start', False)
                self.separate_browser_window = data.get('separate_browser_window', False)
                self.separate_browser_window = data.get('separate_browser_window', False)
                self.skip_toggle_mbus = data.get('skip_toggle_mbus', ["C1-LHR-04", "C1-LHR-05"])
                self.whatsapp_sending_method = data.get('whatsapp_sending_method', "JavaScript")
                self.instant_alarms = data.get('instant_alarms', ["CSL Fault"])
                self.ignored_sites = data.get('ignored_sites', [])
                
                # Load message format settings
                if 'message_formats' in data:
                    fmt = data['message_formats']
                    self.message_formats.mbu_format = fmt.get('mbu_format', self.message_formats.mbu_format)
                    self.message_formats.toggle_format = fmt.get('toggle_format', self.message_formats.toggle_format)
                    self.message_formats.b2s_format = fmt.get('b2s_format', self.message_formats.b2s_format)
                    self.message_formats.omo_format = fmt.get('omo_format', self.message_formats.omo_format)
                
                # Load excel column mappings
                if 'excel_columns' in data:
                    col = data['excel_columns']
                    self.excel_columns.severity_column = col.get('severity_column', self.excel_columns.severity_column)
                    self.excel_columns.alarm_name_column = col.get('alarm_name_column', self.excel_columns.alarm_name_column)
                    self.excel_columns.timestamp_column = col.get('timestamp_column', self.excel_columns.timestamp_column)
                    self.excel_columns.source_column = col.get('source_column', self.excel_columns.source_column)
                    self.excel_columns.alternate_source_column = col.get('alternate_source_column', self.excel_columns.alternate_source_column)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Settings file corrupted, using defaults: {e}")
                # Delete corrupted file and save defaults
                try:
                    SETTINGS_FILE.unlink()
                except:
                    pass
                self.save()
                
            except Exception as e:
                logger.warning(f"Error loading settings: {e}")
        else:
            # Create default settings file
            self.save()
    
    def save(self):
        """Save settings to file"""
        data = {
            'credentials': {
                'username': self.credentials.username,
                'password': self.credentials.password
            },
            'timing': asdict(self.timing),
            'mbu_groups': self.mbu_groups.mapping,
            'b2s_groups': self.b2s_groups.mapping,
            'omo_groups': self.omo_groups.mapping,
            'master_file_path': self.master_file_path,
            'check_interval_seconds': self.check_interval_seconds,
            'auto_start': self.auto_start,
            'separate_browser_window': self.separate_browser_window,
            'separate_browser_window': self.separate_browser_window,
            'skip_toggle_mbus': self.skip_toggle_mbus,
            'whatsapp_sending_method': self.whatsapp_sending_method,
            'instant_alarms': self.instant_alarms,
            'ignored_sites': self.ignored_sites,
            'message_formats': asdict(self.message_formats),
            'excel_columns': asdict(self.excel_columns)
        }
        
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def get_timing_for_alarm(self, alarm_name: str) -> int:
        """Get timing in minutes for an alarm type"""
        alarm_name_lower = alarm_name.lower().replace(" ", "_")
        
        timing_map = {
            "csl_fault": self.timing.csl_fault,
            "rf_unit_maintenance_link_failure": self.timing.rf_unit_failure,
            "cell_unavailable": self.timing.cell_unavailable,
            "low_voltage": self.timing.low_voltage,
            "ac_main_failure": self.timing.ac_main_failure,
            "system_on_battery": self.timing.system_on_battery,
            "battery_high_temp": self.timing.battery_high_temp,
            "genset_operation": self.timing.genset_operation,
            "genset_running": self.timing.genset_operation,
            "mains_failure": self.timing.mains_failure
        }
        
        return timing_map.get(alarm_name_lower, 30)
    
    def get_whatsapp_group_name(self, mbu: str) -> Optional[str]:
        """Get WhatsApp group name for MBU"""
        return self.mbu_groups.mapping.get(mbu)
    
    def get_b2s_group_name(self, company: str) -> Optional[str]:
        """Get B2S WhatsApp group name"""
        return self.b2s_groups.mapping.get(company)
    
    def get_omo_group_name(self, company: str) -> Optional[str]:
        """Get OMO WhatsApp group name"""
        return self.omo_groups.mapping.get(company)


# Global settings instance
settings = Settings()