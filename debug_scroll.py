#!/usr/bin/env python3
"""
Debug script to analyze the Huawei MAE Portal scrolling behavior
Run this to get detailed information about the portal structure and scrolling
"""

import sys
import os
import time
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

def analyze_portal_structure():
    """Analyze the portal HTML structure to understand scrolling mechanism"""
    print("=" * 60)
    print("HUAWEI MAE PORTAL SCROLL DEBUGGING TOOL")
    print("=" * 60)

    try:
        from browser_manager import browser_manager
        from config import TabType

        print("\n1. Starting browser...")
        driver = browser_manager.get_driver()
        if not driver:
            print("❌ Could not get browser driver")
            return

        # Test each portal
        portals = [
            (TabType.CSL_FAULT, "CSL Fault"),
            (TabType.ALL_ALARMS, "All Alarms"),
            (TabType.RF_UNIT, "RF Unit"),
            (TabType.NODEB_CELL, "NodeB Cell")
        ]

        for tab_type, name in portals:
            print(f"\n{'='*20} ANALYZING {name.upper()} {'='*20}")

            if not browser_manager.switch_to_tab(tab_type):
                print(f"❌ Could not switch to {name} tab")
                continue

            time.sleep(3)  # Wait for page to load

            # Analyze iframes
            iframes = driver.find_elements_by_tag_name("iframe")
            print(f"📄 Found {len(iframes)} iframes")

            for idx, iframe in enumerate(iframes):
                try:
                    driver.switch_to.frame(iframe)

                    # Check for EUI table
                    tables = driver.find_elements_by_css_selector(".eui_table_tb, .fmScrollTable")
                    if not tables:
                        driver.switch_to.default_content()
                        continue

                    print(f"\n🔍 IFRAME {idx} - EUI Table Found:")

                    # Get scroll structure
                    scroll_info = driver.execute_script("""
                        var info = {
                            iframes: document.querySelectorAll('iframe').length,
                            scrollWrap: !!document.querySelector('.scrollWrap'),
                            fmScrollWrap: !!document.querySelector('.fmScrollWrap'),
                            virtualScrollbar: !!document.querySelector('.fm_virtual_scrollbar'),
                            virtualScroll: !!document.querySelector('.fm_virtual_scroll'),
                            virtualBar: !!document.querySelector('.fm_virtual_bar'),
                            dropArrow: !!document.querySelector('.dropArrowIcon'),
                            upArrow: !!document.querySelector('.upArrowIcon'),
                            euiTable: !!document.querySelector('.eui_table_tb'),
                            tbody: !!document.querySelector('tbody'),
                            visibleRows: document.querySelectorAll('tbody tr[data-id]').length,
                            indicator: null,
                            scrollbarPos: null
                        };

                        // Get indicator text
                        var tip = document.querySelector('.eui_tipBox_contentStyle, .fm_virtual_bar .eui_tipBox_contentStyle');
                        if (tip) info.indicator = tip.textContent || tip.innerText;

                        // Get scrollbar position
                        var bar = document.querySelector('.fm_virtual_bar');
                        if (bar) info.scrollbarPos = bar.style.top;

                        // Get row data-ids
                        info.dataIds = Array.from(document.querySelectorAll('tbody tr[data-id]')).map(tr => tr.getAttribute('data-id'));

                        return info;
                    """)

                    print(json.dumps(scroll_info, indent=2))

                    # Test scroll mechanisms
                    print("\n🧪 Testing scroll mechanisms...")

                    # Test 1: Down arrow click
                    down_arrows = driver.find_elements_by_css_selector(".fm_virtual_scrollbar .dropArrowIcon, .dropArrowIcon")
                    if down_arrows:
                        print("✅ Found down arrow, testing click...")
                        try:
                            driver.execute_script("arguments[0].click();", down_arrows[0])
                            time.sleep(2)

                            after_click = driver.execute_script("""
                                var info = {
                                    visibleRows: document.querySelectorAll('tbody tr[data-id]').length,
                                    indicator: null,
                                    scrollbarPos: null,
                                    dataIds: Array.from(document.querySelectorAll('tbody tr[data-id]')).map(tr => tr.getAttribute('data-id'))
                                };
                                var tip = document.querySelector('.eui_tipBox_contentStyle, .fm_virtual_bar .eui_tipBox_contentStyle');
                                if (tip) info.indicator = tip.textContent || tip.innerText;
                                var bar = document.querySelector('.fm_virtual_bar');
                                if (bar) info.scrollbarPos = bar.style.top;
                                return info;
                            """)

                            print("After down arrow click:")
                            print(json.dumps(after_click, indent=2))

                        except Exception as e:
                            print(f"❌ Down arrow click failed: {e}")
                    else:
                        print("❌ No down arrow found")

                    # Test 2: JavaScript scroll
                    print("\n🧪 Testing JavaScript scroll simulation...")
                    try:
                        driver.execute_script("""
                            var bar = document.querySelector('.fm_virtual_bar');
                            if (bar) {
                                var currentTop = parseInt(bar.style.top) || 0;
                                bar.style.top = (currentTop + 100) + 'px';
                                ['mousedown', 'mousemove', 'mouseup', 'scroll'].forEach(eventType => {
                                    var event = new Event(eventType, { bubbles: true });
                                    bar.dispatchEvent(event);
                                });
                                console.log('JS scroll: moved bar to', bar.style.top);
                            }
                        """)
                        time.sleep(2)

                        after_js = driver.execute_script("""
                            var info = {
                                visibleRows: document.querySelectorAll('tbody tr[data-id]').length,
                                indicator: null,
                                scrollbarPos: null,
                                dataIds: Array.from(document.querySelectorAll('tbody tr[data-id]')).map(tr => tr.getAttribute('data-id'))
                            };
                            var tip = document.querySelector('.eui_tipBox_contentStyle, .fm_virtual_bar .eui_tipBox_contentStyle');
                            if (tip) info.indicator = tip.textContent || tip.innerText;
                            var bar = document.querySelector('.fm_virtual_bar');
                            if (bar) info.scrollbarPos = bar.style.top;
                            return info;
                        """)

                        print("After JS scroll:")
                        print(json.dumps(after_js, indent=2))

                    except Exception as e:
                        print(f"❌ JS scroll failed: {e}")

                    driver.switch_to.default_content()
                    break  # Only analyze first iframe with table

                except Exception as e:
                    print(f"❌ Error analyzing iframe {idx}: {e}")
                    driver.switch_to.default_content()

        print("\n" + "=" * 60)
        print("DEBUG COMPLETE - Please share this output for analysis")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_portal_structure()
