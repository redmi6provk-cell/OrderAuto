"""
Cart Management Module
Handles product addition, quantity adjustment, and popup handling
"""

import asyncio
import re
from typing import Dict, Any, List

from services.job_queue import job_queue, LogLevel


class CartManager:
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager

    async def select_marketplace_tab(self, page: Any, job_id: int, automation_mode: str = "FLIPKART") -> bool:
        """Select the correct tab in the cart (Flipkart vs Grocery)."""
        try:
            # 1. SETUP REDIRECT BLOCKING (Prevention)
            # We block the known promotional redirect URL patterns to stop the loop at its source
            try:
                await page.route(re.compile(r".*/fpg/cbc/store-page.*|.*/fpg/cc/dashboard.*"), lambda route: route.abort())
                await job_queue.log_job(job_id, LogLevel.DEBUG, "🚫 Blocking promotional redirect URLs for this session.")
            except Exception:
                pass

            # First, ensure we haven't been redirected to an ad page
            await self._ensure_on_cart_page(page, job_id, automation_mode)

            await job_queue.log_job(job_id, LogLevel.INFO, f"Switching to {automation_mode} tab in cart...")
            
            # Wait for tab container
            tab_container_selector = '.css-g5y9jx[style*="width: 800px"]'
            try:
                await page.wait_for_selector(tab_container_selector, timeout=5000)
            except Exception:
                # If tab container is not found, we might have been redirected again or there's only one marketplace
                if await self._ensure_on_cart_page(page, job_id, automation_mode):
                    # If we had to fix the URL, wait again for tabs
                    try:
                        await page.wait_for_selector(tab_container_selector, timeout=3000)
                    except Exception:
                        pass
                else:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, "Tab container not found - might only have one marketplace active.")
                    return True

            if automation_mode == "FLIPKART":
                # First tab is usually Flipkart
                tab_selectors = ['div:has-text("Flipkart (")', 'div:has-text("Flipkart")', 'text="Flipkart"']
            else:
                # Second tab is usually Grocery
                tab_selectors = ['div:has-text("Grocery (")', 'div:has-text("Grocery")', 'text="Grocery"']

            tab_found = False
            for selector in tab_selectors:
                tab = page.locator(selector)
                if await tab.count() > 0:
                    # CHECK IF ALREADY SELECTED
                    # We check if the parent div has a border or style indicating activity to avoid redundant clicks
                    is_active = False
                    try:
                        # Common Flipkart active tab style involves a specific border color or class
                        # We use a broad heuristic: if it has an underline div, it's likely active
                        indicator = tab.locator('xpath=./following-sibling::div[contains(@style, "background-color")]')
                        if await indicator.count() > 0:
                            is_active = True
                    except Exception:
                        pass

                    if is_active:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"✨ {automation_mode} tab is already active, skipping click.")
                    else:
                        await tab.first.click()
                        await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Selected {automation_mode} tab using '{selector}'")
                    
                    tab_found = True
                    break
            
            if tab_found:
                await asyncio.sleep(2.0)
                return True
            else:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"{automation_mode} tab not found - assuming it's already selected or not present.")
                return True

        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to switch marketplace tab: {str(e)}")
            return False

    async def _ensure_on_cart_page(self, page: Any, job_id: int, automation_mode: str) -> bool:
        """Monitor the URL for 5 seconds to detect and recover from any late-triggered redirects.
        Only applied to Flipkart mode as requested by the user.
        Returns True if a redirect was recovered, False otherwise."""
        if automation_mode != "FLIPKART":
            return False
            
        ad_patterns = [
            "productType=CC",
            "fpg/cbc/store-page",
            "utm_source=Cart_OTA",
            "checkout/offers",
            "cc-store-page",
            "fpg/cbc",
            "fpg/cc/dashboard",
            "flipkart.com/fpg/",
            "payment/interstitial"
        ]
        
        last_logged_url = None
        
        # Check every 0.3 seconds for up to 5 seconds for more responsiveness
        for i in range(15):
            current_url = page.url
            
            # Log only if URL changes to avoid spamming
            if current_url != last_logged_url:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Current URL check: {current_url[:150]}")
                last_logged_url = current_url

            if any(pattern in current_url for pattern in ad_patterns):
                await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Detected promotional redirect: {current_url[:100]}...")
                
                # ATTEMPT DISMISSAL FIRST (Fast Recovery)
                # Instead of a full Home -> Cart cycle, try to find 'Cart' or 'Back' buttons on the promo page
                try:
                    dismiss_selectors = [
                        'a[href*="/viewcart"]',
                        'div:has-text("Back to Cart")',
                        'div:has-text("No thanks")',
                        'button:has-text("No thanks")',
                        'span:has-text("✕")',
                        '#container > div > div._2msBFL > div:nth-child(3) > div' # Cart icon path
                    ]
                    for selector in dismiss_selectors:
                        btn = page.locator(selector)
                        if await btn.count() > 0 and await btn.first.is_visible():
                            await job_queue.log_job(job_id, LogLevel.INFO, f"🎯 Dismissing promo using: {selector}")
                            await btn.first.click(timeout=3000)
                            await asyncio.sleep(1.0)
                            if "viewcart" in page.url:
                                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Sucessfully returned to cart via dismissal button.")
                                return True
                except Exception:
                    pass

                await job_queue.log_job(job_id, LogLevel.INFO, "🔄 Dismissal failed, forcing navigation back to the proper cart URL via Home page.")
                await self._navigate_to_cart_safely(page, job_id, automation_mode)
                return True
            
            # Additional check: if not on viewcart and not home, it might be a redirect we didn't pattern-match
            if "viewcart" not in current_url and "flipkart.com/" in current_url and current_url.strip("https://").strip("www.").strip("/") != "flipkart.com":
                 if not any(kw in current_url for kw in ["viewcart", "marketplace="]):
                     # Small delay to see if it's just slow loading
                     await asyncio.sleep(0.5)
                     if "viewcart" not in page.url:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Unexpected URL detected: {page.url[:100]}... Navigating back.")
                        await self._navigate_to_cart_safely(page, job_id, automation_mode)
                        return True
            
            await asyncio.sleep(0.3)
        
        return False

    async def _navigate_to_cart_safely(self, page: Any, job_id: int, automation_mode: str):
        """Navigate to Home page first, then to the Cart to bypass interstitial ads as requested by the user."""
        try:
            # 1. SETUP REDIRECT BLOCKING (Prevention)
            try:
                await page.route(re.compile(r".*/fpg/cbc/store-page.*|.*/fpg/cc/dashboard.*"), lambda route: route.abort())
                await job_queue.log_job(job_id, LogLevel.DEBUG, "🚫 Arming redirect blocker for cart navigation.")
            except Exception:
                pass

            await job_queue.log_job(job_id, LogLevel.INFO, "🏠 Resetting navigation via Home page...")
            await page.goto('https://www.flipkart.com/', wait_until='domcontentloaded', timeout=45000)
            await asyncio.sleep(1.0)
            
            cart_url = f'https://www.flipkart.com/viewcart?marketplace={automation_mode.upper()}'
            await job_queue.log_job(job_id, LogLevel.INFO, f"🛒 Navigating to cart: {cart_url}")
            await page.goto(cart_url, wait_until='domcontentloaded', timeout=45000)
            
            # Verify we landed on viewcart
            try:
                await asyncio.sleep(1.5)
                if "viewcart" not in page.url:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Not yet on cart page, retrying direct link...")
                    await page.goto(cart_url, wait_until='networkidle', timeout=30000)
            except Exception:
                pass
                
            await asyncio.sleep(1.5)
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed safe navigation: {str(e)}")


    async def _get_home_cart_count(self, job_id: int) -> int:

        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            return 0
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            await page.goto('https://www.flipkart.com/', wait_until='domcontentloaded')
            await asyncio.sleep(0.6)
        except Exception:
            return 0

        selectors = [
            '#container > div > div.q8WwEU > div > div > div > div > div > div > div > div > div > div._2nl6Ch.k2FAh4 > div._2NhoPJ > div > header > div._2msBFL > div:nth-child(3) > div > a._3CowY2',
            'a._3CowY2',
            'a[href*="viewcart"]'
        ]

        for sel in selectors:
            try:
                anchor = page.locator(sel)
                if await anchor.count() == 0:
                    continue
                txt = (await anchor.first.inner_text()).strip()
                if not txt:
                    # Try to read any badge within
                    try:
                        badge = anchor.first.locator('span')
                        if await badge.count() > 0:
                            txt = (await badge.first.inner_text()).strip()
                    except Exception:
                        pass
                import re
                m = re.search(r"(\d+)", txt)
                if m:
                    return int(m.group(1))
            except Exception:
                continue
        return 0

    async def clear_cart_if_needed(self, job_id: int, automation_mode: str = "FLIPKART") -> dict:
        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            return {"success": False, "performed": False, "error": "no_context"}
        page = context.pages[0] if context.pages else await context.new_page()

        await job_queue.log_job(job_id, LogLevel.INFO, f"Navigating to {automation_mode} cart page to check and clear if needed...")

        try:
            # 1. Determine which tab to look for
            target_tab = "Grocery" if automation_mode == "GROCERY" else "Flipkart"
            
            # Go to home first then cart to avoid redirects (Safe Navigation) - Flipkart only
            if automation_mode == "FLIPKART":
                await self._navigate_to_cart_safely(page, job_id, automation_mode)
            else:
                await page.goto(f'https://www.flipkart.com/viewcart?marketplace={automation_mode}', wait_until='domcontentloaded')
                await asyncio.sleep(2.0)
            
                pass

            # Switch tab if needed
            await self.select_marketplace_tab(page, job_id, automation_mode)

            async def is_empty() -> bool:
                try:
                    # SAFETY CHECK: If we are not on a cart URL, we cannot be 'empty'
                    # Returning False will trigger the redirect handling in the main loop
                    current_url = page.url
                    if "viewcart" not in current_url:
                        return False

                    # Generic empty indicators
                    empty_indicators = [
                        "Your basket is empty",
                        "Your cart is empty",
                        "Missing items? Login to see the items you added previously",
                        "Your grocery basket is empty",
                        "Flipkart cart is empty"
                    ]
                    for text in empty_indicators:
                        if await page.get_by_text(text).count() > 0:
                            return True
                    
                    # Image based indicator
                    if await page.locator('img[src*="empty-cart"], img[src*="empty_cart"]').count() > 0:
                        return True

                    # Header-based indicators
                    try:
                        header_selectors = ['#guidSearch > div > h1', 'div:has-text("My Cart")', 'h1:has-text("My Cart")']
                        for sel in header_selectors:
                            try:
                                header_loc = page.locator(sel)
                                if await header_loc.count() > 0:
                                    header = await header_loc.first.inner_text()
                                    # If the header doesn't contain "item" or "items", it's likely empty (e.g., "My Cart", "Grocery basket")
                                    if any(kw in header for kw in ["Grocery basket", "My Cart", "Flipkart cart"]) and "item" not in header.lower():
                                        return True
                            except Exception:
                                continue
                    except Exception:
                        pass
                except Exception:
                    pass
                return False

            if await is_empty():
                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Cart is already empty")
                return {"success": True, "performed": False, "removed": 0, "decremented": 0}

            await job_queue.log_job(job_id, LogLevel.INFO, "Cart has items - starting clearing process...")
            removed = 0
            decremented = 0
            max_attempts = 25  # Handling even more items

            for attempt in range(max_attempts):
                # 2. Check and fix promotional redirects (Flipkart only)
                if automation_mode == "FLIPKART":
                    # SAFETY CHECK: If we've been redirected, recover and CONTINUE the loop to refresh state
                    if await self._ensure_on_cart_page(page, job_id, automation_mode):
                        await job_queue.log_job(job_id, LogLevel.INFO, "🔄 Navigation recovered, refreshing state...")
                        # Re-select tab if needed
                        await self.select_marketplace_tab(page, job_id, automation_mode)
                        continue 
                    
                    current_url = page.url
                    if "/p/itm" in current_url or "/product-review/" in current_url:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Redirected to product page {current_url[:60]}... Navigating back.")
                        await self._navigate_to_cart_safely(page, job_id, automation_mode)
                        await self.select_marketplace_tab(page, job_id, automation_mode)
                        continue

                # Check if cart is empty at start of each iteration
                if await is_empty():
                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Cart is now empty! (removed={removed}, decremented={decremented})")
                    return {"success": True, "performed": True, "removed": removed, "decremented": decremented}

                await job_queue.log_job(job_id, LogLevel.INFO, f"Clearing attempt {attempt + 1}/{max_attempts}")
                
                # Scroll to top to ensure we see all items
                try:
                    await page.evaluate('window.scrollTo(0, 0)')
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

                # Scroll through the page to load all items
                try:
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                    await asyncio.sleep(0.3)
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await asyncio.sleep(0.3)
                    await page.evaluate('window.scrollTo(0, 0)')
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

                # Save debug HTML for inspection
                # try:
                #     debug_filename = f"cart_debug_{job_id}_{attempt}.html"
                #     html_content = await page.content()
                #     with open(debug_filename, "w", encoding="utf-8") as f:
                #         f.write(html_content)
                #     await job_queue.log_job(job_id, LogLevel.DEBUG, f"Saved debug HTML to {debug_filename}")
                # except Exception:
                #     pass

                made_progress = False

                if automation_mode == "FLIPKART":
                    # Strategy for Flipkart: Just click Remove button
                    try:
                        # Strategy 1: Case-insensitive "Remove" or "Delete"
                        btns = page.get_by_text(re.compile(r"Remove|Delete", re.I), exact=False)
                        
                        # Strategy 2: Specific div-based patterns (Added the user's specific r- utility classes)
                        if await btns.count() == 0:
                            btns = page.locator('div.css-1pz39u2:has-text("Remove"), div.r-1pz39u2:has-text("Remove"), div.css-1rymq56:has-text("Remove"), div:has-text("Delete")')
                        
                        # Strategy 3: Role-based search
                        if await btns.count() == 0:
                            btns = page.get_by_role("button", name=re.compile(r"Remove|Delete", re.I))
                                                
                        # Strategy 4: Fallback to any clickable containing "Remove"
                        if await btns.count() == 0:
                            btns = page.locator('div[style*="cursor: pointer"]:has-text("Remove")')

                        cnt = await btns.count()
                        if cnt > 0:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Found {cnt} potential Remove button(s)")
                            
                            # Click the first one (we click specific container with cursor:pointer if possible)
                            target = btns.first
                            
                            # TRY TO FIND THE INTERACTIVE PARENT (cursor: pointer)
                            try:
                                # We look for the ancestor div that has cursor: pointer style
                                parent_clickable = target.locator('xpath=./ancestor-or-self::div[contains(@style, "cursor: pointer") or contains(@class, "cursor-pointer")]').last
                                if await parent_clickable.count() > 0:
                                    target = parent_clickable
                                    await job_queue.log_job(job_id, LogLevel.DEBUG, "Targeting interactive parent container for Remove click")
                            except Exception:
                                pass

                            await target.click(force=True, timeout=5000)
                            made_progress = True
                            removed += 1
                            await job_queue.log_job(job_id, LogLevel.INFO, "Clicked Remove button...")
                            
                            # HANDLE CONFIRMATION MODAL (Flipkart Regular)
                            await asyncio.sleep(1.0)
                            confirm_btns = page.locator('div:has-text("Are you sure"), div:has-text("REMOVE ITEM")').locator('div:has-text("Remove")').last
                            if await confirm_btns.count() > 0:
                                await job_queue.log_job(job_id, LogLevel.INFO, "Handling confirmation popup...")
                                await confirm_btns.click(force=True, timeout=3000)
                                await asyncio.sleep(1.0)
                            
                            await page.wait_for_load_state('networkidle', timeout=5000)
                            await asyncio.sleep(1.5)
                        else:
                            await job_queue.log_job(job_id, LogLevel.DEBUG, "No Remove buttons found in this iteration.")
                    except Exception as e:
                        await job_queue.log_job(job_id, LogLevel.DEBUG, f"Remove button search/click failed: {e}")

                elif automation_mode == "GROCERY":
                    # Strategy for Grocery: Use minus buttons to decrement quantities to 0
                    try:
                        minus_buttons = []
                        cart_area = page.locator('#_parentCtr_')
                        containers = cart_area.locator('div.css-175oi2r.r-1awozwy.r-qwd59z.r-18u37iz.r-mabqd8.r-1777fci.r-7bouqp')
                        c = await containers.count()
                        
                        for i in range(c):
                            try:
                                minus = containers.nth(i).locator('> div:nth-child(1)')
                                if await minus.count() > 0:
                                    minus_buttons.append(minus.first)
                            except Exception:
                                continue
                        
                        if len(minus_buttons) == 0:
                            # 1. Try specific minus icon image
                            try:
                                imgs = cart_area.locator('img[src*="beb19156-518d-4110-bceb"]')
                                ic = await imgs.count()
                                for i in range(ic):
                                    parent = imgs.nth(i).locator('xpath=..')
                                    if await parent.count() > 0:
                                        minus_buttons.append(parent.first)
                            except Exception:
                                pass
                                
                            # 2. Try generic text or role based minus buttons
                            try:
                                generic_minus = page.locator('div:has-text("-"):visible, [role="button"]:has-text("-"):visible')
                                gm_count = await generic_minus.count()
                                for i in range(gm_count):
                                    minus_buttons.append(generic_minus.nth(i))
                            except Exception:
                                pass
                        
                        if len(minus_buttons) > 0:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Found {len(minus_buttons)} potential minus button(s)")
                            
                        for idx, btn in enumerate(minus_buttons):
                            try:
                                # Scroll button into view
                                await btn.scroll_into_view_if_needed()
                                await asyncio.sleep(0.2)
                                
                                if await btn.is_visible(timeout=1000):
                                    await btn.click(timeout=2000)
                                    decremented += 1
                                    made_progress = True
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"Clicked minus button {idx+1}")
                                    await asyncio.sleep(0.3)
                            except Exception as e:
                                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Failed to click minus {idx+1}: {e}")
                                continue
                    except Exception as e:
                        await job_queue.log_job(job_id, LogLevel.DEBUG, f"Minus button search failed: {e}")

                # Wait for UI to update after removals
                await asyncio.sleep(1.0)

                # If no progress was made this iteration, break to avoid infinite loop
                if not made_progress:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "No progress made in this iteration, checking final state...")
                    break

            # Final verification - MUST see "Your basket is empty!" message
            if await is_empty():
                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Cart successfully cleared! (removed={removed}, decremented={decremented})")
                return {"success": True, "performed": True, "removed": removed, "decremented": decremented}
            else:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Cart clearing incomplete - items still remain (removed={removed}, decremented={decremented})")
                return {"success": False, "performed": True, "removed": removed, "decremented": decremented, "error": "cart_not_empty"}

        except Exception as e:
            return {"success": False, "performed": False, "error": str(e)}

    async def handle_steal_deals(self, job_id: int, product_name: str) -> Dict[str, Any]:
        """
        Search for and add an unlocked steal deal product by name.
        Only processes unlocked deals (with 'Deal unlocked!' banner and Add button visible).
        
        Args:
            job_id: Job identifier for logging
            product_name: Name of the product to search for in steal deals
            
        Returns:
            Dict with success status and message
        """
        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            return {"success": False, "error": "No browser context"}
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            await job_queue.log_job(job_id, LogLevel.INFO, f"🎁 Searching for Steal Deal product: '{product_name}'")
            
            # Navigate to cart where steal deals section is shown
            marketplace = "GROCERY"
            await page.goto(f'https://www.flipkart.com/viewcart?marketplace={marketplace}', wait_until='domcontentloaded')
            await asyncio.sleep(2.0)
            
            # Scroll down to ensure steal deals section is loaded
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            await asyncio.sleep(1.0)
            
            # Base selector for deal cards container
            deals_container_selector = '#_parentCtr_ > div:nth-child(2) > div > div > div > div > div:nth-child(2) > div > div > div > div > div > div'
            
            # Find all deal cards
            deal_cards = page.locator(f'{deals_container_selector} > div')
            card_count = await deal_cards.count()
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Found {card_count} deal cards to scan")
            
            if card_count == 0:
                await job_queue.log_job(job_id, LogLevel.WARNING, "No steal deal cards found on page")
                return {"success": False, "error": "No steal deals section found"}
            
            # Scan each card for unlocked deals matching the product name
            for i in range(card_count):
                try:
                    card = deal_cards.nth(i)
                    
                    # Check if card is visible
                    if not await card.is_visible():
                        continue
                    
                    # Get card text content
                    card_text = await card.inner_text()
                    
                    # Check if this is an unlocked deal
                    if "Deal unlocked!" not in card_text:
                        await job_queue.log_job(job_id, LogLevel.DEBUG, f"Card {i+1}: Skipping locked deal")
                        continue
                    
                    # Check if product name matches (case-insensitive partial match)
                    if product_name.lower() not in card_text.lower():
                        await job_queue.log_job(job_id, LogLevel.DEBUG, f"Card {i+1}: Product name mismatch")
                        continue
                    
                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Found matching unlocked deal in card {i+1}: {product_name}")
                    
                    # Look for Add button within this card
                    # Try multiple selector strategies
                    add_button_found = False
                    
                    # Strategy 1: Find "Add" text within the card
                    add_button = card.get_by_text("Add", exact=True)
                    if await add_button.count() > 0:
                        try:
                            await add_button.first.scroll_into_view_if_needed()
                            await asyncio.sleep(0.3)
                            await add_button.first.click(timeout=3000)
                            add_button_found = True
                            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Clicked Add button via text locator")
                        except Exception as e:
                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Text-based Add button click failed: {e}")
                    
                    # Strategy 2: Find button with specific styling (brown border button)
                    if not add_button_found:
                        try:
                            # Look for the styled Add button div within this card
                            styled_button = card.locator('div.css-175oi2r[style*="border-color: rgb(133, 60, 14)"]')
                            if await styled_button.count() > 0:
                                await styled_button.first.scroll_into_view_if_needed()
                                await asyncio.sleep(0.3)
                                await styled_button.first.click(timeout=3000)
                                add_button_found = True
                                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Clicked Add button via styled selector")
                        except Exception as e:
                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Styled Add button click failed: {e}")
                    
                    # Strategy 3: Generic role-based button search within card
                    if not add_button_found:
                        try:
                            role_button = card.get_by_role("button", name=re.compile(r"add", re.I))
                            if await role_button.count() > 0:
                                await role_button.first.scroll_into_view_if_needed()
                                await asyncio.sleep(0.3)
                                await role_button.first.click(timeout=3000)
                                add_button_found = True
                                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Clicked Add button via role locator")
                        except Exception as e:
                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Role-based Add button click failed: {e}")
                    
                    if add_button_found:
                        await asyncio.sleep(1.5)
                        await job_queue.log_job(job_id, LogLevel.INFO, f"🎉 Successfully added steal deal: {product_name}")
                        
                        # Handle any popups that might appear after adding
                        try:
                            await self._handle_interruption_popups_fast(page, job_id)
                        except Exception:
                            pass
                        
                        return {"success": True, "message": f"Added steal deal: {product_name}"}
                    else:
                        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Found matching deal but could not click Add button")
                        return {"success": False, "error": "Add button not clickable"}
                        
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Error processing card {i+1}: {str(e)}")
                    continue
            
            # No matching unlocked deal found
            await job_queue.log_job(job_id, LogLevel.WARNING, f"No unlocked steal deal found for: {product_name}")
            return {"success": False, "error": "Product not found in unlocked deals"}
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error in steal deals handler: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _handle_grocery_basket_popup(self, page: Any, job_id: int) -> bool:
        """Handle the grocery basket popup that appears after adding products to cart in mobile view - enhanced detection"""
        try:
            await job_queue.log_job(job_id, LogLevel.INFO, "Checking for grocery basket popup...")
            
            # Wait for popup to fully load
            await asyncio.sleep(1.5)
            
            # First, detect if popup exists by looking for key text
            popup_indicators = [
                'text="Continue building your Grocery Basket"',
                'text="Find great deals & offers on Grocery Home"',
                'text="Cancel"',
                'text="Go to Grocery Home"'
            ]
            
            popup_exists = False
            for indicator in popup_indicators:
                try:
                    if await page.locator(indicator).count() > 0:
                        popup_exists = True
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Grocery basket popup detected via: {indicator}")
                        break
                except Exception:
                    continue
            
            if not popup_exists:
                await job_queue.log_job(job_id, LogLevel.INFO, "No grocery basket popup detected")
                return True
            
            # Enhanced cancel button selectors with scroll and visibility checks
            cancel_selectors = [
                # User-provided specific selector (highest priority)
                'body > div:nth-child(23) > div > div:nth-child(2) > div > div > div > div > div > div > div.css-175oi2r.r-1oszu61.r-18u37iz.r-13qz1uu.r-s1qlax.r-5njf8e > div:nth-child(1) > div',
                # Alternative nth-child variations
                'body > div:nth-child(22) > div > div:nth-child(2) > div > div > div > div > div > div > div.css-175oi2r.r-1oszu61.r-18u37iz.r-13qz1uu.r-s1qlax.r-5njf8e > div:nth-child(1) > div',
                'body > div:nth-child(24) > div > div:nth-child(2) > div > div > div > div > div > div > div.css-175oi2r.r-1oszu61.r-18u37iz.r-13qz1uu.r-s1qlax.r-5njf8e > div:nth-child(1) > div',
                # Class-based selectors
                'div.css-175oi2r.r-1oszu61.r-18u37iz.r-13qz1uu.r-s1qlax.r-5njf8e > div:nth-child(1) > div',
                # Text-based selectors with exact matching
                'div:has-text("Cancel"):visible',
                'button:has-text("Cancel"):visible',
                # More specific text matching
                'div.css-1rynq56:has-text("Cancel")',
                # Generic patterns
                '[role="button"]:has-text("Cancel")',
                'span:has-text("Cancel")'
            ]
            
            popup_handled = False
            for i, selector in enumerate(cancel_selectors):
                try:
                    cancel_elements = page.locator(selector)
                    element_count = await cancel_elements.count()
                    
                    if element_count > 0:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found {element_count} cancel element(s) with selector #{i+1}")
                        
                        # Try each matching element
                        for j in range(element_count):
                            try:
                                cancel_button = cancel_elements.nth(j)
                                
                                # Scroll into view and check visibility
                                await cancel_button.scroll_into_view_if_needed()
                                await asyncio.sleep(0.3)
                                
                                is_visible = await cancel_button.is_visible()
                                if is_visible:
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"Clicking cancel button (element {j+1}) with selector #{i+1}")
                                    await cancel_button.click(timeout=3000)
                                    await asyncio.sleep(1.5)  # Wait for popup to close
                                    
                                    # Verify popup is dismissed
                                    popup_still_exists = False
                                    for indicator in popup_indicators:
                                        if await page.locator(indicator).count() > 0:
                                            popup_still_exists = True
                                            break
                                    
                                    if not popup_still_exists:
                                        await job_queue.log_job(job_id, LogLevel.INFO, "Cancel button clicked successfully - popup dismissed")
                                        popup_handled = True
                                        break
                                    else:
                                        await job_queue.log_job(job_id, LogLevel.WARNING, f"Cancel button clicked but popup still present")
                                else:
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"Cancel element {j+1} not visible")
                            except Exception as e:
                                await job_queue.log_job(job_id, LogLevel.INFO, f"Failed to click cancel element {j+1}: {str(e)}")
                                continue
                        
                        if popup_handled:
                            break
                            
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Cancel selector #{i+1} failed: {str(e)}")
                    continue
            
            # Fallback strategies if cancel button didn't work
            if not popup_handled:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Cancel button approach failed, trying fallback methods")
                
                # Strategy 1: Press Escape key
                try:
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(1)
                    await job_queue.log_job(job_id, LogLevel.INFO, "Pressed Escape key to dismiss popup")
                    popup_handled = True
                except Exception:
                    pass
                
                # Strategy 2: Click outside popup area
                if not popup_handled:
                    try:
                        await page.click('body', position={'x': 50, 'y': 50})
                        await asyncio.sleep(1)
                        await job_queue.log_job(job_id, LogLevel.INFO, "Clicked outside popup to dismiss")
                        popup_handled = True
                    except Exception:
                        pass
                
                # Strategy 3: Click on page background
                if not popup_handled:
                    try:
                        await page.click('html', position={'x': 100, 'y': 100})
                        await asyncio.sleep(1)
                        await job_queue.log_job(job_id, LogLevel.INFO, "Clicked on page background to dismiss popup")
                        popup_handled = True
                    except Exception:
                        pass
            
            if popup_handled:
                await job_queue.log_job(job_id, LogLevel.INFO, "Grocery basket popup handled successfully")
            else:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Failed to dismiss grocery basket popup with all methods")
            
            return popup_handled
                
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error handling grocery basket popup: {str(e)}")
            return False

    async def _handle_deals_popup(self, page: Any, job_id: int) -> bool:
        """Fast, non-blocking handler for the 'Amazing Deals' bottom sheet.
        Dismisses it by clicking 'Continue shopping' if present.
        Uses text/role locators for robustness and keeps waits minimal.
        Returns True if a popup was detected and handled.
        """
        try:
            # Quick role-based match first (most reliable and fast)
            btn = page.get_by_role("button", name=re.compile(r"continue\s+shopping", re.I))
            if await btn.count() > 0 and await btn.first.is_visible():
                await job_queue.log_job(job_id, LogLevel.INFO, "Deals popup detected - clicking 'Continue shopping' (role)")
                await btn.first.click(timeout=2000)
                # Short settle time so overlay can close
                await asyncio.sleep(0.4)
                return True

            # Fallback: text-based match
            txt = page.get_by_text(re.compile(r"\bcontinue\s+shopping\b", re.I))
            if await txt.count() > 0 and await txt.first.is_visible():
                await job_queue.log_job(job_id, LogLevel.INFO, "Deals popup detected - clicking 'Continue shopping' (text)")
                await txt.first.click(timeout=2000)
                await asyncio.sleep(0.4)
                return True

            # Heuristic: if we see typical deal indicators, try a generic 'Continue' action
            indicators = [
                re.compile(r"deals\s+unlocked", re.I),
                re.compile(r"basket\s+discount\s+unlocked", re.I),
                re.compile(r"steal\s+deal", re.I),
            ]
            if any([await page.get_by_text(pat).count() > 0 for pat in indicators]):
                cont = page.get_by_role("button", name=re.compile(r"^\s*continue\s*$", re.I))
                if await cont.count() > 0 and await cont.first.is_visible():
                    await job_queue.log_job(job_id, LogLevel.INFO, "Deals popup heuristic - clicking 'Continue'")
                    await cont.first.click(timeout=2000)
                    await asyncio.sleep(0.4)
                    return True

            return False
        except Exception as e:
            # Do not fail the flow for popup handling issues
            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Deals popup handler error: {str(e)}")
            return False

    async def _handle_interruption_popups_fast(self, page: Any, job_id: int) -> bool:
        """Unified fast handler to dismiss common interrupting overlays during quantity changes.
        Prioritizes clicking on 'Continue shopping' or 'Cancel' by role/text with minimal waits.
        Returns True if a dismiss action was taken.
        """
        try:
            # 1) Continue shopping (role-based)
            btn_role = page.get_by_role("button", name=re.compile(r"\bcontinue\s+shop?ping\b", re.I))
            if await btn_role.count() > 0 and await btn_role.first.is_visible():
                await job_queue.log_job(job_id, LogLevel.INFO, "Deals/Grocery popup - clicking 'Continue shopping' (role)")
                await btn_role.first.click(timeout=1500)
                await asyncio.sleep(0.35)
                return True

            # 2) Continue shopping (text-based)
            btn_text = page.get_by_text(re.compile(r"\bcontinue\s+shop?ping\b", re.I))
            if await btn_text.count() > 0 and await btn_text.first.is_visible():
                await job_queue.log_job(job_id, LogLevel.INFO, "Deals/Grocery popup - clicking 'Continue shopping' (text)")
                await btn_text.first.click(timeout=1500)
                await asyncio.sleep(0.35)
                return True

            # 3) Okay, Got it! (role-based)
            ok_role = page.get_by_role("button", name=re.compile(r"\bokay[, ]*\s*got\s*it!?|\bgot\s*it!?", re.I))
            if await ok_role.count() > 0 and await ok_role.first.is_visible():
                await job_queue.log_job(job_id, LogLevel.INFO, "Popup detected - clicking 'Okay, Got it!' (role)")
                await ok_role.first.click(timeout=1500)
                await asyncio.sleep(0.3)
                return True

            # 4) Okay, Got it! (text-based)
            ok_text = page.get_by_text(re.compile(r"\bokay[, ]*\s*got\s*it!?|\bgot\s*it!?", re.I))
            if await ok_text.count() > 0 and await ok_text.first.is_visible():
                await job_queue.log_job(job_id, LogLevel.INFO, "Popup detected - clicking 'Okay, Got it!' (text)")
                await ok_text.first.click(timeout=1500)
                await asyncio.sleep(0.3)
                return True

            # 5) Cancel (role-based)
            cancel_role = page.get_by_role("button", name=re.compile(r"\bcancel\b", re.I))
            if await cancel_role.count() > 0 and await cancel_role.first.is_visible():
                await job_queue.log_job(job_id, LogLevel.INFO, "Popup detected - clicking 'Cancel' (role)")
                await cancel_role.first.click(timeout=1500)
                await asyncio.sleep(0.3)
                return True

            # 6) Cancel (text-based)
            cancel_text = page.get_by_text(re.compile(r"\bcancel\b", re.I))
            if await cancel_text.count() > 0 and await cancel_text.first.is_visible():
                await job_queue.log_job(job_id, LogLevel.INFO, "Popup detected - clicking 'Cancel' (text)")
                await cancel_text.first.click(timeout=1500)
                await asyncio.sleep(0.3)
                return True

            return False
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Fast popup handler error: {str(e)}")
            return False

    async def _verify_actual_quantity(self, page, job_id: int, product_link: str, max_retries: int = 5) -> int:
        """Verify the actual quantity displayed using quantity_display_selectors with robust retry logic"""
        quantity_display_selectors = [
            # Primary selector - most reliable
            '.css-175oi2r.r-1awozwy.r-jwli3a.r-18u37iz.r-1m7hjod.r-1777fci.r-1aockid',
            # Alternative selectors for different page states
            '#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > div > div.css-175oi2r.r-1awozwy.r-jwli3a.r-18u37iz.r-1m7hjod.r-1777fci.r-1aockid',
            '#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div.css-175oi2r.r-1awozwy.r-jwli3a.r-18u37iz.r-1m7hjod.r-1777fci.r-1aockid',
            # Generic selectors
            'div[class*="quantity"]:visible',
            'span[class*="quantity"]:visible',
            'div:has-text("Qty"):visible',
            'input[type="number"]:visible',
            # Text-based fallbacks
            'div:has-text("1"):visible',
            'div:has-text("2"):visible',
            'div:has-text("3"):visible',
            'div:has-text("4"):visible',
            'div:has-text("5"):visible'
        ]
        
        import re
        
        for attempt in range(max_retries):
            await job_queue.log_job(job_id, LogLevel.INFO, f"Quantity verification attempt {attempt + 1}/{max_retries}")
            
            # Wait for UI to stabilize
            await asyncio.sleep(0.8)
            
            for i, selector in enumerate(quantity_display_selectors):
                try:
                    quantity_element = page.locator(selector)
                    element_count = await quantity_element.count()
                    
                    if element_count > 0:
                        # Try each matching element
                        for j in range(min(element_count, 3)):  # Limit to first 3 matches
                            try:
                                element = quantity_element.nth(j)
                                
                                # Check if element is visible
                                if not await element.is_visible():
                                    continue
                                
                                # Get text content
                                quantity_text = await element.inner_text(timeout=2000)
                                if not quantity_text or quantity_text.strip() == "":
                                    continue
                                
                                # Extract numeric value from text
                                quantity_match = re.search(r'\b(\d+)\b', quantity_text.strip())
                                if quantity_match:
                                    actual_quantity = int(quantity_match.group(1))
                                    # Validate reasonable quantity range (1-99)
                                    if 1 <= actual_quantity <= 99:
                                        await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Verified quantity: {actual_quantity} using selector #{i+1} (element {j+1}) for {product_link}")
                                        return actual_quantity
                                    else:
                                        await job_queue.log_job(job_id, LogLevel.WARNING, f"Quantity {actual_quantity} out of valid range (1-99)")
                                        
                            except Exception as e:
                                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Element {j+1} failed: {str(e)}")
                                continue
                                
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Selector #{i+1} failed: {str(e)}")
                    continue
            
            # If we reach here, no valid quantity found in this attempt
            if attempt < max_retries - 1:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Quantity verification attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(1.0)  # Wait longer between retries
        
        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Could not verify quantity after {max_retries} attempts for {product_link}")
        return 0

    async def _adjust_product_quantity(self, page, desired_quantity: int, job_id: int, product_link: str, max_retries: int = 3) -> bool:
        """Helper method to adjust product quantity using mobile grocery selectors with enhanced reliability"""
        minus_button_selectors = [
            "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(1) > div",
            "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(1) > div",
            'div:has-text("-"):visible',
            '[role="button"]:has-text("-"):visible'
        ]
        
        plus_button_selectors = [
            "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af",
            "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af",
            'div:has-text("+"):visible',
            '[role="button"]:has-text("+"):visible'
        ]

        await job_queue.log_job(job_id, LogLevel.INFO, f"🎯 Setting quantity to {desired_quantity} for {product_link}")

        for retry_attempt in range(max_retries):
            try:
                await job_queue.log_job(job_id, LogLevel.INFO, f"Quantity adjustment attempt {retry_attempt + 1}/{max_retries}")
                
                # Get current quantity with enhanced verification
                current_quantity = await self._verify_actual_quantity(page, job_id, product_link, max_retries=3)
                if current_quantity == 0:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Could not determine current quantity, assuming 1")
                    current_quantity = 1
                
                await job_queue.log_job(job_id, LogLevel.INFO, f"Current quantity: {current_quantity}, Target: {desired_quantity}")
                
                # If already at desired quantity, verify and return
                if current_quantity == desired_quantity:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Quantity already at desired value: {desired_quantity}")
                    return True

                # Adjust quantity step by step with verification
                adjustment_successful = True
                
                while current_quantity < desired_quantity:
                    plus_clicked = False
                    
                    # Try each plus button selector
                    for i, selector in enumerate(plus_button_selectors):
                        try:
                            plus_button = page.locator(selector)
                            if await plus_button.count() > 0 and await plus_button.is_visible():
                                await plus_button.scroll_into_view_if_needed()
                                await asyncio.sleep(0.3)
                                try:
                                    await plus_button.click(timeout=2000)
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"➕ Plus button clicked (selector #{i+1})")
                                    # No popup scanning here to keep it fast; we'll react only on failures or no-change
                                    plus_clicked = True
                                    break
                                except Exception as click_err:
                                    # Heuristic: a failed click likely means a popup overlay; try to dismiss and retry fast
                                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Plus click blocked (selector #{i+1}): {str(click_err)}. Attempting popup dismissal and retry.")
                                    await self._handle_interruption_popups_fast(page, job_id)
                                    # Quick retry on the same element
                                    try:
                                        await plus_button.click(timeout=1500)
                                        await job_queue.log_job(job_id, LogLevel.INFO, f"➕ Plus button clicked after popup dismissal (selector #{i+1})")
                                        plus_clicked = True
                                        break
                                    except Exception as retry_err:
                                        await job_queue.log_job(job_id, LogLevel.DEBUG, f"Retry click failed (selector #{i+1}): {str(retry_err)}")
                                        # Try a generic role/text-based fallback quickly
                                        try:
                                            generic_plus = page.get_by_role("button", name=re.compile(r"(add|\+)", re.I))
                                            if await generic_plus.count() > 0 and await generic_plus.first.is_visible():
                                                await generic_plus.first.click(timeout=1500)
                                                await job_queue.log_job(job_id, LogLevel.INFO, "➕ Plus clicked via generic role/text fallback")
                                                plus_clicked = True
                                                break
                                        except Exception as generic_err:
                                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Generic plus fallback failed: {str(generic_err)}")
                        except Exception as e:
                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Plus selector #{i+1} failed: {str(e)}")
                            continue
                    
                    if not plus_clicked:
                        await job_queue.log_job(job_id, LogLevel.ERROR, "❌ Failed to click plus button with any selector")
                        adjustment_successful = False
                        break
                    
                    # Wait for UI update and verify quantity changed
                    await asyncio.sleep(1.0)  # Increased wait time for UI stability
                    
                    # Verify quantity increased
                    new_quantity = await self._verify_actual_quantity(page, job_id, product_link, max_retries=2)
                    if new_quantity > current_quantity:
                        current_quantity = new_quantity
                        await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Quantity successfully increased to: {current_quantity}")
                    else:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Quantity did not increase as expected. Current: {new_quantity}")
                        # One quick attempt to dismiss popups (deals/grocery) before retry
                        await self._handle_interruption_popups_fast(page, job_id)
                        # Try once more before failing
                        await asyncio.sleep(0.5)
                        new_quantity = await self._verify_actual_quantity(page, job_id, product_link, max_retries=1)
                        if new_quantity > current_quantity:
                            current_quantity = new_quantity
                        else:
                            adjustment_successful = False
                            break

                    # Check for quantity limit error
                    error_indicators = [
                        'text="You can buy only up to"',
                        'text="Maximum quantity reached"',
                        'text="Quantity limit exceeded"'
                    ]
                    
                    quantity_limit_hit = False
                    for error_indicator in error_indicators:
                        if await page.locator(error_indicator).count() > 0:
                            error_text = await page.locator(error_indicator).inner_text()
                            await job_queue.log_job(job_id, LogLevel.WARNING, f"Quantity limit hit: {error_text}")
                            quantity_limit_hit = True
                            break
                    
                    if quantity_limit_hit:
                        await job_queue.log_job(job_id, LogLevel.INFO, "Removing item from cart due to quantity limit")
                        # Remove item logic here...
                        return False
                
                # Handle quantity reduction if needed
                while current_quantity > desired_quantity and adjustment_successful:
                    minus_clicked = False
                    
                    for i, selector in enumerate(minus_button_selectors):
                        try:
                            minus_button = page.locator(selector)
                            if await minus_button.count() > 0 and await minus_button.is_visible():
                                await minus_button.scroll_into_view_if_needed()
                                await asyncio.sleep(0.3)
                                
                                await minus_button.click(timeout=3000)
                                await job_queue.log_job(job_id, LogLevel.INFO, f"➖ Minus button clicked (selector #{i+1})")
                                minus_clicked = True
                                break
                        except Exception as e:
                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Minus selector #{i+1} failed: {str(e)}")
                            continue
                    
                    if not minus_clicked:
                        await job_queue.log_job(job_id, LogLevel.ERROR, "❌ Failed to click minus button")
                        adjustment_successful = False
                        break
                    
                    await asyncio.sleep(1.0)
                    new_quantity = await self._verify_actual_quantity(page, job_id, product_link, max_retries=2)
                    if new_quantity < current_quantity:
                        current_quantity = new_quantity
                        await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Quantity successfully decreased to: {current_quantity}")
                    else:
                        adjustment_successful = False
                        break
                
                if adjustment_successful:
                    # Final verification with multiple attempts
                    final_quantity = await self._verify_actual_quantity(page, job_id, product_link, max_retries=5)
                    if final_quantity == desired_quantity:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"🎉 Successfully set quantity to {desired_quantity} for {product_link}")
                        return True
                    else:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Final verification failed. Desired: {desired_quantity}, Actual: {final_quantity}")
                        if retry_attempt < max_retries - 1:
                            await job_queue.log_job(job_id, LogLevel.INFO, "Retrying quantity adjustment...")
                            await asyncio.sleep(2.0)  # Wait before retry
                            continue
                        else:
                            return False
                else:
                    if retry_attempt < max_retries - 1:
                        await job_queue.log_job(job_id, LogLevel.INFO, "Adjustment failed, retrying...")
                        await asyncio.sleep(2.0)
                        continue
                    else:
                        return False
                        
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"Error in quantity adjustment attempt {retry_attempt + 1}: {str(e)}")
                if retry_attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    return False
        
        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Failed to adjust quantity after {max_retries} attempts")
        return False

    async def _check_cart_total_value(self, page, job_id: int, max_cart_value: float = None) -> Dict[str, Any]:
        """Check if cart total exceeds maximum allowed value"""
        if max_cart_value is None:
            return {"success": True, "total": 0, "within_limit": True}
        
        try:
            # Navigate to cart to check total
            cart_url = "https://www.flipkart.com/viewcart"
            await page.goto(cart_url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(3)
            
            # Look for cart total selectors
            total_selectors = [
                '.css-175oi2r.r-1awozwy.r-jwli3a.r-18u37iz.r-1m7hjod.r-1777fci.r-1aockid:has-text("₹")',
                'div[class*="total"]:has-text("₹")',
                'span[class*="total"]:has-text("₹")',
                'div:has-text("Total"):has-text("₹")',
                'span:has-text("Total"):has-text("₹")'
            ]
            
            cart_total = 0
            for selector in total_selectors:
                try:
                    total_element = page.locator(selector)
                    if await total_element.count() > 0:
                        total_text = await total_element.inner_text()
                        # Extract numeric value from text like "₹1,234" or "Total: ₹1,234"
                        import re
                        total_match = re.search(r'₹\s*([0-9,]+)', total_text)
                        if total_match:
                            cart_total = float(total_match.group(1).replace(',', ''))
                            break
                except Exception:
                    continue
            
            within_limit = cart_total <= max_cart_value
            await job_queue.log_job(job_id, LogLevel.INFO, f"Cart total: ₹{cart_total}, Max allowed: ₹{max_cart_value}, Within limit: {within_limit}")
            
            return {
                "success": True,
                "total": cart_total,
                "within_limit": within_limit,
                "max_allowed": max_cart_value
            }
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to check cart total: {str(e)}")
            return {"success": False, "error": str(e)}

    async def add_and_configure_products_in_cart(self, products: List[Dict], job_id: int, max_cart_value: float = None, automation_mode: str = "FLIPKART") -> Dict[str, Any]:
        """
        Phase 2: Navigate to each product page, add it to cart, and configure the quantity.
        Implements strict validation and cancellation conditions:
        1. Cancel if product quantity not met
        2. Cancel if product unavailable/out of stock
        3. Cancel if cart total exceeds max_cart_value
        """
        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot add products to cart: No browser context.")
            await self.browser_manager.capture_failure_screenshot(job_id, "cart_no_context")
            return {"success": False, "error": "No browser context", "cancel_reason": "technical_error"}
        
        page = context.pages[0] if context.pages else await context.new_page()

        total_products = len(products)
        added_products = 0
        unavailable_products = 0
        skipped_products = 0
        failed_quantity_verification = 0
        is_first_product = True  # Track if this is the first product being added

        await job_queue.log_job(job_id, LogLevel.INFO, f"📦 Starting to add {total_products} products to cart...")
        if max_cart_value:
            await job_queue.log_job(job_id, LogLevel.INFO, f"💰 Maximum cart value limit: ₹{max_cart_value}")

        for product in products:
            # Handle both 'link' and 'product_link' keys for backward compatibility
            product_link = product.get('link') or product.get('product_link')
            
            # Ensure product link has the correct marketplace parameter
            if "marketplace=" not in product_link:
                separator = "&" if "?" in product_link else "?"
                product_link = f"{product_link}{separator}marketplace={automation_mode}"
            elif f"marketplace={automation_mode}" not in product_link:
                # Replace existing marketplace if it's different
                product_link = re.sub(r'marketplace=[^&]+', f'marketplace={automation_mode}', product_link)

            desired_quantity = product.get('quantity', 1)
            
            try:
                await job_queue.log_job(job_id, LogLevel.INFO, f"🔍 Processing product: {product_link}")
                
                # Navigate to product page with retry logic
                navigation_success = False
                for nav_attempt in range(3):
                    try:
                        await page.goto(product_link, timeout=60000)
                        await page.wait_for_load_state('domcontentloaded')
                        await asyncio.sleep(3)
                        navigation_success = True
                        break
                    except Exception as nav_error:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"Navigation attempt {nav_attempt + 1} failed: {str(nav_error)}")
                        if nav_attempt < 2:
                            await asyncio.sleep(2)
                            continue
                        else:
                            raise nav_error
                
                if not navigation_success:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Failed to navigate to {product_link}")
                    await self.browser_manager.capture_failure_screenshot(job_id, "cart_navigation_failed")
                    return {"success": False, "error": f"Navigation failed for {product_link}", "cancel_reason": "navigation_failed"}
                
                # Debug: Log page HTML for selector inspection
                # try:
                #     html_content = await page.content()
                #     debug_file_path = f"product_page_debug_{job_id}.html"
                #     with open(debug_file_path, "w", encoding="utf-8") as f:
                #         f.write(html_content)
                #     await job_queue.log_job(job_id, LogLevel.INFO, f"📄 Debug HTML saved to: {debug_file_path}")
                # except Exception as debug_err:
                #     await job_queue.log_job(job_id, LogLevel.WARNING, f"Could not save debug HTML: {str(debug_err)}")
                
                # Check if product is already in cart (quantity controls already visible)
                plus_button_selector = "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af"
                plus_button = page.locator(plus_button_selector)
                
                if await plus_button.count() > 0:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Product {product_link} is already in cart. Adjusting quantity directly.")
                    # Product is already in cart, skip to quantity adjustment
                    if automation_mode == "GROCERY":
                        await job_queue.log_job(job_id, LogLevel.INFO, f"📦 Product already in cart, adjusting quantity on product page...")
                        quantity_success = await self._adjust_product_quantity(page, desired_quantity, job_id, product_link)
                        if not quantity_success:
                            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Quantity verification failed for {product_link}")
                            await self.browser_manager.capture_failure_screenshot(job_id, "cart_quantity_failed")
                            return {"success": False, "error": f"Quantity not met for product {product_link}", "cancel_reason": "quantity_not_met"}
                        
                        # Double-check final quantity after adjustment
                        final_check = await self._verify_actual_quantity(page, job_id, product_link, max_retries=3)
                        if final_check != desired_quantity:
                            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Final quantity check failed. Expected: {desired_quantity}, Got: {final_check}")
                            await self.browser_manager.capture_failure_screenshot(job_id, "cart_final_quantity_mismatch")
                            return {"success": False, "error": f"Final quantity verification failed for {product_link}", "cancel_reason": "quantity_not_met"}
                    else:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"⏭️ Skipping product-page quantity adjustment for Flipkart mode. Will adjust in cart.")
                    
                    added_products += 1
                    is_first_product = False  # No longer first product after processing
                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Product processed (was already in cart): {product_link}")
                    
                    # Wait for backend processing before moving to next product
                    await job_queue.log_job(job_id, LogLevel.INFO, "⏳ Waiting for backend processing...")
                    await asyncio.sleep(3)  # Increased wait time for stability
                    continue

                # Check if product is unavailable or sold out
                unavailable_indicators = [
                    'text="Currently unavailable"',
                    'text="Out of stock"',
                    'text="Sold out"',
                    'text="This item is currently not available"',
                    'text="Temporarily unavailable"'
                ]
                
                product_unavailable = False
                for indicator in unavailable_indicators:
                    try:
                        if await page.locator(indicator).count() > 0:
                            await job_queue.log_job(job_id, LogLevel.WARNING, f"Product unavailable: {product_link} - {indicator}")
                            product_unavailable = True
                            break
                    except Exception:
                        continue
                
                if product_unavailable:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Product unavailable/out of stock: {product_link}")
                    await self.browser_manager.capture_failure_screenshot(job_id, "cart_product_unavailable")
                    return {"success": False, "error": f"Product unavailable: {product_link}", "cancel_reason": "product_unavailable"}

                # Combine all strategies: exact 'Add to cart', specific classes, and generic 'Add'
                # Note: add_button_selector is defined as a fallback string
                add_button_selector_str = "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div"
                
                add_button_selectors = [
                    # Priority 0: Exact text 'Add to cart' (most reliable for recent structure)
                    'text="Add to cart"',
                    # Priority 1: Specific class combination found in the provide HTML
                    '.css-146c3p1.r-dnmrzs.r-1udh08x.r-1udbk01.r-3s2u2q.r-1iln25a',
                    # Priority 2: Style-based selector provided by user
                    'div[style*="border-radius: 0px"][style*="background: linear-gradient(90deg, rgb(255, 255, 255), rgb(255, 255, 255))"]',
                    # Priority 3: Text-based with specific parent hint
                    '.grid-formation div:has-text("Add to cart")',
                    # Priority 4: Existing strategy for 'Add' text
                    'div.css-1rynq56:has-text("Add")',
                    # Priority 5: More specific class combination with 'Add'
                    'div.css-1rynq56.r-dnmrzs.r-1udh08x.r-1udbk01.r-3s2u2q.r-1iln25a:has-text("Add")',
                    # Priority 6: User provided class
                    '.r-1cenzwm',
                    # Priority 7: Parent div with specific classes
                    'div.css-175oi2r.r-1awozwy.r-18u37iz:has-text("Add")',
                    # Priority 8: Original nth-child selector
                    add_button_selector_str,
                    # Priority 9: Generic div with Add text
                    'div:has-text("Add")',
                    # Priority 10: Button-like element with Add
                    '[role="button"]:has-text("Add")'
                ]
                
                click_success = False
                for i, selector in enumerate(add_button_selectors):
                    try:
                        add_button_element = page.locator(selector).first
                        if await add_button_element.count() > 0:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Add button found using strategy #{i+1}: {selector}")
                            
                            # Try to click this specific element
                            await add_button_element.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            
                            try:
                                await add_button_element.click(timeout=8000)
                                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Add button clicked successfully using strategy #{i+1}")
                                click_success = True
                                break # Success! Exit the selector loop
                            except Exception as click_err:
                                await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Strategy #{i+1} found element but click failed: {str(click_err)}. Trying next strategy...")
                                continue # Try next selector in the outer loop
                                
                    except Exception as e:
                        await job_queue.log_job(job_id, LogLevel.DEBUG, f"Add button strategy #{i+1} search failed: {str(e)}")
                        continue
                
                if not click_success:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: All 'Add' button strategies failed for {product_link}")
                    await self.browser_manager.capture_failure_screenshot(job_id, "cart_add_all_strategies_failed")
                    return {"success": False, "error": f"Failed to add product {product_link} after trying all selectors", "cancel_reason": "product_unavailable"}
                
                # If click was successful, continue with popup handling and verification
                try:
                    await asyncio.sleep(2)  # Wait for potential popup or quantity controls
                    
                    # Check for grocery basket popup only for the first product in GROCERY mode
                    if is_first_product and automation_mode == "GROCERY":
                        await job_queue.log_job(job_id, LogLevel.INFO, "🔍 Checking for grocery basket popup (first product only)...")
                        popup_handled = await self._handle_grocery_basket_popup(page, job_id)
                        if not popup_handled:
                            await job_queue.log_job(job_id, LogLevel.WARNING, "Popup handling may have failed, continuing...")
                        await asyncio.sleep(3)  # Wait for quantity controls after popup handling
                    else:
                        if is_first_product:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"⏭️ Skipping grocery popup check for {automation_mode} mode")
                        await asyncio.sleep(2)  # Normal wait for subsequent products or non-grocery

                    
                    # Verify that the product was actually added by checking for quantity controls
                    plus_button_selector = "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af"
                    
                    # Also check for alternative quantity control indicators
                    quantity_indicators = [
                        plus_button_selector,
                        'div:has-text("+")',
                        'div:has-text("-")',
                        '.css-175oi2r.r-1awozwy.r-jwli3a.r-18u37iz.r-1m7hjod.r-1777fci.r-1aockid'  # quantity display
                    ]
                    
                    product_added = False
                    for indicator in quantity_indicators:
                        if await page.locator(indicator).count() > 0:
                            product_added = True
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Product successfully added to cart - quantity controls detected")
                            break
                    
                    if not product_added:
                        # Additional verification attempts
                        await job_queue.log_job(job_id, LogLevel.WARNING, "Quantity controls not found, performing additional verification...")
                        await asyncio.sleep(2)
                        
                        # Try alternative verification
                        for verify_attempt in range(3):
                            for indicator in quantity_indicators:
                                if await page.locator(indicator).count() > 0:
                                    product_added = True
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Product verification successful on attempt {verify_attempt + 1}")
                                    break
                            if product_added:
                                break
                            await asyncio.sleep(1)
                        
                        if not product_added:
                            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Product not added to cart for {product_link} - no quantity controls found after verification.")
                            return {"success": False, "error": f"Product not added to cart: {product_link}", "cancel_reason": "product_not_added"}
                        
                except Exception as verify_err:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Verification failed for {product_link}: {str(verify_err)}")
                    return {"success": False, "error": f"Verification failed for {product_link}: {str(verify_err)}", "cancel_reason": "verification_failed"}

                # 1.b) Now manipulate the quantity using mobile grocery selectors
                if automation_mode == "GROCERY":
                    await job_queue.log_job(job_id, LogLevel.INFO, f"🔧 Adjusting quantity for newly added product (Grocery)...")
                    quantity_success = await self._adjust_product_quantity(page, desired_quantity, job_id, product_link)
                    if not quantity_success:
                        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Quantity verification failed for {product_link}")
                        return {"success": False, "error": f"Quantity not met for product {product_link}", "cancel_reason": "quantity_not_met"}
                    
                    # Triple-check final quantity after adjustment (critical verification)
                    await asyncio.sleep(1)  # Allow UI to fully update
                    final_check = await self._verify_actual_quantity(page, job_id, product_link, max_retries=5)
                    if final_check != desired_quantity:
                        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Critical final quantity check failed. Expected: {desired_quantity}, Got: {final_check}")
                        return {"success": False, "error": f"Critical quantity verification failed for {product_link}", "cancel_reason": "quantity_not_met"}
                else:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"⏭️ Skipping product-page quantity adjustment for Flipkart mode. Will adjust in cart.")

                
                # Product successfully added and configured
                added_products += 1
                is_first_product = False  # No longer first product after successful addition
                
                # Log success based on mode
                status_msg = f"(Quantity: {final_check})" if automation_mode == "GROCERY" else "(Quantity will be set in cart)"
                await job_queue.log_job(job_id, LogLevel.INFO, f"🎉 Product successfully added: {product_link} {status_msg}")
                
                # Wait for backend processing before moving to next product
                await job_queue.log_job(job_id, LogLevel.INFO, "⏳ Waiting for backend processing...")
                await asyncio.sleep(3)  # Increased wait time for stability


            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Failed to process product {product_link}: {str(e)}")
                
                # Log detailed error information for debugging
                import traceback
                error_details = traceback.format_exc()
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Detailed error trace: {error_details}")
                
                return {"success": False, "error": f"Failed to process product {product_link}: {str(e)}", "cancel_reason": "processing_error"}

        # Note: Cart total validation is handled in checkout_handler.py after offers are applied
        # This ensures accurate total calculation including all discounts and offers
        
        # Only perform critical failure check here; final summary will be logged after checkout
        if added_products == 0:
            await job_queue.log_job(job_id, LogLevel.ERROR, "❌ AUTOMATION CANCELLED: No products were successfully added to cart!")
            return {"success": False, "error": "No products added to cart", "cancel_reason": "no_products_added"}

        # Navigate to cart after all products are processed
        if automation_mode == "FLIPKART":
            await self._navigate_to_cart_safely(page, job_id, automation_mode)
        else:
            marketplace = "GROCERY" if automation_mode == "GROCERY" else "FLIPKART"
            await job_queue.log_job(job_id, LogLevel.INFO, f"Navigating to {marketplace.lower()} cart...")
            cart_url = f"https://www.flipkart.com/viewcart?marketplace={marketplace}"
            await page.goto(cart_url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(3)

        # For Flipkart, adjust quantities in the cart
        if automation_mode == "FLIPKART":
            await job_queue.log_job(job_id, LogLevel.INFO, "🛒 Adjusting quantities in the Flipkart cart...")
            await self.set_cart_quantities_flipkart(page, job_id, products)

        return {"success": True, "added_products": added_products, "total_products": total_products}

    async def set_cart_quantities_flipkart(self, page: Any, job_id: int, products: List[Dict]) -> bool:
        """Set quantities for Flipkart products directly in the cart using the Qty dropdown."""
        try:
            # Re-ensure we're on the cart page
            if "viewcart" not in page.url:
                await self._navigate_to_cart_safely(page, job_id, "FLIPKART")

            # Find all item cards in the cart
            item_cards_selector = 'div.css-g5y9jx.r-14lw9ot'
            cards = page.locator(item_cards_selector)
            card_count = await cards.count()
            
            if card_count == 0:
                await job_queue.log_job(job_id, LogLevel.WARNING, "No item cards found in cart for quantity adjustment")
                return False

            await job_queue.log_job(job_id, LogLevel.INFO, f"Scanning {card_count} items in cart for quantity adjustment...")

            for i in range(card_count):
                card = cards.nth(i)
                try:
                    # Get product name and variant (sometimes split in two divs)
                    # User HTML: <div dir="auto" class="css-146c3p1 r-dnmrzs r-1udh08x r-1udbk01 r-3s2u2q r-1iln25a r-cqee49 r-1et8rh5 r-ubezar">SOFTSPUN Microfiber Vehicle Washing  Cloth </div>
                    name_selector = 'div.css-146c3p1.r-dnmrzs.r-1udh08x.r-1udbk01.r-3s2u2q.r-1iln25a, div.r-cqee49.r-1et8rh5.r-ubezar'
                    name_locs = card.locator(name_selector)
                    
                    name_texts = []
                    for ni in range(await name_locs.count()):
                        name_texts.append(await name_locs.nth(ni).inner_text())
                    
                    if not name_texts:
                        # Fallback: search any text div that doesn't contain "Qty:" or "₹" or "Deal"
                        name_candidates = card.locator('div.css-146c3p1')
                        for ni in range(await name_candidates.count()):
                            txt = await name_candidates.nth(ni).inner_text()
                            if len(txt) > 15 and "Qty:" not in txt and "₹" not in txt and "Deal" not in txt:
                                name_texts.append(txt)
                    
                    if not name_texts:
                        continue
                    
                    # Combine all name parts and normalize whitespace (handles double spaces)
                    import re
                    cart_product_name = re.sub(r'\s+', ' ', ' '.join(name_texts)).strip().lower()
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Checking cart item: {cart_product_name[:60]}...")

                    # Find matching product in the list using word overlap (Token Matching)
                    target_product = None
                    best_overlap = 0.0
                    
                    def get_tokens(s):
                        return set(re.findall(r'\w+', s.lower()))

                    cart_tokens = get_tokens(cart_product_name)
                    
                    for p in products:
                        # Check multiple field names for robustness
                        p_name = p.get('product_name') or p.get('name') or p.get('title', '')
                        if not p_name: continue
                        
                        req_tokens = get_tokens(p_name)
                        if not req_tokens: continue
                        
                        intersection = cart_tokens.intersection(req_tokens)
                        overlap = len(intersection) / len(req_tokens)
                        
                        if overlap > best_overlap:
                            best_overlap = overlap
                            if overlap >= 0.5: # 50% or more words must match
                                target_product = p
                    
                    if not target_product:
                        # If no direct name match, try checking the first product if there's only one
                        if len(products) == 1:
                            target_product = products[0]
                            await job_queue.log_job(job_id, LogLevel.DEBUG, "Auto-matching single product in list")
                        else:
                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"No match for '{cart_product_name[:30]}' (Best overlap: {best_overlap:.2f}, Cart Tokens: {list(cart_tokens)[:5]}...)")
                            continue

                    desired_qty = target_product.get('quantity', 1)
                    if desired_qty <= 1:
                        # Already 1 by default, check if we need to do anything
                        qty_text_loc = card.locator('div:has-text("Qty:")').first
                        if await qty_text_loc.count() > 0:
                            current_qty_text = await qty_text_loc.inner_text()
                            if f"Qty: {desired_qty}" in current_qty_text:
                                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ '{cart_product_name[:30]}' is already at Qty: {desired_qty}")
                                continue

                    await job_queue.log_job(job_id, LogLevel.INFO, f"⚙️ Setting quantity for '{cart_product_name[:30]}' to {desired_qty}...")

                    # Find Qty dropdown in this card
                    qty_selector = 'div.css-146c3p1:has-text("Qty:")'
                    qty_dropdown = card.locator(qty_selector).first
                    
                    if await qty_dropdown.count() == 0:
                        qty_dropdown = card.locator('div:has-text("Qty:")').first
                    
                    if await qty_dropdown.count() > 0:
                        await qty_dropdown.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        
                        # Click the interactive parent if possible
                        try:
                            interactive_parent = qty_dropdown.locator('xpath=ancestor::div[@style*="cursor: pointer"]').first
                            if await interactive_parent.count() > 0:
                                await interactive_parent.click()
                            else:
                                await qty_dropdown.click()
                        except Exception:
                            await qty_dropdown.click()
                        
                        await job_queue.log_job(job_id, LogLevel.DEBUG, "Clicked Qty dropdown")
                        await asyncio.sleep(1.5) # Wait for selection sheet

                        # Now look for the quantity option in the bottom sheet
                        option_clicked = False
                        
                        # Priority selection: Only pick the option if it's the target number
                        num_regex = re.compile(f"^\\s*{desired_qty}\\s*$")
                        
                        # Only try direct selection for 1, 2, 3 as these are always present
                        if desired_qty <= 3:
                            try:
                                options = page.locator('div.css-146c3p1').filter(has_text=num_regex)
                                if await options.count() > 0:
                                    await options.first.scroll_into_view_if_needed()
                                    await options.first.click(force=True)
                                    option_clicked = True
                            except Exception:
                                pass

                        if not option_clicked:
                            # If desired quantity > 3 or wasn't found directly, look for 'More' or '10+'
                            try:
                                more_patterns = [
                                    re.compile(r"10\+", re.I),
                                    re.compile(r"More", re.I),
                                    re.compile(r"^[4-9]\s*$", re.I) # Sometimes 4, 5 etc can be selected directly too
                                ]
                                
                                # Try direct match first for any number
                                direct_opt = page.locator('div.css-146c3p1').filter(has_text=num_regex).first
                                if await direct_opt.count() > 0:
                                    await direct_opt.click(force=True)
                                    option_clicked = True
                                
                                if not option_clicked:
                                    # Fallback to "More" button
                                    for pattern in [re.compile(r"More", re.I), re.compile(r"10\+", re.I)]:
                                        more_opt = page.locator('div.css-146c3p1').filter(has_text=pattern).first
                                        if await more_opt.count() > 0:
                                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"Clicking 'More' quantity option")
                                            await more_opt.click(force=True)
                                            await asyncio.sleep(1.2)
                                            
                                            # Manual Input Field
                                            qty_input = page.locator('input[placeholder="Quantity"], input[type="number"], input[role="spinbutton"]').first
                                            if await qty_input.count() > 0:
                                                await qty_input.fill(str(desired_qty))
                                                await asyncio.sleep(0.5)
                                                # Click APPLY
                                                apply_btn = page.locator('div:has-text("APPLY"), [role="button"]:has-text("APPLY")').last
                                                if await apply_btn.count() > 0:
                                                    try:
                                                        parent_clickable = apply_btn.locator('xpath=./ancestor-or-self::div[contains(@style, "cursor: pointer")]').last
                                                        if await parent_clickable.count() > 0:
                                                            await parent_clickable.click(force=True)
                                                        else:
                                                            await apply_btn.click(force=True)
                                                    except Exception:
                                                        await apply_btn.click(force=True)
                                                        
                                                    option_clicked = True
                                                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Manually set quantity to {desired_qty}")
                                            break
                            except Exception as e:
                                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Failed to select quantity: {e}")

                        if option_clicked:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Quantity updated to {desired_qty}")
                            await asyncio.sleep(2.5) # Wait for cart update
                        else:
                            await job_queue.log_job(job_id, LogLevel.WARNING, f"❌ Could not find option '{desired_qty}'")
                    else:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"❌ Could not find Qty dropdown for '{cart_product_name[:30]}'")

                except Exception as card_err:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Error processing cart item {i+1}: {str(card_err)}")
                    continue

            return True
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error adjusting cart quantities: {str(e)}")
            return False

