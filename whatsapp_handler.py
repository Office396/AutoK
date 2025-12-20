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
        """Get the browser driver"""
        return browser_manager.get_driver()
    
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
            return None
        
        selectors = self.SELECTORS.get(selector_key, [])
        
        for by, value in selectors:
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((by, value))
                )
                return element
            except TimeoutException:
                continue
            except Exception:
                continue
        
        return None
    
    def check_connection(self) -> WhatsAppStatus:
        """Check WhatsApp connection status - improved detection"""
        try:
            driver = self._get_driver()
            if not driver:
                self._notify_status(WhatsAppStatus.DISCONNECTED)
                return WhatsAppStatus.DISCONNECTED
            
            # Switch to WhatsApp tab
            browser_manager.switch_to_tab(TabType.WHATSAPP)
            time.sleep(0.5)
            
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
            
            # Switch to WhatsApp tab
            browser_manager.switch_to_tab(TabType.WHATSAPP)
            time.sleep(0.5)
            
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
    
    def _verify_current_chat(self, expected_name: str) -> bool:
        """Verify we're in the correct chat"""
        try:
            driver = self._get_driver()
            
            # Find chat header
            header = driver.find_element(By.CSS_SELECTOR, 'header span[dir="auto"]')
            current_name = header.text or header.get_attribute('title') or ""
            
            # Case-insensitive partial match
            return (expected_name.lower() in current_name.lower() or 
                    current_name.lower() in expected_name.lower())
            
        except:
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
            self._notify_status(WhatsAppStatus.SENDING)
            
            driver = self._get_driver()
            if not driver:
                return SendResult(
                    success=False,
                    group_name=group_name,
                    message_preview=message[:50],
                    error="Browser not available"
                )
            
            # Switch to WhatsApp tab
            browser_manager.switch_to_tab(TabType.WHATSAPP)
            time.sleep(0.5)
            
            # Search and select group
            if not self.search_group(group_name):
                return SendResult(
                    success=False,
                    group_name=group_name,
                    message_preview=message[:50],
                    error=f"Group not found: {group_name}"
                )
            
            # Find message input
            message_input = self._find_clickable_element('message_input', timeout=10)
            if not message_input:
                return SendResult(
                    success=False,
                    group_name=group_name,
                    message_preview=message[:50],
                    error="Could not find message input"
                )
            
            # Click on message input
            message_input.click()
            time.sleep(0.3)
            
            # Send message (handle multi-line)
            self._type_message(message_input, message)
            
            # Click send button or press Enter
            if not self._click_send():
                # Try pressing Enter
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
            logger.success(f"Message sent to {group_name}")
            
            return result
            
        except Exception as e:
            self.messages_failed += 1
            self._notify_status(WhatsAppStatus.ERROR)
            
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
        logger.info(f"Queued message for {group_name} (priority: {priority})")
    
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
    Formats alarm messages for WhatsApp
    """
    
    @staticmethod
    def format_mbu_alarms(alarms: List, alarm_type: str) -> str:
        """
        Format alarms for MBU group
        
        Format:
        Low Voltage    12-11-2025 05:20:03    LTE_LHR1459__S_Eden_Value_Homes
        """
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
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
        
        lines = []
        for alarm in alarms:
            line = f"Toggle alarm\t{alarm.severity}\t{alarm.alarm_type}\t{alarm.timestamp_str}\t{alarm.site_name}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_b2s_alarms(alarms: List) -> str:
        """
        Format alarms for B2S group
        
        Format:
        C1-LHR-04    LHR60    CSL Fault    LHR9147__S_RajputPark    12-11-2025 02:43:32    e.coPK000506PU
        """
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
            mbu = alarm.mbu or ""
            ring_id = alarm.ftts_ring_id or "#N/A"
            b2s_id = alarm.b2s_id or ""
            
            line = f"{mbu}\t{ring_id}\t{alarm.alarm_type}\t{alarm.site_name}\t{alarm.timestamp_str}\t{b2s_id}"
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