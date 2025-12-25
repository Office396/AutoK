[1mdiff --git a/alarm_processor.py b/alarm_processor.py[m
[1mindex 226768a..e69de29 100644[m
[1m--- a/alarm_processor.py[m
[1m+++ b/alarm_processor.py[m
[36m@@ -1,711 +0,0 @@[m
[31m-"""[m
[31m-Alarm Processor[m
[31m-Processes, categorizes, and formats alarms for sending to WhatsApp groups[m
[31m-"""[m
[31m-[m
[31m-import re[m
[31m-from datetime import datetime, timedelta[m
[31m-from typing import Dict, List, Optional, Tuple, Set[m
[31m-from dataclasses import dataclass, field[m
[31m-from enum import Enum[m
[31m-from collections import defaultdict[m
[31m-import threading[m
[31m-[m
[31m-from config import settings, AlarmTypes, PowerStatusClassifier[m
[31m-from master_data import master_data, SiteInfo[m
[31m-from site_code_extractor import SiteCodeExtractor, ExtractedSiteInfo[m
[31m-from logger_module import logger[m
[31m-[m
[31m-[m
[31m-class AlarmCategory(Enum):[m
[31m-    """Categories of alarms"""[m
[31m-    CSL_FAULT = "CSL Fault"[m
[31m-    RF_UNIT = "RF Unit"[m
[31m-    CELL_UNAVAILABLE = "Cell Unavailable"[m
[31m-    POWER_ALARM = "Power Alarm"[m
[31m-    OTHER = "Other"[m
[31m-[m
[31m-[m
[31m-@dataclass[m
[31m-class ProcessedAlarm:[m
[31m-    """Processed alarm ready for sending"""[m
[31m-    alarm_id: str  # Unique identifier[m
[31m-    alarm_type: str  # e.g., "Low Voltage"[m
[31m-    severity: str  # e.g., "Major"[m
[31m-    timestamp: datetime[m
[31m-    timestamp_str: str  # Original timestamp string[m
[31m-    site_code: str  # e.g., "LHR9147"[m
[31m-    site_name: str  # Full site name[m
[31m-    site_info: Optional[SiteInfo]  # Master data info[m
[31m-    mbu: str  # MBU code[m
[31m-    is_toggle: bool  # Toggle alarm flag[m
[31m-    is_b2s: bool  # B2S site flag[m
[31m-    is_omo: bool  # OMO site flag[m
[31m-    b2s_company: Optional[str][m
[31m-    omo_company: Optional[str][m
[31m-    b2s_id: Optional[str]  # B2S/OMO ID[m
[31m-    ftts_ring_id: Optional[str][m
[31m-    raw_data: str  # Original alarm string[m
[31m-    category: AlarmCategory[m
[31m-    cell_info: Optional[str] = None  # For sector alarms[m
[31m-    [m
[31m-    def __hash__(self):[m
[31m-        return hash(self.alarm_id)[m
[31m-    [m
[31m-    def __eq__(self, other):[m
[31m-        if isinstance(other, ProcessedAlarm):[m
[31m-            return self.alarm_id == other.alarm_id[m
[31m-        return False[m
[31m-[m
[31m-[m
[31m-@dataclass[m
[31m-class AlarmBatch:[m
[31m-    """Batch of alarms grouped for sending"""[m
[31m-    alarm_type: str[m
[31m-    mbu: str[m
[31m-    group_name: str[m
[31m-    alarms: List[ProcessedAlarm] = field(default_factory=list)[m
[31m-    toggle_alarms: List[ProcessedAlarm] = field(default_factory=list)[m
[31m-    [m
[31m-    @property[m
[31m-    def total_count(self) -> int:[m
[31m-        return len(self.alarms) + len(self.toggle_alarms)[m
[31m-    [m
[31m-    @property[m
[31m-    def regular_count(self) -> int:[m
[31m-        return len(self.alarms)[m
[31m-    [m
[31m-    @property[m
[31m-    def toggle_count(self) -> int:[m
[31m-        return len(self.toggle_alarms)[m
[31m-[m
[31m-[m
[31m-class AlarmProcessor:[m
[31m-    """Main alarm processor class"""[m
[31m-    [m
[31m-    def __init__(self):[m
[31m-        self.processed_alarms: Dict[str, ProcessedAlarm] = {}[m
[31m-        self.alarm_history: Dict[str, datetime] = {}  # alarm_id -> last_sent_time[m
[31m-        self.csl_sites: Dict[str, Set[str]] = defaultdict(set)  # mbu -> set of site_codes[m
[31m-        self.lock = threading.Lock()[m
[31m-        [m
[31m-        # Ensure master data is loaded[m
[31m-        if not master_data.is_loaded:[m
[31m-            master_data.load()[m
[31m-    [m
[31m-    def process_exported_excel(self, file_path: str) -> List[ProcessedAlarm]:[m
[31m-        """[m
[31m-        Process an exported Excel file from the portal[m
[31m-        [m
[31m-        Args:[m
[31m-            file_path: Path to exported Excel file[m
[31m-            [m
[31m-        Returns:[m
[31m-            List of ProcessedAlarm objects[m
[31m-        """[m
[31m-        import pandas as pd[m
[31m-        [m
[31m-        try:[m
[31m-            # Read Excel file[m
[31m-            df = pd.read_excel(file_path, header=None, dtype=str)[m
[31m-            df = df.fillna('')[m
[31m-            [m
[31m-            # Find the header row (contains "Severity", "Name", etc.)[m
[31m-            header_row_idx = None[m
[31m-            col_map = {}[m
[31m-            [m
[31m-            for idx, row in df.iterrows():[m
[31m-                row_values = [str(v).strip() for v in row.values][m
[31m-                # Check for key columns[m
[31m-                if 'Severity' in row_values and 'Name' in row_values:[m
[31m-                    header_row_idx = idx[m
[31m-                    # Build column map[m
[31m-                    for col_idx, val in enumerate(row_values):[m
[31m-                        if val in ['Severity', 'Name', 'Last Occurred (NT)', 'Alarm Source', 'MO Name']:[m
[31m-                            col_map[val] = col_idx[m
[31m-                    break[m
[31m-            [m
[31m-            if header_row_idx is None:[m
[31m-                logger.error(f"Could not find header row in {file_path}")[m
[31m-                return [][m
[31m-            [m
[31m-            # Map alternative column names to standard keys[m
[31m-            final_map = {}[m
[31m-            if 'Severity' in col_map:[m
[31m-                final_map['severity'] = col_map['Severity'][m
[31m-            if 'Name' in col_map:[m
[31m-                final_map['name'] = col_map['Name'][m
[31m-            [m
[31m-            # Timestamp might be "Last Occurred (NT)" or similar[m
[31m-            if 'Last Occurred (NT)' in col_map:[m
[31m-                final_map['time'] = col_map['Last Occurred (NT)'][m
[31m-            elif 'Last Occurred' in col_map:[m
[31m-                final_map['time'] = col_map['Last Occurred'][m
[31m-                [m
[31m-            # Source might be "Alarm Source" or "MO Name"[m
[31m-            if 'Alarm Source' in col_map:[m
[31m-                final_map['source'] = col_map['Alarm Source'][m
[31m-            elif 'MO Name' in col_map:[m
[31m-                final_map['source'] = col_map['MO Name'][m
[31m-                [m
[31m-            # Verify we have minimum required columns[m
[31m-            if 'name' not in final_map or 'source' not in final_map:[m
[31m-                logger.error(f"Missing required columns (Name/Source) in {file_path}. Found: {list(final_map.keys())}")[m
[31m-                return [][m
[31m-[m
[31m-            # Process data rows[m
[31m-            alarms = [][m
[31m-            for idx in range(header_row_idx + 1, len(df)):[m
[31m-                row = df.iloc[idx][m
[31m-                alarm = self._process_excel_row(row, final_map)[m
[31m-                if alarm:[m
[31m-                    alarms.append(alarm)[m
[31m-            [m
[31m-            logger.info(f"Processed {len(alarms)} alarms from {file_path}")[m
[31m-            return alarms[m
[31m-            [m
[31m-        except Exception as e:[m
[31m-            logger.error(f"Error processing Excel file: {e}")[m
[31m-            return [][m
[31m-    [m
[31m-    def process_raw_data(self, raw_lines: List[str]) -> List[ProcessedAlarm]:[m
[31m-        """[m
[31m-        Process raw alarm data (copy-pasted from portal)[m
[31m-        [m
[31m-        Args:[m
[31m-            raw_lines: List of raw alarm lines[m
[31m-            [m
[31m-        Returns:[m
[31m-            List of ProcessedAlarm objects[m
[31m-        """[m
[31m-        alarms = [][m
[31m-        [m
[31m-        for line in raw_lines:[m
[31m-            line = line.strip()[m
[31m-            if not line:[m
[31m-                continue[m
[31m-            [m
[31m-            alarm = self._process_raw_line(line)[m
[31m-        