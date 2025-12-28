"""
Test script to verify WhatsApp session persistence and QR code loading
"""

import time
from browser_manager import browser_manager
from logger_module import logger

def test_whatsapp_session_persistence():
    """Test WhatsApp session persistence and QR code loading"""
    try:
        logger.info("Testing WhatsApp session persistence...")

        # Check if session preservation is enabled
        preservation_enabled = browser_manager.is_whatsapp_session_preserved()
        logger.info(f"WhatsApp session preservation: {preservation_enabled}")

        # Start browsers
        success = browser_manager.start()
        if not success:
            logger.error("Failed to start browsers")
            return False

        logger.info("Browsers started successfully")

        # Check WhatsApp status
        whatsapp_ready = browser_manager.is_whatsapp_ready()
        logger.info(f"WhatsApp ready: {whatsapp_ready}")

        if whatsapp_ready:
            logger.success("WhatsApp is already logged in - session persistence working!")
            return True
        else:
            logger.info("WhatsApp not logged in - check the browser window for QR code")
            logger.info("Session persistence means you won't need to scan QR again after first login")

            # Wait a bit and check again
            time.sleep(10)
            whatsapp_ready = browser_manager.is_whatsapp_ready()
            if whatsapp_ready:
                logger.success("WhatsApp became ready after waiting")
                return True
            else:
                logger.warning("WhatsApp still not ready - please scan QR code in browser window")
                return False

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        logger.info("Test complete - browsers remain open for manual verification")

if __name__ == "__main__":
    test_whatsapp_session_persistence()
