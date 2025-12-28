"""
Browser Manager
Manages both Portal and WhatsApp Web in separate browser instances
Optimized for Huawei MAE Portal login with session recovery
"""

import os
import time
import threading
import shutil
from typing import Optional, Callable, List, Dict
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

from config import settings, PROFILES_DIR, EXPORTS_DIR, BASE_DIR
from logger_module import logger

class TabType(Enum):
    """Types of browser tabs"""
    WHATSAPP = "WhatsApp Web"
    MAIN_TOPOLOGY = "Main Topology"
    CSL_FAULT = "CSL Fault"
    RF_UNIT = "RF Unit"
    NODEB_CELL = "NodeB Cell"
    ALL_ALARMS = "All Alarms"

@dataclass
class BrowserStatus:
    """Browser status"""
    is_open: bool = False
    whatsapp_ready: bool = False
    portal_logged_in: bool = False
    active_tab: Optional[TabType] = None
    tab_handles: Dict[TabType, str] = field(default_factory=dict)

class BrowserManager:
    """
    Manages browser instances for Portal and WhatsApp
    """
    
    WHATSAPP_URL = "https://web.whatsapp.com"
    
    PORTAL_URLS = {
        TabType.MAIN_TOPOLOGY: "https://10.226.101.71:31943/ossfacewebsite/index.html#Access/Access_MainTopoTitle?switch",
        TabType.CSL_FAULT: "https://10.226.101.71:31943/ossfacewebsite/index.html#Access/fmAlarmView?switch",
        TabType.RF_UNIT: "https://10.226.101.71:31943/ossfacewebsite/index.html#Access/fmAlarmView@@fmAlarmApp_alarmView_templateId835%26tabTitle%3DRF-Unit%20AR?switch=undefined&maeUrl=%2Feviewwebsite%2Findex.html%23path%3D%2FfmAlarmApp%2FfmAlarmView%26templateId%3D835%26fmPage%3Dtrue&maeTitle=Current%20Alarms%20-%20%5BRF-Unit%20AR%5D&loadType=iframe",
        TabType.NODEB_CELL: "https://10.226.101.71:31943/ossfacewebsite/index.html#Access/fmAlarmView@@fmAlarmApp_alarmView_templateId803%26tabTitle%3DC1%20NodeB%20UMTS%20Cell%20Unavailable%20.?switch=undefined&maeUrl=%2Feviewwebsite%2Findex.html%23path%3D%2FfmAlarmApp%2FfmAlarmView%26templateId%3D803%26fmPage%3Dtrue&maeTitle=Current%20Alarms%20-%20%5BC1%20NodeB%20UMTS%20Cell%20Unavailable%20.%5D&loadType=iframe",
        TabType.ALL_ALARMS: "https://10.226.101.71:31943/ossfacewebsite/index.html#Access/fmAlarmView@@fmAlarmApp_alarmView_templateId592%26tabTitle%3Dc1-c2%20All%20Alarm?switch=undefined&maeUrl=%2Feviewwebsite%2Findex.html%23path%3D%2FfmAlarmApp%2FfmAlarmView%26templateId%3D592%26fmPage%3Dtrue&maeTitle=Current%20Alarms%20-%20%5Bc1-c2%20All%20Alarm%5D&loadType=iframe",
    }
    
    def __init__(self):
        self.portal_driver: Optional[webdriver.Chrome] = None
        self.whatsapp_driver: Optional[webdriver.Chrome] = None
        self.driver: Optional[webdriver.Chrome] = None  # Alias for portal_driver
        self.status = BrowserStatus()
        self.lock = threading.Lock()
        self._status_callbacks: List[Callable] = []
        
        # Ensure profiles directory exists
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    
    def add_status_callback(self, callback: Callable):
        self._status_callbacks.append(callback)
    
    def _notify_status(self):
        for callback in self._status_callbacks:
            try:
                callback(self.status)
            except:
                pass

    def _create_driver(self, profile_name: str) -> webdriver.Chrome:
        """Create a Chrome driver with a specific profile"""
        profile_path = PROFILES_DIR / profile_name
        profile_path.mkdir(parents=True, exist_ok=True)
        
        # Clean up stale locks
        self._cleanup_profile_locks(profile_path)
        
        chrome_options = Options()
        # Use forward slashes for Chrome compatibility and absolute path
        profile_path_str = str(profile_path.absolute()).replace("\\", "/")
        chrome_options.add_argument(f"--user-data-dir={profile_path_str}")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # SSL and certificate handling
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--allow-insecure-localhost")
        
        # Security/Automation bypasses
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Additional options for WhatsApp persistence
        if profile_name == "whatsapp":
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            chrome_options.add_argument("--disable-site-isolation-trials")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Set download directory for portal
        if profile_name == "portal":
            prefs = {
                "download.default_directory": str(EXPORTS_DIR.absolute()),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            if WEBDRIVER_MANAGER_AVAILABLE:
                service = Service(ChromeDriverManager().install())
            else:
                # Fallback to system chromedriver
                service = Service()
                
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Remove automation flag from navigator
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
            return driver
        except Exception as e:
            logger.error(f"Failed to create driver for {profile_name}: {e}")
            raise

    def _cleanup_profile_locks(self, profile_dir: Path):
        """Clean up Chrome lock files"""
        lock_files = ["SingletonLock", "SingletonSocket", "Parent.lock", "lock"]
        for lock_file in lock_files:
            lock_path = profile_dir / lock_file
            if lock_path.exists():
                try:
                    if lock_file == "SingletonLock" and os.name == 'nt':
                        # On Windows, we can't easily unlink SingletonLock if it's held
                        continue
                    lock_path.unlink()
                except:
                    pass

    def start_browsers(self):
        """Start both browsers if not already open"""
        with self.lock:
            if not self.portal_driver:
                try:
                    logger.info("Starting Portal browser...")
                    self.portal_driver = self._create_driver("portal")
                    self.driver = self.portal_driver
                except Exception as e:
                    logger.error(f"Failed to start Portal browser: {e}")
            
            if not self.whatsapp_driver:
                try:
                    logger.info("Starting WhatsApp browser...")
                    self.whatsapp_driver = self._create_driver("whatsapp")
                    self.whatsapp_driver.get(self.WHATSAPP_URL)
                except Exception as e:
                    logger.error(f"Failed to start WhatsApp browser: {e}")
            
            self.status.is_open = True
            self._notify_status()

    def reset_whatsapp_session(self) -> bool:
        """Completely reset WhatsApp session by deleting profile"""
        try:
            logger.warning("RESETTING WHATSAPP SESSION...")
            
            # Close driver first (outside lock to avoid deadlock)
            driver_to_close = None
            with self.lock:
                driver_to_close = self.whatsapp_driver
                self.whatsapp_driver = None
                self.status.whatsapp_ready = False
            
            if driver_to_close:
                try:
                    driver_to_close.quit()
                    logger.info("WhatsApp browser closed")
                except Exception as e:
                    logger.warning(f"Error closing WhatsApp browser: {e}")
            
            # Wait for browser processes to fully exit
            time.sleep(3)
            
            # Now delete the profile
            profile_dir = PROFILES_DIR / "whatsapp"
            if profile_dir.exists():
                for i in range(10):
                    try:
                        shutil.rmtree(str(profile_dir))
                        logger.success(f"Deleted WhatsApp profile: {profile_dir}")
                        break
                    except PermissionError as e:
                        logger.warning(f"Delete attempt {i+1} failed (permission): {e}")
                        time.sleep(2)
                    except Exception as e:
                        logger.warning(f"Delete attempt {i+1} failed: {e}")
                        time.sleep(1)
            
            self._notify_status()
            
            # Wait a bit before recreating
            time.sleep(2)
            
            # Restart with fresh profile
            logger.info("Restarting WhatsApp with fresh profile...")
            with self.lock:
                self.whatsapp_driver = self._create_driver("whatsapp")
                self.whatsapp_driver.get(self.WHATSAPP_URL)
            
            logger.success("WhatsApp browser restarted - please scan QR code")
            return True
            
        except Exception as e:
            logger.error(f"Reset WhatsApp failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def close(self):
        """Close all browsers"""
        with self.lock:
            if self.portal_driver:
                try: self.portal_driver.quit()
                except: pass
                self.portal_driver = None
            if self.whatsapp_driver:
                try: self.whatsapp_driver.quit()
                except: pass
                self.whatsapp_driver = None
            self.driver = None
            self.status = BrowserStatus()
            self._notify_status()
            logger.info("Browsers closed")

    def is_whatsapp_ready(self) -> bool:
        """Check if WhatsApp is connected and ready to send messages"""
        if not self.whatsapp_driver:
            return False
        
        try:
            # Check for logged in indicators (chat list, search bar, etc.)
            logged_in_selectors = [
                '#pane-side',
                '[data-testid="chat-list"]',
                'div[aria-label="Chat list"]',
                '[data-testid="menu-bar-menu"]',
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = self.whatsapp_driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        self.status.whatsapp_ready = True
                        return True
                except:
                    continue
            
            # Check if QR code is shown (not ready)
            qr_selectors = [
                '[data-testid="qrcode"]',
                'canvas[aria-label*="Scan"]',
                'canvas[aria-label*="QR"]',
            ]
            
            for selector in qr_selectors:
                try:
                    qr = self.whatsapp_driver.find_element(By.CSS_SELECTOR, selector)
                    if qr and qr.is_displayed():
                        self.status.whatsapp_ready = False
                        return False
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking WhatsApp ready: {e}")
            return False

    def wait_for_whatsapp_scan(self, timeout: int = 120) -> bool:
        """Wait for user to scan WhatsApp QR code"""
        logger.info(f"Waiting up to {timeout}s for WhatsApp QR scan...")
        start = time.time()
        
        while time.time() - start < timeout:
            if self.is_whatsapp_ready():
                logger.success("WhatsApp is now connected!")
                self.status.whatsapp_ready = True
                self._notify_status()
                return True
            time.sleep(2)
        
        logger.warning("WhatsApp QR scan timeout")
        return False

    def start(self) -> bool:
        """Start both browsers and return success status"""
        try:
            self.start_browsers()
            return self.portal_driver is not None
        except Exception as e:
            logger.error(f"Failed to start browsers: {e}")
            return False

    def get_driver(self) -> Optional[webdriver.Chrome]:
        return self.portal_driver

    def get_status(self) -> BrowserStatus:
        return self.status

    def switch_to_tab(self, tab_type: TabType) -> bool:
        """Switch to a tab in portal driver or focus whatsapp window"""
        if tab_type == TabType.WHATSAPP:
            if self.whatsapp_driver:
                try:
                    self.whatsapp_driver.execute_script("window.focus();")
                    return True
                except: return False
            return False
        
        if not self.portal_driver: return False
        
        handle = self.status.tab_handles.get(tab_type)
        if handle:
            try:
                self.portal_driver.switch_to.window(handle)
                self.status.active_tab = tab_type
                return True
            except: pass
            
        return False

# Global instance
browser_manager = BrowserManager()
