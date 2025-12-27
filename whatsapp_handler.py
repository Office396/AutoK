"""
WhatsApp Handler
Manages WhatsApp Web automation for sending alarm messages
Optimized for speed with cached chat list and efficient group finding
"""

import time
import threading
import queue
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


@dataclass
class QueuedMessage:
    group_name: str
    message: str
    alarm_type: str
    priority: int = 1
    timestamp: datetime = field(default_factory=datetime.now)


class WhatsAppMessageFormatter:
    """Formats alarm messages for WhatsApp"""
    
    @staticmethod
    def format_mbu_alarms(alarms: List, alarm_type: str) -> str:
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
            line = f"{alarm.alarm_type}\t{alarm.timestamp_str}\t{alarm.site_name}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_toggle_alarms(alarms: List) -> str:
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
            severity = getattr(alarm, 'severity', 'Major')
            line = f"Toggle alarm\t{severity}\t{alarm.alarm_type}\t{alarm.timestamp_str}\t{alarm.site_name}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_b2s_alarms(alarms: List) -> str:
        if not alarms:
            return ""
        
        lines = []
        for alarm in alarms:
            mbu = getattr(alarm, 'mbu', '') or ""
            ring_id = getattr(alarm, 'ftts_ring_id', '') or "#N/A"
            b2s_id = getattr(alarm, 'b2s_id', '') or ""
            
            line = f"{mbu}\t{ring_id}\t{alarm.alarm_type}\t{alarm.site_name}\t{alarm.timestamp_str}\t{b2s_id}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_omo_alarms(alarms: List) -> str:
        return WhatsAppMessageFormatter.format_b2s_alarms(alarms)
    
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
        
        self._messages_sent = 0
        self._last_message_time: Optional[datetime] = None
        
        self.chat_cache = CachedChatList()
        self._driver: Optional[webdriver.Chrome] = None
    
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
            logged_in_selectors = [
                '#pane-side',
                '[data-testid="chat-list"]',
                'div[aria-label="Chat list"]',
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        self._notify_status(WhatsAppStatus.CONNECTED)
                        return WhatsAppStatus.CONNECTED
                except:
                    continue
            
            qr_selectors = [
                '[data-testid="qrcode"]',
                'canvas[aria-label*="Scan"]',
            ]
            
            for selector in qr_selectors:
                try:
                    qr = driver.find_element(By.CSS_SELECTOR, selector)
                    if qr and qr.is_displayed():
                        self._notify_status(WhatsAppStatus.QR_REQUIRED)
                        return WhatsAppStatus.QR_REQUIRED
                except:
                    continue
            
            if 'web.whatsapp.com' in driver.current_url:
                self._notify_status(WhatsAppStatus.CONNECTED)
                return WhatsAppStatus.CONNECTED
            
            self._notify_status(WhatsAppStatus.DISCONNECTED)
            return WhatsAppStatus.DISCONNECTED
            
        except Exception as e:
            logger.error(f"Error checking WhatsApp connection: {e}")
            self._notify_status(WhatsAppStatus.ERROR)
            return WhatsAppStatus.ERROR
    
    def refresh_chat_cache(self) -> bool:
        driver = self.get_driver()
        if not driver:
            return False
        return self.chat_cache.refresh(driver)
    
    def queue_message(self, group_name: str, message: str, alarm_type: str, priority: int = 1):
        if not message.strip():
            logger.warning(f"Attempted to queue empty message for {group_name}")
            return
        
        queued = QueuedMessage(
            group_name=group_name,
            message=message,
            alarm_type=alarm_type,
            priority=priority
        )
        
        self.message_queue.put((priority, datetime.now().timestamp(), queued))
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
                    _, _, queued = self.message_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                result = self.send_message(queued.group_name, queued.message)
                self._notify_message_sent(result)
                
                if result.success:
                    self._messages_sent += 1
                    self._last_message_time = datetime.now()
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Sender loop error: {e}")
                time.sleep(2)
    
    def send_message(self, group_name: str, message: str, retry_count: int = 3) -> MessageResult:
        driver = self.get_driver()
        if not driver:
            return MessageResult(success=False, group_name=group_name, error="No WhatsApp driver")
        
        logger.info(f"Attempting to send message to: {group_name}")
        logger.info(f"DEBUG send_message: Entry point - group={group_name}, msg_len={len(message)}")
        
        self._notify_status(WhatsAppStatus.SENDING)
        
        for attempt in range(retry_count):
            try:
                logger.info(f"DEBUG send_message: Finding group {group_name}")
                if not self._find_and_open_group(driver, group_name):
                    if attempt < retry_count - 1:
                        logger.warning(f"Retrying message to {group_name} (attempt {attempt + 1}/{retry_count})")
                        time.sleep(2)
                        continue
                    return MessageResult(success=False, group_name=group_name, error="Group not found")
                
                logger.info(f"DEBUG send_message: Group opened, waiting for chat to load...")
                time.sleep(2)
                
                logger.info(f"DEBUG send_message: Finding message input")
                input_box = self._find_clickable_element(driver, "message_input")
                if not input_box:
                    logger.error("DEBUG send_message: Message input not found")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                        continue
                    return MessageResult(success=False, group_name=group_name, error="Message input not found")
                
                logger.info(f"DEBUG send_message: Clicking message input")
                input_box.click()
                time.sleep(0.3)
                
                logger.info(f"DEBUG send_message: About to type message - length: {len(message)} characters")
                logger.info(f"DEBUG send_message: First 100 chars: {message[:100]}")
                
                logger.info(f"DEBUG send_message: Ready to type message")
                for line in message.split('\n'):
                    input_box.send_keys(line)
                    input_box.send_keys(Keys.SHIFT + Keys.ENTER)
                
                logger.info(f"DEBUG send_message: Message typed successfully")
                
                logger.info(f"DEBUG send_message: Clicking send button")
                send_btn = self._find_clickable_element(driver, "send_button")
                if send_btn:
                    send_btn.click()
                else:
                    logger.info(f"DEBUG send_message: Send button not found, pressing Enter")
                    input_box.send_keys(Keys.ENTER)
                
                time.sleep(1)
                
                self._notify_status(WhatsAppStatus.CONNECTED)
                logger.success(f"DEBUG send_message: SUCCESS - Message sent to {group_name}")
                logger.success(f"✓ Message sent successfully to {group_name}")
                
                return MessageResult(success=True, group_name=group_name, message=message)
                
            except Exception as e:
                logger.error(f"Error sending message to {group_name}: {e}")
                if attempt < retry_count - 1:
                    time.sleep(2)
                    continue
                
                self._notify_status(WhatsAppStatus.ERROR)
                return MessageResult(success=False, group_name=group_name, error=str(e))
        
        return MessageResult(success=False, group_name=group_name, error="Max retries exceeded")
    
    def _find_and_open_group(self, driver: webdriver.Chrome, group_name: str) -> bool:
        logger.info(f"DEBUG find_and_open_group_direct: Refreshing chat list before search")
        
        if self.chat_cache.needs_refresh():
            self.chat_cache.refresh(driver)
        
        logger.info(f"DEBUG find_and_open_group_direct: Looking for group '{group_name}'")
        
        cached_element = self.chat_cache.get_chat_element(group_name)
        if cached_element:
            try:
                logger.info(f"DEBUG: Found group in cache, clicking...")
                ActionChains(driver).move_to_element(cached_element).click().perform()
                time.sleep(1)
                
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
                    logger.info(f"DEBUG: Found chat list with selector: {selector}")
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
        
        logger.info(f"DEBUG: Found {len(rows)} chat rows to search through")
        
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
                
                logger.info(f"DEBUG: Found chat title: '{chat_title}'")
                
                if chat_title.strip() == group_name.strip():
                    logger.info(f"DEBUG: Exact match found for '{group_name}'")
                    
                    logger.info(f"DEBUG: Scrolling group '{group_name}' into view")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
                    time.sleep(0.5)
                    
                    logger.info(f"DEBUG: Clicking on group '{group_name}'")
                    try:
                        ActionChains(driver).move_to_element(row).click().perform()
                        logger.info(f"DEBUG: ActionChains click successful on '{group_name}'")
                    except:
                        row.click()
                    
                    time.sleep(1)
                    
                    logger.info(f"DEBUG: Waiting for chat '{group_name}' to load...")
                    
                    for attempt in range(5):
                        if self._verify_chat_opened(driver, group_name):
                            logger.success(f"Successfully opened group: {group_name}")
                            return True
                        logger.info(f"Chat verification attempt {attempt + 1} failed, waiting longer...")
                        time.sleep(1)
                    
                    for chat in self.chat_cache.get_all_group_names()[:5]:
                        logger.info(f"DEBUG: Found chat title: '{chat}'")
                    
                    logger.warning(f"Opened wrong chat. Expected: '{group_name}', Got: different chat")
                    logger.info(f"DEBUG: Trying one more click on the group...")
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
                        logger.info(f"DEBUG: Found chat title with selector '{selector}': '{chat_name}'")
                        logger.info(f"DEBUG: Verifying chat - Expected: '{expected_group}', Got: '{chat_name}'")
                        
                        if chat_name.strip() == expected_group.strip():
                            logger.info(f"DEBUG: Chat verification PASSED")
                            return True
                        else:
                            logger.info(f"DEBUG: Chat verification FAILED")
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying chat: {e}")
            return False
    
    def _find_clickable_element(self, driver: webdriver.Chrome, element_type: str, timeout: int = 15) -> Optional[object]:
        logger.info(f"DEBUG _find_clickable_element: Finding {element_type}")
        
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
                        logger.info(f"DEBUG _find_clickable_element: Found {element_type} with {selector}")
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


whatsapp_handler = WhatsAppHandler()


def send_alarms_to_whatsapp(group_name: str, message: str, alarm_type: str):
    whatsapp_handler.queue_message(group_name, message, alarm_type)


class OrderedAlarmSender:
    """
    Sends alarms in the user-specified order:
    1. Alarm Types: CSL -> RF Unit -> AC Main -> Battery High Temp -> Genset -> Low Voltage -> System on Battery -> Toggle -> Cell Unavailable
    2. Groups within each: MBU (1-8) -> B2S (ATL, Edotco, Enfra, Tawal) -> OMO (Ufone, Telenor, CMpak/Zong)
    """
    
    ALARM_TYPE_ORDER = [
        "CSL Fault",
        "RF Unit Maintenance Link Failure",
        "AC Main Failure",
        "Battery High Temp",
        "Genset Running",
        "Genset Operation",
        "Low Voltage",
        "System on Battery",
        "Toggle",
        "Cell Unavailable"
    ]
    
    MBU_ORDER = [
        "C1-LHR-01", "C1-LHR-02", "C1-LHR-03", "C1-LHR-04",
        "C1-LHR-05", "C1-LHR-06", "C1-LHR-07", "C1-LHR-08"
    ]
    
    B2S_ORDER = ["ATL", "Edotco", "Enfrashare", "Tawal"]
    OMO_ORDER = ["Ufone", "Telenor", "CMpak", "Zong", "CMPAK", "CM-PAK"]
    
    @classmethod
    def get_ordered_batches(cls, alarms: List) -> List[Tuple[str, str, List, bool]]:
        from alarm_processor import alarm_processor
        
        batches = []
        
        for alarm_type in cls.ALARM_TYPE_ORDER:
            is_toggle = alarm_type == "Toggle"
            
            if is_toggle:
                type_alarms = [a for a in alarms if getattr(a, 'is_toggle', False)]
            else:
                type_alarms = [a for a in alarms if a.alarm_type == alarm_type and not getattr(a, 'is_toggle', False)]
            
            if not type_alarms:
                continue
            
            for mbu in cls.MBU_ORDER:
                mbu_alarms = [a for a in type_alarms if getattr(a, 'mbu', '') == mbu]
                if mbu_alarms:
                    group_name = settings.get_whatsapp_group_name(mbu)
                    if group_name:
                        if is_toggle and alarm_processor.should_skip_toggle_for_mbu(mbu):
                            continue
                        batches.append((group_name, alarm_type, mbu_alarms, is_toggle))
            
            for company in cls.B2S_ORDER:
                b2s_alarms = [a for a in type_alarms if getattr(a, 'b2s_company', '') == company]
                if b2s_alarms:
                    group_name = settings.get_b2s_group_name(company)
                    if group_name:
                        batches.append((group_name, alarm_type, b2s_alarms, is_toggle))
            
            for company in cls.OMO_ORDER:
                omo_alarms = [a for a in type_alarms if getattr(a, 'omo_company', '') == company]
                if omo_alarms:
                    group_name = settings.get_omo_group_name(company)
                    if group_name:
                        batches.append((group_name, alarm_type, omo_alarms, is_toggle))
        
        return batches
    
    @classmethod
    def send_all_ordered(cls, alarms: List):
        batches = cls.get_ordered_batches(alarms)
        
        for group_name, alarm_type, batch_alarms, is_toggle in batches:
            if is_toggle:
                message = message_formatter.format_toggle_alarms(batch_alarms)
            elif any(a.is_b2s for a in batch_alarms if hasattr(a, 'is_b2s')):
                message = message_formatter.format_b2s_alarms(batch_alarms)
            elif any(a.is_omo for a in batch_alarms if hasattr(a, 'is_omo')):
                message = message_formatter.format_omo_alarms(batch_alarms)
            else:
                message = message_formatter.format_mbu_alarms(batch_alarms, alarm_type)
            
            if message.strip():
                priority = 1 if "csl" in alarm_type.lower() else 2
                whatsapp_handler.queue_message(group_name, message, alarm_type, priority)
                logger.info(f"Ordered batch queued: {alarm_type} | Count: {len(batch_alarms)} | Group: {group_name}")


ordered_sender = OrderedAlarmSender()
