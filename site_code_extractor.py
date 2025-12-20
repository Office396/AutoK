"""
Site Code Extractor
Extracts site codes from various alarm format strings
Handles multiple formats found in portal data
"""

import re
from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class ExtractedSiteInfo:
    """Information extracted from alarm source string"""
    site_code: str  # e.g., "LHR9147"
    site_id: str  # e.g., "9147" (4 digits only)
    prefix: str  # e.g., "LHR"
    full_name: str  # e.g., "LHR9147__S_RajputPark"
    cell_info: Optional[str] = None  # For sector alarms
    original_string: str = ""


class SiteCodeExtractor:
    """
    Extracts site codes from various alarm format strings
    
    Supported formats:
    - Format 1: RUR6499__S_KhankeMod (CSL Fault - MO Name)
    - Format 2: LTE_LHR9147__S_RajputPark (Alarm Source with LTE_ prefix)
    - Format 3: LTE_RUR6614_S_HardosohalMuslimRd (single underscore before S)
    - Format 4: eNodeB Function Name=LTE_HWY0993__P_KudaltiMor, Local Cell ID=51...
    - Format 5: L1FRQ59402A (Cell name format)
    """
    
    # Regex patterns for different formats
    PATTERNS = [
        # Pattern 1: eNodeB Function Name=LTE_XXX0000__X_Name, ...
        re.compile(
            r'(?:eNodeB\s*Function\s*Name\s*=\s*)?'
            r'(?:LTE_)?'
            r'([A-Z]{3}\d{4})'
            r'(?:__|_)'
            r'([SHPT]_[\w\s\-_]+)',
            re.IGNORECASE
        ),
        
        # Pattern 2: LTE_XXX0000__X_Name or LTE_XXX0000_X_Name
        re.compile(
            r'(?:LTE_)?'
            r'([A-Z]{3}\d{4})'
            r'(?:__|_)'
            r'([SHPT]_[\w\s\-_]+)',
            re.IGNORECASE
        ),
        
        # Pattern 3: XXX0000__X_Name (without LTE prefix)
        re.compile(
            r'^([A-Z]{3}\d{4})'
            r'(?:__|_)'
            r'([SHPT]_[\w\s\-_]+)',
            re.IGNORECASE
        ),
        
        # Pattern 4: Just site code XXX0000
        re.compile(
            r'(?:LTE_)?([A-Z]{3}\d{4})',
            re.IGNORECASE
        ),
    ]
    
    # Pattern for cell name (e.g., L1LHR52692A)
    CELL_NAME_PATTERN = re.compile(
        r'Cell\s*Name\s*=\s*L\d([A-Z]{3}\d{4})\d[A-Z]',
        re.IGNORECASE
    )
    
    # Pattern to extract from complex eNodeB string
    ENODEB_PATTERN = re.compile(
        r'eNodeB\s*Function\s*Name\s*=\s*(?:LTE_)?([A-Z]{3}\d{4})',
        re.IGNORECASE
    )
    
    @classmethod
    def extract(cls, source_string: str) -> Optional[ExtractedSiteInfo]:
        """
        Extract site code from any alarm source string
        
        Args:
            source_string: The alarm source or MO Name string
            
        Returns:
            ExtractedSiteInfo or None if no valid site code found
        """
        if not source_string or not isinstance(source_string, str):
            return None
        
        source_string = source_string.strip()
        
        # Try eNodeB pattern first (for complex Cell Unavailable alarms)
        enodeb_match = cls.ENODEB_PATTERN.search(source_string)
        if enodeb_match:
            site_code = enodeb_match.group(1).upper()
            return cls._create_extracted_info(site_code, source_string)
        
        # Try cell name pattern
        cell_match = cls.CELL_NAME_PATTERN.search(source_string)
        if cell_match:
            site_code = cell_match.group(1).upper()
            # Extract cell info
            cell_info = None
            cell_name_match = re.search(r'Cell\s*Name\s*=\s*(\w+)', source_string)
            if cell_name_match:
                cell_info = cell_name_match.group(1)
            
            info = cls._create_extracted_info(site_code, source_string)
            if info:
                info.cell_info = cell_info
            return info
        
        # Try standard patterns
        for pattern in cls.PATTERNS:
            match = pattern.search(source_string)
            if match:
                site_code = match.group(1).upper()
                return cls._create_extracted_info(site_code, source_string)
        
        return None
    
    @classmethod
    def _create_extracted_info(cls, site_code: str, original: str) -> Optional[ExtractedSiteInfo]:
        """Create ExtractedSiteInfo from site code"""
        if not site_code or len(site_code) != 7:
            return None
        
        # Validate format: 3 letters + 4 digits
        if not re.match(r'^[A-Z]{3}\d{4}$', site_code):
            return None
        
        prefix = site_code[:3]
        site_id = site_code[3:]
        
        # Extract full name if possible
        full_name = cls._extract_full_name(original, site_code)
        
        return ExtractedSiteInfo(
            site_code=site_code,
            site_id=site_id,
            prefix=prefix,
            full_name=full_name,
            original_string=original
        )
    
    @classmethod
    def _extract_full_name(cls, source: str, site_code: str) -> str:
        """Extract the full site name from source string"""
        # Try to find pattern like XXX0000__X_Name or LTE_XXX0000__X_Name
        patterns = [
            re.compile(rf'(?:LTE_)?({site_code}(?:__|_)[SHPT]_[\w\s\-_]+)', re.IGNORECASE),
            re.compile(rf'({site_code}(?:__|_)[SHPT]_[\w\s\-_]+)', re.IGNORECASE),
        ]
        
        for pattern in patterns:
            match = pattern.search(source)
            if match:
                full_name = match.group(1)
                # Clean up the name
                full_name = re.sub(r'\s*,\s*Local\s*Cell.*$', '', full_name)
                full_name = re.sub(r'\s*,\s*Cell\s*FDD.*$', '', full_name)
                return full_name.strip()
        
        return site_code
    
    @classmethod
    def extract_multiple(cls, source_string: str) -> List[ExtractedSiteInfo]:
        """
        Extract all site codes from a string (for strings with multiple sites)
        
        Args:
            source_string: String that may contain multiple site codes
            
        Returns:
            List of ExtractedSiteInfo
        """
        if not source_string:
            return []
        
        results = []
        seen_codes = set()
        
        # Find all potential site codes
        all_matches = re.findall(r'(?:LTE_)?([A-Z]{3}\d{4})', source_string, re.IGNORECASE)
        
        for match in all_matches:
            site_code = match.upper()
            if site_code not in seen_codes:
                seen_codes.add(site_code)
                info = cls._create_extracted_info(site_code, source_string)
                if info:
                    results.append(info)
        
        return results
    
    @classmethod
    def normalize_site_code(cls, code: str) -> Optional[str]:
        """
        Normalize a site code to standard format (XXX0000)
        
        Args:
            code: Any form of site code
            
        Returns:
            Normalized site code or None
        """
        if not code:
            return None
        
        code = code.strip().upper()
        
        # Remove LTE_ prefix if present
        if code.startswith('LTE_'):
            code = code[4:]
        
        # Extract just the site code part
        match = re.match(r'^([A-Z]{3}\d{4})', code)
        if match:
            return match.group(1)
        
        return None
    
    @classmethod
    def validate_site_code(cls, code: str) -> bool:
        """
        Validate if a string is a valid site code format
        
        Args:
            code: String to validate
            
        Returns:
            True if valid site code format
        """
        if not code:
            return False
        
        normalized = cls.normalize_site_code(code)
        if not normalized:
            return False
        
        return bool(re.match(r'^[A-Z]{3}\d{4}$', normalized))


# Test function
def test_extractor():
    """Test the site code extractor with various formats"""
    test_cases = [
        "RUR6499__S_KhankeMod",
        "LTE_LHR9147__S_RajputPark",
        "LTE_RUR6614_S_HardosohalMuslimRd",
        "eNodeB Function Name=LTE_HWY0993__P_KudaltiMor, Local Cell ID=51, Cell Name=L1HWY09933M1, Cell FDD TDD indication=CELL_FDD",
        "LTE_LHR5864__S_KhayabanEZohra_CMPak40488",
        "Major	CSL Fault	12-11-2025 01:04:06	RUR6499__S_KhankeMod",
        "LTE_RUR1302__S_Chak55 5L",
    ]
    
    print("Testing Site Code Extractor:")
    print("=" * 60)
    
    for test in test_cases:
        result = SiteCodeExtractor.extract(test)
        if result:
            print(f"Input: {test[:50]}...")
            print(f"  Site Code: {result.site_code}")
            print(f"  Full Name: {result.full_name}")
            print()
        else:
            print(f"Input: {test[:50]}...")
            print(f"  No match found!")
            print()


if __name__ == "__main__":
    test_extractor()