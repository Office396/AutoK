"""
Test script to verify WhatsApp Web loading fix
"""

import time
from browser_manager import browser_manager
from logger_module import logger

def test_whatsapp_loading():
    """Test WhatsApp Web loading"""
    try:
        logger.info("Starting WhatsApp loading test...")

        # Start browsers
        success = browser_manager.start()
        if not success:
            logger.error("Failed to start browsers")
            return False

        logger.info("Browsers started, checking WhatsApp...")

        # Check WhatsApp status
        whatsapp_ready = browser_manager.is_whatsapp_ready()
        logger.info(f"WhatsApp ready: {whatsapp_ready}")

        if whatsapp_ready:
            logger.success("WhatsApp is ready!")
            return True
        else:
            logger.warning("WhatsApp not ready - check the browser window for QR code")
            return False

    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False
    finally:
        # Keep browsers open for manual testing
        logger.info("Test complete - browsers will remain open for manual verification")

if __name__ == "__main__":
    test_whatsapp_loading()

