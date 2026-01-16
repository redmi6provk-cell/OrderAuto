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

    async def clear_cart_if_needed(self, job_id: int) -> dict:
        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            return {"success": False, "performed": False, "error": "no_context"}
        page = context.pages[0] if context.pages else await context.new_page()

        await job_queue.log_job(job_id, LogLevel.INFO, "Navigating to cart page to check and clear if needed...")

        try:
            await page.goto('https://www.flipkart.com/viewcart?marketplace=GROCERY', wait_until='domcontentloaded')
            await asyncio.sleep(1.0)

            async def is_empty() -> bool:
                try:
                    if await page.get_by_text("Your basket is empty").count() > 0:
                        return True
                    try:
                        header = await page.locator('#guidSearch > div > h1').inner_text()
                        if "Grocery basket" in header and "item" not in header:
                            return True
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
            max_attempts = 20  # Increased attempts to handle more items

            for attempt in range(max_attempts):
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

                made_progress = False

                # Try Remove buttons first
                try:
                    btns = page.get_by_text("Remove", exact=True)
                    cnt = await btns.count()
                    if cnt == 0:
                        btns = page.get_by_role("button", name=re.compile(r"^Remove$", re.I))
                        cnt = await btns.count()
                    
                    if cnt > 0:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found {cnt} Remove button(s)")
                        for i in range(cnt):
                            try:
                                b = btns.nth(i)
                                # Scroll button into view
                                await b.scroll_into_view_if_needed()
                                await asyncio.sleep(0.2)
                                
                                if await b.is_visible(timeout=1000):
                                    await b.click(timeout=2000)
                                    removed += 1
                                    made_progress = True
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"Clicked Remove button {i+1}")
                                    await asyncio.sleep(0.5)
                            except Exception as e:
                                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Failed to click Remove {i+1}: {e}")
                                continue
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Remove button search failed: {e}")

                # Try minus buttons to decrement quantities to 0
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
                        imgs = cart_area.locator('img[src*="beb19156-518d-4110-bceb"]')
                        ic = await imgs.count()
                        for i in range(ic):
                            try:
                                parent = imgs.nth(i).locator('xpath=..')
                                if await parent.count() > 0:
                                    minus_buttons.append(parent.first)
                            except Exception:
                                continue
                    
                    if len(minus_buttons) > 0:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found {len(minus_buttons)} minus button(s)")
                        
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
            await page.goto('https://www.flipkart.com/viewcart?marketplace=GROCERY', wait_until='domcontentloaded')
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
            cart_url = "https://www.flipkart.com/viewcart?marketplace=GROCERY"
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

    async def add_and_configure_products_in_cart(self, products: List[Dict], job_id: int, max_cart_value: float = None) -> Dict[str, Any]:
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
                
                # Check if product is already in cart (quantity controls already visible)
                plus_button_selector = "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af"
                plus_button = page.locator(plus_button_selector)
                
                if await plus_button.count() > 0:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Product {product_link} is already in cart. Adjusting quantity directly.")
                    # Product is already in cart, skip to quantity adjustment
                    await job_queue.log_job(job_id, LogLevel.INFO, f"📦 Product already in cart, adjusting quantity...")
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
                    
                    added_products += 1
                    is_first_product = False  # No longer first product after processing
                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Product quantity adjusted successfully (was already in cart): {product_link}")
                    
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

                # 1.a) Click on 'Add' button to add product to cart (Mobile Grocery Flow)
                add_button_selector = "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div"
                
                # Check for Add button with multiple strategies
                add_button_selectors = [
                    # Priority 1: Class-based selector (user provided)
                    '.r-1cenzwm',
                    # Priority 2: Class-based selector from provided HTML structure
                    'div.css-1rynq56:has-text("Add")',
                    # Priority 3: Text-based selector
                    'text="Add"',
                    # Priority 4: More specific class combination
                    'div.css-1rynq56.r-dnmrzs.r-1udh08x.r-1udbk01.r-3s2u2q.r-1iln25a:has-text("Add")',
                    # Priority 5: Parent div with specific classes
                    'div.css-175oi2r.r-1awozwy.r-18u37iz:has-text("Add")',
                    # Priority 6: Original nth-child selector as fallback
                    add_button_selector,
                    # Priority 7: Generic div with Add text
                    'div:has-text("Add")',
                    # Priority 8: Button-like element with Add
                    '[role="button"]:has-text("Add")'
                ]
                
                add_button_found = False
                add_button_element = None
                
                for i, selector in enumerate(add_button_selectors):
                    try:
                        add_button_element = page.locator(selector)
                        if await add_button_element.count() > 0:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Add button found using strategy #{i+1}: {selector}")
                            add_button_found = True
                            break
                    except Exception as e:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Add button strategy #{i+1} failed: {str(e)}")
                        continue
                
                if not add_button_found:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: 'Add' button not found for {product_link}. Product may be unavailable.")
                    await self.browser_manager.capture_failure_screenshot(job_id, "cart_add_button_not_found")
                    return {"success": False, "error": f"Add button not found for product {product_link}", "cancel_reason": "product_unavailable"}
                
                await job_queue.log_job(job_id, LogLevel.INFO, "Clicking 'Add' button")
                try:
                    # Enhanced click with retry mechanism
                    click_success = False
                    for click_attempt in range(3):
                        try:
                            await add_button_element.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            await add_button_element.click(timeout=10000)
                            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Add button clicked successfully (attempt {click_attempt + 1})")
                            click_success = True
                            break
                        except Exception as click_err:
                            await job_queue.log_job(job_id, LogLevel.WARNING, f"Add button click attempt {click_attempt + 1} failed: {str(click_err)}")
                            if click_attempt < 2:
                                await asyncio.sleep(1)
                                continue
                    
                    if not click_success:
                        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION STOPPED: Add button found but failed to click after 3 attempts for {product_link}")
                        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ PRODUCT MARKED AS OUT OF STOCK: Product may be unavailable or experiencing technical issues")
                        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ ACCOUNT AUTOMATION CANCELLED: Unable to add product to cart")
                        await self.browser_manager.capture_failure_screenshot(job_id, "cart_add_button_click_failed")
                        return {"success": False, "error": f"Add button click failed after 3 attempts for product {product_link}", "cancel_reason": "product_out_of_stock"}
                    
                    await asyncio.sleep(2)  # Wait for potential popup or quantity controls
                    
                    # Check for grocery basket popup only for the first product
                    if is_first_product:
                        await job_queue.log_job(job_id, LogLevel.INFO, "🔍 Checking for grocery basket popup (first product only)...")
                        popup_handled = await self._handle_grocery_basket_popup(page, job_id)
                        if not popup_handled:
                            await job_queue.log_job(job_id, LogLevel.WARNING, "Popup handling may have failed, continuing...")
                        await asyncio.sleep(3)  # Wait for quantity controls after popup handling
                    else:
                        await job_queue.log_job(job_id, LogLevel.INFO, "⏭️ Skipping popup check (not first product)")
                        await asyncio.sleep(2)  # Shorter wait for subsequent products
                    
                    # Verify that the product was actually added by checking for quantity controls
                    plus_button_selector = "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af"
                    plus_button = page.locator(plus_button_selector)
                    
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
                        
                except Exception as click_error:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Failed to click 'Add' button for {product_link}: {str(click_error)}")
                    return {"success": False, "error": f"Failed to add product {product_link}: {str(click_error)}", "cancel_reason": "add_button_failed"}

                # 1.b) Now manipulate the quantity using mobile grocery selectors
                await job_queue.log_job(job_id, LogLevel.INFO, f"🔧 Adjusting quantity for newly added product...")
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
                
                # Product successfully added and configured
                added_products += 1
                is_first_product = False  # No longer first product after successful addition
                await job_queue.log_job(job_id, LogLevel.INFO, f"🎉 Product successfully added and configured: {product_link} (Quantity: {final_check})")
                
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
        await job_queue.log_job(job_id, LogLevel.INFO, "Navigating to grocery cart...")
        cart_url = "https://www.flipkart.com/viewcart?marketplace=GROCERY"
        await page.goto(cart_url, timeout=60000)
        await page.wait_for_load_state('domcontentloaded')
        await asyncio.sleep(3)

        return {"success": True, "added_products": added_products, "total_products": total_products}
