"""
WhatsApp Handler
Handles all WhatsApp Web automation for sending alarm messages to groups
"""

import time
import threading
import queue
from datetime import datetime
from typing import Optional, List, Dict, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import urllib.parse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException
)
from selenium.webdriver.common.action_chains import ActionChains

from browser_manager import browser_manager, TabType
from config import settings
from logger_module import logger
from alarm_processor import AlarmCategory


class WhatsAppStatus(Enum):
    """WhatsApp connection status"""
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    QR_REQUIRED = "QR Code Required"
    CONNECTED = "Connected"
    SENDING = "Sending Message"
    ERROR = "Error"


@dataclass
class MessageTask:
    """A message to be sent"""
    group_name: str
    message: str
    alarm_type: str
    priority: int = 1  # 1 = high (CSL), 2 = normal
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    
    def __lt__(self, other):
        """For priority queue ordering"""
        return self.priority < other.priority


@dataclass
class SendResult:
    """Result of sending a message"""
    success: bool
    group_name: str
    message_preview: str
    error: Optional[str] = None
    sent_at: Optional[datetime] = None


class WhatsAppHandler:
    """
    Handles WhatsApp Web automation
    """
    
    WHATSAPP_URL = "https://web.whatsapp.com"
    
    # Selectors for WhatsApp Web elements (Updated Dec 2024)
    SELECTORS = {
        # QR Code and loading - Multiple fallbacks for different WhatsApp versions
        'qr_code': [
            (By.CSS_SELECTOR, '[data-testid="qrcode"]'),
            (By.CSS_SELECTOR, 'canvas[aria-label="Scan me!"]'),
            (By.CSS_SELECTOR, 'canvas[aria-label*="Scan"]'),
            (By.CSS_SELECTOR, '[data-ref]'),  # QR code container
            (By.XPATH, '//canvas[contains(@aria-label, "Scan")]'),
        ],
        'loading': [
            (By.CSS_SELECTOR, '[data-testid="startup"]'),
            (By.CSS_SELECTOR, '.startup'),
            (By.CSS_SELECTOR, '[data-testid="intro-md-beta-logo-dark"]'),
            (By.CSS_SELECTOR, '[data-testid="intro-md-beta-logo-light"]'),
        ],
        
        # Main chat elements - Logged in indicators
        'chat_list': [
            (By.CSS_SELECTOR, '#pane-side'),
            (By.CSS_SELECTOR, '[data-testid="chat-list"]'),
            (By.CSS_SELECTOR, '[data-testid="chatlist"]'),
            (By.CSS_SELECTOR, 'div#pane-side'),
            (By.CSS_SELECTOR, '[aria-label="Chat list"]'),
            (By.CSS_SELECTOR, '[aria-label="Chats"]'),
        ],
        'search_box': [
            (By.CSS_SELECTOR, '[data-testid="chat-list-search"]'),
            (By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="3"]'),
            (By.CSS_SELECTOR, 'div[role="textbox"][data-tab="3"]'),
            (By.CSS_SELECTOR, '[title="Search input textbox"]'),
            (By.CSS_SELECTOR, 'div[contenteditable="true"][title*="Search"]'),
            (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]'),
            (By.XPATH, '//div[contains(@class, "lexical-rich-text-input")]//div[@contenteditable="true"]'),
        ],
        
        # Chat/Group elements
        'chat_item': [
            (By.CSS_SELECTOR, '[data-testid="cell-frame-container"]'),
            (By.CSS_SELECTOR, '[data-testid="list-item"]'),
            (By.CSS_SELECTOR, 'div[data-testid="chat-list"] > div'),
        ],
        'chat_title': [
            (By.CSS_SELECTOR, '[data-testid="conversation-info-header-chat-title"]'),
            (By.CSS_SELECTOR, 'header span[dir="auto"][title]'),
            (By.CSS_SELECTOR, 'header span[dir="auto"]'),
            (By.CSS_SELECTOR, '#main header span[dir="auto"]'),
        ],
        
        # Message input - Multiple fallbacks for current WhatsApp Web
        'message_input': [
            (By.CSS_SELECTOR, '[data-testid="conversation-compose-box-input"]'),
            (By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="10"]'),
            (By.CSS_SELECTOR, 'div[role="textbox"][data-tab="10"]'),
            (By.CSS_SELECTOR, '#main footer div[contenteditable="true"]'),
            (By.CSS_SELECTOR, 'footer div[contenteditable="true"]'),
            (By.CSS_SELECTOR, 'div[title="Type a message"]'),
            (By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]'),
            (By.XPATH, '//footer//div[@contenteditable="true"]'),
        ],
        'send_button': [
            (By.CSS_SELECTOR, '[data-testid="send"]'),
            (By.CSS_SELECTOR, 'button[aria-label="Send"]'),
            (By.CSS_SELECTOR, 'span[data-icon="send"]'),
            (By.XPATH, '//button[@aria-label="Send"]'),
            (By.XPATH, '//span[@data-icon="send"]/parent::button'),
        ],
        
        # Confirmation elements
        'message_sent_tick': [
            (By.CSS_SELECTOR, '[data-testid="msg-check"]'),
            (By.CSS_SELECTOR, 'span[data-icon="msg-check"]'),
        ],
        'message_delivered_tick': [
            (By.CSS_SELECTOR, '[data-testid="msg-dblcheck"]'),
            (By.CSS_SELECTOR, 'span[data-icon="msg-dblcheck"]'),
        ],
        
        # Additional logged-in indicators
        'side_menu': [
            (By.CSS_SELECTOR, '[data-testid="menu-bar-menu"]'),
            (By.CSS_SELECTOR, 'span[data-testid="menu"]'),
            (By.CSS_SELECTOR, 'header span[data-icon="menu"]'),
        ],
    }
    
    def __init__(self):
        self.status = WhatsAppStatus.DISCONNECTED
        self.message_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.sending = False
        self.sender_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Callbacks
        self.status_callbacks: List[Callable] = []
        self.message_sent_callbacks: List[Callable] = []
        
        # Group cache
        self.group_cache: Dict[str, bool] = {}  # group_name -> found
        
        # Stats
        self.messages_sent = 0
        self.messages_failed = 0
        self.last_message_time: Optional[datetime] = None
    
    def add_status_callback(self, callback: Callable):
        """Add callback for status changes"""
        self.status_callbacks.append(callback)
    
    def add_message_sent_callback(self, callback: Callable):
        """Add callback for when message is sent"""
        self.message_sent_callbacks.append(callback)
    
    def _notify_status(self, status: WhatsAppStatus):
        """Notify status callbacks"""
        self.status = status
        for callback in self.status_callbacks:
            try:
                callback(status)
            except:
                pass
    
    def _notify_message_sent(self, result: SendResult):
        """Notify message sent callbacks"""
        for callback in self.message_sent_callbacks:
            try:
                callback(result)
            except:
                pass
    
    def _get_driver(self) -> Optional[webdriver.Chrome]:
        """Get the WhatsApp WebDriver"""
        return browser_manager.whatsapp_driver  # Use dedicated WhatsApp browser
    
    def _find_element(self, selector_key: str, timeout: int = 10) -> Optional[any]:
        """Find element using multiple selectors"""
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
    
    def _find_clickable_element(self, selector_key: str, timeout: int = 10) -> Optional[any]:
        """Find clickable element"""
        driver = self._get_driver()
        if not driver:
            logger.error(f"DEBUG _find_clickable_element: No driver for {selector_key}")
            return None
        
        logger.info(f"DEBUG _find_clickable_element: Finding {selector_key}")
        selectors = self.SELECTORS.get(selector_key, [])
        
        for by, value in selectors:
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((by, value))
                )
                logger.info(f"DEBUG _find_clickable_element: Found {selector_key} with {value}")
                return element
            except TimeoutException:
                continue
            except Exception as e:
                logger.error(f"DEBUG _find_clickable_element: Error finding {selector_key}: {e}")
                continue
        
        logger.error(f"DEBUG _find_clickable_element: Could not find {selector_key} after {timeout}s")
        return None
    
    def check_connection(self) -> WhatsAppStatus:
        """Check WhatsApp connection status - improved detection"""
        try:
            driver = self._get_driver()
            if not driver:
                self._notify_status(WhatsAppStatus.DISCONNECTED)
                return WhatsAppStatus.DISCONNECTED
            
            # WhatsApp runs in dedicated browser instance - no need to switch tabs
            
            # First check URL to ensure we're on WhatsApp
            try:
                current_url = driver.current_url
                if 'web.whatsapp.com' not in current_url:
                    logger.warning(f"Not on WhatsApp Web: {current_url}")
                    self._notify_status(WhatsAppStatus.DISCONNECTED)
                    return WhatsAppStatus.DISCONNECTED
            except:
                pass
            
            # Check for various logged-in indicators (fast check first)
            logged_in_selectors = [
                '#pane-side',
                '[data-testid="chat-list"]',
                '[data-testid="chatlist"]',
                'div#pane-side',
                '[aria-label="Chat list"]',
                '[aria-label="Chats"]',
                '[data-testid="menu-bar-menu"]',
                '[data-testid="cell-frame-container"]',
                'header[data-testid="chatlist-header"]',
                '#main',
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        logger.debug(f"WhatsApp connected - found: {selector}")
                        self._notify_status(WhatsAppStatus.CONNECTED)
                        return WhatsAppStatus.CONNECTED
                except:
                    continue
            
            # Check page source for indicators (fallback)
            try:
                page_source = driver.page_source.lower()
                if 'pane-side' in page_source or 'chat-list' in page_source or 'chatlist' in page_source:
                    logger.info("WhatsApp connected - found in page source")
                    self._notify_status(WhatsAppStatus.CONNECTED)
                    return WhatsAppStatus.CONNECTED
            except:
                pass
            
            # Check for QR code (not logged in)
            qr_selectors = [
                '[data-testid="qrcode"]',
                'canvas[aria-label*="Scan"]',
                '[data-ref]',  # QR container
            ]
            
            for selector in qr_selectors:
                try:
                    qr = driver.find_element(By.CSS_SELECTOR, selector)
                    if qr and qr.is_displayed():
                        logger.info("WhatsApp requires QR code scan")
                        self._notify_status(WhatsAppStatus.QR_REQUIRED)
                        return WhatsAppStatus.QR_REQUIRED
                except:
                    continue
            
            # Check for loading screen
            loading = self._find_element('loading', timeout=1)
            if loading:
                self._notify_status(WhatsAppStatus.CONNECTING)
                return WhatsAppStatus.CONNECTING
            
            # If we're on WhatsApp URL and no QR found, assume connected
            try:
                if 'web.whatsapp.com' in driver.current_url:
                    logger.info("On WhatsApp URL with no QR - assuming connected")
                    self._notify_status(WhatsAppStatus.CONNECTED)
                    return WhatsAppStatus.CONNECTED
            except:
                pass
            
            self._notify_status(WhatsAppStatus.DISCONNECTED)
            return WhatsAppStatus.DISCONNECTED
            
        except Exception as e:
            logger.error(f"Error checking WhatsApp connection: {e}")
            # Don't mark as error for minor issues, assume connected if we got this far
            self._notify_status(WhatsAppStatus.CONNECTED)
            return WhatsAppStatus.CONNECTED
    
    def wait_for_connection(self, timeout: int = 120) -> bool:
        """
        Wait for WhatsApp to be connected (QR scanned)
        
        Args:
            timeout: Maximum seconds to wait
            
        Returns:
            True if connected
        """
        logger.info("Waiting for WhatsApp connection...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.check_connection()
            
            if status == WhatsAppStatus.CONNECTED:
                logger.success("WhatsApp connected!")
                return True
            elif status == WhatsAppStatus.QR_REQUIRED:
                logger.info("Please scan the QR code...")
            
            time.sleep(2)
        
        logger.error("WhatsApp connection timeout")
        return False
    
    def search_group(self, group_name: str) -> bool:
        """
        Search for a group by name
        
        Args:
            group_name: Name of the group to find
            
        Returns:
            True if group found and selected
        """
        try:
            driver = self._get_driver()
            if not driver:
                return False
            
            # Switch to WhatsApp tab - NOT NEEDED
            # browser_manager.switch_to_tab(TabType.WHATSAPP)
            # time.sleep(0.5)
            
            # Find search box
            search_box = self._find_clickable_element('search_box', timeout=10)
            if not search_box:
                logger.error("Could not find search box")
                return False
            
            # Clear and type group name
            search_box.click()
            time.sleep(0.3)
            
            # Clear existing text
            search_box.send_keys(Keys.CONTROL + "a")
            search_box.send_keys(Keys.DELETE)
            time.sleep(0.2)
            
            # Type group name
            search_box.send_keys(group_name)
            time.sleep(1.5)  # Wait for search results
            
            # Find and click the group
            return self._click_group_in_results(group_name)
            
        except Exception as e:
            logger.error(f"Error searching for group '{group_name}': {e}")
            return False
    
    def _click_group_in_results(self, group_name: str) -> bool:
        """Click on a group in search results"""
        try:
            driver = self._get_driver()
            
            # Find chat items
            chat_items = driver.find_elements(By.CSS_SELECTOR, '[data-testid="cell-frame-container"]')
            
            for item in chat_items:
                try:
                    # Get the title/name of this chat
                    title_elem = item.find_element(By.CSS_SELECTOR, 'span[dir="auto"][title]')
                    title = title_elem.get_attribute('title') or title_elem.text
                    
                    # Check if this is our group (case-insensitive partial match)
                    if group_name.lower() in title.lower() or title.lower() in group_name.lower():
                        # Click on the chat item
                        item.click()
                        time.sleep(1)
                        
                        # Verify we're in the right chat
                        if self._verify_current_chat(group_name):
                            logger.info(f"Found and selected group: {group_name}")
                            return True
                            
                except StaleElementReferenceException:
                    continue
                except NoSuchElementException:
                    continue
            
            # Try alternative method - clicking any result that appears
            try:
                first_result = driver.find_element(
                    By.CSS_SELECTOR,
                    '#pane-side > div > div > div > div'
                )
                first_result.click()
                time.sleep(1)
                
                if self._verify_current_chat(group_name):
                    return True
            except:
                pass
            
            logger.warning(f"Group not found: {group_name}")
            return False
            
        except Exception as e:
            logger.error(f"Error clicking group: {e}")
            return False
    
    def _get_current_chat_title(self) -> Optional[str]:
        """Get the current chat title"""
        try:
            driver = self._get_driver()
            if not driver:
                return None

            # Try multiple selectors for chat title
            title_selectors = [
                (By.CSS_SELECTOR, '[data-testid="conversation-info-header-chat-title"]'),
                (By.CSS_SELECTOR, 'header [dir="auto"]'),
                (By.CSS_SELECTOR, '.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6.xlyipyv.xuxw1ft.x1rg5ohu span[dir="auto"]'),
                (By.CSS_SELECTOR, 'header span[dir="auto"][title]'),
                (By.CSS_SELECTOR, 'header span[dir="auto"]'),
                (By.CSS_SELECTOR, '[data-testid="chat-info-drawer-name"]'),
            ]

            for by, selector in title_selectors:
                try:
                    element = WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    title = element.get_attribute('title') or element.text
                    if title and title.strip():
                        logger.info(f"DEBUG: Found chat title with selector '{selector}': '{title}'")
                        return title.strip()
                except:
                    continue

            # Fallback: try the old method
            header = self._find_element('chat_title', timeout=2)
            if header:
                title = header.get_attribute('title') or header.text
                if title and title.strip():
                    logger.info(f"DEBUG: Found chat title with fallback selector: '{title}'")
                    return title.strip()

            logger.warning("DEBUG: No chat title found with any selector")
            return None
        except Exception as e:
            logger.warning(f"DEBUG: Error getting current chat title: {e}")
            return None

    def _fuzzy_group_match(self, group_name: str, title: str) -> bool:
        """Fuzzy matching for group names with common variations"""
        try:
            # Remove extra spaces and normalize
            group_norm = ' '.join(group_name.split())
            title_norm = ' '.join(title.split())

            # Handle common spacing variations
            group_words = set(group_norm.lower().split())
            title_words = set(title_norm.lower().split())

            # If most words match, consider it a match
            common_words = group_words.intersection(title_words)
            if len(common_words) >= min(len(group_words), len(title_words)) * 0.8:  # 80% overlap
                    return True
            
            return False
        except:
            return False

    def _refresh_chat_list(self):
        """Refresh the chat list to ensure it's up to date"""
        try:
            driver = self._get_driver()
            if not driver:
                return

            # Try to scroll the chat list to refresh it
            chat_list_selectors = [
                (By.CSS_SELECTOR, '[aria-label="Chat list"][role="grid"]'),
                (By.CSS_SELECTOR, '[aria-label="Chat list"]'),
                (By.CSS_SELECTOR, '#pane-side'),
                (By.CSS_SELECTOR, '[data-testid="chat-list"]'),
            ]

            for by, selector in chat_list_selectors:
                try:
                    chat_list = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    # Scroll to top and then back down to refresh
                    driver.execute_script("arguments[0].scrollTo(0, 0);", chat_list)
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].scrollTo(0, 100);", chat_list)
                    time.sleep(0.2)
                    break
                except:
                    continue
        except:
            pass

    def _verify_current_chat(self, expected_name: str) -> bool:
        """Verify we're in the correct chat"""
        try:
            chat_title = self._get_current_chat_title()
            if chat_title:
                logger.info(f"DEBUG: Verifying chat - Expected: '{expected_name}', Got: '{chat_title}'")
                # Use same fuzzy matching logic as group finding
                match = self._fuzzy_group_match(expected_name, chat_title) or \
                       expected_name.lower() in chat_title.lower() or \
                       chat_title.lower() in expected_name.lower()
                if match:
                    logger.info(f"DEBUG: Chat verification PASSED")
                else:
                    logger.info(f"DEBUG: Chat verification FAILED")
                return match
            logger.warning("DEBUG: Could not get current chat title for verification")
            return False
        except Exception as e:
            logger.error(f"DEBUG: Error in chat verification: {e}")
            return False
    
    def find_and_open_group_direct(self, group_name: str) -> bool:
        """
        Find and open a group directly from chat list by title attribute.
        This is faster than using the search bar and avoids search delays.
        
        Args:
            group_name: Name of the group to find
            
        Returns:
            True if group found and opened
        """
        try:
            driver = self._get_driver()
            if not driver:
                logger.error("No driver available for group selection")
                return False
            
            # Ensure chat list is refreshed and visible
            logger.info(f"DEBUG find_and_open_group_direct: Refreshing chat list before search")
            self._refresh_chat_list()

            # No need to switch tabs - WhatsApp is in separate browser instance

            logger.info(f"DEBUG find_and_open_group_direct: Looking for group '{group_name}'")
            
            # Find chat list container - try multiple selectors based on HTML structure
            chat_list = None
            chat_list_selectors = [
                (By.CSS_SELECTOR, '[aria-label="Chat list"][role="grid"]'),  # Primary selector
                (By.CSS_SELECTOR, '[aria-label="Chat list"]'),                # Fallback
                (By.CSS_SELECTOR, '#pane-side'),                           # Alternative
                (By.CSS_SELECTOR, '[data-testid="chat-list"]'),           # Another fallback
            ]

            for by, selector in chat_list_selectors:
                try:
                    chat_list = driver.find_element(by, selector)
                    logger.info(f"DEBUG: Found chat list with selector: {selector}")
                    break
            except:
                    continue

            if not chat_list:
                logger.error("Could not find chat list container")
                return False

            # Find all chat rows - based on the HTML structure provided
            rows = chat_list.find_elements(By.CSS_SELECTOR, '[role="row"]')

            if not rows:
                # Try alternative row selectors
                row_selectors = [
                    (By.CSS_SELECTOR, 'div[role="gridcell"]'),  # Alternative structure
                    (By.CSS_SELECTOR, '[data-testid="cell-frame-container"]'),  # Another fallback
                    (By.CSS_SELECTOR, '.x10l6tqk'),  # Class-based selector from HTML
                ]

                for by, selector in row_selectors:
                    try:
                        rows = chat_list.find_elements(by, selector)
                        if rows:
                            logger.info(f"DEBUG: Found {len(rows)} rows with alternative selector: {selector}")
                            break
                except:
                        continue

            if not rows:
                logger.error("No chat rows found in chat list")
                    return False
            
            logger.info(f"DEBUG: Found {len(rows)} chat rows to search through")
            
            # Search through rows for matching group name
            for row in rows:
                try:
                    # Find the group name - multiple selectors based on HTML structure
                    title = None
                    title_selectors = [
                        'span[dir="auto"][title]',          # Primary selector
                        'span[dir="auto"]',                  # Fallback
                        '[data-testid="conversation-info-header-chat-title"]',  # Alternative
                        '.x1iyjqo2.x6ikm8r.x10wlt62.x1n2onr6.xlyipyv.xuxw1ft.x1rg5ohu.x1jchvi3.xjb2p0i.xo1l8bm.x17mssa0.x1ic7a3i._ao3e',  # Class selector from HTML
                    ]

                    for selector in title_selectors:
                        try:
                            title_element = row.find_element(By.CSS_SELECTOR, selector)
                            title = title_element.get_attribute('title') or title_element.text
                            if title and title.strip():
                                break
                        except:
                            continue

                    if not title:
                        continue

                    title = title.strip()
                    logger.info(f"DEBUG: Found chat title: '{title}'")
                    
                    # Match group name - try multiple matching strategies
                    group_match = False

                    # Strategy 1: Exact match
                    if group_name.lower() == title.lower():
                        group_match = True
                        logger.info(f"DEBUG: Exact match found for '{group_name}'")

                    # Strategy 2: Group name contains title (handles truncated titles)
                    elif title.lower() in group_name.lower():
                        group_match = True
                        logger.info(f"DEBUG: Reverse partial match found for '{group_name}' contains '{title}'")

                    # Strategy 3: Title contains group name (original partial match)
                    elif group_name.lower() in title.lower():
                        group_match = True
                        logger.info(f"DEBUG: Partial match found for '{group_name}' in '{title}'")

                    # Strategy 4: Fuzzy matching for common variations
                    elif self._fuzzy_group_match(group_name, title):
                        group_match = True
                        logger.info(f"DEBUG: Fuzzy match found for '{group_name}' ~ '{title}'")

                    if group_match:
                        # Scroll into view and click using JavaScript
                        logger.info(f"DEBUG: Scrolling group '{title}' into view")
                        # Small delay before scrolling to ensure stability
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
                        time.sleep(0.8)  # Longer wait for scroll to complete

                        # Click the row - try multiple approaches
                        logger.info(f"DEBUG: Clicking on group '{title}'")
                        click_success = False

                        # Approach 1: Try ActionChains for more reliable clicking
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            actions = ActionChains(driver)
                            actions.move_to_element(row).click().perform()
                            logger.info(f"DEBUG: ActionChains click successful on '{title}'")
                            click_success = True
                        except Exception as e1:
                            logger.warning(f"DEBUG: ActionChains click failed: {e1}")

                            # Approach 2: Try to find the actual clickable element within the row
                            try:
                                # Look for clickable elements within the row
                                clickable_selectors = [
                                    '[role="link"]',
                                    '[data-testid*="conversation"]',
                                    'div[tabindex="0"]',
                                    'div[data-testid*="cell"]'
                                ]

                                clickable_element = None
                                for selector in clickable_selectors:
                                    try:
                                        clickable_element = row.find_element(By.CSS_SELECTOR, selector)
                                        if clickable_element.is_displayed() and clickable_element.is_enabled():
                                            break
                                    except:
                                        continue

                                if clickable_element:
                                    # Try ActionChains on the specific element
                                    actions = ActionChains(driver)
                                    actions.move_to_element(clickable_element).click().perform()
                                    logger.info(f"DEBUG: ActionChains on element successful on '{title}'")
                                    click_success = True
                                else:
                                    # Fallback to direct row click
                                    row.click()
                                    logger.info(f"DEBUG: Direct row click successful on '{title}'")
                                    click_success = True

                            except Exception as e2:
                                logger.warning(f"DEBUG: Element click failed, trying JavaScript: {e2}")
                                try:
                                    # Last resort: JavaScript click
                        driver.execute_script("arguments[0].click();", row)
                                    logger.info(f"DEBUG: JavaScript click successful on '{title}'")
                                    click_success = True
                                except Exception as e3:
                                    logger.error(f"DEBUG: All click methods failed: {e3}")
                                    continue

                        if not click_success:
                            continue

                        # Wait for chat to fully load - longer initial wait
                        logger.info(f"DEBUG: Waiting for chat '{group_name}' to load...")
                        time.sleep(5.0)  # Increased wait time

                        # Try multiple times to verify we're in the right chat
                        verification_attempts = 0
                        max_attempts = 5  # Increased attempts

                        while verification_attempts < max_attempts:
                        # Verify we're in the right chat
                        if self._verify_current_chat(group_name):
                                logger.success(f"Successfully opened group: {group_name}")
                            return True

                            verification_attempts += 1
                            if verification_attempts < max_attempts:
                                logger.info(f"Chat verification attempt {verification_attempts} failed, waiting longer...")
                                time.sleep(3.0)  # Increased wait between attempts
                        else:
                                # Final attempt - check if we opened any chat at all
                                try:
                                    current_title = self._get_current_chat_title()
                                    if current_title:
                                        logger.warning(f"Opened wrong chat. Expected: '{group_name}', Got: '{current_title}'")
                                        # Try to continue anyway if it's close enough
                                        if group_name.lower() in current_title.lower() or current_title.lower() in group_name.lower():
                                            logger.info(f"Close enough match - proceeding with '{current_title}'")
                            return True
                                        else:
                                            # Try one more click if we're still on the wrong chat
                                            logger.info("DEBUG: Trying one more click on the group...")
                                            try:
                                                if clickable_element:
                                                    driver.execute_script("arguments[0].click();", clickable_element)
                                                else:
                                                    driver.execute_script("arguments[0].click();", row)
                                                time.sleep(2.0)
                                                if self._verify_current_chat(group_name):
                                                    logger.success(f"Successfully opened group on retry: {group_name}")
                                                    return True
                                            except:
                                                pass
                                            logger.warning(f"Chat verification failed after {max_attempts} attempts")
                                    else:
                                        logger.warning("No chat title found after click")
                                except Exception as e:
                                    logger.warning(f"Could not verify chat after click: {e}")

                except (NoSuchElementException, StaleElementReferenceException) as e:
                    logger.debug(f"Skipping row due to element error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing row: {e}")
                    continue
            
            # If direct search failed
            logger.warning(f"Group '{group_name}' not found in chat list")
            return False
            
        except Exception as e:
            logger.error(f"Error finding group directly: {e}")
            return False
    
    def send_message(self, group_name: str, message: str) -> SendResult:
        """
        Send a message to a group
        
        Args:
            group_name: Name of the group
            message: Message text to send
            
        Returns:
            SendResult with success status
        """
        try:
            # self.sending_active = True  # No longer needed with dual browsers
            logger.info(f"DEBUG send_message: Entry point - group={group_name}, msg_len={len(message)}")
            self._notify_status(WhatsAppStatus.SENDING)
            
            driver = self._get_driver()
            if not driver:
                logger.error("DEBUG send_message: Browser not available")
                return SendResult(
                    success=False,
                    group_name=group_name,
                    message_preview=message[:50],
                    error="Browser not available"
                )
            
            # WhatsApp is in separate browser instance - no tab switching needed
            
            logger.info(f"DEBUG send_message: Finding group {group_name}")
            # Find and select group directly (no search bar - direct HTML selection)
            if not self.find_and_open_group_direct(group_name):
                logger.error(f"DEBUG send_message: Group not found: {group_name}")
                return SendResult(
                    success=False,
                    group_name=group_name,
                    message_preview=message[:50],
                    error=f"Group not found: {group_name}"
                )
            
            logger.info("DEBUG send_message: Group opened, waiting for chat to load...")
            time.sleep(2)  # Wait for chat to fully load
            
            logger.info("DEBUG send_message: Finding message input")
            # Find message input
            message_input = self._find_clickable_element('message_input', timeout=15)
            if not message_input:
                logger.error("DEBUG send_message: Could not find message input - TIMEOUT")
                logger.error("DEBUG send_message: This means WhatsApp chat UI didn't load or selectors are wrong")
                return SendResult(
                    success=False,
                    group_name=group_name,
                    message_preview=message[:50],
                    error="Could not find message input - chat may not have loaded"
                )
            
            logger.info("DEBUG send_message: Clicking message input")
            
            # Click on message input
            message_input.click()
            time.sleep(0.3)
            
            # DEBUG: Log the actual message being sent
            logger.info(f"DEBUG send_message: About to type message - length: {len(message)} characters")
            logger.info(f"DEBUG send_message: First 100 chars: {message[:100]}")
            
            logger.info("DEBUG send_message: Ready to type message")
            
            # Send message (handle multi-line)
            self._type_message(message_input, message)
            logger.info("DEBUG send_message: Message typed successfully")
            
            logger.info("DEBUG send_message: Clicking send button")
            # Click send button or press Enter
            if not self._click_send():
                # Try pressing Enter
                logger.info("DEBUG send_message: Send button not found, pressing Enter")
                message_input.send_keys(Keys.ENTER)
            
            time.sleep(1)
            
            # Update stats
            self.messages_sent += 1
            self.last_message_time = datetime.now()
            
            self._notify_status(WhatsAppStatus.CONNECTED)
            
            result = SendResult(
                success=True,
                group_name=group_name,
                message_preview=message[:50] + "..." if len(message) > 50 else message,
                sent_at=datetime.now()
            )
            
            self._notify_message_sent(result)
            logger.success(f"DEBUG send_message: SUCCESS - Message sent to {group_name}")
            
            # self.sending_active = False  # Allow portal to resume
            return result
            
        except Exception as e:
            # self.sending_active = False  # Allow portal to resume
            self.messages_failed += 1
            self._notify_status(WhatsAppStatus.ERROR)
            logger.error(f"DEBUG send_message: EXCEPTION - {str(e)}")
            import traceback
            traceback.print_exc()
            
            return SendResult(
                success=False,
                group_name=group_name,
                message_preview=message[:50],
                error=str(e)
            )
    
    def _type_message(self, input_element, message: str):
        """Type a message, handling multi-line text"""
        try:
            # Split message into lines
            lines = message.split('\n')
            
            for i, line in enumerate(lines):
                # Type the line
                input_element.send_keys(line)
                
                # If not last line, press Shift+Enter for new line
                if i < len(lines) - 1:
                    input_element.send_keys(Keys.SHIFT + Keys.ENTER)
                    time.sleep(0.1)
            
        except Exception as e:
            # Fallback: paste the entire message
            try:
                import pyperclip
                pyperclip.copy(message)
                input_element.send_keys(Keys.CONTROL + 'v')
            except:
                # Last resort: send without formatting
                input_element.send_keys(message.replace('\n', ' '))
    
    def _click_send(self) -> bool:
        """Click the send button"""
        try:
            send_button = self._find_clickable_element('send_button', timeout=5)
            if send_button:
                send_button.click()
                return True
        except:
            pass
        return False
    
    def queue_message(self, group_name: str, message: str, alarm_type: str, priority: int = 2):
        """
        Add a message to the send queue
        
        Args:
            group_name: Target group name
            message: Message to send
            alarm_type: Type of alarm (for logging)
            priority: 1 = high (CSL), 2 = normal
        """
        task = MessageTask(
            group_name=group_name,
            message=message,
            alarm_type=alarm_type,
            priority=priority
        )
        self.message_queue.put((priority, task))
        # logger.info(f"Queued message for {group_name} (priority: {priority})")
    
    def start_sender(self):
        """Start the background message sender"""
        if self.sending:
            return
        
        self.sending = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()
        logger.info("WhatsApp message sender started")
    
    def stop_sender(self):
        """Stop the background message sender"""
        self.sending = False
        if self.sender_thread:
            self.sender_thread.join(timeout=10)
        logger.info("WhatsApp message sender stopped")
    
    def _sender_loop(self):
        """Background loop for sending queued messages - improved reliability"""
        connection_check_counter = 0
        
        while self.sending:
            try:
                # Get next message (with timeout to allow checking self.sending)
                try:
                    priority, task = self.message_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Only check WhatsApp connection every 5 messages or if never checked
                # This prevents constant tab switching which can cause issues
                connection_check_counter += 1
                if connection_check_counter >= 5:
                    connection_status = self.check_connection()
                    connection_check_counter = 0
                    
                    if connection_status == WhatsAppStatus.QR_REQUIRED:
                        # Definitely not connected - requeue and wait
                        logger.warning("WhatsApp requires QR scan - waiting...")
                        self.message_queue.put((priority, task))
                        time.sleep(10)
                        continue
                    elif connection_status == WhatsAppStatus.DISCONNECTED:
                        # Try to send anyway - connection check might be wrong
                        logger.warning("WhatsApp shows disconnected but trying to send anyway...")
                
                # Send the message (try regardless of connection status)
                logger.info(f"Attempting to send message to: {task.group_name}")
                result = self.send_message(task.group_name, task.message)
                
                if result.success:
                    logger.success(f"✓ Message sent successfully to {task.group_name}")
                    # Reset connection counter on success
                    connection_check_counter = 0
                elif task.retry_count < task.max_retries:
                    # Retry
                    task.retry_count += 1
                    logger.warning(f"Retrying message to {task.group_name} (attempt {task.retry_count}/{task.max_retries})")
                    self.message_queue.put((priority + 1, task))  # Lower priority for retries
                    time.sleep(3)
                else:
                    logger.error(f"✗ Failed to send message to {task.group_name} after {task.max_retries} retries: {result.error}")
                
                # Small delay between messages to avoid rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Sender loop error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
    
    def send_to_mbu_group(self, mbu: str, message: str, alarm_type: str):
        """Send message to MBU group"""
        group_name = settings.get_whatsapp_group_name(mbu)
        if group_name:
            priority = 1 if "csl" in alarm_type.lower() else 2
            self.queue_message(group_name, message, alarm_type, priority)
        else:
            logger.warning(f"No WhatsApp group configured for MBU: {mbu}")
    
    def send_to_b2s_group(self, company: str, message: str, alarm_type: str):
        """Send message to B2S group"""
        group_name = settings.get_b2s_group_name(company)
        if group_name:
            self.queue_message(group_name, message, alarm_type, priority=2)
        else:
            logger.warning(f"No WhatsApp group configured for B2S: {company}")
    
    def send_to_omo_group(self, company: str, message: str, alarm_type: str):
        """Send message to OMO group"""
        group_name = settings.get_omo_group_name(company)
        if group_name:
            self.queue_message(group_name, message, alarm_type, priority=2)
        else:
            logger.warning(f"No WhatsApp group configured for OMO: {company}")
    
    def get_queue_size(self) -> int:
        """Get number of messages in queue"""
        return self.message_queue.qsize()
    
    def clear_queue(self):
        """Clear the message queue"""
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except:
                break
        logger.info("Message queue cleared")
    
    def get_stats(self) -> Dict:
        """Get sending statistics"""
        return {
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "queue_size": self.get_queue_size(),
            "last_message_time": self.last_message_time,
            "status": self.status.value
        }


class WhatsAppMessageFormatter:
    """
    Formats alarm messages for WhatsApp according to specific formats
    """
    
    @staticmethod
    def format_mbu_alarms(alarms: List, alarm_type: str) -> str:
        """
        Format alarms for MBU group
        
        Formats:
        - CSL Fault: CSL Fault\t12-24-2025 02:42:05\tRUR5677__S_Padri
        - RF Unit: RF Unit Maintenance Link Failure\t12-23-2025 23:53:46\tLTE_LHR9239__S_BhogiwalGridStation
        - Other: Low Voltage\t12-23-2025 07:47:26\tLTE_LHR6626__S_ChananDinHospital
        - Cell Unavailable: Cell Unavailable\t12-23-2025 23:54:23\teNodeB Function Name=LTE_LHR9239__S_BhogiwalGridStation...
        """
        if not alarms:
            return ""
        
        # Format alarms exactly as they appear in portal export
        lines = []
        for alarm in alarms:
            # Use the exact format from portal export: AlarmType Timestamp SiteName
            line = f"{alarm.alarm_type}\t{alarm.timestamp_str}\t{alarm.site_name}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_toggle_alarms(alarms: List) -> str:
        """
        Format toggle alarms for MBU group
        
        Format:
        Toggle alarm    Major    Low Voltage    12-11-2025 03:32:09    LTE_LHR6931__S_BostanColony
        """
        if not alarms:
            return ""
        
        # Format toggle alarms exactly as they appear in portal export
        lines = []
        for alarm in alarms:
            # Use the exact format: Toggle alarm Severity AlarmType Timestamp SiteName
            line = f"Toggle alarm\t{alarm.severity}\t{alarm.alarm_type}\t{alarm.timestamp_str}\t{alarm.site_name}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_b2s_alarms(alarms: List) -> str:
        """
        Format alarms for B2S/OMO group
        
        Formats:
        - CSL: C1-LHR-03\tCSL Fault      RUR5677__S_Padri      12-24-2025 02:42:05      EC1-LHR-02599
        - RF Unit: C1-LHR-04\tLHR70\tRF Unit Maintenance Link Failure      LHR9239__S_BhogiwalGridStation      12-23-2025 23:53:46      ATLHR142
        - Other: C1-LHR-05\tLHR122\tLow Voltage      LHR6626__S_ChananDinHospital      12-23-2025 07:47:26      e.coPK015545PU
        - Cell Unavailable: Cell Unavailable\t12-23-2025 23:54:23     LHR9239__S_BhogiwalGridStation     C1-LHR-04     ATLHR142
        """
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
            mbu = alarm.mbu or ""
            ring_id = alarm.ftts_ring_id or "#N/A"
            b2s_id = alarm.b2s_id or ""
            
            # Format B2S alarms exactly as specified: MBU AlarmType SiteName Timestamp B2S_ID
            line = f"{mbu}\t{alarm.alarm_type}\t{alarm.site_name}\t{alarm.timestamp_str}\t{b2s_id}"

            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_omo_alarms(alarms: List) -> str:
        """Format alarms for OMO group (same as B2S)"""
        return WhatsAppMessageFormatter.format_b2s_alarms(alarms)
    
    @staticmethod
    def format_csl_fault(alarms: List) -> str:
        """
        Format CSL Fault alarms
        
        Format:
        CSL Fault    12-11-2025 02:43:32    LHR9147__S_RajputPark
        """
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
            line = f"{alarm.alarm_type}\t{alarm.timestamp_str}\t{alarm.site_name}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_rf_unit(alarms: List) -> str:
        """
        Format RF Unit alarms
        
        Format:
        RF Unit Maintenance Link Failure    RUR5269__S_KarolpindLHR_CMPak7437    12-10-2025 21:51:38    7437
        """
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
            b2s_id = alarm.b2s_id or ""
            line = f"{alarm.alarm_type}\t{alarm.site_name}\t{alarm.timestamp_str}\t{b2s_id}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_cell_unavailable(alarms: List) -> str:
        """
        Format Cell Unavailable alarms
        
        Includes full eNodeB information
        """
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
            # Use raw data which contains full eNodeB info
            if alarm.cell_info:
                line = f"{alarm.alarm_type}\t{alarm.timestamp_str}\t{alarm.raw_data}"
            else:
                line = f"{alarm.alarm_type}\t{alarm.timestamp_str}\t{alarm.site_name}"
            lines.append(line)
        
        return '\n'.join(lines)


# Global instance
whatsapp_handler = WhatsAppHandler()
message_formatter = WhatsAppMessageFormatter()


# Integration function for alarm scheduler
def send_alarms_to_whatsapp(group_name: str, message: str, alarm_type: str):
    """
    Callback function for alarm scheduler to send messages
    
    Args:
        group_name: WhatsApp group name
        message: Formatted message
        alarm_type: Type of alarm
    """
    if not message.strip():
        return
    
    priority = 1 if "csl" in alarm_type.lower() else 2
    whatsapp_handler.queue_message(group_name, message, alarm_type, priority)