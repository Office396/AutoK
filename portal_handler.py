"""
Portal Handler
Handles all portal automation using Selenium
- Login to MAE Access portal
- Navigate to different alarm views
- Export alarm data
- Monitor for new alarms
"""

import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import urllib3

# Disable SSL warnings for internal network
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

from config import settings, PortalConfig, PROFILES_DIR, EXPORTS_DIR
from logger_module import logger
from browser_manager import browser_manager


class PortalType(Enum):
    """Types of portal views"""
    MAIN_TOPOLOGY = "Main Topology"
    CSL_FAULT = "C1 OML Fault"
    RF_UNIT = "RF-Unit AR"
    NODEB_CELL = "C1 NodeB UMTS Cell Unavailable"
    ALL_ALARMS = "c1-c2 All Alarm"


@dataclass
class PortalStatus:
    """Status of portal connection"""
    is_connected: bool = False
    is_logged_in: bool = False
    current_portal: Optional[PortalType] = None
    last_refresh: Optional[datetime] = None
    error_message: Optional[str] = None


class PortalHandler:
    """
    Handles all portal automation
    """
    
    # Element selectors (may need adjustment based on actual portal)
    SELECTORS = {
        # Login page - Huawei MAE Portal specific selectors
        'username_input': [
            (By.ID, 'username'),
            (By.CSS_SELECTOR, '#username'),
            (By.NAME, 'username'),
            (By.CSS_SELECTOR, 'input[type="text"]'),
            (By.CSS_SELECTOR, 'input[placeholder*="user"]'),
            (By.XPATH, '//input[@type="text"]'),
        ],
        'password_input': [
            (By.ID, 'value'),  # Huawei portal uses #value for password
            (By.CSS_SELECTOR, '#value'),
            (By.ID, 'password'),
            (By.NAME, 'password'),
            (By.CSS_SELECTOR, 'input[type="password"]'),
            (By.XPATH, '//input[@type="password"]'),
        ],
        'login_button': [
            (By.ID, 'submitDataverify'),  # Huawei portal login button
            (By.ID, 'btn_outerverify'),
            (By.CSS_SELECTOR, '.loginBtn'),
            (By.ID, 'loginBtn'),
            (By.CSS_SELECTOR, 'button[type="submit"]'),
            (By.XPATH, '//button[contains(text(), "Login")]'),
            (By.XPATH, '//button[contains(text(), "Sign")]'),
            (By.CSS_SELECTOR, '.login-btn'),
            (By.CSS_SELECTOR, 'button.primary'),
        ],
        
        # Main page after login
        'welcome_text': [
            (By.XPATH, '//*[contains(text(), "Welcome")]'),
            (By.XPATH, '//*[contains(text(), "MAE")]'),
        ],
        
        # Alarm table
        'alarm_table': [
            (By.CSS_SELECTOR, 'table.alarm-table'),
            (By.CSS_SELECTOR, '.grid-table'),
            (By.CSS_SELECTOR, 'table'),
            (By.XPATH, '//table[contains(@class, "alarm")]'),
        ],
        'alarm_rows': [
            (By.CSS_SELECTOR, 'table tbody tr'),
            (By.CSS_SELECTOR, '.grid-row'),
            (By.XPATH, '//table/tbody/tr'),
        ],
        
        # Export button - based on the HTML structure provided
        # Export button - Optimized
        'export_button': [
            # Exact match for user's portal
            (By.XPATH, '//div[@id="exportBtn"]//button'), 
            (By.XPATH, '//button[contains(., "Export")]'),
            (By.CSS_SELECTOR, '#exportBtn button'),
        ],

        # Export dropdown options - appears in popup menu after clicking export button
        'export_all_option': [
            # Try by ID first
            (By.ID, 'allExport'),
            (By.CSS_SELECTOR, '#allExport'),
            # Try in popup menu
            (By.XPATH, '//div[contains(@class, "eui_popupMenu_popup")]//*[contains(text(), "All")]'),
            (By.XPATH, '//div[contains(@class, "eui-aligned-popup")]//*[contains(text(), "All")]'),
            (By.XPATH, '//li[@id="allExport"]'),
            (By.XPATH, '//*[contains(@id, "allExport")]'),
            # Generic fallback - any clickable element with "All" text in popup
            (By.XPATH, '//div[contains(@class, "popup")]//*[contains(text(), "All") and not(ancestor::*[contains(@class, "hidden")])]'),
        ],
        'export_selected_option': [
            (By.ID, 'selectedExport'),
            (By.CSS_SELECTOR, '#selectedExport'),
            (By.XPATH, '//li[@id="selectedExport"]'),
        ],

        # Export popup dialog
        'export_popup': [
            (By.CSS_SELECTOR, '.eui_Dialog.fm_root_dialog.fm_root_dialog_v2'),
            (By.CSS_SELECTOR, '.eui_Dialog'),
            (By.ID, 'dialog_panel'),
        ],
        'export_xlsx_option': [
            # Try by label text first (most reliable)
            (By.XPATH, '//label[contains(text(), "XLSX")]'),
            (By.XPATH, '//div[contains(@class, "eui_radio")]//label[contains(text(), "XLSX")]'),
            # Try by radio button that's checked (XLSX is usually default)
            (By.XPATH, '//div[contains(@class, "eui_radio")]//span[contains(@class, "checked")]/ancestor::div[contains(@class, "eui_radio")]//label[contains(text(), "XLSX")]'),
            # Try by ID pattern (may vary)
            (By.XPATH, '//*[contains(@id, "eui_radio_group") and contains(@id, "_radio_0")]'),
            (By.CSS_SELECTOR, '[id*="eui_radio_group"][id*="_radio_0"]'),
        ],
        'export_csv_option': [
            (By.ID, 'eui_radio_group_10091_radio_1'),
            (By.CSS_SELECTOR, '#eui_radio_group_10091_radio_1'),
            (By.XPATH, '//*[@id="eui_radio_group_10091_radio_1"]'),
        ],
        'export_html_option': [
            (By.ID, 'eui_radio_group_10091_radio_2'),
            (By.CSS_SELECTOR, '#eui_radio_group_10091_radio_2'),
            (By.XPATH, '//*[@id="eui_radio_group_10091_radio_2"]'),
        ],
        'export_ok_button': [
            (By.ID, 'confirmBtn'),
            (By.CSS_SELECTOR, '#confirmBtn'),
            (By.XPATH, '//button[@id="confirmBtn"]'),
            (By.XPATH, '//button[contains(text(), "OK")]'),
        ],
    }
    
    def __init__(self):
        self.status = PortalStatus()
        self.portal_urls = settings.portal
        self.lock = threading.Lock()
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.alarm_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        self.portal_handles: Dict[PortalType, str] = {} # Store window handles for instant switching

        # Download directory for exports
        self.download_dir = str(EXPORTS_DIR)
    
    # Removed driver creation methods - now using browser_manager's driver
    
    def _get_driver(self):
        """Get the driver from browser_manager"""
        return browser_manager.get_driver()

    def _find_element(self, selector_key: str, timeout: int = 10) -> Optional[any]:
        """Find element using multiple selector strategies"""
        driver = self._get_driver()
        if not driver:
            return None

        selectors = self.SELECTORS.get(selector_key, [])

        for by, value in selectors:
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                return element
            except TimeoutException:
                continue
            except Exception:
                continue

        return None
    
    def _find_elements(self, selector_key: str, timeout: int = 10) -> List:
        """Find multiple elements using multiple selector strategies"""
        driver = self._get_driver()
        if not driver:
            return []

        selectors = self.SELECTORS.get(selector_key, [])

        for by, value in selectors:
            try:
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                elements = driver.find_elements(by, value)
                if elements:
                    return elements
            except TimeoutException:
                continue
            except Exception:
                continue

        return []
    
    def _wait_for_element(self, selector_key: str, timeout: int = 10) -> bool:
        """Wait for an element to be visible"""
        driver = self._get_driver()
        if not driver:
            return False

        selectors = self.SELECTORS.get(selector_key, [])
        
        # If multiple selectors are provided, divide the timeout among them
        # to avoid extremely long waits when element is not present
        per_selector_timeout = max(2, timeout // len(selectors)) if selectors else timeout

        for by, value in selectors:
            try:
                WebDriverWait(driver, per_selector_timeout).until(
                    EC.visibility_of_element_located((by, value))
                )
                return True
            except TimeoutException:
                continue
            except Exception:
                continue

        return False

    def _click_element(self, selector_key: str, timeout: int = 10) -> bool:
        """Click an element with multiple fallback methods"""
        driver = self._get_driver()
        if not driver:
            return False

        element = self._find_element(selector_key, timeout)
        if element:
            try:
                # Method 1: Standard click
                element.click()
                return True
            except Exception as e:
                logger.debug(f"Standard click failed for {selector_key}: {e}")
                try:
                    # Method 2: JavaScript click
                    driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception as e2:
                    logger.debug(f"JavaScript click failed for {selector_key}: {e2}")
                    try:
                        # Method 3: Action chains click
                        from selenium.webdriver.common.action_chains import ActionChains
                        actions = ActionChains(driver)
                        actions.move_to_element(element).click().perform()
                        return True
                    except Exception as e3:
                        logger.debug(f"Action chains click failed for {selector_key}: {e3}")
                        try:
                            # Method 4: Scroll into view and click
                            driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            time.sleep(0.5)
                            element.click()
                            return True
                        except Exception as e4:
                            logger.error(f"All click methods failed for {selector_key}: {e4}")
        return False
    
    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Login to the portal and initialize multi-tab session
        
        Args:
            username: Portal username (uses saved if not provided)
            password: Portal password (uses saved if not provided)
        
        Returns:
            True if login successful AND tabs opened
        """
        try:
            username = username or settings.credentials.username
            password = password or settings.credentials.password
            
            if not username or not password:
                logger.error("No credentials provided")
                self.status.error_message = "No credentials provided"
                return False
            
            driver = self._get_driver()
            if not driver:
                logger.error("No driver available")
                return False
            
            # Check if already on login page (redirected)
            current_url = driver.current_url
            if not self._is_login_page():
                # Not on login page - navigate to base URL
                logger.info("Navigating to portal...")
                driver.get(self.portal_urls.base_url)
                time.sleep(2)
            else:
                logger.info("Already on login page - proceeding with login")
            
            # Check if already logged in
            if self._check_logged_in():
                logger.info("Already logged in (Session active)")
            else:
                # Perform Login Logic
                logger.info("Entering credentials...")
                
                # Find and fill username
                username_input = self._find_element('username_input', timeout=15)
                if not username_input:
                    logger.error("Could not find username input")
                    self.status.error_message = "Could not find username field"
                    return False
                
                username_input.clear()
                username_input.send_keys(username)
                
                # Find and fill password
                password_input = self._find_element('password_input', timeout=5)
                if not password_input:
                    logger.error("Could not find password input")
                    self.status.error_message = "Could not find password field"
                    return False
                
                password_input.clear()
                password_input.send_keys(password)
                
                # Click login button
                time.sleep(1)
                login_success = False
                try:
                    login_btn = self._find_element('login_button', timeout=1)
                    if login_btn:
                        login_btn.click()
                        login_success = True
                        logger.info("Login button clicked")
                except Exception as e:
                    logger.debug(f"Could not click login button: {e}")
                
                if not login_success:
                    # Try pressing Enter
                    try:
                        password_input.send_keys(Keys.RETURN)
                        logger.info("Pressed Enter on password field")
                    except Exception as e:
                        logger.warning(f"Could not press Enter: {e}")
                
                # Check for error messages (Fast check)
                try:
                    error_elem = driver.find_element(By.CSS_SELECTOR, '#errorMessage')
                    if error_elem.is_displayed() and error_elem.text.strip():
                        logger.error(f"Login error: {error_elem.text.strip()}")
                        self.status.error_message = error_elem.text.strip()
                        return False
                except:
                    pass

                # Check URL - if still on login page
                current_url = driver.current_url
                if 'unisso/login.action' in current_url:
                    # Don't fail immediately, give it a second chance via check_logged_in
                    pass
                
                # Verify Login with Polling (Max 10 seconds)
                # We need to wait for the redirect to happen
                check_start = time.time()
                is_verified = False
                
                while time.time() - check_start < 10:
                    try:
                        # Check URL (Fastest)
                        current_url = driver.current_url
                        if 'login' not in current_url.lower() and ('Access' in current_url or 'fmAlarmView' in current_url):
                            logger.success("Login verified via URL check")
                            is_verified = True
                            break
                        
                        # Check State
                        if self._check_logged_in():
                            logger.success("Login verified via element check")
                            is_verified = True
                            break
                            
                        # Check for error again just in case
                        try:
                             error_elem = driver.find_element(By.CSS_SELECTOR, '#errorMessage')
                             if error_elem.is_displayed() and error_elem.text.strip():
                                 logger.error(f"Login error appearing during wait: {error_elem.text.strip()}")
                                 self.status.error_message = error_elem.text.strip()
                                 return False
                        except:
                            pass
                            
                        time.sleep(0.5)
                    except:
                        time.sleep(0.5)
                        
                if not is_verified:
                    logger.error("Login verification timed out - still on login page or loading")
                    return False

            # SUCCESS: Now open all portal tabs immediately
            # This is the "Accurate Method": Login First -> Then Open Tabs
            logger.info("Login successful/verified. Initializing portal tabs...")
            
            # Save credentials on success
            settings.credentials.username = username
            settings.credentials.password = password
            settings.save()
            
            if not self.open_all_portals_in_tabs():
                logger.error("Failed to open all portal tabs")
                return False

            self.status.is_logged_in = True
            self.status_callback(self.status) if self.status_callback else None
            return True

        except Exception as e:
            logger.error(f"Login error: {e}")
            self.status.error_message = str(e)
            return False
    
    def _is_login_page(self) -> bool:
        """Check if currently on login page"""
        try:
            driver = self._get_driver()
            if not driver:
                return False

            # Check URL for login page
            current_url = driver.current_url
            if 'unisso/login.action' in current_url or '/login' in current_url.lower():
                return True

            # Check for login form elements
            username_input = self._find_element('username_input', timeout=2)
            password_input = self._find_element('password_input', timeout=2)
            if username_input and password_input:
                return True

            return False

        except Exception:
            return False

    def _check_logged_in(self) -> bool:
        """Check if currently logged in"""
        try:
            driver = self._get_driver()
            if not driver:
                return False

            # First check if we're on login page
            if self._is_login_page():
                self.status.is_logged_in = False
                return False

            # 1. OPTIMIZATION: Check URL FIRST (Fastest)
            current_url = driver.current_url
            if 'Access_MainTopoTitle' in current_url or 'fmAlarmView' in current_url:
                self.status.is_logged_in = True
                return True
            
            # 2. Check for welcome text or main page elements (Slower)
            if self._find_element('welcome_text', timeout=2):
                self.status.is_logged_in = True
                return True

            # If we have a username/password field visible, we're not logged in
            username_input = self._find_element('username_input', timeout=2)
            if username_input:
                self.status.is_logged_in = False
                return False

            # If no login elements found, assume still logged in but maybe on a subpage
            # self.status.is_logged_in = True # Don't explicitly set True here to avoid false positives
            return self.status.is_logged_in

        except Exception:
            return False
    
    def navigate_to_portal(self, portal_type: PortalType) -> bool:
        """
        Navigate to a specific portal/alarm view

        Args:
            portal_type: The portal type to navigate to

        Returns:
            True if navigation successful
        """
        try:
            driver = self._get_driver()
            if not driver:
                logger.error("No driver available for navigation")
                return False

            url_map = {
                PortalType.MAIN_TOPOLOGY: self.portal_urls.main_topology,
                PortalType.CSL_FAULT: self.portal_urls.csl_fault,
                PortalType.RF_UNIT: self.portal_urls.rf_unit,
                PortalType.NODEB_CELL: self.portal_urls.nodeb_cell,
                PortalType.ALL_ALARMS: self.portal_urls.all_alarms,
            }

            url = url_map.get(portal_type)
            if not url:
                logger.error(f"Unknown portal type: {portal_type}")
                return False

            logger.info(f"Navigating to {portal_type.value}...")
            driver.get(url)
            time.sleep(1)

            # Wait for page to load
            self._wait_for_page_load()

            # Check if redirected to login page
            current_url = driver.current_url
            if 'unisso/login.action' in current_url or self._is_login_page():
                logger.warning(f"Redirected to login page - session expired. Re-logging in...")
                self.status.is_logged_in = False
                
                # Re-login
                if not self.login():
                    logger.error("Failed to re-login - cannot navigate to portal")
                    return False
                
                # Wait a bit after login
                
                # Navigate again after successful login
                logger.info(f"Re-navigating to {portal_type.value} after login...")
                driver.get(url)
                time.sleep(1)
                self._wait_for_page_load()
                
                # Verify we're not on login page again
                current_url = driver.current_url
                if 'unisso/login.action' in current_url:
                    logger.error("Still on login page after re-login - navigation failed")
                    return False

            self.status.current_portal = portal_type
            self.status.last_refresh = datetime.now()
            logger.info(f"Navigated to {portal_type.value}")

            if self.status_callback:
                self.status_callback(self.status)

            return True

        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False
    
    def _wait_for_page_load(self, timeout: int = 30):
        """Wait for page to fully load"""
        try:
            driver = self._get_driver()
            if driver:
                WebDriverWait(driver, timeout).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
        except TimeoutException:
            logger.warning("Page load timeout")
        except Exception as e:
            logger.debug(f"Page load wait error: {e}")
    
    def open_all_portals_in_tabs(self) -> bool:
        """
        Open all required portals in separate tabs and store their handles.
        """
        try:
            driver = self._get_driver()
            if not driver:
                logger.error("No driver available")
                return False

            self.portal_handles = {} # Reset handles
            
            # 1. Main Application/Topology (Already open as current tab)
            # Store current handle as Main Topology
            # We will PRESERVE this tab and open all other portals in NEW tabs.
            main_handle = driver.current_window_handle
            self.portal_handles[PortalType.MAIN_TOPOLOGY] = main_handle
            logger.info("Preserved Tab 1 as Main Topology/Login Session")
            
            # List of functional portals to open
            portals_to_open = [
                (PortalType.CSL_FAULT, self.portal_urls.csl_fault),
                (PortalType.ALL_ALARMS, self.portal_urls.all_alarms),
                (PortalType.RF_UNIT, self.portal_urls.rf_unit),
                (PortalType.NODEB_CELL, self.portal_urls.nodeb_cell),
            ]
            
            for pt, url in portals_to_open:
                logger.info(f"Opening New Tab for {pt.value}...")
                driver.execute_script("window.open('about:blank', '_blank');")
                time.sleep(1)
                
                # Switch to new tab (it's the last one)
                new_handle = driver.window_handles[-1]
                driver.switch_to.window(new_handle)
                
                # Navigate
                driver.get(url)
                self._wait_for_page_load()
                
                # Store handle
                self.portal_handles[pt] = new_handle
                logger.info(f"Tab opened for {pt.value} (Handle: {new_handle[:8]})")
            
            # Switch back to Main Topology or CSL?
            # User workflow usually starts monitoring immediately. 
            # We'll switch to CSL Fault as confirmed by previous behavior.
            if PortalType.CSL_FAULT in self.portal_handles:
                driver.switch_to.window(self.portal_handles[PortalType.CSL_FAULT])
                
            logger.success("All portal tabs opened successfully")
            return True

        except Exception as e:
            logger.error(f"Error opening tabs: {e}")
            return False
    
    def switch_to_tab(self, portal_type: PortalType) -> bool:
        """
        Switch to the dedicated tab for the portal type using window handle.
        INSTANT SWITCHING - No URL matching, no reloading.
        """
        try:
            driver = self._get_driver()
            if not driver:
                return False

            # Get the stored handle
            handle = self.portal_handles.get(portal_type)
            if not handle:
                logger.warning(f"No handle stored for {portal_type.value}. attempting to find or open...")
                # Fallback: Logic to maybe recover? For now, fail to force fixing source.
                return False
            
            # Verify handle is still valid
            if handle not in driver.window_handles:
                logger.error(f"Handle for {portal_type.value} is no longer valid (tab closed?)")
                return False

            # Switch
            driver.switch_to.window(handle)
            logger.info(f"Switched to {portal_type.value} using handle {handle[:8]}")
            
            # Reset default content
            try:
                driver.switch_to.default_content()
            except:
                pass
                
            return True

        except Exception as e:
            logger.error(f"Error switching tab: {e}")
            return False
    
    def refresh_current_portal(self) -> bool:
        """Refresh the current portal view"""
        try:
            driver = self._get_driver()
            if not driver:
                logger.error("No driver available for refresh")
                return False

            # Ensure we're in default content before refresh
            try:
                driver.switch_to.default_content()
            except:
                pass

            driver.refresh()
            time.sleep(1)
            self._wait_for_page_load()
            self.status.last_refresh = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Refresh error: {e}")
            return False
    
    def export_alarms(self, portal_type: PortalType) -> Optional[str]:
        """
        Export alarms from a portal to Excel file
        
        Args:
            portal_type: The portal to export from
            
        Returns:
            path to downloaded file or None if failed
        """
        try:
            driver = self._get_driver()
            if not driver:
                logger.error("No driver available for export")
                return None

            # Switch to the portal tab
            if not self.switch_to_tab(portal_type):
                logger.info(f"Switching to portal {portal_type.value}...")
                self.navigate_to_portal(portal_type)
                time.sleep(1)

            # Ensure we're in default content before looking for table
            try:
                driver.switch_to.default_content()
            except:
                pass

            # Ensure we're on the correct portal page
            current_url = self.get_current_url()
            # Simplified check - trust switch_to_tab mostly
            expected_urls = {
                PortalType.ALL_ALARMS: 'templateId592',
                PortalType.CSL_FAULT: 'fmAlarmView', # Relaxed
                PortalType.RF_UNIT: 'templateId835',
                PortalType.NODEB_CELL: 'templateId803',
            }

            expected_part = expected_urls.get(portal_type)
            if expected_part and expected_part not in current_url:
                logger.warning(f"Mismatch: Expected '{expected_part}' in URL, but got {current_url}")
                logger.info(f"Re-navigating to {portal_type.value}...")
                if not self.navigate_to_portal(portal_type):
                    return None
                time.sleep(1)
                try:
                    driver.switch_to.default_content()
                except:
                    pass

            # Wait for the alarm table to be loaded (sets the stage)
            # We don't strictly need to find the table to export, but it confirms page load
            logger.info("Waiting for alarm table to load...")
            # (Keeping table finding logic minimal here to save time, relying on button find)
            
            # Get list of files before export
            existing_files = set(os.listdir(self.download_dir))

            # NO RETRY LOGIC - SINGLE ATTEMPT
            # User specifically requested removing retries and delays.
            
            logger.info(f"Finding export button for {portal_type.value}...")
            
            # 1. FIND THE EXPORT BUTTON
            export_btn = None
            in_iframe_context = False
            
            # Try default content first
            try:
                driver.switch_to.default_content()
                export_btn = self._find_element('export_button', timeout=2)
            except:
                pass
            
            if not export_btn:
                # Search iframes
                try:
                    driver.switch_to.default_content()
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for idx, iframe in enumerate(iframes):
                        try:
                            driver.switch_to.frame(iframe)
                            export_btn = self._find_element('export_button', timeout=1)
                            if export_btn:
                                in_iframe_context = True
                                break
                            driver.switch_to.parent_frame() 
                        except:
                            driver.switch_to.default_content()
                except:
                    pass
            
            if not export_btn:
                logger.error("Export button not found (Single Attempt)")
                # Only if really needed, we can try one fallback or just return
                return None

            # 2. CLICK THE BUTTON
            try:
                # Scroll to view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", export_btn)
                time.sleep(0.5)
                
                # Click Strategy: ActionChains (Move & Click) -> JS Click -> Standard Click
                from selenium.webdriver.common.action_chains import ActionChains
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(export_btn).click().perform()
                except:
                    try:
                        driver.execute_script("arguments[0].click();", export_btn)
                    except:
                        export_btn.click()
                
                logger.info("Clicked export button")
                
            except Exception as e:
                logger.error(f"Failed to click export button: {e}")
                return None
            
            time.sleep(1)
            
            # 3. FIND THE DROPDOWN
            # Check current context (iframe)
            if self._wait_for_element('export_all_option', timeout=3):
                found_dropdown = True
            else:
                # Check default content (common for popups)
                try:
                    driver.switch_to.default_content()
                    if self._wait_for_element('export_all_option', timeout=3):
                        found_dropdown = True
                        in_iframe_context = False # We are now in default content
                except:
                    pass
            
            if not found_dropdown:
                logger.error(f"Export dropdown did not appear for {portal_type.value}")
                self.take_screenshot(f"dropdown_not_found_{portal_type.value}")
                return None

            # Step 2: Click "All" option
            logger.info("Selecting 'All' alarms option...")
            if not self._click_element('export_all_option', timeout=5):
                logger.error("Could not select 'All' option")
                return None

            time.sleep(1)

            # Step 3: Handle the export dialog popup
            logger.info("Waiting for export dialog...")
            
            # We might have switched contexts, ensure we find the popup
            found_popup = False
            if self._wait_for_element('export_popup', timeout=5):
                found_popup = True
            else:
                try:
                    driver.switch_to.default_content()
                    if self._wait_for_element('export_popup', timeout=5):
                        found_popup = True
                except:
                    pass
            
            if not found_popup:
                logger.error("Export popup not found")
                return None

            # Step 4: Ensure XLSX is selected
            logger.info("Ensuring XLSX format is selected...")
            try:
                self._click_element('export_xlsx_option', timeout=2)
            except:
                pass

            # Step 5: Click OK
            logger.info("Clicking OK to start export...")
            if not self._click_element('export_ok_button', timeout=10):
                logger.error("Could not find OK button")
                return None

            # Step 6: Wait for download
            logger.info("Waiting for file download...")
            downloaded_file = self._wait_for_download(existing_files, timeout=60)

            if downloaded_file:
                logger.success(f"Export completed: {downloaded_file}")
                return downloaded_file
            else:
                logger.error("Export download timeout")
                return None

        except Exception as e:
            logger.error(f"Export error: {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            # Always ensure we switch back to default content
            try:
                driver.switch_to.default_content()
            except:
                pass
    
    def _wait_for_download(self, existing_files: set, timeout: int = 30) -> Optional[str]:
        """Wait for a new file to appear in download directory"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_files = set(os.listdir(self.download_dir))
            new_files = current_files - existing_files
            
            # Filter out temporary download files
            new_files = {f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')}
            
            if new_files:
                # Return the newest file
                newest = max(new_files, key=lambda f: os.path.getctime(os.path.join(self.download_dir, f)))
                return os.path.join(self.download_dir, newest)
            
            time.sleep(1)
        
        return None
    
    def get_alarm_data_from_table(self) -> List[Dict]:
        """
        Get alarm data directly from the table in the current portal
        
        Returns:
            List of alarm dictionaries
        """
        try:
            alarms = []
            
            # Find table rows
            rows = self._find_elements('alarm_rows', timeout=10)
            
            if not rows:
                logger.warning("No alarm rows found in table")
                return []
            
            for row in rows:
                try:
                    driver = self._get_driver()
                    if not driver:
                        continue
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    if len(cells) >= 4:
                        alarm = {
                            'is_toggle': 'toggle' in cells[0].text.lower() if cells[0].text else False,
                            'severity': cells[1].text if len(cells) > 1 else '',
                            'name': cells[2].text if len(cells) > 2 else '',
                            'timestamp': cells[3].text if len(cells) > 3 else '',
                            'source': cells[4].text if len(cells) > 4 else '',
                        }
                        alarms.append(alarm)
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    continue
            
            logger.info(f"Retrieved {len(alarms)} alarms from table")
            return alarms
            
        except Exception as e:
            logger.error(f"Error getting alarm data: {e}")
            return []
    
    def get_page_source(self) -> str:
        """Get the current page source"""
        try:
            driver = self._get_driver()
            if driver:
                return driver.page_source
            return ""
        except:
            return ""

    def get_current_url(self) -> str:
        """Get current URL"""
        try:
            driver = self._get_driver()
            if driver:
                return driver.current_url
            return ""
        except:
            return ""
    
    # Monitoring methods
    def start_monitoring(self, callback: Callable, interval_seconds: int = 30):
        """
        Start monitoring portals for new alarms
        
        Args:
            callback: Function to call with new alarm data
            interval_seconds: How often to check for new alarms
        """
        self.alarm_callback = callback
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, args=(interval_seconds,), daemon=True)
        self.monitor_thread.start()
        logger.info(f"Started portal monitoring (interval: {interval_seconds}s)")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logger.info("Stopped portal monitoring")
    
    def _monitoring_loop(self, interval: int):
        """Main monitoring loop"""
        portals_to_monitor = [
            PortalType.CSL_FAULT,
            PortalType.RF_UNIT,
            PortalType.NODEB_CELL,
            PortalType.ALL_ALARMS,
        ]
        
        while self.monitoring:
            try:
                for portal in portals_to_monitor:
                    if not self.monitoring:
                        break
                    
                    # Switch to portal tab
                    with self.lock:
                        if not self.switch_to_tab(portal):
                            logger.warning(f"Could not switch to {portal.value} tab, trying navigation")
                            self.navigate_to_portal(portal)
                        
                        # No refresh needed - portals show real-time data
                        time.sleep(1)
                        
                        # Get alarm data
                        alarms = self.get_alarm_data_from_table()
                        
                        if alarms and self.alarm_callback:
                            self.alarm_callback(portal, alarms)
                
                # Wait before next cycle
                for _ in range(interval):
                    if not self.monitoring:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(2)
    
    def set_status_callback(self, callback: Callable):
        """Set callback for status updates"""
        self.status_callback = callback
    
    def get_status(self) -> PortalStatus:
        """Get current portal status"""
        return self.status
    
    def take_screenshot(self, filename: str = None) -> Optional[str]:
        """Take a screenshot"""
        try:
            driver = self._get_driver()
            if not driver:
                logger.error("No driver available for screenshot")
                return None

            if not filename:
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            elif not filename.endswith('.png'):
                filename = f"{filename}.png"

            filepath = os.path.join(str(EXPORTS_DIR), filename)
            driver.save_screenshot(filepath)
            return filepath
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None
    
    def close(self):
        """Close the portal handler"""
        try:
            self.stop_monitoring()
            # Note: We don't close the browser here as it's managed by browser_manager
            self.status.is_connected = False
            self.status.is_logged_in = False
            logger.info("Portal handler closed")
        except Exception as e:
            logger.error(f"Error closing portal handler: {e}")
    
    def __del__(self):
        """Destructor"""
        self.close()


class PortalDataFetcher:
    """
    High-level class for fetching and processing portal data
    """
    
    def __init__(self, portal_handler: PortalHandler):
        self.portal = portal_handler
        self.last_fetch: Dict[PortalType, datetime] = {}
        self.cached_data: Dict[PortalType, List[Dict]] = {}
    
    def fetch_all_alarms(self) -> Dict[PortalType, List[Dict]]:
        """Fetch alarms from all portals"""
        results = {}
        
        for portal_type in [PortalType.CSL_FAULT, PortalType.RF_UNIT, 
                           PortalType.NODEB_CELL, PortalType.ALL_ALARMS]:
            try:
                self.portal.switch_to_tab(portal_type)
                # No refresh needed - portals show real-time data
                time.sleep(1)
                
                alarms = self.portal.get_alarm_data_from_table()
                results[portal_type] = alarms
                self.cached_data[portal_type] = alarms
                self.last_fetch[portal_type] = datetime.now()
                
            except Exception as e:
                logger.error(f"Error fetching {portal_type.value}: {e}")
                results[portal_type] = []
        
        return results
    
    def fetch_portal_alarms(self, portal_type: PortalType) -> List[Dict]:
        """Fetch alarms from a specific portal"""
        try:
            self.portal.switch_to_tab(portal_type)
            # No refresh needed - portals show real-time data
            time.sleep(1)
            
            alarms = self.portal.get_alarm_data_from_table()
            self.cached_data[portal_type] = alarms
            self.last_fetch[portal_type] = datetime.now()
            
            return alarms
            
        except Exception as e:
            logger.error(f"Error fetching {portal_type.value}: {e}")
            return []
    
    def export_and_process(self, portal_type: PortalType) -> Optional[str]:
        """Export alarms to file and return the file path"""
        return self.portal.export_alarms(portal_type)
    
    def get_cached_data(self, portal_type: PortalType) -> List[Dict]:
        """Get cached data for a portal"""
        return self.cached_data.get(portal_type, [])
    
    def get_last_fetch_time(self, portal_type: PortalType) -> Optional[datetime]:
        """Get last fetch time for a portal"""
        return self.last_fetch.get(portal_type)


# Global instance
portal_handler = PortalHandler()
portal_fetcher = PortalDataFetcher(portal_handler)


# Convenience functions
def initialize_portal() -> bool:
    """Initialize the portal handler (now uses browser_manager)"""
    # Portal handler now uses browser_manager's driver, so initialization is handled there
    logger.info("Portal handler initialized (using browser_manager)")
    return True


def login_to_portal(username: str = None, password: str = None) -> bool:
    """Login to the portal"""
    return portal_handler.login(username, password)


def open_all_tabs() -> bool:
    """Open all portal tabs"""
    return portal_handler.open_all_portals_in_tabs()


def start_monitoring(callback: Callable, interval: int = 30):
    """Start monitoring portals"""
    portal_handler.start_monitoring(callback, interval)


def stop_monitoring():
    """Stop monitoring"""
    portal_handler.stop_monitoring()


def get_portal_status() -> PortalStatus:
    """Get portal status"""
    return portal_handler.get_status()


def close_portal():
    """Close the portal"""
    portal_handler.close()


def test_export_functionality():
    """Test the export functionality for all portal types"""
    import os
    from pathlib import Path

    try:
        logger.info("Testing export functionality...")

        # Initialize portal
        if not initialize_portal():
            logger.error("Failed to initialize portal")
            return False

        # Login
        if not login_to_portal():
            logger.error("Failed to login")
            return False

        # Open all tabs
        if not open_all_tabs():
            logger.error("Failed to open tabs")
            return False

        # Test export for each portal type
        portal_types = [
            PortalType.ALL_ALARMS,
            PortalType.CSL_FAULT,
            PortalType.RF_UNIT,
            PortalType.NODEB_CELL,
        ]

        results = {}

        for portal_type in portal_types:
            logger.info(f"Testing export for {portal_type.value}...")

            try:
                # Export alarms
                exported_file = portal_handler.export_alarms(portal_type)

                if exported_file and os.path.exists(exported_file):
                    file_size = os.path.getsize(exported_file)
                    logger.success(f"Export successful for {portal_type.value}: {exported_file} ({file_size} bytes)")

                    # Try to process the file
                    try:
                        alarms = alarm_processor.process_exported_excel(exported_file)
                        logger.info(f"Processed {len(alarms)} alarms from {portal_type.value}")
                        results[portal_type] = {"success": True, "file": exported_file, "alarms": len(alarms)}
                    except Exception as e:
                        logger.warning(f"Could not process exported file: {e}")
                        results[portal_type] = {"success": True, "file": exported_file, "alarms": 0}
                else:
                    logger.error(f"Export failed for {portal_type.value}")
                    results[portal_type] = {"success": False, "file": None, "alarms": 0}

            except Exception as e:
                logger.error(f"Error testing {portal_type.value}: {e}")
                results[portal_type] = {"success": False, "file": None, "alarms": 0}

        # Summary
        logger.info("=" * 60)
        logger.info("EXPORT TEST SUMMARY")
        logger.info("=" * 60)

        successful_exports = 0
        total_alarms = 0

        for portal_type, result in results.items():
            status = "SUCCESS" if result["success"] else "FAILED"
            alarms = result["alarms"]
            logger.info(f"{portal_type.value}: {status} ({alarms} alarms)")

            if result["success"]:
                successful_exports += 1
                total_alarms += alarms

        logger.info(f"Total successful exports: {successful_exports}/{len(portal_types)}")
        logger.info(f"Total alarms processed: {total_alarms}")

        # Close portal
        close_portal()

        return successful_exports == len(portal_types)

    except Exception as e:
        logger.error(f"Test error: {e}")
        try:
            close_portal()
        except:
            pass
        return False


def test_export_single_portal(portal_type: str):
    """Test export for a single portal type"""
    try:
        portal_map = {
            "all": PortalType.ALL_ALARMS,
            "csl": PortalType.CSL_FAULT,
            "rf": PortalType.RF_UNIT,
            "nodeb": PortalType.NODEB_CELL,
        }

        if portal_type not in portal_map:
            logger.error(f"Invalid portal type: {portal_type}")
            return False

        pt = portal_map[portal_type]

        logger.info(f"Testing export for {pt.value}...")

        # Initialize portal
        if not initialize_portal():
            logger.error("Failed to initialize portal")
            return False

        # Login
        if not login_to_portal():
            logger.error("Failed to login")
            return False

        # Navigate to portal
        portal_handler.navigate_to_portal(pt)
        time.sleep(2)

        # Export
        exported_file = portal_handler.export_alarms(pt)

        if exported_file:
            logger.success(f"Export successful: {exported_file}")
            close_portal()
            return True
        else:
            logger.error("Export failed")
            close_portal()
            return False

    except Exception as e:
        logger.error(f"Test error: {e}")
        try:
            close_portal()
        except:
            pass
        return False