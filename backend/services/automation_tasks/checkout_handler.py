"""
Checkout Handler Module
Handles address selection, payment processing, and order confirmation
"""

import asyncio
from typing import Any, Optional, Dict
import asyncpg
from urllib.parse import urlparse, parse_qs

from services.job_queue import job_queue, LogLevel
from database import DATABASE_URL


class CheckoutHandler:
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        self.settings_cache = None

    async def load_address_configuration(self, job_id: int, address_id: Optional[int] = None) -> bool:
        """Load address configuration from addresses table - REQUIRED for proper address validation"""
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            
            # Load address configuration
            if address_id:
                address = await conn.fetchrow('''
                    SELECT * FROM addresses 
                    WHERE id = $1 AND is_active = TRUE
                ''', address_id)
            else:
                # Use default address
                address = await conn.fetchrow('''
                    SELECT * FROM addresses 
                    WHERE is_default = TRUE AND is_active = TRUE
                    LIMIT 1
                ''')
                
                if not address:
                    # Fallback to first active address
                    address = await conn.fetchrow('''
                        SELECT * FROM addresses 
                        WHERE is_active = TRUE
                        ORDER BY created_at ASC
                        LIMIT 1
                    ''')
            
            await conn.close()
            
            if not address:
                await job_queue.log_job(job_id, LogLevel.ERROR, "❌ AUTOMATION CANCELLED: No active address configuration found")
                await self.browser_manager.capture_failure_screenshot(job_id, "checkout_no_address_config")
                return False
            
            # Store address configuration in settings_cache format for compatibility
            self.settings_cache = {
                'address_template': address['address_template'],
                'name_postfix': address['name_postfix'],
                'pincode': address['pincode'],
                'address_name': address['name'],
                'address_id': address['id']
            }
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Loaded address '{address['name']}': name_postfix='{address['name_postfix']}', pincode='{address['pincode']}'")
            return True
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Failed to load address configuration: {str(e)}")
            await self.browser_manager.capture_failure_screenshot(job_id, "checkout_address_config_error")
            return False

    async def select_correct_address(self, job_id: int, address_id: Optional[int] = None, retry_count: int = 0, automation_mode: str = "FLIPKART") -> bool:
        """Select the correct delivery address at cart/checkout and verify it.
        Opens the "Change" sheet, picks the configured address, and confirms selection."""
        # Load address configuration first - CRITICAL for validation
        address_loaded = await self.load_address_configuration(job_id, address_id)
        if not address_loaded:
            await job_queue.log_job(job_id, LogLevel.ERROR, "❌ AUTOMATION CANCELLED: Cannot proceed without address configuration")
            await self.browser_manager.capture_failure_screenshot(job_id, "checkout_address_not_loaded")
            return False
        
        # Strict mode: if a specific address_id was provided, require postfix match
        strict_postfix = bool(address_id)

        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot verify address: No browser context.")
            await self.browser_manager.capture_failure_screenshot(job_id, "checkout_no_context")
            return False
        
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            # Ensure we're on cart/checkout page first
            current_url = page.url
            await job_queue.log_job(job_id, LogLevel.INFO, f"Current page: {current_url}")
            
            # Wait for page to be fully loaded
            try:
                # Wait for key checkout elements to ensure page is ready
                await page.wait_for_load_state('domcontentloaded', timeout=10000)
                await asyncio.sleep(1.0)  # Additional settle time
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Page load wait timeout: {e}")
            
            # Verify we're on the right page (cart or checkout)
            if 'viewcart' not in current_url.lower() and 'checkout' not in current_url.lower():
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Not on cart/checkout page. Current URL: {current_url}")
                # Try to navigate to cart safely
                await self._navigate_to_cart_safely(page, job_id, automation_mode)
            
                # Check if marketplace param exists and is correct
                current_url = page.url # Update URL after navigation
                correct_marketplace = automation_mode.lower()
                is_wrong_marketplace = False
                
                if 'exploreMode=true' in current_url:
                    is_wrong_marketplace = True
                elif 'marketplace=' in current_url:
                    # If it's regular Flipkart, we want it NOT to have 'grocery' or to have 'FLIPKART'
                    if correct_marketplace == 'grocery':
                        if 'grocery' not in current_url.lower():
                            is_wrong_marketplace = True
                    else:
                        if 'grocery' in current_url.lower():
                            is_wrong_marketplace = True

                if is_wrong_marketplace:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Wrong marketplace cart detected. Redirecting safely to {automation_mode} cart...")
                    await self._navigate_to_cart_safely(page, job_id, automation_mode)
            
            await job_queue.log_job(job_id, LogLevel.INFO, "Selecting delivery address at checkout…")

            # Helper: read current address text if available
            async def get_current_address_text() -> str:
                selectors = [
                    'div[data-testid="address-summary"]',
                    'div:has-text("Deliver to")',
                    'div:has-text("Delivering to")',
                ]
                for sel in selectors:
                    try:
                        el = page.locator(sel)
                        if await el.count() > 0:
                            txt = (await el.first.inner_text()).strip()
                            if txt:
                                return txt
                    except Exception:
                        continue
                return ""

            # If already correct, short-circuit
            current_text = await get_current_address_text()
            if current_text and self._is_correct_address(current_text, require_postfix=strict_postfix):
                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Address already correct, no change needed.")
                return True

            # Open the Change selector on cart/checkout
            opened = False
            change_selectors = [
                'button:has-text("Change")',
                'text="Change"',
                '#_parentCtr_ button:has-text("Change")',
                'div:has-text("Change")'
            ]
            for sel in change_selectors:
                try:
                    loc = page.locator(sel)
                    if await loc.count() > 0:
                        # Ensure it's visible and clickable
                        if await loc.first.is_visible(timeout=2000):
                            await loc.first.click(timeout=3000)
                            opened = True
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Opened Change sheet using: {sel}")
                            await asyncio.sleep(0.6)
                            break
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Change selector failed ({sel}): {e}")
                    continue
            if not opened:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Could not find 'Change' control. Checking if cart is empty or wrong marketplace...")
                
                # Check if we accidentally landed on wrong cart (empty)
                try:
                    # Check for grocery cart indicator only if in GROCERY mode
                    if automation_mode == "GROCERY":
                        grocery_indicator = page.locator('text="Grocery basket"')
                        if await grocery_indicator.count() == 0:
                            await job_queue.log_job(job_id, LogLevel.WARNING, "Grocery basket not detected. Might be on wrong cart. Redirecting...")
                            await page.goto('https://www.flipkart.com/viewcart?marketplace=GROCERY', wait_until='domcontentloaded')
                            await asyncio.sleep(2.0)
                    else:
                        # For regular Flipkart, we might want to check for "My Cart" or similar
                        flipkart_indicator = page.locator('text="My Cart", text="Flipkart (")')
                        if await flipkart_indicator.count() == 0:
                            await job_queue.log_job(job_id, LogLevel.WARNING, "Flipkart cart not detected. Might be on wrong cart. Redirecting...")
                            await page.goto('https://www.flipkart.com/viewcart?marketplace=FLIPKART', wait_until='domcontentloaded')
                            await asyncio.sleep(2.0)
                        
                        # Retry opening Change control after redirect
                        for sel in change_selectors:
                            try:
                                loc = page.locator(sel)
                                if await loc.count() > 0:
                                    if await loc.first.is_visible(timeout=2000):
                                        await loc.first.click(timeout=3000)
                                        opened = True
                                        await job_queue.log_job(job_id, LogLevel.INFO, f"Opened Change sheet after redirect using: {sel}")
                                        await asyncio.sleep(0.6)
                                        break
                            except Exception:
                                continue
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Grocery basket check error: {e}")
                
                if not opened:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Still could not find 'Change' control. Proceeding to verify only.")
                    # Fall back to verification only
                    current_text = await get_current_address_text()
                    if current_text and self._is_correct_address(current_text, require_postfix=strict_postfix):
                        return True
                    return not strict_postfix

            # Wait for the address sheet to appear
            try:
                await page.wait_for_selector('#_parentCtr_', timeout=5000)
                await asyncio.sleep(0.4)  # Let sheet fully render
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Address sheet did not appear: {e}")
                # Try to proceed anyway
                pass

            # Expand more addresses if present
            try:
                see_more_variants = [
                    'text="See more"',
                    'text="more addresses"',
                    '#_parentCtr_ > div:nth-child(1) > div > div > div > div.css-175oi2r.r-13awgt0.r-eqz5dr.r-ymttw5.r-1ygmrgt > div:nth-child(2) > div > div'
                ]
                for sm in see_more_variants:
                    btn = page.locator(sm)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click()
                        await asyncio.sleep(0.6)
                        break
            except Exception:
                pass

            # Try to click matching address by scanning listed entries
            def build_front_selector(i: int) -> str:
                base = '#_parentCtr_ > div:nth-child(1) > div > div > div > div.css-175oi2r.r-13awgt0.r-eqz5dr.r-ymttw5.r-1ygmrgt > div.css-175oi2r'
                return f"{base} > div:nth-child({i}) > div"

            def build_more_selector(i: int) -> str:
                base = '#_parentCtr_ > div:nth-child(1) > div > div > div > div:nth-child(2) > div'
                return f"{base} > div:nth-child({i})"

            async def address_text_matches(el, idx: int = 0) -> bool:
                try:
                    txt = (await el.inner_text()).lower()
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Address {idx}: {txt[:80]}...")
                except Exception:
                    return False
                postfix = (self.settings_cache.get('name_postfix') or '').lower().strip()
                pin = (self.settings_cache.get('pincode') or '').strip()
                if strict_postfix and postfix:
                    matches = postfix in txt
                    if matches:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found match at address {idx} (postfix: '{postfix}')")
                    return matches
                # otherwise, match by postfix or pincode
                matches = (postfix and postfix in txt) or (pin and pin in txt)
                if matches:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Found match at address {idx}")
                return matches

            selected = False
            await job_queue.log_job(job_id, LogLevel.INFO, "Scanning visible addresses...")
            # First, try the first 6 visible entries
            for i in range(1, 7):
                try:
                    sel = build_front_selector(i)
                    el = page.locator(sel)
                    if await el.count() == 0:
                        continue
                    if await address_text_matches(el.first, idx=i):
                        await el.first.click()
                        selected = True
                        await asyncio.sleep(0.6)
                        break
                except Exception:
                    continue

            # If not selected, scan the expanded list (up to 20)
            if not selected:
                await job_queue.log_job(job_id, LogLevel.INFO, "Scanning expanded address list...")
                for i in range(1, 21):
                    try:
                        sel = build_more_selector(i)
                        el = page.locator(sel)
                        if await el.count() == 0:
                            await job_queue.log_job(job_id, LogLevel.DEBUG, f"No more addresses found at position {i}")
                            break
                        if await address_text_matches(el.first, idx=i):
                            await el.first.click()
                            selected = True
                            await asyncio.sleep(0.6)
                            break
                    except Exception:
                        continue

            if not selected:
                if retry_count == 0:
                    # First attempt - signal that address needs to be created
                    await job_queue.log_job(job_id, LogLevel.WARNING, "No matching address found in sheet. Will attempt to create it.")
                    # Close sheet first
                    try:
                        await page.mouse.click(50, 50)
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass
                    return False  # Signal to caller to create address
                else:
                    # Retry after address creation - proceed with what we have
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Address still not found after creation. Proceeding with current address.")
                    return not strict_postfix

            # After selecting, sheet should close. Wait and verify.
            await asyncio.sleep(1.2)
            
            # Verify sheet closed
            try:
                sheet_still_open = await page.locator('#_parentCtr_').is_visible(timeout=1000)
                if sheet_still_open:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Address sheet still open - clicking outside to close")
                    await page.mouse.click(50, 50)
                    await asyncio.sleep(0.5)
            except Exception:
                # Sheet closed = good
                pass
            
            # Final verification
            final_text = await get_current_address_text()
            if final_text and self._is_correct_address(final_text, require_postfix=strict_postfix):
                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Address selected and verified at checkout")
                return True
            else:
                if strict_postfix:
                    name_postfix = self.settings_cache.get('name_postfix', '')
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Selected address does not match required postfix '{name_postfix}'")
                    await self.browser_manager.capture_failure_screenshot(job_id, "checkout_address_select_mismatch")
                    return False
                await job_queue.log_job(job_id, LogLevel.WARNING, "Address selection verification relaxed - proceeding")
                return True
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error during address verification: {str(e)}")
            await self.browser_manager.capture_failure_screenshot(job_id, "checkout_address_verify_error")
            return False

    async def _navigate_to_cart_safely(self, page: Any, job_id: int, automation_mode: str):
        """Navigate to Home page first, then to the Cart to bypass interstitial ads."""
        try:
            await job_queue.log_job(job_id, LogLevel.INFO, "🏠 Resetting navigation via Home page...")
            await page.goto('https://www.flipkart.com/', wait_until='domcontentloaded')
            await asyncio.sleep(1.0)
            
            cart_url = f'https://www.flipkart.com/viewcart?marketplace={automation_mode}'
            await job_queue.log_job(job_id, LogLevel.INFO, f"🛒 Navigating to cart: {cart_url}")
            await page.goto(cart_url, wait_until='domcontentloaded')
            await asyncio.sleep(1.5)
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed safe navigation: {str(e)}")

    def _is_correct_address(self, address_text: str, require_postfix: bool = False) -> bool:
        """Check if the address text matches our criteria using database settings.
        If require_postfix is True, only accept matches that contain the configured name_postfix."""
        if not self.settings_cache:
            return False
            
        address_lower = address_text.lower()
        
        # Get settings from cache
        name_postfix = self.settings_cache.get('name_postfix', '').lower()
        pincode = self.settings_cache.get('pincode', '')
        address_template = self.settings_cache.get('address_template', '').lower()
        
        # Strict requirement: postfix must be present
        if require_postfix:
            return bool(name_postfix) and (name_postfix in address_lower)
        
        # Flexible matching (legacy behavior)
        # Check for name postfix (e.g., "Shivshakti") with any prefix name
        if name_postfix and name_postfix in address_lower:
            return True
        
        # Check for specific pincode from settings
        if pincode and pincode in address_text:
            return True
        
        # Check for key parts of address template (e.g., "metha chamber", "Dana Bunder")
        template_keywords = ["metha chamber", "dana bunder", "masjid bandar"]
        for keyword in template_keywords:
            if keyword in address_lower:
                return True
                
        return False

    async def validate_cart_total(self, page: Any, job_id: int, max_cart_value: Optional[float] = None) -> bool:
        """Validate cart total amount against maximum cart value limit"""
        if max_cart_value is None:
            await job_queue.log_job(job_id, LogLevel.INFO, "No maximum cart value configured, skipping validation")
            return True
        
        try:
            await job_queue.log_job(job_id, LogLevel.INFO, f"Validating cart total against maximum limit: ₹{max_cart_value}")
            
            # Look for cart total elements
            total_selectors = [
                'span:has-text("₹")',
                'div:has-text("Total")',
                'span[class*="total"]',
                'div[class*="amount"]'
            ]
            
            cart_total = 0.0
            total_found = False
            
            for selector in total_selectors:
                try:
                    total_elements = page.locator(selector)
                    element_count = await total_elements.count()
                    
                    for i in range(element_count):
                        try:
                            element = total_elements.nth(i)
                            text = await element.inner_text()
                            
                            # Extract price from text
                            import re
                            price_match = re.search(r'₹\s*([0-9,]+(?:\.[0-9]{2})?)', text)
                            if price_match:
                                price_str = price_match.group(1).replace(',', '')
                                price = float(price_str)
                                
                                if price > cart_total:  # Take the highest price found (likely the total)
                                    cart_total = price
                                    total_found = True
                                    
                        except Exception:
                            continue
                            
                except Exception:
                    continue
            
            if not total_found:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Could not extract cart total - proceeding without validation")
                return True
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Cart total: ₹{cart_total}")
            
            if cart_total > max_cart_value:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Cart total (₹{cart_total}) exceeds maximum limit (₹{max_cart_value})")
                await self.browser_manager.capture_failure_screenshot(job_id, "checkout_cart_total_exceeded")
                return False
            else:
                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Cart total (₹{cart_total}) is within limit (₹{max_cart_value})")
                return True
                
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error validating cart total: {str(e)}")
            return True  # Continue on error

    async def _ensure_on_checkout_page(self, page: Any, job_id: int, automation_mode: str) -> bool:
        """Monitor the URL to detect and recover from any late-triggered redirects during checkout (Flipkart Regular only)."""
        if automation_mode != "FLIPKART":
            return False
            
        ad_patterns = [
            "productType=CC",
            "fpg/cbc/store-page",
            "utm_source=Cart_OTA",
            "checkout/offers",
            "cc-store-page",
            "fpg/cbc"
        ]
        
        # Check URL for promotional redirects
        current_url = page.url
        if any(pattern in current_url for pattern in ad_patterns):
            await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Detected promotional redirect: {current_url[:100]}...")
            await job_queue.log_job(job_id, LogLevel.INFO, "🔄 Forcing navigation back to Order Summary...")
            await self._navigate_to_checkout_safely(page, job_id, automation_mode)
            return True
        
        return False

    async def _navigate_to_checkout_safely(self, page: Any, job_id: int, automation_mode: str):
        """Navigate specifically back to the checkout sequence to bypass ads."""
        try:
            # We use the checkout URL directly or go via cart if needed
            checkout_url = f'https://www.flipkart.com/checkout/init?marketplace={automation_mode}'
            await job_queue.log_job(job_id, LogLevel.INFO, f"🛒 Navigating to checkout: {checkout_url}")
            await page.goto(checkout_url, wait_until='domcontentloaded')
            await asyncio.sleep(2.0)
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed safe checkout navigation: {str(e)}")

    async def complete_checkout_process(self, job_id: int, max_cart_value: float = None, address_id: Optional[int] = None, gstin: Optional[str] = None, business_name: Optional[str] = None, steal_deal_product: Optional[str] = None, automation_mode: str = "FLIPKART") -> Dict[str, Any]:
        """Complete the checkout process: Apply Offers -> Steal Deals -> Validate Cart -> Order Summary -> Payments -> Place Order

        Returns a dict with keys: success, cart_total, basket_items, expected_delivery, order_id, message
        """
        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot complete checkout: No browser context.")
            return {"success": False, "message": "No browser context"}

        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            # Load address configuration for summary (account now has only one address)
            try:
                await self.load_address_configuration(job_id, address_id)
                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Using the single address in account (no selection needed)")
            except Exception:
                pass
            # Initialize summary fields
            cart_total_value: Optional[float] = None
            basket_items: Optional[int] = None
            expected_delivery: Optional[str] = None
            order_id: Optional[str] = None
            delivery_address_name: Optional[str] = None
            try:
                if self.settings_cache and isinstance(self.settings_cache, dict):
                    delivery_address_name = self.settings_cache.get('address_name')
            except Exception:
                delivery_address_name = None

            # Step 0: Apply offers on cart page
            await job_queue.log_job(job_id, LogLevel.INFO, "Step 0: Applying available offers...")
            
            # Prefer robust text-based locator for the "Apply" action
            try:
                apply_text = page.get_by_text("Apply")
                if await apply_text.count() > 0:
                    await apply_text.first.click()
                    await job_queue.log_job(job_id, LogLevel.INFO, "✅ Clicked Apply via text locator")
                    await asyncio.sleep(2)  # Wait for offers to be applied
                else:
                    # Fallback: use the previous specific selector if text locator is not found
                    apply_offer_selector = "#_parentCtr_ > div:nth-child(3) > div > div > div > div:nth-child(1) > div:nth-child(2) > div > div > div.css-175oi2r.r-1awozwy.r-1777fci.r-1ow6zhx.r-5njf8e > div > div"
                    apply_button = page.locator(apply_offer_selector)
                    if await apply_button.count() > 0 and await apply_button.is_visible():
                        await apply_button.click()
                        await job_queue.log_job(job_id, LogLevel.INFO, "✅ Clicked Apply via fallback selector")
                        await asyncio.sleep(2)
                    else:
                        await job_queue.log_job(job_id, LogLevel.INFO, "No Apply control found, proceeding...")
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to trigger Apply: {str(e)}")
            
            # Step 0.1: Handle Steal Deals if product name provided
            if steal_deal_product and steal_deal_product.strip():
                await job_queue.log_job(job_id, LogLevel.INFO, f"Step 0.1: Adding Steal Deal product: {steal_deal_product}")
                try:
                    # Import cart_manager to access handle_steal_deals
                    from services.automation_tasks.cart_manager import CartManager
                    cart_manager = CartManager(self.browser_manager)
                    
                    steal_deal_result = await cart_manager.handle_steal_deals(job_id, steal_deal_product.strip())
                    
                    if steal_deal_result.get("success"):
                        await job_queue.log_job(job_id, LogLevel.INFO, f"✅ {steal_deal_result.get('message')}")
                    else:
                        # Log warning but don't fail the automation - steal deal is optional
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Steal deal not added: {steal_deal_result.get('error')}")
                        await job_queue.log_job(job_id, LogLevel.INFO, "Continuing with automation (steal deal is optional)")
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Steal deal handler error: {str(e)}. Continuing...")
            
            # Click Continue or Place Order button to proceed to checkout
            await job_queue.log_job(job_id, LogLevel.INFO, f"Step 1: Proceeding to checkout ({automation_mode} flow)...")
            
            # Select button text based on automation type
            primary_button_text = "Place Order" if automation_mode == "FLIPKART" else "Continue"
            
            button_selectors = [
                # Text-based selectors (most reliable)
                f'div:has-text("{primary_button_text}"):not(:has(div:has-text("{primary_button_text}")))',
                f'text="{primary_button_text}"',
                f'div.css-1rynq56:has-text("{primary_button_text}")',
                f'div[role="button"]:has-text("{primary_button_text}")',
                # Grocery-specific Continue button
                'div.css-175oi2r.r-1awozwy.r-1kneemv:has-text("Continue")',
                # Regular Flipkart Place Order button
                'button:has-text("Place Order")',
                'div.HaReuk div.cDeXU9 button',
                # Fallbacks from previous logic
                'div.HaReuk > div.cDeXU9 > div > div > div > div:nth-child(1) > div > div > div > div > div:nth-child(2) > div > div > div.css-175oi2r.r-13awgt0.r-eqz5dr > div.css-175oi2r.r-13awgt0.r-eqz5dr > div > div:nth-child(1) > div',
            ]
            
            checkout_proceed_clicked = False
            for i, selector in enumerate(button_selectors):
                try:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Attempting {primary_button_text} button with strategy #{i+1}: {selector[:50]}...")
                    btn_locator = page.locator(selector)
                    if await btn_locator.count() > 0:
                        for idx in range(await btn_locator.count()):
                            btn = btn_locator.nth(idx)
                            try:
                                if await btn.is_visible(timeout=2000):
                                    await btn.click(timeout=5000)
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Clicked {primary_button_text} button using strategy #{i+1}")
                                    checkout_proceed_clicked = True
                                    await asyncio.sleep(3)
                                    break
                            except Exception:
                                continue
                        if checkout_proceed_clicked:
                            break
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Strategy #{i+1} failed: {str(e)}")
                    continue
            
            if not checkout_proceed_clicked:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"{primary_button_text} button not found with all strategies")
                await self.browser_manager.capture_failure_screenshot(job_id, f"checkout_{primary_button_text.lower()}_not_found")
                return {"success": False, "message": f"{primary_button_text} button not found"}
            
            # Step 0.5: Validate cart total on checkout page
            if max_cart_value:
                await job_queue.log_job(job_id, LogLevel.INFO, f"Step 0.5: Validating cart total against maximum limit: ₹{max_cart_value}")
                
                cart_total_selector = "#_parentCtr_ > div:nth-child(5) > div > div:nth-child(1) > div > div:nth-child(2) > div.css-175oi2r.r-1awozwy.r-18u37iz.r-ur6pnr.r-1wtj0ep.r-ymttw5 > div.css-175oi2r.r-18u37iz.r-1awozwy > div > div"
                
                try:
                    cart_total_element = page.locator(cart_total_selector)
                    if await cart_total_element.count() > 0:
                        total_text = await cart_total_element.inner_text()
                        
                        # Extract numeric value from text like "₹1,234" or "1,234"
                        import re
                        total_match = re.search(r'₹?\s*([0-9,]+(?:\.[0-9]{2})?)', total_text)
                        if total_match:
                            cart_total_value = float(total_match.group(1).replace(',', ''))
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Cart total after offers: ₹{cart_total_value}")
                            
                            if cart_total_value > max_cart_value:
                                await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION STOPPED: Cart total (₹{cart_total_value}) exceeds maximum limit (₹{max_cart_value})")
                                await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ ACCOUNT MARKED AS FAILED: Cart value exceeded limit")
                                return {"success": False, "message": "Cart value exceeded limit", "cart_total": cart_total_value}
                            else:
                                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Cart total (₹{cart_total_value}) is within limit (₹{max_cart_value})")
                        else:
                            await job_queue.log_job(job_id, LogLevel.WARNING, f"Could not extract cart total from text: {total_text}")
                    else:
                        await job_queue.log_job(job_id, LogLevel.WARNING, "Cart total element not found, proceeding without validation")
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Error validating cart total: {str(e)}")

            # Always attempt to capture cart total for the final summary even if no max_cart_value
            if cart_total_value is None:
                try:
                    cart_total_selectors = [
                        "#_parentCtr_ > div:nth-child(5) > div > div:nth-child(1) > div > div:nth-child(2) > div.css-175oi2r.r-1awozwy.r-18u37iz.r-ur6pnr.r-1wtj0ep.r-ymttw5 > div.css-175oi2r.r-18u37iz.r-1awozwy > div > div",
                        'span:has-text("₹")'
                    ]
                    import re
                    for sel in cart_total_selectors:
                        el = page.locator(sel)
                        if await el.count() > 0:
                            txt = await el.first.inner_text()
                            m = re.search(r'₹?\s*([0-9,]+(?:\.[0-9]{2})?)', txt)
                            if m:
                                cart_total_value = float(m.group(1).replace(',', ''))
                                await job_queue.log_job(job_id, LogLevel.INFO, f"Cart total (summary capture): ₹{cart_total_value}")
                                break
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Cart total summary capture error: {str(e)}")

            # Extract total basket items on checkout page
            try:
                basket_selectors = [
                    '#_parentCtr_ > div:nth-child(3) > div > div > div > div:nth-child(1) > div > div > div > div > div',
                    'div.css-1rynq56.r-op4f77.r-1vgyyaa.r-ubezar.r-1rsjblm',
                    'div:has-text("Grocery basket (")'
                ]
                import re
                for bsel in basket_selectors:
                    try:
                        el = page.locator(bsel)
                        if await el.count() > 0:
                            text = await el.first.inner_text()
                            m = re.search(r'Grocery basket\s*\((\d+)\s*items?\s*\)', text, re.IGNORECASE)
                            if m:
                                basket_items = int(m.group(1))
                                await job_queue.log_job(job_id, LogLevel.INFO, f"Basket items detected: {basket_items}")
                                break
                    except Exception:
                        continue
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Basket items extraction error: {str(e)}")

            # Extract expected delivery date on checkout page
            try:
                expected_delivery_selectors = [
                    '#_parentCtr_ > div:nth-child(1) > div > div > div.css-1rynq56.r-1et8rh5.r-1b43r93.r-jwli3a',
                    'div.css-1rynq56.r-1et8rh5.r-1b43r93.r-jwli3a'
                ]
                for esel in expected_delivery_selectors:
                    try:
                        el = page.locator(esel)
                        if await el.count() > 0:
                            text = (await el.first.inner_text()).strip()
                            if text:
                                expected_delivery = text
                                await job_queue.log_job(job_id, LogLevel.INFO, f"Expected delivery: {expected_delivery}")
                                break
                    except Exception:
                        continue
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Expected delivery extraction error: {str(e)}")
            
            # Step 1: Handle Order Summary page (Step 2)
            await job_queue.log_job(job_id, LogLevel.INFO, "Step 2: Processing Order Summary...")
            
            # Wait and check for promotional redirects (Flipkart only)
            if automation_mode == "FLIPKART":
                await asyncio.sleep(2) # Initial wait for navigation
                await self._ensure_on_checkout_page(page, job_id, automation_mode)
            else:
                await asyncio.sleep(2)

            # Step 1.a: GST Invoice handling (optional, when provided)
            try:
                if gstin or business_name:
                    await job_queue.log_job(job_id, LogLevel.INFO, "GST preferences provided. Checking 'Use GST Invoice' option...")

                    # Primary selector provided by user for the GST block
                    gst_block_selector = "#_parentCtr_ > div:nth-child(4) > div > div.css-175oi2r.r-nsbfu8 > div.css-175oi2r.r-13awgt0.r-18u37iz.r-1wtj0ep.r-1awozwy > div:nth-child(1) > div > div"
                    gst_block = page.locator(gst_block_selector)

                    # If not found, try a text-based fallback near 'GST'
                    if await gst_block.count() == 0:
                        gst_block = page.locator("#_parentCtr_ div:has-text('GST')").first

                    if await gst_block.count() > 0:
                        try:
                            text = (await gst_block.inner_text()).strip()
                        except Exception:
                            text = ""

                        if 'Use GST Invoice' in text:
                            await job_queue.log_job(job_id, LogLevel.INFO, "'Use GST Invoice' detected. Clicking to open GST details popup...")
                            try:
                                await gst_block.scroll_into_view_if_needed()
                            except Exception:
                                pass
                            await gst_block.click()
                            await asyncio.sleep(1)

                            # Wait for popup container to appear (best-effort)
                            try:
                                await page.wait_for_selector('text="GSTIN"', timeout=5000)
                            except Exception:
                                # continue with input detection heuristics
                                pass

                            # Locate GSTIN and Business Name inputs
                            gstin_value = (gstin or '').strip()
                            business_name_value = (business_name or '').strip()

                            # Prefer placeholder-based locators
                            gstin_input = None
                            biz_input = None
                            try:
                                li = page.get_by_placeholder("GSTIN")
                                if await li.count() > 0:
                                    gstin_input = li.first
                            except Exception:
                                pass
                            try:
                                li2 = page.get_by_placeholder("Business Name")
                                if await li2.count() > 0:
                                    biz_input = li2.first
                            except Exception:
                                pass

                            # Fallback to class-based selector provided (both fields share same selector)
                            if gstin_input is None or biz_input is None:
                                try:
                                    multi = page.locator('input.css-11aywtz.r-6taxm2.r-16y2uox.r-1b43r93.r-crgep1.r-1m04atk.r-85oauj.r-fdjqy7.r-dfe81l.r-1mi0q7o.r-5t7p9m')
                                    count = await multi.count()
                                    if count >= 1 and gstin_input is None:
                                        gstin_input = multi.nth(0)
                                    if count >= 2 and biz_input is None:
                                        biz_input = multi.nth(1)
                                except Exception:
                                    pass

                            # As another fallback, search generic inputs in popup and match by label proximity
                            if gstin_input is None or biz_input is None:
                                try:
                                    inputs = page.locator('#_parentCtr_ input')
                                    if await inputs.count() >= 2:
                                        if gstin_input is None:
                                            gstin_input = inputs.nth(0)
                                        if biz_input is None:
                                            biz_input = inputs.nth(1)
                                except Exception:
                                    pass

                            # Fill fields if available
                            if gstin_input is not None and gstin_value:
                                try:
                                    await gstin_input.click()
                                    await gstin_input.fill(gstin_value)
                                    await asyncio.sleep(0.2)
                                except Exception as e:
                                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to fill GSTIN: {e}")
                            if biz_input is not None and business_name_value:
                                try:
                                    await biz_input.click()
                                    await biz_input.fill(business_name_value)
                                    await asyncio.sleep(0.2)
                                except Exception as e:
                                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to fill Business Name: {e}")

                            # Click Confirm and Save
                            confirm_clicked = False
                            confirm_selectors = [
                                'text="Confirm and Save"',
                                'button:has-text("Confirm and Save")',
                                'div[role="button"]:has-text("Confirm and Save")',
                                'body > div:nth-child(21) > div > div:nth-child(2) > div > div > div > div > div > div > div > div:nth-child(4) > div > div > div > div > div > div:nth-child(2) > div'
                            ]
                            for sel in confirm_selectors:
                                try:
                                    loc = page.locator(sel)
                                    if await loc.count() > 0 and await loc.first.is_visible():
                                        try:
                                            await loc.first.scroll_into_view_if_needed()
                                        except Exception:
                                            pass
                                        await loc.first.click()
                                        confirm_clicked = True
                                        await job_queue.log_job(job_id, LogLevel.INFO, f"Clicked 'Confirm and Save' using selector: {sel}")
                                        break
                                except Exception:
                                    continue

                            if not confirm_clicked:
                                await job_queue.log_job(job_id, LogLevel.WARNING, "Could not click 'Confirm and Save'. Proceeding anyway.")
                            else:
                                await asyncio.sleep(2)
                                await job_queue.log_job(job_id, LogLevel.INFO, "GST details submitted.")
                        else:
                            await job_queue.log_job(job_id, LogLevel.INFO, "GST already applied or control not actionable. Proceeding.")
                    else:
                        await job_queue.log_job(job_id, LogLevel.DEBUG, "GST control block not found on Order Summary. Skipping GST step.")
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"GST handling encountered an issue: {str(e)}")

            
            # Click Continue button on Order Summary page - using multiple fallback selectors
            order_summary_continue_selectors = [
                # Text-based selectors (most reliable)
                'div:has-text("Continue"):not(:has(div:has-text("Continue")))',  # Innermost div with "Continue"
                'text="Continue"',
                'div.css-1rynq56:has-text("Continue")',  # The text container class from the HTML
                # Button-like div classes with yellow background
                'div.css-175oi2r.r-1awozwy.r-1kneemv:has-text("Continue")',
                # Specific selector for Flipkart Order Summary button
                '#_parentCtr_ > div:nth-child(7) > div > div:nth-child(1) > div > div:nth-child(1) > div',
                # Generic role-based selectors
                'button:has-text("Continue")',
                'div[role="button"]:has-text("Continue")'
            ]
            
            # If Flipkart mode is active, the button might sometimes say "Place Order" even in Step 2 
            # (depending on direct checkout vs regular flow)
            if automation_mode == "FLIPKART":
                order_summary_continue_selectors.insert(0, 'div:has-text("Place Order"):not(:has(div:has-text("Place Order"))) >> visible=true')
                order_summary_continue_selectors.insert(1, 'text="Place Order"')

            order_summary_continue_clicked = False
            for i, os_continue_selector in enumerate(order_summary_continue_selectors):
                try:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Attempting Order Summary Continue with strategy #{i+1}: {os_continue_selector[:50]}...")
                    continue_button = page.locator(os_continue_selector)
                    if await continue_button.count() > 0:
                        # For text selectors, we might get multiple matches - use the visible one
                        for idx in range(await continue_button.count()):
                            btn = continue_button.nth(idx)
                            try:
                                if await btn.is_visible(timeout=2000):
                                    await btn.click(timeout=5000)
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Clicked Continue button on Order Summary using strategy #{i+1}")
                                    order_summary_continue_clicked = True
                                    await asyncio.sleep(3)  # Wait for payments page to load
                                    break
                            except Exception:
                                continue
                        if order_summary_continue_clicked:
                            break
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Order Summary Continue strategy #{i+1} failed: {str(e)}")
                    continue
            
            if not order_summary_continue_clicked:
                # Last resort: try using page.get_by_text
                try:
                    await job_queue.log_job(job_id, LogLevel.INFO, "Trying get_by_text fallback for Order Summary Continue button...")
                    continue_text = page.get_by_text("Continue", exact=False)
                    if await continue_text.count() > 0:
                        for idx in range(await continue_text.count()):
                            btn = continue_text.nth(idx)
                            try:
                                if await btn.is_visible(timeout=2000):
                                    text_content = await btn.inner_text()
                                    if text_content.strip().lower() == "continue":
                                        await btn.click(timeout=5000)
                                        await job_queue.log_job(job_id, LogLevel.INFO, "✅ Clicked Order Summary Continue using get_by_text fallback")
                                        order_summary_continue_clicked = True
                                        await asyncio.sleep(3)
                                        break
                            except Exception:
                                continue
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"get_by_text fallback failed: {str(e)}")
            
            if not order_summary_continue_clicked:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Continue button not found on Order Summary with all strategies")
                await self.browser_manager.capture_failure_screenshot(job_id, "checkout_order_summary_continue_failed")
                return {"success": False, "message": "Order Summary Continue button not found"}
            
            # Step 2: Handle Payments page (Step 3)
            await job_queue.log_job(job_id, LogLevel.INFO, "Step 3: Processing Payments...")
            
            # Click on "Cash on Delivery" option with multiple fallback strategies
            cod_selectors = [
                # Class-based selector from provided HTML
                '.rwYWFp._3Awrcc',
                # Text-based selector
                'text="Cash on Delivery"',
                # Data attribute selector
                '[data-disabled="false"]:has-text("Cash on Delivery")',
                # Original nth-child selector as fallback
                '#container > div.Wr52Y1 > div > section.iGRJtT > div > div > div > section > div > div:nth-child(5) > div:nth-child(1) > div',
                # Generic span selector
                'span.EtFGuU:has-text("Cash on Delivery")'
            ]
            
            cod_clicked = False
            for i, cod_selector in enumerate(cod_selectors):
                try:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Attempting Cash on Delivery selection with strategy #{i+1}")
                    
                    # Wait for the element and click
                    cod_element = page.locator(cod_selector)
                    if await cod_element.count() > 0:
                        await cod_element.click(timeout=5000)
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Successfully selected 'Cash on Delivery' using strategy #{i+1}")
                        cod_clicked = True
                        await asyncio.sleep(2)  # Wait for selection to register
                        break
                    else:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Cash on Delivery element not found with strategy #{i+1}")
                        
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Strategy #{i+1} failed: {str(e)}")
                    continue
            
            if not cod_clicked:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to select Cash on Delivery with all strategies")
                return {"success": False, "message": "Failed to select COD"}
            
            # Click "Place Order" button with multiple fallback strategies
            place_order_selectors = [
                # Original specific selector
                '#cod-place-order',
                # Text-based selector
                'text="Place Order"',
                # Button with text
                'button:has-text("Place Order")',
                # Generic button selector with COD context
                'button[type="submit"]',
                # Div with place order text
                'div:has-text("Place Order")'
            ]
            
            order_placed = False
            for i, place_order_selector in enumerate(place_order_selectors):
                try:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Attempting Place Order with strategy #{i+1}")
                    
                    # Wait for the element and click
                    place_order_element = page.locator(place_order_selector)
                    if await place_order_element.count() > 0:
                        await place_order_element.click(timeout=5000)
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Successfully clicked 'Place Order' using strategy #{i+1}")
                        order_placed = True
                        await asyncio.sleep(3)  # Wait for order to be processed
                        break
                    else:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Place Order element not found with strategy #{i+1}")
                        
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Place Order strategy #{i+1} failed: {str(e)}")
                    continue
            
            if not order_placed:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to place order with all strategies")
                return {"success": False, "message": "Failed to click Place Order"}
            
            # Final Step: Handle Order Confirmation popup
            await job_queue.log_job(job_id, LogLevel.INFO, "Step 4: Confirming order placement...")
            
            # Click "Confirm order" button with multiple fallback strategies
            confirm_order_selectors = [
                # Class-based selector from provided HTML
                'button.Button-module_button__P7hTI.Button-module_neutral__OtiH-.RILzPv',
                # Variant attribute selector
                'button[variant="neutral"]:has-text("Confirm order")',
                # Text-based selector
                'text="Confirm order"',
                # Button with text
                'button:has-text("Confirm order")',
                # Generic confirm selector
                'button:has-text("Confirm")',
                # Mobile bottom sheet buttons
                'div[role="button"]:has-text("Confirm")',
                'div[role="button"]:has-text("YES")',
                'div[role="button"]:has-text("OK")'
            ]
            
            # Additional logic to find ANY button in a recently appeared modal
            order_confirmed = False
            
            # Strategy: First try specific selectors
            for i, confirm_selector in enumerate(confirm_order_selectors):
                try:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Attempting Order Confirmation with strategy #{i+1}")
                    
                    # Wait for the confirmation popup and click
                    confirm_element = page.locator(confirm_selector).last
                    if await confirm_element.count() > 0:
                        await confirm_element.first.scroll_into_view_if_needed()
                        await confirm_element.first.click(timeout=5000)
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Successfully clicked 'Confirm order' using strategy #{i+1}")
                        order_confirmed = True
                        await asyncio.sleep(4)  # Wait for order confirmation to process
                        break
                    else:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Confirm order element not found with strategy #{i+1}")
                        
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Confirm order strategy #{i+1} failed: {str(e)}")
                    continue
            
            # Strategy: Role-based fallback
            if not order_confirmed:
                try:
                    await job_queue.log_job(job_id, LogLevel.INFO, "Attempting Role-based Order Confirmation (get_by_role)...")
                    confirm_btn = page.get_by_role("button", name=re.compile(r"Confirm|YES|OK|Place", re.I)).last
                    if await confirm_btn.count() > 0:
                        await confirm_btn.click(timeout=5000)
                        await job_queue.log_job(job_id, LogLevel.INFO, "Successfully clicked 'Confirm order' using Role-based locator")
                        order_confirmed = True
                        await asyncio.sleep(4)
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Role-based Confirmation failed: {str(e)}")
            
            if order_confirmed:
                # Handle potential redirect and 410 Gone errors
                await job_queue.log_job(job_id, LogLevel.INFO, "Waiting for order confirmation and handling potential redirects...")
                
                # Monitor for redirect or error responses
                redirect_handled = False
                confirmation_found = False
                
                for attempt in range(3):  # Try up to 3 times
                    try:
                        await asyncio.sleep(2)  # Shorter wait between attempts
                        
                        # Check current URL for error indicators
                        current_url = page.url
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Current URL (attempt {attempt + 1}): {current_url}")

                        # Try to parse order_id from URL query params
                        try:
                            parsed = urlparse(current_url)
                            qs = parse_qs(parsed.query)
                            if 'reference_id' in qs and qs['reference_id']:
                                order_id = qs['reference_id'][0]
                                await job_queue.log_job(job_id, LogLevel.INFO, f"Extracted order_id from URL: {order_id}")
                        except Exception:
                            pass
                        
                        # Check for 410 Gone or other error pages
                        if "error" in current_url.lower() or "410" in current_url:
                            await job_queue.log_job(job_id, LogLevel.WARNING, f"Detected error page or 410 Gone. Attempting to navigate back to order confirmation.")
                            
                            # Try to navigate to order history or account page
                            try:
                                await page.goto('https://www.flipkart.com/account/orders', timeout=10000)
                                await asyncio.sleep(3)
                                await job_queue.log_job(job_id, LogLevel.INFO, "Navigated to order history to verify order placement")
                                redirect_handled = True
                                break
                            except Exception:
                                # If that fails, try main account page
                                try:
                                    await page.goto('https://www.flipkart.com/account', timeout=10000)
                                    await asyncio.sleep(3)
                                    await job_queue.log_job(job_id, LogLevel.INFO, "Navigated to account page after redirect error")
                                    redirect_handled = True
                                    break
                                except Exception:
                                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to handle redirect error on attempt {attempt + 1}")
                        
                        # Check for order confirmation indicators
                        order_placed_indicators = [
                            'text="Order Placed"',
                            'text="Order"',
                            'text="Placed"',
                            'text="SuperCoins"',
                            'text="Saved"',
                            'text="Thank you"',
                            'text="confirmed"'
                        ]
                        
                        for indicator in order_placed_indicators:
                            if await page.locator(indicator).count() > 0:
                                await job_queue.log_job(job_id, LogLevel.INFO, f"Order confirmation detected with indicator: {indicator}")
                                confirmation_found = True
                                break
                        
                        if confirmation_found:
                            break
                            
                        # Check if we're on a success page by URL patterns
                        success_url_patterns = [
                            'success', 'confirmation', 'placed', 'thank', 'order'
                        ]
                        
                        for pattern in success_url_patterns:
                            if pattern in current_url.lower():
                                await job_queue.log_job(job_id, LogLevel.INFO, f"Success page detected by URL pattern: {pattern}")
                                confirmation_found = True
                                break
                        
                        if confirmation_found:
                            break
                            
                    except Exception as e:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"Error during confirmation check attempt {attempt + 1}: {str(e)}")
                        continue
                
                # Final status determination
                if confirmation_found or redirect_handled:
                    await job_queue.log_job(job_id, LogLevel.INFO, "🎉 FULL AUTOMATION COMPLETED SUCCESSFULLY! ORDER PLACED! 🎉")
                    if delivery_address_name:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Delivery Address: {delivery_address_name}")
                    
                    # Additional verification: Try to check order history
                    try:
                        if not redirect_handled:  # Only if we haven't already navigated there
                            await page.goto('https://www.flipkart.com/account/orders', timeout=10000)
                            await asyncio.sleep(2)
                        
                        # Look for recent orders
                        recent_order_indicators = [
                            'text="Confirmed"',
                            'text="Processing"',
                            'text="Ordered"',
                            'div[class*="order"]'
                        ]
                        
                        for indicator in recent_order_indicators:
                            if await page.locator(indicator).count() > 0:
                                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Order verified in order history!")
                                break
                        
                    except Exception:
                        await job_queue.log_job(job_id, LogLevel.INFO, "Order placed successfully (history verification failed)")
                    
                    return {
                        "success": True,
                        "cart_total": cart_total_value,
                        "basket_items": basket_items,
                        "expected_delivery": expected_delivery,
                        "order_id": order_id,
                        "delivery_address_name": delivery_address_name,
                        "message": "Order placed successfully"
                    }
                else:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Order may have been placed but confirmation unclear due to redirect issues")
                    return {
                        "success": True,
                        "cart_total": cart_total_value,
                        "basket_items": basket_items,
                        "expected_delivery": expected_delivery,
                        "order_id": order_id,
                        "delivery_address_name": delivery_address_name,
                        "message": "Order placed (confirmation unclear)"
                    }
            else:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to confirm order with all strategies")
                return {"success": False, "message": "Failed to confirm order"}
                
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error in checkout process: {str(e)}")
            return {"success": False, "message": f"Checkout error: {str(e)}"}
