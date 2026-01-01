"""
Alarm Processor
Processes, categorizes, and formats alarms for sending to WhatsApp groups
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading

from config import settings, AlarmTypes, PowerStatusClassifier
from master_data import master_data, SiteInfo
from site_code_extractor import SiteCodeExtractor, ExtractedSiteInfo
from logger_module import logger


class AlarmCategory(Enum):
    """Categories of alarms"""
    CSL_FAULT = "CSL Fault"
    RF_UNIT = "RF Unit"
    CELL_UNAVAILABLE = "Cell Unavailable"
    POWER_ALARM = "Power Alarm"
    OTHER = "Other"


@dataclass
class ProcessedAlarm:
    """Processed alarm ready for sending"""
    alarm_id: str  # Unique identifier
    alarm_type: str  # e.g., "Low Voltage"
    severity: str  # e.g., "Major"
    timestamp: datetime
    timestamp_str: str  # Original timestamp string
    site_code: str  # e.g., "LHR9147"
    site_name: str  # Full site name
    site_info: Optional[SiteInfo]  # Master data info
    mbu: str  # MBU code
    is_toggle: bool  # Toggle alarm flag
    is_b2s: bool  # B2S site flag
    is_omo: bool  # OMO site flag
    b2s_company: Optional[str]
    omo_company: Optional[str]
    b2s_id: Optional[str]  # B2S/OMO ID
    ftts_ring_id: Optional[str]
    raw_data: str  # Original alarm string
    category: AlarmCategory
    cell_info: Optional[str] = None  # For sector alarms
    
    def __hash__(self):
        return hash(self.alarm_id)
    
    def __eq__(self, other):
        if isinstance(other, ProcessedAlarm):
            return self.alarm_id == other.alarm_id
        return False


@dataclass
class AlarmBatch:
    """Batch of alarms grouped for sending"""
    alarm_type: str
    mbu: str
    group_name: str
    alarms: List[ProcessedAlarm] = field(default_factory=list)
    toggle_alarms: List[ProcessedAlarm] = field(default_factory=list)
    
    @property
    def total_count(self) -> int:
        return len(self.alarms) + len(self.toggle_alarms)
    
    @property
    def regular_count(self) -> int:
        return len(self.alarms)
    
    @property
    def toggle_count(self) -> int:
        return len(self.toggle_alarms)


class AlarmProcessor:
    """Main alarm processor class"""
    
    def __init__(self):
        self.processed_alarms: Dict[str, ProcessedAlarm] = {}
        self.alarm_history: Dict[str, datetime] = {}  # alarm_id -> last_sent_time
        self.csl_sites: Dict[str, Set[str]] = defaultdict(set)  # mbu -> set of site_codes
        self.lock = threading.Lock()
        
        # Ensure master data is loaded
        if not master_data.is_loaded:
            master_data.load()
    
    def process_exported_excel(self, file_path: str) -> List[ProcessedAlarm]:
        """
        Process an exported Excel file from the portal
        
        Args:
            file_path: Path to exported Excel file
            
        Returns:
            List of ProcessedAlarm objects
        """
        import pandas as pd
        
        try:
            # Read Excel file
            df = pd.read_excel(file_path, header=None, dtype=str)
            df = df.fillna('')
            
            # Find the header row (contains "Severity", "Name", etc.)
            header_row_idx = None
            col_map = {}
            
            for idx, row in df.iterrows():
                row_values = [str(v).strip() for v in row.values]
                # Check for key columns
                if 'Severity' in row_values and 'Name' in row_values:
                    header_row_idx = idx
                    # Build column map
                    for col_idx, val in enumerate(row_values):
                        if val in ['Severity', 'Name', 'Last Occurred (NT)', 'Alarm Source', 'MO Name']:
                            col_map[val] = col_idx
                    break
            
            if header_row_idx is None:
                logger.error(f"Could not find header row in {file_path}")
                return []
            
            # Map alternative column names to standard keys
            final_map = {}
            if 'Severity' in col_map:
                final_map['severity'] = col_map['Severity']
            if 'Name' in col_map:
                final_map['name'] = col_map['Name']
            
            # Timestamp might be "Last Occurred (NT)" or similar
            if 'Last Occurred (NT)' in col_map:
                final_map['time'] = col_map['Last Occurred (NT)']
            elif 'Last Occurred' in col_map:
                final_map['time'] = col_map['Last Occurred']
                
            # Source might be "Alarm Source" or "MO Name"
            if 'Alarm Source' in col_map:
                final_map['source'] = col_map['Alarm Source']
            elif 'MO Name' in col_map:
                final_map['source'] = col_map['MO Name']
                
            # Verify we have minimum required columns
            if 'name' not in final_map or 'source' not in final_map:
                logger.error(f"Missing required columns (Name/Source) in {file_path}. Found: {list(final_map.keys())}")
                return []

            # Process data rows
            alarms = []
            for idx in range(header_row_idx + 1, len(df)):
                row = df.iloc[idx]
                # Pass the loop index to distinguish between identical rows in the same file
                alarm = self._process_excel_row(row, final_map, instance_index=idx)
                if alarm:
                    alarms.append(alarm)
            
            logger.info(f"Processed {len(alarms)} alarms from {file_path}")
            return alarms
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return []
    
    def process_raw_data(self, raw_lines: List[str]) -> List[ProcessedAlarm]:
        """
        Process raw alarm data (copy-pasted from portal)
        
        Args:
            raw_lines: List of raw alarm lines
            
        Returns:
            List of ProcessedAlarm objects
        """
        alarms = []
        
        for idx, line in enumerate(raw_lines):
            line = line.strip()
            if not line:
                continue
            
            # Use index to distinguish identical lines
            alarm = self._process_raw_line(line, instance_index=idx)
            if alarm:
                alarms.append(alarm)
        
        return alarms
    
    def _process_excel_row(self, row, col_map: Dict[str, int], instance_index: int = 0) -> Optional[ProcessedAlarm]:
        """Process a single Excel row using column map"""
        try:
            values = [str(v).strip() for v in row.values]
            
            # Safe extraction helper
            def get_val(key):
                idx = col_map.get(key)
                if idx is not None and idx < len(values):
                    return values[idx]
                return ""

            severity = get_val('severity')
            alarm_name = get_val('name')
            timestamp_str = get_val('time')
            source = get_val('source')
            
            # Check for toggle in the first few columns
            # The severity column index tells us where data starts generally
            severity_idx = col_map.get('severity', 1)
            is_toggle = False
            
            # Check columns before severity for "Toggle" indicators
            # We check up to severity_idx because toggle indicator is usually to the left
            for i in range(severity_idx):
                if i < len(values):
                    val = values[i].lower()
                    if 'toggle' in val:
                        is_toggle = True
                        break
            
            # Skip if no valid alarm name or source
            if not alarm_name or not source:
                return None
            
            # Skip alarms that should be ignored
            if self._should_skip_alarm(alarm_name):
                return None
            
            # Extract site code
            extracted = SiteCodeExtractor.extract(source)
            if not extracted:
                return None
            
            site_code = extracted.site_code
            
            # Get site info from master data
            site_info = master_data.get_site(site_code)
            
            # Skip if site not in our data
            if not site_info:
                return None
            
            # Parse timestamp
            timestamp = self._parse_timestamp(timestamp_str)
            
            # Create processed alarm
            return self._create_processed_alarm(
                alarm_type=alarm_name,
                severity=severity,
                timestamp=timestamp,
                timestamp_str=timestamp_str,
                site_code=site_code,
                site_name=extracted.full_name,
                site_info=site_info,
                is_toggle=is_toggle,
                raw_data='\t'.join(values),
                instance_index=instance_index,
                cell_info=extracted.cell_info
            )
            
        except Exception as e:
            logger.error(f"Error processing row: {e}")
            return None
    
    def _process_raw_line(self, line: str, instance_index: int = 0) -> Optional[ProcessedAlarm]:
        """Process a single raw line"""
        try:
            # Split by tab
            parts = line.split('\t')
            
            # Check for toggle
            is_toggle = False
            if parts[0].lower().strip() == 'toggle alarm':
                is_toggle = True
                parts = parts[1:]
            elif parts[0].strip() == '-':
                parts = parts[1:]
            
            if len(parts) < 4:
                return None
            
            severity = parts[0].strip()
            alarm_name = parts[1].strip()
            timestamp_str = parts[2].strip()
            source = parts[3].strip()
            
            # Skip if invalid
            if not alarm_name or not source:
                return None
            
            if self._should_skip_alarm(alarm_name):
                return None
            
            # Extract site code
            extracted = SiteCodeExtractor.extract(source)
            if not extracted:
                return None
            
            site_code = extracted.site_code
            site_info = master_data.get_site(site_code)
            
            if not site_info:
                return None
            
            timestamp = self._parse_timestamp(timestamp_str)
            
            return self._create_processed_alarm(
                alarm_type=alarm_name,
                severity=severity,
                timestamp=timestamp,
                timestamp_str=timestamp_str,
                site_code=site_code,
                site_name=extracted.full_name,
                site_info=site_info,
                is_toggle=is_toggle,
                raw_data=line,
                instance_index=instance_index,
                cell_info=extracted.cell_info
            )
            
        except Exception as e:
            return None
    
    def _create_processed_alarm(
        self,
        alarm_type: str,
        severity: str,
        timestamp: datetime,
        timestamp_str: str,
        site_code: str,
        site_name: str,
        site_info: SiteInfo,
        is_toggle: bool,
        raw_data: str,
        instance_index: int = 0,
        cell_info: Optional[str] = None
    ) -> ProcessedAlarm:
        """Create a ProcessedAlarm object"""
        
        # Generate unique ID - include instance_index to allow duplicates in the same scan
        import hashlib
        # We include instance_index so that two identical lines in the same portal view get different IDs
        # This allows them both to be sent, but keeps them stable across refreshes (same row index)
        id_source = f"{alarm_type}_{site_code}_{timestamp_str}_{instance_index}"
        alarm_id = hashlib.md5(id_source.encode()).hexdigest()[:16]
        
        # Determine category
        category = self._categorize_alarm(alarm_type)
        
        # Get B2S/OMO info from site_info
        b2s_company = site_info.b2s_company if site_info else None
        omo_company = site_info.omo_company if site_info else None
        is_b2s = b2s_company is not None
        is_omo = omo_company is not None
        
        return ProcessedAlarm(
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            severity=severity,
            timestamp=timestamp,
            timestamp_str=timestamp_str,
            site_code=site_code,
            site_name=site_name,
            site_info=site_info,
            mbu=site_info.new_mbu if site_info else "",
            is_toggle=is_toggle,
            is_b2s=is_b2s,
            is_omo=is_omo,
            b2s_company=b2s_company,
            omo_company=omo_company,
            b2s_id=site_info.omo_b2s_id if site_info else None,
            ftts_ring_id=site_info.ftts_ring_id if site_info else None,
            raw_data=raw_data,
            category=category,
            cell_info=cell_info
        )
    
    def _should_skip_alarm(self, alarm_name: str) -> bool:
        """Check if alarm should be skipped"""
        alarm_lower = alarm_name.lower().strip()
        
        skip_patterns = [
            "local cell unusable",
        ]
        
        for pattern in skip_patterns:
            if pattern in alarm_lower:
                return True
        
        return False
    
    def _categorize_alarm(self, alarm_type: str) -> AlarmCategory:
        """Categorize an alarm type"""
        alarm_lower = alarm_type.lower()
        
        if "csl" in alarm_lower:
            return AlarmCategory.CSL_FAULT
        elif "rf unit" in alarm_lower:
            return AlarmCategory.RF_UNIT
        elif "cell unavailable" in alarm_lower:
            return AlarmCategory.CELL_UNAVAILABLE
        elif any(x in alarm_lower for x in ["voltage", "battery", "ac main", "mains", "genset"]):
            return AlarmCategory.POWER_ALARM
        else:
            return AlarmCategory.OTHER
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime"""
        formats = [
            "%m-%d-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str.strip(), fmt)
            except ValueError:
                continue
        
        return datetime.now()
    
    def get_ordered_batches(self, alarms: List[ProcessedAlarm]) -> List[Tuple[str, str, List[ProcessedAlarm], bool]]:
        """
        Get batches of alarms ordered specifically as requested by the user.
        
        Order: 
        1. Categories: CSL -> RF -> AC -> Battery Temp -> Genset -> Low Volt -> System on Battery -> Toggle -> Cell Unavailable
        2. Group Priority within each category: MBUs (1-8) -> B2S (ATL, Edotco, Enfra, Tawal) -> OMO (Ufone, Telenore, CMpak)
        
        Returns:
            List of (group_name, alarm_type, alarms, is_toggle)
        """
        # Define Category Order
        category_order = [
            "CSL Fault",
            "RF Unit Maintenance Link Failure",
            "AC Main Failure",
            "Battery High Temp",
            "Genset Running",
            "Genset Operation",
            "Low Voltage",
            "System on Battery",
            "Toggle",  # Special handling for toggle
            "Cell Unavailable"
        ]
        
        # Define Group Order (Priority)
        mbu_list = [f"C1-LHR-0{i}" for i in range(1, 9)]
        b2s_list = ["ATL", "Edotco", "Enfrashare", "Tawal"]
        omo_list = ["Ufone", "Telenor", "CMpak", "Zong", "CMPAK", "CM-PAK"]
        
        # Helper to get priority score for a group
        def get_group_priority(alarm: ProcessedAlarm) -> int:
            if alarm.mbu in mbu_list:
                return mbu_list.index(alarm.mbu)
            if alarm.is_b2s and alarm.b2s_company in b2s_list:
                return 10 + b2s_list.index(alarm.b2s_company)
            if alarm.is_omo and alarm.omo_company in omo_list:
                return 20 + omo_list.index(alarm.omo_company)
            return 99

        batches = []
        
        for cat_name in category_order:
            # Filter alarms for this category
            if cat_name == "Toggle":
                cat_alarms = [a for a in alarms if a.is_toggle]
            else:
                cat_alarms = [a for a in alarms if a.alarm_type == cat_name and not a.is_toggle]
            
            if not cat_alarms:
                continue
                
            # Group these alarms by their target WhatsApp group
            group_map = defaultdict(list)
            for a in cat_alarms:
                group_name = None
                if a.mbu:
                    group_name = settings.get_whatsapp_group_name(a.mbu)
                elif a.is_b2s:
                    group_name = settings.get_b2s_group_name(a.b2s_company)
                elif a.is_omo:
                    group_name = settings.get_omo_group_name(a.omo_company)
                
                if group_name:
                    group_map[group_name].append(a)
            
            # Sort the found groups by their priority
            sorted_groups = sorted(group_map.keys(), key=lambda g: min([get_group_priority(a) for a in group_map[g]]))
            
            for group_name in sorted_groups:
                batch_alarms = group_map[group_name]
                # Check toggle setting if this is a toggle batch
                if cat_name == "Toggle":
                    mbu = batch_alarms[0].mbu
                    if self.should_skip_toggle_for_mbu(mbu):
                        continue
                
                batches.append((group_name, cat_name, batch_alarms, cat_name == "Toggle"))
                
        return batches

    def group_alarms_by_mbu(self, alarms: List[ProcessedAlarm]) -> Dict[str, Dict[str, AlarmBatch]]:
        """
        Group alarms by MBU and alarm type
        
        Returns:
            Dict[mbu -> Dict[alarm_type -> AlarmBatch]]
        """
        result: Dict[str, Dict[str, AlarmBatch]] = defaultdict(lambda: defaultdict(lambda: None))
        
        for alarm in alarms:
            mbu = alarm.mbu
            alarm_type = alarm.alarm_type
            
            if not mbu:
                continue
            
            # Get WhatsApp group name for MBU
            group_name = settings.get_whatsapp_group_name(mbu)
            if not group_name:
                continue
            
            # Initialize batch if needed
            if result[mbu][alarm_type] is None:
                result[mbu][alarm_type] = AlarmBatch(
                    alarm_type=alarm_type,
                    mbu=mbu,
                    group_name=group_name
                )
            
            # Add to appropriate list
            batch = result[mbu][alarm_type]
            if alarm.is_toggle:
                batch.toggle_alarms.append(alarm)
            else:
                batch.alarms.append(alarm)
        
        return result
    
    def group_alarms_for_b2s(self, alarms: List[ProcessedAlarm]) -> Dict[str, Dict[str, AlarmBatch]]:
        """
        Group B2S alarms by company and alarm type
        
        Returns:
            Dict[company -> Dict[alarm_type -> AlarmBatch]]
        """
        result: Dict[str, Dict[str, AlarmBatch]] = defaultdict(lambda: defaultdict(lambda: None))
        
        for alarm in alarms:
            if not alarm.is_b2s or not alarm.b2s_company:
                continue
            
            company = alarm.b2s_company
            alarm_type = alarm.alarm_type
            
            group_name = settings.get_b2s_group_name(company)
            if not group_name:
                continue
            
            if result[company][alarm_type] is None:
                result[company][alarm_type] = AlarmBatch(
                    alarm_type=alarm_type,
                    mbu=company,
                    group_name=group_name
                )
            
            # For B2S, we don't separate toggle alarms
            result[company][alarm_type].alarms.append(alarm)
        
        return result
    
    def group_alarms_for_omo(self, alarms: List[ProcessedAlarm]) -> Dict[str, Dict[str, AlarmBatch]]:
        """
        Group OMO alarms by company and alarm type
        
        Returns:
            Dict[company -> Dict[alarm_type -> AlarmBatch]]
        """
        result: Dict[str, Dict[str, AlarmBatch]] = defaultdict(lambda: defaultdict(lambda: None))
        
        for alarm in alarms:
            if not alarm.is_omo or not alarm.omo_company:
                continue
            
            company = alarm.omo_company
            alarm_type = alarm.alarm_type
            
            group_name = settings.get_omo_group_name(company)
            if not group_name:
                continue
            
            if result[company][alarm_type] is None:
                result[company][alarm_type] = AlarmBatch(
                    alarm_type=alarm_type,
                    mbu=company,
                    group_name=group_name
                )
            
            result[company][alarm_type].alarms.append(alarm)
        
        return result
    
    def _format_alarm_line(self, alarm: ProcessedAlarm, template: str) -> str:
        """Format a single alarm using a template"""
        from whatsapp_handler import WhatsAppMessageFormatter
        return WhatsAppMessageFormatter._format_alarm(alarm, template)
    
    def format_mbu_message(self, alarms: List[ProcessedAlarm]) -> str:
        """
        Format alarms for MBU WhatsApp group message
        Uses custom template from settings
        """
        if not alarms:
            return ""
        
        template = settings.message_formats.mbu_format
        lines = [self._format_alarm_line(alarm, template) for alarm in alarms]
        return '\n'.join(lines)
    
    def format_toggle_message(self, alarms: List[ProcessedAlarm]) -> str:
        """
        Format toggle alarms for MBU WhatsApp group message
        Uses custom template from settings
        """
        if not alarms:
            return ""
        
        template = settings.message_formats.toggle_format
        lines = [self._format_alarm_line(alarm, template) for alarm in alarms]
        return '\n'.join(lines)
    
    def format_b2s_message(self, alarms: List[ProcessedAlarm]) -> str:
        """
        Format alarms for B2S WhatsApp group message
        Uses custom template from settings
        """
        if not alarms:
            return ""
        
        template = settings.message_formats.b2s_format
        lines = [self._format_alarm_line(alarm, template) for alarm in alarms]
        return '\n'.join(lines)
    
    def format_omo_message(self, alarms: List[ProcessedAlarm]) -> str:
        """
        Format alarms for OMO WhatsApp group message
        Uses custom template from settings
        """
        if not alarms:
            return ""
        
        template = settings.message_formats.omo_format
        lines = [self._format_alarm_line(alarm, template) for alarm in alarms]
        return '\n'.join(lines)
    
    def should_skip_toggle_for_mbu(self, mbu: str) -> bool:
        """Check if toggle alarms should be skipped for this MBU"""
        return mbu in settings.skip_toggle_mbus
    
    # CSL Fault specific methods
    def process_csl_fault(self, alarm: ProcessedAlarm) -> List[Tuple[str, str, List[ProcessedAlarm]]]:
        """
        Process CSL Fault alarm for real-time sending
        Returns list of (group_name, group_type, alarms) tuples
        
        CSL Fault logic:
        - When new site appears, send all current CSL sites for that MBU/B2S/OMO
        """
        if alarm.category != AlarmCategory.CSL_FAULT:
            return []
        
        results = []
        mbu = alarm.mbu
        
        with self.lock:
            # Check if this is a new site for this MBU
            is_new = alarm.site_code not in self.csl_sites[mbu]
            
            # Add to tracking
            self.csl_sites[mbu].add(alarm.site_code)
            
            if is_new:
                # Get all current CSL alarms for this MBU
                all_mbu_csl = self._get_all_csl_for_mbu(mbu)
                
                # MBU Group
                group_name = settings.get_whatsapp_group_name(mbu)
                if group_name:
                    results.append((group_name, "MBU", all_mbu_csl))
                
                # B2S Group (if applicable)
                if alarm.is_b2s and alarm.b2s_company:
                    b2s_group = settings.get_b2s_group_name(alarm.b2s_company)
                    if b2s_group:
                        # Get all CSL for same B2S company
                        b2s_alarms = [a for a in all_mbu_csl if a.b2s_company == alarm.b2s_company]
                        results.append((b2s_group, "B2S", b2s_alarms))
                
                # OMO Group (if applicable)
                if alarm.is_omo and alarm.omo_company:
                    omo_group = settings.get_omo_group_name(alarm.omo_company)
                    if omo_group:
                        omo_alarms = [a for a in all_mbu_csl if a.omo_company == alarm.omo_company]
                        results.append((omo_group, "OMO", omo_alarms))
        
        return results
    
    def _get_all_csl_for_mbu(self, mbu: str) -> List[ProcessedAlarm]:
        """Get all current CSL alarms for an MBU"""
        alarms = []
        for site_code in self.csl_sites.get(mbu, set()):
            if site_code in self.processed_alarms:
                alarms.append(self.processed_alarms[site_code])
        return alarms
    
    def clear_csl_site(self, site_code: str):
        """Clear a CSL site (when it recovers)"""
        with self.lock:
            for mbu in self.csl_sites:
                self.csl_sites[mbu].discard(site_code)
            if site_code in self.processed_alarms:
                del self.processed_alarms[site_code]
    
    def get_alarm_statistics(self) -> Dict:
        """Get statistics about processed alarms"""
        stats = {
            "total_processed": len(self.processed_alarms),
            "by_type": defaultdict(int),
            "by_mbu": defaultdict(int),
            "by_category": defaultdict(int),
            "toggle_count": 0,
            "b2s_count": 0,
            "omo_count": 0,
        }
        
        for alarm in self.processed_alarms.values():
            stats["by_type"][alarm.alarm_type] += 1
            stats["by_mbu"][alarm.mbu] += 1
            stats["by_category"][alarm.category.value] += 1
            
            if alarm.is_toggle:
                stats["toggle_count"] += 1
            if alarm.is_b2s:
                stats["b2s_count"] += 1
            if alarm.is_omo:
                stats["omo_count"] += 1
        
        return stats


# Lazy global instance to avoid import-time initialization issues
class _LazyAlarmProcessor:
    """Lazy wrapper to avoid creating AlarmProcessor on import"""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AlarmProcessor()
        return cls._instance

    def __getattr__(self, name):
        return getattr(self.get_instance(), name)

# Create lazy instance
alarm_processor = _LazyAlarmProcessor()


# Test function
def test_processor():
    """Test the alarm processor"""
    # Load master data first
    master_data.load()
    
    # Test raw data processing
    test_lines = [
        "-\tMajor\tLow Voltage\t12-11-2025 05:20:03\tLTE_LHR1459__S_Eden_Value_Homes_MDLH4515",
        "Toggle alarm\tMajor\tLow Voltage\t12-11-2025 07:00:29\tLTE_SRK3897__S_Zarai_Bank_Sharaqpur_MDRH1425",
        "-\tMajor\tCSL Fault\t12-11-2025 01:04:06\tRUR6499__S_KhankeMod",
        "-\tMajor\tCell Unavailable\t12-11-2025 00:21:30\teNodeB Function Name=LTE_HWY0993__P_KudaltiMor, Local Cell ID=53, Cell Name=L1HWY09933M3, Cell FDD TDD indication=CELL_FDD",
    ]
    
    alarms = alarm_processor.process_raw_data(test_lines)
    
    print("Processed Alarms:")
    print("=" * 60)
    for alarm in alarms:
        print(f"Type: {alarm.alarm_type}")
        print(f"Site: {alarm.site_code} - {alarm.site_name}")
        print(f"MBU: {alarm.mbu}")
        print(f"Toggle: {alarm.is_toggle}")
        print(f"B2S: {alarm.is_b2s} ({alarm.b2s_company})")
        print(f"OMO: {alarm.is_omo} ({alarm.omo_company})")
        print("-" * 40)


if __name__ == "__main__":
    test_processor()