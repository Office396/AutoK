"""
Browser Manager
Manages both Portal and WhatsApp Web in separate browser instances
Optimized for Huawei MAE Portal login with session recovery
Includes automatic session recovery for browser crashes
"""

import os
import time
import threading
from typing import Optional, Callable, List, Dict
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    ElementNotInteractableException,
    StaleElementReferenceException
)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

from config import settings, CHROME_PROFILE_DIR, EXPORTS_DIR
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
    Manages a single browser instance with multiple tabs
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
        self.portal_driver: Optional[webdriver.Chrome] = None  # For portal monitoring
        self.whatsapp_driver: Optional[webdriver.Chrome] = None  # Dedicated WhatsApp browser
        self.driver: Optional[webdriver.Chrome] = None  # Backwards compatibility - points to portal_driver
        self.status = BrowserStatus()
        self.lock = threading.Lock()
        self._status_callbacks: List[Callable] = []
    
    def add_status_callback(self, callback: Callable):
        """Add a callback for status updates"""
        self._status_callbacks.append(callback)
    
    def _notify_status(self):
        """Notify all callbacks of status change"""
        for callback in self._status_callbacks:
            try:
                callback(self.status)
            except:
                pass
    
    def _create_driver(self, profile_name: str = "portal") -> webdriver.Chrome:
        """Create Chrome WebDriver with specified profile"""
        options = Options()
        
        # Use different profile directories for portal and WhatsApp
        if profile_name == "whatsapp":
            profile_dir = CHROME_PROFILE_DIR.parent / "chrome_whatsapp"
        else:
            # Use a dedicated directory for portal too, to avoid conflicts/corruption
            profile_dir = CHROME_PROFILE_DIR.parent / "chrome_portal"
        
        profile_dir.mkdir(parents=True, exist_ok=True)
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        
        options.add_argument(f"--user-data-dir={profile_dir}")
        # Basic stable options
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--allow-insecure-localhost')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-gpu')
        # options.add_argument('--no-sandbox')  # Potentially unstable on Windows
        options.add_argument('--disable-dev-shm-usage')  # Reduce memory pressure
        options.add_argument('--remote-allow-origins=*')  # Fix for Chrome 111+ connection issues
        
        # EXPERIMENTAL: Optimization flags - APPLY ONLY TO WHATSAPP
        # These flags prevent background freezing but can cause Portal to crash
        if profile_name == "whatsapp":
            options.add_argument('--disable-features=CalculateNativeWinOcclusion')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-ipc-flooding-protection')
        
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        prefs = {
            "download.default_directory": str(EXPORTS_DIR),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                options.binary_location = path
                logger.info(f"Found Chrome at: {path}")
                break
        
        errors = []
        
        if WEBDRIVER_MANAGER_AVAILABLE:
            try:
                logger.info("Trying WebDriver Manager...")
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                logger.success("Browser started with WebDriver Manager")
                return driver
            except Exception as e:
                errors.append(f"WebDriver Manager: {e}")
                logger.warning(f"WebDriver Manager failed: {e}")
        
        try:
            logger.info("Trying default Chrome...")
            driver = webdriver.Chrome(options=options)
            logger.success("Browser started with default Chrome")
            return driver
        except Exception as e:
            errors.append(f"Default Chrome: {e}")
            logger.warning(f"Default Chrome failed: {e}")
        
        try:
            current_dir = Path(__file__).parent
            chromedriver_path = current_dir / "chromedriver.exe"
            
            if chromedriver_path.exists():
                logger.info(f"Trying local ChromeDriver: {chromedriver_path}")
                service = Service(str(chromedriver_path))
                driver = webdriver.Chrome(service=service, options=options)
                logger.success("Browser started with local ChromeDriver")
                return driver
        except Exception as e:
            errors.append(f"Local ChromeDriver: {e}")
            logger.warning(f"Local ChromeDriver failed: {e}")
        
        error_msg = "\n".join(errors)
        raise Exception(f"Could not start Chrome browser.\n\nErrors:\n{error_msg}")
    
    def start(self) -> bool:
        """Start both portal and WhatsApp browsers"""
        try:
            with self.lock:
                logger.info("Starting browsers...")
                
                # Step 1: Create Portal Browser
                logger.info("Creating portal browser...")
                self.portal_driver = self._create_driver(profile_name="portal")
                self.driver = self.portal_driver  # Backwards compatibility
                self.status.is_open = True
                
                # Small delay to reduce resource spike
                time.sleep(2)
                
                # Step 2: Create WhatsApp Browser (separate profile - saves login!)
                logger.info("Creating WhatsApp browser...")
                self.whatsapp_driver = self._create_driver(profile_name="whatsapp")
                
                # Step 3: Open WhatsApp Web in its dedicated browser
                logger.info("Opening WhatsApp Web...")
                self.whatsapp_driver.get(self.WHATSAPP_URL)
                time.sleep(4)
                
                # Check WhatsApp status
                self._check_whatsapp_status()
                
                # Step 4: Open Main Topology in portal browser and login
                logger.info("Opening Main Topology for login...")
                self.portal_driver.get(self.PORTAL_URLS[TabType.MAIN_TOPOLOGY])
                self.status.tab_handles[TabType.MAIN_TOPOLOGY] = self.portal_driver.current_window_handle
                
                logger.info("Waiting for login page to load...")
                time.sleep(5)
                
                # Step 5: Login to portal
                login_success = self._login_to_huawei_portal()

                if login_success:
                    logger.info("Waiting for portal to load after login...")
                    time.sleep(3)  # Reduced delay

                    # Don't open all tabs at once - open them on demand
                    logger.info("Portal ready - tabs will be opened on demand")
                else:
                    logger.warning("Portal login may have failed, opening other tabs anyway...")
                    time.sleep(1)
                    self._open_other_portal_tabs()
                
                self._notify_status()
                logger.success("Both browsers started successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to start browsers: {e}")
            self.status.is_open = False
            raise e
    
    def _check_whatsapp_status(self):
        """Check if WhatsApp is logged in"""
        try:
            # Use whatsapp_driver instead of switching tabs
            driver = self.whatsapp_driver if self.whatsapp_driver else self.driver
            
            time.sleep(2)
            
            # Check for logged in indicators
            logged_in_selectors = [
                '#pane-side',
                '[data-testid="chat-list"]',
                '[data-testid="chatlist"]',
                '[data-testid="default-user"]',
                '[data-testid="menu-bar-menu"]',
                'div[aria-label="Chat list"]',
                'div[aria-label="Chats"]',
                '[data-testid="cell-frame-container"]',
                'header[data-testid="chatlist-header"]',
                '#main',
                'div[id="main"]',
                'div[id="pane-side"]',
                '[data-testid="conversation-panel-wrapper"]',
                'span[data-testid="menu"]',
                'div[data-testid="chat-list-search"]',
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        logger.info(f"WhatsApp logged in - found: {selector}")
                        self.status.whatsapp_ready = True
                        return
                except:
                    continue
            
            # Check page source for indicators
            try:
                page_source = driver.page_source.lower()
                
                if 'pane-side' in page_source or 'chat-list' in page_source:
                    logger.info("WhatsApp logged in - found in page source")
                    self.status.whatsapp_ready = True
                    return
                
                if 'scan' in page_source and 'qr' in page_source:
                    logger.warning("WhatsApp requires QR code scan")
                    self.status.whatsapp_ready = False
                    return
            except:
                pass
            
            # Check for QR code
            qr_selectors = [
                '[data-testid="qrcode"]',
                'canvas[aria-label*="Scan"]',
                'canvas[aria-label*="QR"]',
            ]
            
            for selector in qr_selectors:
                try:
                    qr = driver.find_element(By.CSS_SELECTOR, selector)
                    if qr and qr.is_displayed():
                        logger.warning("WhatsApp requires QR code scan")
                        self.status.whatsapp_ready = False
                        return
                except:
                    continue
            
            # Check URL
            try:
                current_url = driver.current_url
                if 'web.whatsapp.com' in current_url:
                    # No QR found, assume logged in
                    logger.info("WhatsApp appears to be logged in")
                    self.status.whatsapp_ready = True
                    return
            except:
                pass
            
            self.status.whatsapp_ready = False
                    
        except Exception as e:
            logger.error(f"Error checking WhatsApp status: {e}")
            self.status.whatsapp_ready = False
    
    def _login_to_huawei_portal(self) -> bool:
        """Login to Huawei MAE Portal"""
        try:
            username = settings.credentials.username
            password = settings.credentials.password
            
            if not username or not password:
                logger.warning("NO PORTAL CREDENTIALS CONFIGURED!")
                logger.warning("Please go to Settings tab and enter username/password")
                return False
            
            logger.info(f"Logging in to Huawei MAE Portal...")
            logger.info(f"Username: {username}")
            
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '#username'))
                )
                logger.info("Login page loaded successfully")
            except TimeoutException:
                if 'Access_MainTopoTitle' in self.driver.current_url:
                    logger.info("Already logged in")
                    self.status.portal_logged_in = True
                    return True
                else:
                    logger.error("Login page did not load")
                    return False
            
            # Enter username
            try:
                logger.info("Entering username...")
                username_field = self.driver.find_element(By.CSS_SELECTOR, '#username')
                username_field.click()
                time.sleep(0.3)
                username_field.clear()
                time.sleep(0.2)
                for char in username:
                    username_field.send_keys(char)
                    time.sleep(0.05)
                time.sleep(0.3)
                logger.info("Username entered successfully")
            except Exception as e:
                logger.error(f"Failed to enter username: {e}")
                return False
            
            # Enter password
            try:
                logger.info("Entering password...")
                password_field = self.driver.find_element(By.CSS_SELECTOR, '#value')
                password_field.click()
                time.sleep(0.3)
                password_field.clear()
                time.sleep(0.2)
                for char in password:
                    password_field.send_keys(char)
                    time.sleep(0.05)
                time.sleep(0.3)
                logger.info("Password entered successfully")
            except Exception as e:
                logger.error(f"Failed to enter password: {e}")
                return False
            
            # Click login button
            try:
                logger.info("Clicking login button...")
                try:
                    login_btn = self.driver.find_element(By.CSS_SELECTOR, '#submitDataverify')
                    login_btn.click()
                except:
                    try:
                        login_btn = self.driver.find_element(By.CSS_SELECTOR, '#btn_outerverify')
                        login_btn.click()
                    except:
                        try:
                            login_btn = self.driver.find_element(By.CSS_SELECTOR, '.loginBtn')
                            login_btn.click()
                        except:
                            password_field = self.driver.find_element(By.CSS_SELECTOR, '#value')
                            password_field.send_keys(Keys.RETURN)
                
                logger.info("Login button clicked")
            except Exception as e:
                logger.error(f"Failed to click login: {e}")
            
            logger.info("Waiting for login to complete...")
            time.sleep(5)
            
            # Check for errors
            try:
                error_elem = self.driver.find_element(By.CSS_SELECTOR, '#errorMessage')
                error_text = error_elem.text.strip()
                if error_text:
                    logger.error(f"Login error: {error_text}")
                    return False
            except:
                pass
            
            # Check success
            current_url = self.driver.current_url
            if 'access_maintopoTitle' in current_url.lower() or '#username' not in self.driver.page_source:
                self.status.portal_logged_in = True
                logger.success("PORTAL LOGIN SUCCESSFUL!")
                return True
            else:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, '#username')
                    logger.error("Still on login page - login failed")
                    return False
                except:
                    self.status.portal_logged_in = True
                    logger.success("Login appears successful")
                    return True
                
        except Exception as e:
            logger.error(f"Portal login error: {e}")
            return False
    

        logger.info("Finished opening portal tabs")
    
    def switch_to_tab(self, tab_type: TabType) -> bool:
        """Switch to a specific tab, opening it if necessary"""
        try:
            handle = self.status.tab_handles.get(tab_type)
            if handle:
                self.driver.switch_to.window(handle)
                self.status.active_tab = tab_type
                return True

            # Tab not found - try to open it on demand
            logger.info(f"Tab {tab_type.value} not found, opening on demand...")
            return self._open_tab_on_demand(tab_type)

        except Exception as e:
            logger.error(f"Error switching to tab {tab_type.value}: {e}")
            return False

    def _open_tab_on_demand(self, tab_type: TabType) -> bool:
        """Open a tab when first accessed"""
        try:
            url = self.PORTAL_URLS.get(tab_type)
            if not url:
                logger.error(f"No URL found for tab type {tab_type.value}")
                return False

            # Open new tab
            self.driver.execute_script("window.open()")
            time.sleep(0.5)

            # Switch to new tab
            self.driver.switch_to.window(self.driver.window_handles[-1])

            # Navigate to URL
            self.driver.get(url)
            self.status.tab_handles[tab_type] = self.driver.current_window_handle

            time.sleep(1)
            logger.success(f"Successfully opened {tab_type.value} on demand")
            return True

        except Exception as e:
            logger.error(f"Error opening tab {tab_type.value} on demand: {e}")
            return False
    
    def refresh_tab(self, tab_type: TabType) -> bool:
        """Refresh a specific tab"""
        try:
            if self.switch_to_tab(tab_type):
                self.driver.refresh()
                time.sleep(2)
                return True
            return False
        except Exception as e:
            logger.error(f"Error refreshing tab: {e}")
            return False
    
    def get_current_tab(self) -> Optional[TabType]:
        """Get the current active tab type"""
        try:
            current_handle = self.driver.current_window_handle
            for tab_type, handle in self.status.tab_handles.items():
                if handle == current_handle:
                    return tab_type
            return None
        except:
            return None
    
    def is_whatsapp_ready(self) -> bool:
        """Check if WhatsApp is ready for sending"""
        if not self.status.whatsapp_ready:
            self._check_whatsapp_status()
        return self.status.whatsapp_ready
    
    def wait_for_whatsapp_scan(self, timeout: int = 300) -> bool:
        """Wait for WhatsApp to be ready"""
        logger.info("=" * 50)
        logger.info("CHECKING WHATSAPP STATUS")
        logger.info("=" * 50)
        
        self.switch_to_tab(TabType.WHATSAPP)
        time.sleep(3)
        
        # First check
        self._check_whatsapp_status()
        
        if self.status.whatsapp_ready:
            logger.success("WhatsApp is already ready!")
            return True
        
        logger.info("Waiting for WhatsApp...")
        logger.info("If you can see your chats, please wait...")
        
        start_time = time.time()
        check_interval = 5
        
        while time.time() - start_time < timeout:
            self.switch_to_tab(TabType.WHATSAPP)
            time.sleep(1)
            self._check_whatsapp_status()
            
            if self.status.whatsapp_ready:
                logger.success("WHATSAPP IS NOW READY!")
                return True
            
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed
            
            if elapsed % 30 == 0 and elapsed > 0:
                logger.info(f"Still checking... {remaining} seconds remaining")
            
            # After 30 seconds, if we're on WhatsApp URL, assume ready
            if elapsed >= 30:
                try:
                    if 'web.whatsapp.com' in self.driver.current_url:
                        # Check if there's NO QR code visible
                        try:
                            qr = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="qrcode"]')
                            if not qr.is_displayed():
                                logger.info("No QR code visible - assuming WhatsApp is ready")
                                self.status.whatsapp_ready = True
                                return True
                        except:
                            # No QR found, assume ready
                            logger.info("No QR code found - WhatsApp is ready")
                            self.status.whatsapp_ready = True
                            return True
                except:
                    pass
            
            time.sleep(check_interval)
        
        logger.warning("WhatsApp check timeout - assuming ready")
        self.status.whatsapp_ready = True
        return True
    
    def close(self):
        """Close both browsers"""
        try:
            if self.portal_driver:
                self.portal_driver.quit()
                self.portal_driver = None
            if self.whatsapp_driver:
                self.whatsapp_driver.quit()
                self.whatsapp_driver = None
            self.driver = None
            self.status = BrowserStatus()
            logger.info("Both browsers closed")
        except Exception as e:
            logger.error(f"Error closing browsers: {e}")
    
    def is_session_alive(self) -> bool:
        """Check if browser session is still alive"""
        try:
            if not self.driver:
                return False

            # Try to get current URL - this will fail if session is dead
            self.driver.current_url
            return True
        except Exception:
            return False

    def recover_session(self) -> bool:
        """Try to recover from a dead browser session"""
        try:
            logger.warning("Browser session lost, attempting recovery...")

            # Close dead driver
            try:
                if self.driver:
                    self.driver.quit()
            except:
                pass

            # Recreate portal driver
            self.portal_driver = self._create_driver(profile_name="portal")
            self.driver = self.portal_driver
            self.status.is_open = True

            # Reopen Main Topology
            self.portal_driver.get(self.PORTAL_URLS[TabType.MAIN_TOPOLOGY])
            self.status.tab_handles[TabType.MAIN_TOPOLOGY] = self.portal_driver.current_window_handle

            logger.success("Browser session recovered")
            return True

        except Exception as e:
            logger.error(f"Session recovery failed: {e}")
            return False

    def ensure_session_alive(self) -> bool:
        """Ensure browser session is alive, recover if needed"""
        if not self.is_session_alive():
            return self.recover_session()
        return True

    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Get the WebDriver instance"""
        return self.driver

    def get_status(self) -> BrowserStatus:
        """Get current browser status"""
        return self.status


# Global instance
browser_manager = BrowserManager()