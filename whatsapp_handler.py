"""
WhatsApp Handler
Manages WhatsApp Web automation for sending alarm messages
Optimized for speed with cached chat list and efficient group finding
"""

import time
import threading
import queue
import pyperclip
from datetime import datetime
from typing import Optional, Callable, List, Dict, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    StaleElementReferenceException,
    ElementNotInteractableException
)

from config import settings
from logger_module import logger


class WhatsAppStatus(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    QR_REQUIRED = "QR Code Required"
    CONNECTED = "Connected"
    SENDING = "Sending Message"
    ERROR = "Error"


@dataclass
class MessageResult:
    success: bool
    group_name: str
    message: str = ""
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    alarm_type: str = ""


@dataclass(order=True)
class QueuedMessage:
    sort_index: int = field(init=False, repr=False)
    group_name: str = field(compare=False)
    message: str = field(compare=False)
    alarm_type: str = field(compare=False)
    priority: int = field(default=1, compare=False)
    timestamp: datetime = field(default_factory=datetime.now, compare=False)
    sequence: int = field(default=0, compare=False)
    
    def __post_init__(self):
        self.sort_index = self.priority * 1000000000 + self.sequence


class WhatsAppMessageFormatter:
    """Formats alarm messages for WhatsApp using customizable templates"""
    
    @staticmethod
    def _format_alarm(alarm, template: str) -> str:
        """Format a single alarm using a template"""
        data = {
            "alarm_type": getattr(alarm, 'alarm_type', '') or '',
            "timestamp": getattr(alarm, 'timestamp_str', '') or '',
            "site_name": getattr(alarm, 'site_name', '') or getattr(alarm, 'site_code', '') or '',
            "site_code": getattr(alarm, 'site_code', '') or '',
            "severity": getattr(alarm, 'severity', 'Major') or 'Major',
            "mbu": getattr(alarm, 'mbu', '') or '',
            "ring_id": getattr(alarm, 'ftts_ring_id', '') or '#N/A',
            "b2s_id": getattr(alarm, 'b2s_id', '') or '',
        }
        
        try:
            # Replace escaped \t if present in template from GUI
            fmt_template = template.replace("\\t", "\t")
            formatted = fmt_template.format(**data)
            # WhatsApp doesn't support tabs well, replace with spaces for alignment
            return formatted.replace("\t", "    ")
        except KeyError as e:
            logger.warning(f"Unknown placeholder in template: {e}")
            # Fallback to basic format without tabs
            return f"{data['alarm_type']}    {data['timestamp']}    {data['site_name']}"
    
    @staticmethod
    def format_mbu_alarms(alarms: List, alarm_type: str) -> str:
        if not alarms:
            return ""
        
        template = settings.message_formats.mbu_format
        lines = []
        for alarm in alarms:
            line = WhatsAppMessageFormatter._format_alarm(alarm, template)
            if line.strip():
                lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_toggle_alarms(alarms: List) -> str:
        if not alarms:
            return ""
        
        template = settings.message_formats.toggle_format
        lines = []
        for alarm in alarms:
            line = WhatsAppMessageFormatter._format_alarm(alarm, template)
            if line.strip():
                lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_b2s_alarms(alarms: List) -> str:
        if not alarms:
            return ""
        
        template = settings.message_formats.b2s_format
        lines = []
        for alarm in alarms:
            line = WhatsAppMessageFormatter._format_alarm(alarm, template)
            if line.strip():
                lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_omo_alarms(alarms: List) -> str:
        if not alarms:
            return ""
        
        template = settings.message_formats.omo_format
        lines = []
        for alarm in alarms:
            line = WhatsAppMessageFormatter._format_alarm(alarm, template)
            if line.strip():
                lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_csl_fault(alarms: List) -> str:
        return WhatsAppMessageFormatter.format_mbu_alarms(alarms, "CSL Fault")


message_formatter = WhatsAppMessageFormatter()


class CachedChatList:
    """Cached WhatsApp chat list for fast group finding"""
    
    def __init__(self):
        self.chats: Dict[str, object] = {}
        self.last_refresh: Optional[datetime] = None
        self.refresh_interval = 60
        self.lock = threading.Lock()
    
    def needs_refresh(self) -> bool:
        if self.last_refresh is None:
            return True
        elapsed = (datetime.now() - self.last_refresh).total_seconds()
        return elapsed > self.refresh_interval
    
    def refresh(self, driver: webdriver.Chrome) -> bool:
        try:
            with self.lock:
                self.chats.clear()
                
                chat_list_selectors = [
                    '[aria-label="Chat list"][role="grid"]',
                    '[aria-label="Chat list"]',
                    '#pane-side',
                    'div[data-testid="chat-list"]',
                ]
                
                chat_list = None
                for selector in chat_list_selectors:
                    try:
                        chat_list = driver.find_element(By.CSS_SELECTOR, selector)
                        if chat_list:
                            break
                    except:
                        continue
                
                if not chat_list:
                    logger.error("Could not find chat list for caching")
                    return False
                
                row_selectors = [
                    '[data-testid="cell-frame-container"]',
                    'div[role="row"]',
                    'div[role="listitem"]',
                    'div[data-testid="chat-list-item"]',
                ]
                
                rows = []
                for selector in row_selectors:
                    try:
                        rows = chat_list.find_elements(By.CSS_SELECTOR, selector)
                        if rows:
                            break
                    except:
                        continue
                
                for row in rows:
                    try:
                        title_selectors = [
                            'span[title]',
                            'span[dir="auto"]',
                            '[data-testid="cell-frame-title"] span',
                        ]
                        
                        for sel in title_selectors:
                            try:
                                title_elem = row.find_element(By.CSS_SELECTOR, sel)
                                title = title_elem.get_attribute('title') or title_elem.text
                                if title:
                                    self.chats[title.strip()] = row
                                    break
                            except:
                                continue
                    except:
                        continue
                
                self.last_refresh = datetime.now()
                logger.info(f"Cached {len(self.chats)} chats")
                return True
                
        except Exception as e:
            logger.error(f"Error refreshing chat cache: {e}")
            return False
    
    def get_chat_element(self, group_name: str) -> Optional[object]:
        with self.lock:
            for cached_name, element in self.chats.items():
                if cached_name == group_name:
                    return element
                if cached_name.lower() == group_name.lower():
                    return element
            return None
    
    def get_all_group_names(self) -> List[str]:
        with self.lock:
            return list(self.chats.keys())


class WhatsAppHandler:
    """
    WhatsApp Web handler with optimized message sending
    """
    
    def __init__(self):
        self.status = WhatsAppStatus.DISCONNECTED
        self.message_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.sending_active = False
        self.sender_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        self._status_callbacks: List[Callable] = []
        self._message_sent_callbacks: List[Callable] = []
        self._popup_callback: Optional[Callable] = None
        
        self._messages_sent = 0
        self._last_message_time: Optional[datetime] = None
        self._message_sequence = 0
        
        self.chat_cache = CachedChatList()
        self.chat_cache = CachedChatList()
        self._driver: Optional[webdriver.Chrome] = None
        self._current_chat_name: Optional[str] = None  # Cache currently open chat
        self._current_message: Optional[QueuedMessage] = None
        from collections import deque
        self._recent_sent = deque(maxlen=50)
    
    def set_popup_callback(self, callback: Callable):
        """Set callback for showing error popups"""
        self._popup_callback = callback

    def _show_error_popup(self, title: str, message: str):
        """Trigger error popup via callback and WAIT for user to click OK"""
        if self._popup_callback:
            wait_event = threading.Event()
            self._popup_callback(title, message, wait_event)
            logger.info(f"Waiting for user to acknowledge error: {title}")
            wait_event.wait() # Block the sender thread until OK is clicked
            logger.info("Error acknowledged, continuing...")
    
    def set_driver(self, driver: webdriver.Chrome):
        self._driver = driver
    
    def get_driver(self) -> Optional[webdriver.Chrome]:
        if self._driver:
            return self._driver
        try:
            from browser_manager import browser_manager
            return browser_manager.whatsapp_driver
        except:
            return None
    
    def add_status_callback(self, callback: Callable):
        self._status_callbacks.append(callback)
    
    def add_message_sent_callback(self, callback: Callable):
        self._message_sent_callbacks.append(callback)
    
    def _notify_status(self, status: WhatsAppStatus):
        self.status = status
        for callback in self._status_callbacks:
            try:
                callback(status)
            except:
                pass
    
    def _notify_message_sent(self, result: MessageResult):
        for callback in self._message_sent_callbacks:
            try:
                callback(result)
            except:
                pass
    
    def check_connection(self) -> WhatsAppStatus:
        driver = self.get_driver()
        if not driver:
            self._notify_status(WhatsAppStatus.DISCONNECTED)
            return WhatsAppStatus.DISCONNECTED
        
        try:
            # First ensure we're on the right page
            current_url = driver.current_url
            if 'web.whatsapp.com' not in current_url:
                self._notify_status(WhatsAppStatus.DISCONNECTED)
                return WhatsAppStatus.DISCONNECTED
            
            # Wait a moment for page to stabilize
            time.sleep(1)
            
            # 1. Check for logged in indicators FIRST (most reliable)
            logged_in_selectors = [
                '#pane-side',
                '[data-testid="chat-list"]',
                'div[aria-label="Chat list"]',
                'div[aria-label="Chats"]',
                '[data-testid="menu-bar-menu"]',
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        logger.info(f"WhatsApp connected - found: {selector}")
                        self._notify_status(WhatsAppStatus.CONNECTED)
                        return WhatsAppStatus.CONNECTED
                except:
                    continue

            # 2. Check for QR code (if no login indicator found)
            qr_selectors = [
                '[data-testid="qrcode"]',
                'canvas[aria-label*="Scan"]',
                'canvas[aria-label*="QR"]',
                'div[data-ref]',  # QR code container
            ]
            
            for selector in qr_selectors:
                try:
                    qr = driver.find_element(By.CSS_SELECTOR, selector)
                    if qr and qr.is_displayed():
                        logger.info(f"WhatsApp QR code visible - found: {selector}")
                        self._notify_status(WhatsAppStatus.QR_REQUIRED)
                        return WhatsAppStatus.QR_REQUIRED
                except:
                    continue
            
            # 3. Check page content for loading/connecting state
            try:
                page_source = driver.page_source.lower()
                if "loading" in page_source or "connecting" in page_source:
                    self._notify_status(WhatsAppStatus.CONNECTING)
                    return WhatsAppStatus.CONNECTING
            except:
                pass

            # 4. If nothing found, keep current status or assume connecting
            logger.warning("WhatsApp status unclear - page may be loading")
            return self.status
              
        except Exception as e:
            logger.error(f"Error checking WhatsApp connection: {e}")
            return self.status
    
    def refresh_chat_cache(self) -> bool:
        driver = self.get_driver()
        if not driver:
            return False
        return self.chat_cache.refresh(driver)
    
    def queue_message(self, group_name: str, message: str, alarm_type: str, priority: int = 1):
        if not message.strip():
            logger.warning(f"Attempted to queue empty message for {group_name}")
            return
        
        # PERFORMANCE: Get sequence number with minimal lock time
        with self.lock:
            self._message_sequence += 1
            seq = self._message_sequence
        
        queued = QueuedMessage(
            group_name=group_name,
            message=message,
            alarm_type=alarm_type,
            priority=priority,
            sequence=seq
        )
        
        self.message_queue.put(queued)
        logger.info(f"Queued message for {group_name}: {alarm_type} (priority {priority})")
    
    def start_sender(self):
        if self.sender_thread and self.sender_thread.is_alive():
            return
        
        self.sending_active = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()
        logger.info("WhatsApp message sender started")
    
    def stop_sender(self):
        self.sending_active = False
        if self.sender_thread:
            self.sender_thread.join(timeout=5)
        logger.info("WhatsApp message sender stopped")
    
    def _sender_loop(self):
        while self.sending_active:
            try:
                try:
                    queued = self.message_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                self._current_message = queued
                result = self.send_message(queued.group_name, queued.message)
                result.alarm_type = queued.alarm_type
                self._notify_message_sent(result)
                
                if result.success:
                    self._messages_sent += 1
                    self._last_message_time = datetime.now()
                
                try:
                    self._recent_sent.append({
                        'group_name': queued.group_name,
                        'alarm_type': queued.alarm_type,
                        'success': result.success,
                        'timestamp': result.timestamp
                    })
                except:
                    pass
                
                self._current_message = None
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Sender loop error: {e}")
                time.sleep(2)
    
    def _keep_alive(self):
        """No-op keep-alive"""
        pass

    def send_message(self, group_name: str, message: str, retry_count: int = 3) -> MessageResult:
        driver = self.get_driver()
        if not driver:
            return MessageResult(success=False, group_name=group_name, error="No WhatsApp driver")
        
        logger.info(f"Attempting to send message to: {group_name}")
        self._notify_status(WhatsAppStatus.SENDING)
        
        # PERFORMANCE: Track message sending time
        with logger.performance_track("WhatsApp_Send"):
            return self._send_message_impl(driver, group_name, message, retry_count)
    
    def _send_message_impl(self, driver, group_name: str, message: str, retry_count: int) -> MessageResult:
        """Internal message sending implementation"""
        
        for attempt in range(retry_count):
            try:
                # 1. OPTIMIZATION: Check if already in the correct group
                already_open = False
                if self._current_chat_name == group_name:
                    if self._verify_chat_opened(driver, group_name):
                        logger.info(f"Group '{group_name}' is already open, skipping search")
                        already_open = True
                    else:
                        self._current_chat_name = None # Reset if verification fails
                
                if not already_open:
                    if not self._find_and_open_group(driver, group_name):
                        logger.warning(f"Group '{group_name}' not found (Attempt {attempt + 1})")
                        if attempt < retry_count - 1:
                            time.sleep(0.3)  # Reduced from 0.5s
                            continue
                        
                        # ALERT on group not found
                        self._show_error_popup(
                            "Group Not Found", 
                            f"Could not find group '{group_name}' in WhatsApp chat list.\nPlease ensure the group exists and is visible."
                        )
                        return MessageResult(success=False, group_name=group_name, error="Group not found")
                    
                    # Update current chat cache
                    self._current_chat_name = group_name
                    # Wait for chat to stabilize after opening
                    time.sleep(0.3)  # Reduced from 1.5s total
                
                # 2. Find input box with smart wait
                input_box = self._find_clickable_element(driver, "message_input", timeout=10)
                if not input_box:
                    if attempt < retry_count - 1:
                        time.sleep(0.5)  # Reduced from 1s
                        continue
                    
                    # ALERT on input not found
                    self._show_error_popup(
                        "Interface Error", 
                        f"Could not find message input box in group '{group_name}'.\nWhatsApp Web might be lagging or layout has changed."
                    )
                    return MessageResult(success=False, group_name=group_name, error="Input box not found")
                
                # 3. INSTANT PASTE logic
                input_box.click()
                time.sleep(0.15)  # Reduced from 0.2s
                
                # determine sending method
                method = settings.whatsapp_sending_method
                
                if method == "Clipboard":
                    # 3a. CLIPBOARD METHOD
                    try:
                        pyperclip.copy(message)
                        input_box.send_keys(Keys.CONTROL + 'v')
                        time.sleep(0.3)  # Reduced from 0.5s
                    except Exception as clip_e:
                        logger.error(f"Clipboard method failed, falling back to JavaScript: {clip_e}")
                        method = "JavaScript"
                
                if method == "JavaScript":
                    # 3b. JAVASCRIPT METHOD: Simulate Paste Event (No OS Clipboard)
                    # This preserves newlines correctly unlike insertText
                    try:
                        driver.execute_script("""
                            var text = arguments[0];
                            var input = arguments[1];
                            input.focus();
                            
                            // Create a fake paste event
                            var dataTransfer = new DataTransfer();
                            dataTransfer.setData('text/plain', text);
                            
                            var event = new ClipboardEvent('paste', {
                                clipboardData: dataTransfer,
                                bubbles: true,
                                cancelable: true
                            });
                            
                            input.dispatchEvent(event);
                        """, message, input_box)
                    except Exception as js_e:
                        logger.warning(f"JS Paste failed, falling back to send_keys: {js_e}")
                        # Fallback: Split by newline and use Shift+Enter
                        parts = message.split('\n')
                        for i, part in enumerate(parts):
                            input_box.send_keys(part)
                            if i < len(parts) - 1:
                                input_box.send_keys(Keys.SHIFT + Keys.ENTER)
                
                time.sleep(0.3)  # Reduced from 0.5s - Wait for input to register
                
                # 4. Send
                input_box.send_keys(Keys.ENTER)
                time.sleep(0.3)  # Reduced from 0.5s
                
                self._notify_status(WhatsAppStatus.CONNECTED)
                logger.success(f"Message sent successfully to {group_name}")
                return MessageResult(success=True, group_name=group_name, message=message)
                
            except Exception as e:
                logger.error(f"Error sending to {group_name}: {e}")
                if attempt < retry_count - 1:
                    time.sleep(0.5)  # Reduced from 1s
                    continue
                
                # ALERT on crash/error
                self._show_error_popup(
                    "Sending Failed", 
                    f"An error occurred while sending to '{group_name}':\n{str(e)}"
                )
                self._notify_status(WhatsAppStatus.ERROR)
                return MessageResult(success=False, group_name=group_name, error=str(e))
        
        return MessageResult(success=False, group_name=group_name, error="Max retries exceeded")

    
    def _find_and_open_group(self, driver: webdriver.Chrome, group_name: str) -> bool:
        logger.debug(f" find_and_open_group_direct: Refreshing chat list before search")
        
        if self.chat_cache.needs_refresh():
            self.chat_cache.refresh(driver)
        
        logger.debug(f" find_and_open_group_direct: Looking for group '{group_name}'")
        
        cached_element = self.chat_cache.get_chat_element(group_name)
        if cached_element:
            try:
                logger.debug(f": Found group in cache, clicking...")
                ActionChains(driver).move_to_element(cached_element).click().perform()
                time.sleep(0.5)  # Reduced from 1s
                
                if self._verify_chat_opened(driver, group_name):
                    return True
            except StaleElementReferenceException:
                logger.info("Cached element stale, refreshing cache...")
                self.chat_cache.refresh(driver)
        
        chat_list_selectors = [
            '[aria-label="Chat list"][role="grid"]',
            '[aria-label="Chat list"]',
            '#pane-side',
        ]
        
        chat_list = None
        for selector in chat_list_selectors:
            try:
                chat_list = driver.find_element(By.CSS_SELECTOR, selector)
                if chat_list:
                    logger.debug(f": Found chat list with selector: {selector}")
                    break
            except:
                continue
        
        if not chat_list:
            logger.error("Could not find chat list")
            return False
        
        row_selectors = [
            '[data-testid="cell-frame-container"]',
            'div[role="row"]',
            'div[role="listitem"]',
        ]
        
        rows = []
        for selector in row_selectors:
            try:
                rows = chat_list.find_elements(By.CSS_SELECTOR, selector)
                if rows:
                    break
            except:
                continue
        
        logger.debug(f": Found {len(rows)} chat rows to search through")
        
        for row in rows:
            try:
                title_selectors = [
                    'span[title]',
                    'span[dir="auto"]',
                    '[data-testid="cell-frame-title"] span',
                ]
                
                chat_title = None
                for sel in title_selectors:
                    try:
                        title_elem = row.find_element(By.CSS_SELECTOR, sel)
                        chat_title = title_elem.get_attribute('title') or title_elem.text
                        if chat_title:
                            break
                    except:
                        continue
                
                if not chat_title:
                    continue
                
                logger.debug(f": Found chat title: '{chat_title}'")
                
                if chat_title.strip() == group_name.strip():
                    logger.debug(f": Exact match found for '{group_name}'")
                    
                    logger.debug(f": Scrolling group '{group_name}' into view")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
                    time.sleep(0.3)  # Reduced from 0.5s
                    
                    logger.debug(f": Clicking on group '{group_name}'")
                    try:
                        ActionChains(driver).move_to_element(row).click().perform()
                        logger.debug(f": ActionChains click successful on '{group_name}'")
                    except:
                        row.click()
                    
                    
                    time.sleep(0.3)  # Reduced from 0.5s
                    
                    logger.debug(f": Waiting for chat '{group_name}' to load...")
                    
                    # More aggressive verification with shorter sleep
                    for attempt in range(10): # More attempts, shorter interval
                        if self._verify_chat_opened(driver, group_name):
                            logger.success(f"Successfully opened group: {group_name}")
                            return True
                        time.sleep(0.3)  # Reduced from 0.5s
                    
                    for chat in self.chat_cache.get_all_group_names()[:5]:
                        logger.debug(f": Found chat title: '{chat}'")
                    
                    logger.warning(f"Opened wrong chat. Expected: '{group_name}', Got: different chat")
                    logger.debug(f": Trying one more click on the group...")
                    logger.warning("Chat verification failed after 5 attempts")
                    break
                    
            except Exception as e:
                continue
        
        logger.warning(f"Group '{group_name}' not found in chat list")
        return False
    
    def _verify_chat_opened(self, driver: webdriver.Chrome, expected_group: str) -> bool:
        try:
            header_selectors = [
                'header [dir="auto"]',
                'header span[title]',
                '#main header span',
                '[data-testid="conversation-info-header"] span',
            ]
            
            for selector in header_selectors:
                try:
                    header = driver.find_element(By.CSS_SELECTOR, selector)
                    chat_name = header.get_attribute('title') or header.text
                    if chat_name:
                        logger.debug(f": Found chat title with selector '{selector}': '{chat_name}'")
                        logger.debug(f": Verifying chat - Expected: '{expected_group}', Got: '{chat_name}'")
                        
                        if chat_name.strip() == expected_group.strip():
                            logger.debug(f": Chat verification PASSED")
                            return True
                        else:
                            logger.debug(f": Chat verification FAILED")
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying chat: {e}")
            return False
    
    def _find_clickable_element(self, driver: webdriver.Chrome, element_type: str, timeout: int = 15) -> Optional[object]:
        logger.debug(f" _find_clickable_element: Finding {element_type}")
        
        selectors = {
            "message_input": [
                'div[contenteditable="true"][data-tab="10"]',
                'div[contenteditable="true"][title="Type a message"]',
                'footer div[contenteditable="true"]',
                '[data-testid="conversation-compose-box-input"]',
            ],
            "send_button": [
                'button[aria-label="Send"]',
                '[data-testid="send"]',
                'span[data-icon="send"]',
            ]
        }
        
        element_selectors = selectors.get(element_type, [])
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            for selector in element_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        logger.debug(f" _find_clickable_element: Found {element_type} with {selector}")
                        return element
                except:
                    continue
            time.sleep(0.5)
        
        logger.error(f"DEBUG _find_clickable_element: Could not find {element_type} after {timeout}s")
        return None
    
    def get_stats(self) -> Dict:
        return {
            'status': self.status.value,
            'messages_sent': self._messages_sent,
            'queue_size': self.message_queue.qsize(),
            'last_message_time': self._last_message_time.isoformat() if self._last_message_time else None,
            'cached_chats': len(self.chat_cache.chats)
        }

    def get_detailed_stats(self) -> Dict:
        try:
            current = None
            if self._current_message:
                current = {
                    'group_name': self._current_message.group_name,
                    'alarm_type': self._current_message.alarm_type,
                    'priority': self._current_message.priority,
                    'queued_at': self._current_message.timestamp.isoformat()
                }
            
            try:
                queue_items = list(self.message_queue.queue)
                queue_preview = []
                for qm in sorted(queue_items, key=lambda x: x.sort_index)[:10]:
                    queue_preview.append({
                        'group_name': qm.group_name,
                        'alarm_type': qm.alarm_type,
                        'priority': qm.priority,
                        'queued_at': qm.timestamp.isoformat()
                    })
            except:
                queue_preview = []
            
            sent_preview = []
            try:
                for item in list(self._recent_sent)[-10:]:
                    sent_preview.append({
                        'group_name': item.get('group_name'),
                        'alarm_type': item.get('alarm_type'),
                        'success': item.get('success'),
                        'timestamp': item.get('timestamp').isoformat() if item.get('timestamp') else None
                    })
            except:
                pass
            
            base = self.get_stats()
            base.update({
                'current': current,
                'queue_preview': queue_preview,
                'sent_recent': sent_preview
            })
            return base
        except Exception as e:
            logger.error(f"Error building detailed stats: {e}")
            return self.get_stats()


whatsapp_handler = WhatsAppHandler()


def send_alarms_to_whatsapp(group_name: str, message: str, alarm_type: str):
    whatsapp_handler.queue_message(group_name, message, alarm_type)


class OrderedAlarmSender:
    """
    Sends alarms in the strict user-specified order:
    Outer loop: Groups (MBU 1-8 -> B2S -> OMO)
    Inner loop: Alarm Types (CSL -> RF Unit -> AC Main -> Battery Temp -> Genset -> Low Voltage -> System on Battery -> Toggle -> Cell Unavailable)
    """
    
    ALARM_TYPE_ORDER = [
        "CSL Fault",
        "RF Unit Maintenance Link Failure",
        "AC Main Failure",
        "Battery High Temp",
        "Genset Running",
        "Low Voltage",
        "System on Battery",
        "Toggle",
        "Cell Unavailable"
    ]
    
    @classmethod
    def get_ordered_batches(cls, alarms: List) -> List[Tuple[str, str, List, bool, str]]:
        from alarm_processor import alarm_processor
        
        batches = []
        
        # Read group mappings dynamically at runtime (not at import time!)
        mbu_order = list(settings.mbu_groups.mapping.keys())
        b2s_order = list(settings.b2s_groups.mapping.keys())
        omo_order = list(settings.omo_groups.mapping.keys())
        
        all_groups = []
        for mbu in mbu_order:
            all_groups.append(('MBU', mbu))
        for b2s in b2s_order:
            all_groups.append(('B2S', b2s))
        for omo in omo_order:
            all_groups.append(('OMO', omo))
        
        extended_order = list(cls.ALARM_TYPE_ORDER)
        known_types_lower = {t.lower() for t in cls.ALARM_TYPE_ORDER}
        
        all_alarm_types = set()
        for a in alarms:
            if hasattr(a, 'alarm_type') and a.alarm_type:
                all_alarm_types.add(a.alarm_type)
        
        for atype in sorted(all_alarm_types):
            if atype.lower() not in known_types_lower:
                extended_order.append(atype)
            
        for group_type, group_id in all_groups:
            for alarm_type in extended_order:
                is_toggle = alarm_type == "Toggle"
                
                group_alarms = []
                for a in alarms:
                    if is_toggle:
                        if not getattr(a, 'is_toggle', False): continue
                    else:
                        # Case-insensitive comparison for alarm types
                        current_type = getattr(a, 'alarm_type', '')
                        if current_type.lower() != alarm_type.lower() or getattr(a, 'is_toggle', False): continue
                    
                    # Match alarm to group based on its properties
                    if group_type == 'MBU':
                        if getattr(a, 'mbu', '') == group_id:
                            group_alarms.append(a)
                    elif group_type == 'B2S':
                        if getattr(a, 'is_b2s', False) and getattr(a, 'b2s_company', '') == group_id:
                            group_alarms.append(a)
                    elif group_type == 'OMO':
                        if getattr(a, 'is_omo', False) and getattr(a, 'omo_company', '') == group_id:
                            group_alarms.append(a)

                if not group_alarms:
                    continue
                
                whatsapp_group = ""
                if group_type == 'MBU':
                    whatsapp_group = settings.get_whatsapp_group_name(group_id)
                    if is_toggle and alarm_processor.should_skip_toggle_for_mbu(group_id):
                        continue
                elif group_type == 'B2S':
                    whatsapp_group = settings.get_b2s_group_name(group_id)
                elif group_type == 'OMO':
                    whatsapp_group = settings.get_omo_group_name(group_id)
                
                # Check send control: skip if disabled for this group/alarm
                from config import settings as _settings
                if _settings.is_alarm_disabled(group_type, group_id, alarm_type):
                    logger.info(f"Skipping disabled alarm: {alarm_type} for {group_type} {group_id}")
                    continue
                
                if whatsapp_group:
                    batches.append((whatsapp_group, alarm_type, group_alarms, is_toggle, group_type))
        
        return batches
    
    @classmethod
    def send_all_ordered(cls, alarms: List, mbu_only: bool = False):
        if not alarms:
            return
            
        # We NO LONGER deduplicate here because the user wants multiple entries if they appear in terminal.
        # The alarm_processor already handles stability across refreshes using row indices.
        # If we get multiple alarms here, they are intended to be sent.
        
        batches = cls.get_ordered_batches(alarms)
        
        for i, (group_name, alarm_type, batch_alarms, is_toggle, group_type) in enumerate(batches):
            # If mbu_only is True, skip non-MBU groups
            if mbu_only and group_type != 'MBU':
                continue
                
            if is_toggle:
                message = message_formatter.format_toggle_alarms(batch_alarms)
            elif group_type == 'B2S':
                message = message_formatter.format_b2s_alarms(batch_alarms)
            elif group_type == 'OMO':
                message = message_formatter.format_omo_alarms(batch_alarms)
            else:
                # Default to MBU format for MBU groups
                message = message_formatter.format_mbu_alarms(batch_alarms, alarm_type)
            
            if message.strip():
                # Priority: 1 for instant alarms (like CSL), 2 for others. 
                # We check if the alarm type is in the configured instant alarms list
                is_instant = False
                try:
                    instant_types = [t.strip().lower() for t in settings.instant_alarms]
                    if alarm_type.lower() in instant_types:
                        is_instant = True
                except:
                    # Fallback if settings not available or error
                    if "csl" in alarm_type.lower():
                        is_instant = True
                
                priority = 1 if is_instant else 2
                whatsapp_handler.queue_message(group_name, message, alarm_type, priority)
                logger.info(f"Ordered batch queued: {alarm_type} | Count: {len(batch_alarms)} | Group: {group_name}")


ordered_sender = OrderedAlarmSender()
