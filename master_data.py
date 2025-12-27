"""
Master Data Handler
Reads and manages the Master Excel sheet with all site information
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

# Import settings carefully to avoid circular import
try:
    from config import settings, BASE_DIR, DATA_DIR
except ImportError:
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.absolute()
    DATA_DIR = BASE_DIR / "data"
    settings = None


@dataclass
class SiteInfo:
    """Information about a single site"""
    site_id: str
    site_code: str
    technology: str
    old_mbu: str
    site_name: str
    site_type: str
    dependent_sites: str
    power_status: str
    latitude: float
    longitude: float
    new_mbu: str
    dg_capacity: str
    dg_count: str
    share_holder: str
    remarks: str
    site_status: str
    omo_b2s_name: str
    omo_b2s_id: str
    hw_mbu_lead: str
    day_tech: str
    night_tech: str
    jazz_mbu_tech: str
    jazz_mbu_lead: str
    dependency_count: str
    connectivity: str
    ftts_ring_id: str
    site_type_new: str
    dependent: str
    new_dependent: str
    b2s_company: Optional[str] = None
    omo_company: Optional[str] = None
    
    def __post_init__(self):
        """Compute B2S and OMO company from power status"""
        self.b2s_company = self._get_b2s_company(self.power_status)
        self.omo_company = self._get_omo_company(self.power_status)
    
    def _get_b2s_company(self, power_status: str) -> Optional[str]:
        """Get B2S company from power status with intelligent matching"""
        if not power_status:
            return None

        # Normalize the power status - handle case, spaces, and common variations
        ps_normalized = power_status.lower().strip()

        # Remove extra spaces and normalize separators
        ps_normalized = ' '.join(ps_normalized.split())
        ps_normalized = ps_normalized.replace('/', ' ').replace('\\', ' ').replace('-', ' ')

        b2s_patterns = {
            "ATL": ["guest atl", "atl", "atlantic"],
            "Edotco": ["guest edotco", "edotco", "e dotco", "e.co"],
            "Enfrashare": ["guest enfrashare", "enfrashare", "enfra share", "enfra"],
            "Tawal": ["guest tawal", "tawal"]
        }

        for company, patterns in b2s_patterns.items():
            for pattern in patterns:
                # Check if pattern exists in normalized string
                if pattern in ps_normalized:
                    return company

                # Also check if normalized string contains key parts
                pattern_parts = pattern.split()
                if all(part in ps_normalized for part in pattern_parts):
                    return company

        return None
    
    def _get_omo_company(self, power_status: str) -> Optional[str]:
        """Get OMO company from power status with intelligent matching"""
        if not power_status:
            return None

        # Normalize the power status - handle case, spaces, and common variations
        ps_normalized = power_status.lower().strip()

        # Remove extra spaces and normalize separators
        ps_normalized = ' '.join(ps_normalized.split())
        ps_normalized = ps_normalized.replace('/', ' ').replace('\\', ' ').replace('-', ' ')

        omo_patterns = {
            "Zong": ["guest zong", "cm pak", "cmpak", "jazz guest cm pak", "jazz host cm pak", "zong"],
            "Ufone": ["guest ufone", "jazz guest ufone", "jazz host ufone", "ufone"],
            "Telenor": ["guest telenor", "jazz guest telenor", "telenor"]
        }

        for company, patterns in omo_patterns.items():
            for pattern in patterns:
                # Check if pattern exists in normalized string
                if pattern in ps_normalized:
                    return company

                # Also check if normalized string contains key parts
                pattern_parts = pattern.split()
                if all(part in ps_normalized for part in pattern_parts):
                    return company

        return None
    
    @property
    def is_b2s(self) -> bool:
        return self.b2s_company is not None
    
    @property
    def is_omo(self) -> bool:
        return self.omo_company is not None
    
    @property
    def is_standby(self) -> bool:
        return self.power_status and "standby" in self.power_status.lower()


class MasterDataManager:
    """Manages the master Excel data"""
    
    def __init__(self, file_path: Optional[str] = None):
        if file_path:
            self.file_path = file_path
        elif settings:
            self.file_path = settings.master_file_path
        else:
            self.file_path = str(DATA_DIR / "Master_Data.xlsx")
        
        self.df: Optional[pd.DataFrame] = None
        self.sites: Dict[str, SiteInfo] = {}
        self.site_codes: List[str] = []
        self._loaded = False
    
    @property
    def is_loaded(self) -> bool:
        """Check if data is loaded"""
        return self._loaded
    
    @property
    def site_count(self) -> int:
        """Get number of sites"""
        return len(self.sites)
    
    def load(self) -> bool:
        """Load the master Excel file"""
        try:
            path = Path(self.file_path)
            if not path.exists():
                print(f"Master file not found: {self.file_path}")
                return False
            
            print(f"Loading master data from: {self.file_path}")
            self.df = pd.read_excel(
                self.file_path, 
                sheet_name='Master',
                header=0,
                dtype=str
            )
            
            self.df = self.df.fillna('')
            
            print(f"Excel file has {len(self.df)} rows")
            
            self.sites = {}
            self.site_codes = []
            
            skipped_rows = []
            duplicate_codes = []
            duplicate_details = []
            
            for idx, row in self.df.iterrows():
                try:
                    site_info = self._parse_row(row)
                    if site_info and site_info.site_code:
                        if site_info.site_code in self.sites:
                            duplicate_codes.append(site_info.site_code)
                            existing = self.sites[site_info.site_code]
                            duplicate_details.append({
                                'site_code': site_info.site_code,
                                'row_number': idx + 2,
                                'new_name': site_info.site_name,
                                'existing_name': existing.site_name,
                                'new_mbu': site_info.new_mbu,
                                'existing_mbu': existing.new_mbu
                            })
                        else:
                            self.sites[site_info.site_code] = site_info
                            self.site_codes.append(site_info.site_code)
                    else:
                        skipped_rows.append(idx + 2)
                except Exception as e:
                    skipped_rows.append(idx + 2)
                    continue
            
            self._loaded = True
            
            print(f"")
            print(f"=" * 60)
            print(f"MASTER DATA LOAD SUMMARY")
            print(f"=" * 60)
            print(f"Total rows in Excel: {len(self.df)}")
            print(f"Sites loaded: {len(self.sites)}")
            print(f"Skipped rows: {len(skipped_rows)}")
            print(f"Duplicate codes: {len(duplicate_codes)}")
            print(f"=" * 60)
            
            if skipped_rows:
                if len(skipped_rows) <= 10:
                    print(f"\n⚠️ Skipped rows (empty/invalid): {skipped_rows}")
                else:
                    print(f"\n⚠️ Skipped {len(skipped_rows)} rows. First 10: {skipped_rows[:10]}")
            
            if duplicate_details:
                print(f"\n" + "=" * 60)
                print(f"⚠️ DUPLICATE SITE CODES FOUND:")
                print(f"=" * 60)
                for dup in duplicate_details:
                    print(f"")
                    print(f"  📍 Site Code: {dup['site_code']}")
                    print(f"     Excel Row: {dup['row_number']}")
                    print(f"     This Site Name: {dup['new_name'][:50]}...")
                    print(f"     This MBU: {dup['new_mbu']}")
                    print(f"     ─────────────────────────────────")
                    print(f"     Already Loaded Name: {dup['existing_name'][:50]}...")
                    print(f"     Already Loaded MBU: {dup['existing_mbu']}")
                    print(f"     ⚠️ This duplicate was SKIPPED (first one kept)")
                print(f"")
                print(f"=" * 60)
                print(f"TIP: Check your Excel file and remove duplicate site codes")
                print(f"=" * 60)
            
            print(f"")
            
            return True
            
        except Exception as e:
            print(f"Error loading master file: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _parse_row(self, row) -> Optional[SiteInfo]:
        """Parse a row into SiteInfo"""
        try:
            values = row.tolist()
            
            def get_val(idx: int) -> str:
                if idx < len(values):
                    val = values[idx]
                    return str(val).strip() if pd.notna(val) and val != '' else ''
                return ''
            
            site_code = get_val(1)
            if not site_code or len(site_code) < 4:
                return None
            
            site_code = site_code.strip().upper()
            
            return SiteInfo(
                site_id=get_val(0),
                site_code=site_code,
                technology=get_val(2),
                old_mbu=get_val(3),
                site_name=get_val(4),
                site_type=get_val(5),
                dependent_sites=get_val(6),
                power_status=get_val(7),
                latitude=self._safe_float(get_val(8)),
                longitude=self._safe_float(get_val(9)),
                new_mbu=get_val(10),
                dg_capacity=get_val(11) if len(values) > 11 else '',
                dg_count=get_val(12) if len(values) > 12 else '',
                share_holder=get_val(14) if len(values) > 14 else '',
                remarks=get_val(15) if len(values) > 15 else '',
                site_status=get_val(18) if len(values) > 18 else '',
                omo_b2s_name=get_val(19) if len(values) > 19 else '',
                omo_b2s_id=get_val(20) if len(values) > 20 else '',
                hw_mbu_lead=get_val(21) if len(values) > 21 else '',
                day_tech=get_val(22) if len(values) > 22 else '',
                night_tech=get_val(23) if len(values) > 23 else '',
                jazz_mbu_tech=get_val(24) if len(values) > 24 else '',
                jazz_mbu_lead=get_val(25) if len(values) > 25 else '',
                dependency_count=get_val(26) if len(values) > 26 else '',
                connectivity=get_val(27) if len(values) > 27 else '',
                ftts_ring_id=get_val(28) if len(values) > 28 else '',
                site_type_new=get_val(29) if len(values) > 29 else '',
                dependent=get_val(30) if len(values) > 30 else '',
                new_dependent=get_val(31) if len(values) > 31 else ''
            )
        except Exception as e:
            return None
    
    def _safe_float(self, value: str) -> float:
        """Safely convert to float"""
        try:
            if value:
                return float(value)
            return 0.0
        except:
            return 0.0
    
    def get_site(self, site_code: str) -> Optional[SiteInfo]:
        """Get site information by site code"""
        if not self._loaded:
            self.load()
        
        site_code = site_code.upper().strip()
        
        if site_code in self.sites:
            return self.sites[site_code]
        
        for stored_code in self.sites.keys():
            if stored_code.upper() == site_code:
                return self.sites[stored_code]
        
        return None
    
    def site_exists(self, site_code: str) -> bool:
        """Check if site exists in master data"""
        return self.get_site(site_code) is not None
    
    def get_mbu(self, site_code: str) -> Optional[str]:
        """Get MBU for a site"""
        site = self.get_site(site_code)
        return site.new_mbu if site else None
    
    def get_sites_by_mbu(self, mbu: str) -> List[SiteInfo]:
        """Get all sites for an MBU"""
        if not self._loaded:
            self.load()
        return [site for site in self.sites.values() if site.new_mbu == mbu]
    
    def get_b2s_sites(self) -> List[SiteInfo]:
        """Get all B2S sites"""
        if not self._loaded:
            self.load()
        return [site for site in self.sites.values() if site.is_b2s]
    
    def get_omo_sites(self) -> List[SiteInfo]:
        """Get all OMO sites"""
        if not self._loaded:
            self.load()
        return [site for site in self.sites.values() if site.is_omo]
    
    def get_all_mbus(self) -> List[str]:
        """Get list of all unique MBUs"""
        if not self._loaded:
            self.load()
        mbus = set(site.new_mbu for site in self.sites.values() if site.new_mbu)
        return sorted(list(mbus))
    
    def search_sites(self, query: str) -> List[SiteInfo]:
        """Search sites by code or name"""
        if not self._loaded:
            self.load()
        
        query = query.lower().strip()
        results = []
        for site in self.sites.values():
            if (query in site.site_code.lower() or 
                query in site.site_name.lower() or
                query in site.site_id.lower()):
                results.append(site)
        return results
    
    def reload(self) -> bool:
        """Reload the master data"""
        self._loaded = False
        self.sites = {}
        self.site_codes = []
        return self.load()


# Global instance
master_data = MasterDataManager()