#!/usr/bin/env python3
"""
Test browser session recovery functionality
"""

import sys
import time
sys.path.append('.')

from browser_manager import browser_manager
from logger_module import logger


def test_session_recovery():
    """Test session recovery functionality"""
    print("Testing Browser Session Recovery")
    print("=" * 40)

    try:
        # Test session alive check
        print("1. Testing session alive check...")
        is_alive = browser_manager.is_session_alive()
        print(f"   Session alive: {is_alive}")

        # Start browsers
        print("2. Starting browsers...")
        started = browser_manager.start()
        print(f"   Browsers started: {started}")

        if started:
            print("3. Testing session recovery...")
            # Force close driver to simulate crash
            try:
                driver = browser_manager.get_driver()
                if driver:
                    driver.quit()
                    print("   Driver forcibly closed")
            except:
                pass

            # Test session recovery
            time.sleep(2)
            recovered = browser_manager.recover_session()
            print(f"   Session recovered: {recovered}")

            if recovered:
                # Test ensure_session_alive
                print("4. Testing ensure_session_alive...")
                ensured = browser_manager.ensure_session_alive()
                print(f"   Session ensured: {ensured}")

                print("✓ Session recovery tests completed successfully")
                return True
            else:
                print("✗ Session recovery failed")
                return False
        else:
            print("✗ Browser startup failed")
            return False

    except Exception as e:
        print(f"Error testing session recovery: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        try:
            browser_manager.close()
            print("5. Browsers closed")
        except:
            pass


if __name__ == "__main__":
    success = test_session_recovery()
    sys.exit(0 if success else 1)




