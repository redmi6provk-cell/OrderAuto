"""
Core Automation Worker
Main orchestration class that coordinates all automation modules
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List
import traceback

# Add the parent directory to Python path to import automation modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from services.job_queue import register_worker, job_queue, LogLevel
from services.gmail_service import gmail_service
from database import DATABASE_URL
import asyncpg
from services.automation_tasks.add_address_task import fill_address_form

# Import the new modular components
from .browser_manager import BrowserManager
from .authentication_handler import AuthenticationHandler
from .cart_manager import CartManager
from .checkout_handler import CheckoutHandler


class AutomationWorker:
    def __init__(self):
        # Initialize all module components
        self.browser_manager = BrowserManager()
        self.auth_handler = AuthenticationHandler(self.browser_manager)
        self.cart_manager = CartManager(self.browser_manager)
        self.checkout_handler = CheckoutHandler(self.browser_manager)
        
        # Legacy properties for backward compatibility
        self.browser = None
        self.playwright = None
        self.active_contexts = {}
        
    # Delegate browser management methods
    async def initialize_browser(self):
        """Initialize Playwright browser"""
        result = await self.browser_manager.initialize_browser()
        # Update legacy properties for compatibility
        self.browser = self.browser_manager.browser
        self.playwright = self.browser_manager.playwright
        self.active_contexts = self.browser_manager.active_contexts
        return result
    
    async def create_isolated_context(self, job_id: int, email: str, view_mode: str = 'desktop'):
        """Create an isolated browser context for a specific job"""
        return await self.browser_manager.create_isolated_context(job_id, email, view_mode)
    
    async def cleanup_job_context(self, job_id: int):
        """Clean up browser context for a specific job"""
        return await self.browser_manager.cleanup_job_context(job_id)
    
    async def get_job_context(self, job_id: int):
        """Get existing browser context for a job"""
        return await self.browser_manager.get_job_context(job_id)
    
    def get_active_contexts_count(self):
        """Get number of active browser contexts"""
        return self.browser_manager.get_active_contexts_count()
    
    def get_active_contexts_info(self):
        """Get information about active contexts"""
        return self.browser_manager.get_active_contexts_info()
    
    async def cleanup_browser(self):
        """Cleanup browser resources"""
        return await self.browser_manager.cleanup_browser()

    # Delegate authentication methods
    async def try_cookie_login(self, email: str, job_id: int, view_mode: str = 'desktop') -> bool:
        """Try to login using saved cookies first"""
        return await self.auth_handler.try_cookie_login(email, job_id, view_mode)

    async def login_to_flipkart(self, email: str, job_id: int, view_mode: str = 'desktop') -> bool:
        """Login to Flipkart - try cookies first, then OTP if needed"""
        return await self.auth_handler.login_to_flipkart(email, job_id, view_mode)

    # Delegate cart management methods
    async def add_and_configure_products_in_cart(self, products: List[Dict], job_id: int, max_cart_value: float = None) -> Dict[str, Any]:
        """Phase 2: Navigate to each product page, add it to cart, and configure the quantity."""
        return await self.cart_manager.add_and_configure_products_in_cart(products, job_id, max_cart_value)

    # Delegate checkout methods
    async def select_correct_address(self, job_id: int) -> bool:
        """Check current address and select the correct one if needed"""
        return await self.checkout_handler.select_correct_address(job_id)

    async def validate_cart_total(self, page: Any, job_id: int, max_cart_value: Optional[float] = None) -> bool:
        """Validate cart total amount against maximum cart value limit"""
        return await self.checkout_handler.validate_cart_total(page, job_id, max_cart_value)

    async def complete_checkout_process(self, job_id: int, max_cart_value: float = None, address_id: Optional[int] = None, gstin: Optional[str] = None, business_name: Optional[str] = None, steal_deal_product: Optional[str] = None) -> Dict[str, Any]:
        """Complete the checkout process: Order Summary -> Payments -> Place Order"""
        return await self.checkout_handler.complete_checkout_process(job_id, max_cart_value, address_id, gstin, business_name, steal_deal_product)

    # Legacy methods for backward compatibility
    async def create_browser_context(self, user_data: Dict[str, Any]) -> bool:
        """Create a new browser context for a user (legacy method)"""
        return await self.browser_manager.create_browser_context(user_data)

    async def save_cookies(self, flipkart_user_id: int):
        """Save cookies to database (legacy method)"""
        try:
            if not hasattr(self, 'context') or not self.context:
                return
                
            cookies = await self.context.cookies()
            cookies_json = json.dumps(cookies)
            
            conn = await asyncpg.connect(DATABASE_URL)
            try:
                await conn.execute(
                    """
                    UPDATE flipkart_users 
                    SET cookies = $1, updated_at = $2 
                    WHERE id = $3
                    """,
                    cookies_json, datetime.utcnow(), flipkart_user_id
                )
                
                logging.info(f"Saved cookies for user {flipkart_user_id}")
                
            finally:
                await conn.close()
                
        except Exception as e:
            logging.error(f"Failed to save cookies: {e}")

    def extract_essential_cookies(self, all_cookies: list) -> list:
        """Extract only the essential 'at' and 'rt' cookies from all cookies"""
        return self.browser_manager.extract_essential_cookies(all_cookies)
    
    def validate_essential_cookies(self, cookies: list) -> bool:
        """Check if cookies contain both 'at' and 'rt' tokens"""
        return self.browser_manager.validate_essential_cookies(cookies)

    async def save_cookies_to_db(self, job_id: int, cookies: list):
        """Save cookies to database for isolated session"""
        return await self.browser_manager.save_cookies_to_db(job_id, cookies)

    # Location and product methods (kept in core worker)
    async def select_delivery_location(self, job_id: int, pincode: str = "400010", expected_postfix: Optional[str] = None) -> bool:
        """Homepage regionalization only: open the Deliver To sheet and submit the pincode.
        Address selection now happens on checkout via `CheckoutHandler.select_correct_address()`.
        """
        context = await self.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot select delivery location: No browser context.")
            return False
        
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            await job_queue.log_job(job_id, LogLevel.INFO, f"Setting homepage pincode only: {pincode}")

            # Ensure we are on a page where the location control is present
            try:
                await job_queue.log_job(job_id, LogLevel.INFO, "Navigating to Flipkart home to ensure location control is available")
                await page.goto('https://www.flipkart.com/', wait_until='domcontentloaded')
                await asyncio.sleep(2)
            except Exception as nav_err:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Navigation to home failed or unnecessary: {str(nav_err)}")

            # Try multiple robust selectors to open the location selection UI
            await job_queue.log_job(job_id, LogLevel.INFO, "Opening delivery selector (Deliver to)…")
            location_selectors = [
                'a[class*="_3n8fna1co"][class*="_3n8fna10j"]',  # existing hashed classes (may change)
                'button:has-text("Deliver to")',
                'button:has-text("Change")',
                'button:has-text("Enter pincode")',
                'a:has-text("Deliver to")',
                'a:has-text("Change")',
                '[data-testid*="location"]',
                '[aria-label*="location"]'
            ]

            opened = False
            for idx, sel in enumerate(location_selectors):
                try:
                    locator = page.locator(sel)
                    count = await locator.count()
                    if count > 0:
                        candidate = locator.first
                        # Verify it is visible and enabled before clicking
                        if await candidate.is_visible():
                            await candidate.click()
                            opened = True
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Clicked location control using selector #{idx+1}: {sel}")
                            break
                except Exception as click_err:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Selector #{idx+1} failed to open location UI ({sel}): {str(click_err)}")

            if not opened:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Could not find or open location selection control with any selector")
                return False

            # Wait for either the address list dialog or a pincode input to appear
            try:
                await page.wait_for_selector('#_parentCtr_', timeout=5000)
            except Exception:
                pass
            
            # We only need to submit the pincode here
            await job_queue.log_job(job_id, LogLevel.INFO, "Entering pincode on the sheet and submitting…")
            
            # Enter pincode in the input field
            # Primary specific selector provided by user
            specific_input_sel = '#_parentCtr_ > div:nth-child(2) > div > div > div > div.css-175oi2r.r-nsbfu8.r-13awgt0.r-eqz5dr.r-1habvwh.r-1h0z5md > div > div.css-175oi2r.r-13awgt0.r-18u37iz > input'
            pincode_input = page.locator(specific_input_sel)
            if await pincode_input.count() == 0:
                # Fallback to placeholder/name based inputs
                pincode_input = page.locator('input[placeholder*="pincode" i], input[name*="pincode" i]')
            if await pincode_input.count() == 0:
                # Generic fallback
                pincode_input = page.locator('#_parentCtr_ input').first
            if await pincode_input.count() == 0:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Could not find pincode input field")
                return False
            
            await pincode_input.fill(pincode)
            await asyncio.sleep(0.5)
            
            # Click submit using specific selector, then fallbacks
            submit_selectors = [
                '#_parentCtr_ > div:nth-child(2) > div > div > div > div.css-175oi2r.r-nsbfu8.r-13awgt0.r-eqz5dr.r-1habvwh.r-1h0z5md > div > div:nth-child(2) > div',
                'div.css-1rynq56:has-text("Submit")',
                'button:has-text("Submit")',
                'div[role="button"]:has-text("Submit")',
                'text="Submit"'
            ]
            
            submit_clicked = False
            for i, submit_selector in enumerate(submit_selectors):
                try:
                    submit_elements = page.locator(submit_selector)
                    element_count = await submit_elements.count()
                    
                    if element_count > 0:
                        for j in range(element_count):
                            try:
                                submit_button = submit_elements.nth(j)
                                
                                is_visible = await submit_button.is_visible(timeout=1000)
                                
                                if is_visible:
                                    await submit_button.click(timeout=3000)
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"✓ Clicked submit button with selector #{i+1}")
                                    submit_clicked = True
                                    break
                            except Exception:
                                continue
                        
                        if submit_clicked:
                            break
                        
                except Exception:
                    continue
            
            if not submit_clicked:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Submit button not found, trying Enter key")
                try:
                    await pincode_input.first.press('Enter')
                    await job_queue.log_job(job_id, LogLevel.INFO, "Pressed Enter key on pincode input")
                    submit_clicked = True
                except Exception:
                    pass
            
            if not submit_clicked:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to submit pincode")
                return False
            
            # CRITICAL: Wait for submission to complete - sheet should close
            await asyncio.sleep(1.5)
            
            # Verify sheet closed (submission succeeded)
            try:
                sheet_still_open = await page.locator('#_parentCtr_').is_visible(timeout=2000)
                if sheet_still_open:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "⚠️ Delivery sheet still open after submit - clicking outside to close")
                    # Click outside to close and proceed
                    await page.mouse.click(50, 50)
                    await asyncio.sleep(0.5)
            except Exception:
                # Sheet not visible = good, submission worked
                pass
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Homepage pincode set: {pincode}. Address will be selected at checkout.")
            return True
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to select delivery location: {str(e)}")
            return False

    async def _check_and_select_existing_address(self, page, job_id: int, target_pincode: str, expected_postfix: Optional[str] = None) -> bool:
        """Check existing addresses and select matching one if found.
        If expected_postfix is provided, only consider addresses that contain this postfix as valid matches."""
        try:
            # Wait for address list to load
            await asyncio.sleep(2)
            
            # OPTIMIZATION: Check for "See more" immediately and expand list early if present
            # This avoids checking limited addresses first, then expanding and rechecking same addresses
            see_more = page.locator('text="See more"')
            if await see_more.count() > 0:
                await job_queue.log_job(job_id, LogLevel.INFO, "Found 'See more' option, expanding address list immediately for complete search...")
                await see_more.first.click()
                await asyncio.sleep(3)  # Wait for more addresses to load
                
                # Search the complete expanded address list
                await job_queue.log_job(job_id, LogLevel.INFO, "🔍 Searching complete expanded address list...")
                
                # Use the specific selector pattern for expanded addresses
                expanded_base_selector = "#_parentCtr_ > div:nth-child(1) > div > div > div > div:nth-child(2) > div"
                addresses_found = 0
                
                # Check all addresses in expanded list
                for i in range(1, 21):  # Check up to 20 addresses
                    address_selector = f"{expanded_base_selector} > div:nth-child({i})"
                    address_element = page.locator(address_selector)
                    
                    if await address_element.count() == 0:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"No more addresses found at position {i}, stopping search")
                        break  # No more addresses
                    
                    addresses_found += 1
                    
                    try:
                        # Get the full text content of this address entry
                        address_text = await address_element.inner_text()
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Address {i}: {address_text[:150]}...")
                        
                        # Check if this address matches our criteria
                        if self._is_target_address(address_text, target_pincode, expected_postfix):
                            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Found matching address at position {i}")
                            
                            # Click on this address to select it
                            await address_element.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            await address_element.click()
                            await asyncio.sleep(1)
                            
                            # Look for "Select" or "Deliver Here" button after clicking address
                            select_button_selectors = [
                                'button:has-text("Select")',
                                'button:has-text("Deliver Here")',
                                'button:has-text("Use this address")',
                                'div:has-text("Select")',
                                'span:has-text("Select")'
                            ]
                            
                            for selector in select_button_selectors:
                                try:
                                    select_button = page.locator(selector)
                                    if await select_button.count() > 0:
                                        await select_button.first.click()
                                        await asyncio.sleep(2)
                                        await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Selected address using {selector}")
                                        return True
                                except Exception:
                                    continue
                            
                            # If no explicit select button, the click might be enough
                            await job_queue.log_job(job_id, LogLevel.INFO, "Address clicked, assuming selection successful")
                            return True
                            
                    except Exception as e:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"Error checking address {i}: {str(e)}")
                        continue
                
                await job_queue.log_job(job_id, LogLevel.INFO, f"Checked {addresses_found} addresses in expanded list, no matching address found")
                return False
            
            # Fallback: No "See more" button found, search current limited list
            await job_queue.log_job(job_id, LogLevel.INFO, "No 'See more' option found, searching current address list...")
            
            # For limited address list, use alternative selectors that work without expansion
            # Try multiple selector patterns that might work for different address list layouts
            address_list_selectors = [
                "#_parentCtr_ > div:nth-child(1) > div > div > div > div:nth-child(2) > div > div",
                "#_parentCtr_ > div:nth-child(1) > div > div > div > div:nth-child(2) > div",
                "#_parentCtr_ div[class*='address']",
                "#_parentCtr_ div:has-text('WORK')",
                "#_parentCtr_ div:has-text('HOME')"
            ]
            
            addresses_found = 0
            address_elements = []
            
            # Try to find addresses using multiple selector patterns
            for selector_pattern in address_list_selectors:
                try:
                    elements = page.locator(selector_pattern)
                    count = await elements.count()
                    if count > 0:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found {count} address elements using selector: {selector_pattern}")
                        for i in range(count):
                            element = elements.nth(i)
                            if await element.count() > 0:
                                address_elements.append(element)
                        break
                except Exception:
                    continue
            
            if not address_elements:
                await job_queue.log_job(job_id, LogLevel.WARNING, "No address elements found with any selector pattern")
                return False
            
            # Check each address element
            for i, address_element in enumerate(address_elements[:10]):  # Limit to 10 addresses
                try:
                    # Get the full text content of this address entry
                    address_text = await address_element.inner_text()
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Address {i+1}: {address_text[:150]}...")
                    
                    # Check if this address matches our criteria
                    if self._is_target_address(address_text, target_pincode, expected_postfix):
                        await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Found matching address at position {i+1}")
                        
                        # Click directly on this address to select it (same as expanded list logic)
                        await address_element.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        await address_element.click()
                        await asyncio.sleep(2)
                        
                        # Since we're clicking directly on the address (like in expanded list), 
                        # the click itself should be sufficient to select it
                        await job_queue.log_job(job_id, LogLevel.INFO, "✅ Successfully selected existing address")
                        return True
                        
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Error checking address {i}: {str(e)}")
                    continue
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Checked {addresses_found} existing addresses, no matching address found")
            return False
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error checking existing addresses: {str(e)}")
            return False

    
    def _is_target_address(self, address_text: str, target_pincode: str, expected_postfix: Optional[str] = None) -> bool:
        """Check if address text matches our target criteria.
        If expected_postfix is provided, require that it is present in the address text."""
        address_lower = address_text.lower()
        
        # Strict requirement: specific postfix must be present
        if expected_postfix:
            exp = expected_postfix.lower().strip()
            if exp:
                return exp in address_lower

        # Secondary criteria: Check for target pincode only
        if target_pincode in address_text:
            return True
        
        # Check for specific address patterns if needed
        address_patterns = [
            "dwarka",
            "police housing", 
            "sector 16",
            "mumbai"
        ]
        
        pattern_matches = 0
        for pattern in address_patterns:
            if pattern in address_lower:
                pattern_matches += 1
        
        # If multiple patterns match, consider it a target address
        if pattern_matches >= 2:
            return True
        
        return False

    async def check_product_price(self, product_url: str, price_cap: Optional[float], job_id: int) -> Dict[str, Any]:
        """Check product price and availability"""
        try:
            if not hasattr(self, 'context') or not self.context:
                return {"success": False, "error": "No browser context"}
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Checking price for: {product_url}")
            
            page = await self.context.new_page()
            await page.goto(product_url)
            await asyncio.sleep(3)
            
            # Extract price
            price_selectors = [
                '._30jeq3._16Jk6d',
                '._1_WHN1',
                '.CEmiEU .sr_price_wrap .notranslate'
            ]
            
            current_price = 0
            for selector in price_selectors:
                try:
                    price_element = await page.query_selector(selector)
                    if price_element:
                        price_text = await price_element.inner_text()
                        # Extract numeric price
                        import re
                        price_match = re.search(r'[\d,]+', price_text.replace('₹', '').replace(',', ''))
                        current_price = float(price_match.group()) if price_match else 0
                        break
                except:
                    continue
            
            if current_price == 0:
                # Try alternative price extraction
                price_text = await page.inner_text('body')
                import re
                price_matches = re.findall(r'₹\s*([0-9,]+)', price_text)
                if price_matches:
                    current_price = float(price_matches[0].replace(',', ''))
                
            # Check availability
            add_to_cart_btn = page.locator('button:has-text("Add to cart")')
            is_available = await add_to_cart_btn.count() > 0
            
            result = {
                "success": True,
                "price": current_price,
                "available": is_available,
                "within_budget": price_cap is None or current_price <= price_cap
            }
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Price check result: ₹{current_price}, Available: {is_available}")
            
            await page.close()
            return result
            
        except Exception as e:
            error_msg = f"Price check failed: {str(e)}"
            await job_queue.log_job(job_id, LogLevel.ERROR, error_msg)
            return {"success": False, "error": error_msg}
    
    async def add_to_cart_and_checkout(self, product_url: str, quantity: int, job_id: int) -> Dict[str, Any]:
        """Add product to cart and proceed to checkout (legacy method)"""
        try:
            if not hasattr(self, 'context') or not self.context:
                return {"success": False, "error": "No browser context"}
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Adding to cart: {product_url}")
            
            page = await self.context.new_page()
            await page.goto(product_url)
            await asyncio.sleep(3)
            
            # Add to cart
            add_to_cart_btn = page.locator('button:has-text("Add to cart")').first
            await add_to_cart_btn.click()
            await asyncio.sleep(2)
            
            await job_queue.log_job(job_id, LogLevel.INFO, "Product added to cart")
            
            # Go to cart
            await page.goto('https://www.flipkart.com/viewcart')
            await asyncio.sleep(3)
            
            # Place order
            place_order_btn = page.locator('span:has-text("Place Order")').first
            if await place_order_btn.count() == 0:
                place_order_btn = page.locator('button:has-text("Place Order")').first
            
            if await place_order_btn.count() > 0:
                await place_order_btn.click()
                await asyncio.sleep(3)
                
                await job_queue.log_job(job_id, LogLevel.INFO, "Proceeding to checkout")
            else:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Place Order button not found")
            
            await page.close()
            return {
                "success": True,
                "message": "Product added to cart and ready for order placement",
                "status": "ready_to_order"
            }
            
        except Exception as e:
            error_msg = f"Add to cart failed: {str(e)}"
            await job_queue.log_job(job_id, LogLevel.ERROR, error_msg)
            return {"success": False, "error": error_msg}

    # Main automation workflow method
    async def run_full_automation(self, products: List[Dict], job_id: int) -> bool:
        """
        Main automation workflow that orchestrates all phases
        """
        try:
            await job_queue.log_job(job_id, LogLevel.INFO, "🚀 Starting full automation workflow...")
            
            # Phase 1: Add products to cart
            cart_success = await self.add_and_configure_products_in_cart(products, job_id)
            if not cart_success:
                return False
            
            # Phase 2: Select correct address
            await job_queue.log_job(job_id, LogLevel.INFO, "Selecting correct delivery address...")
            address_success = await self.select_correct_address(job_id)
            if not address_success:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Address selection failed, continuing with current address")
            
            await job_queue.log_job(job_id, LogLevel.INFO, "Successfully navigated to cart and verified address. Proceeding to checkout...")
            
            # Phase 3: Complete checkout process
            checkout_success = await self.complete_checkout_process(job_id, address_id=address_id)
            if not checkout_success:
                return False
            
            await job_queue.log_job(job_id, LogLevel.INFO, "Full automation completed successfully. Order placed!")
            return True
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Full automation workflow failed: {str(e)}")
            return False

    async def remove_all_addresses(self, job_id: int) -> bool:
        """Remove all addresses from the account"""
        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot remove addresses: No browser context.")
            return False

        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            # Navigate to addresses page
            target_url = 'https://www.flipkart.com/rv/accounts/addresses'
            await job_queue.log_job(job_id, LogLevel.INFO, f"Navigating to addresses page: {target_url}")
            await page.goto(target_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)

            list_container_selector = '#fk-cp-richviews > div > div.Ts1TZW > div._2c9DHk'
            address_items_selector = f"{list_container_selector} > div"

            removed = 0
            max_iterations = 25

            for attempt in range(max_iterations):
                # Count addresses currently visible
                try:
                    items = page.locator(address_items_selector)
                    count = await items.count()
                except Exception:
                    count = 0

                if count == 0:
                    await job_queue.log_job(job_id, LogLevel.INFO, "No addresses found - all removed")
                    break

                await job_queue.log_job(job_id, LogLevel.INFO, f"Removing address {attempt+1}: {count} address(es) remaining")

                # Always target the first address
                menu_selector = f"{list_container_selector} > div:nth-child(1) > div > div > div:nth-child(1) > button"
                remove_selector = f"{list_container_selector} > div:nth-child(1) > div > div > div:nth-child(1) > ul > li._3nL9IF"
                confirm_selector = '#fk-cp-richviews > div > div.Ts1TZW > div._2BAM3D > div > div > div.Lz0Ctu > button:nth-child(2)'

                # Click the 3-dot menu
                try:
                    menu = page.locator(menu_selector)
                    if await menu.count() > 0 and await menu.first.is_visible():
                        await menu.first.click(timeout=4000)
                        await asyncio.sleep(0.4)
                    else:
                        menu = page.locator("button:has(svg)").first
                        await menu.click(timeout=4000)
                        await asyncio.sleep(0.4)
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Could not open menu: {e}")
                    break

                # Click Remove
                try:
                    rem = page.locator(remove_selector)
                    if await rem.count() > 0 and await rem.first.is_visible():
                        await rem.first.click(timeout=3000)
                    else:
                        by_text = page.get_by_text("Remove")
                        if await by_text.count() > 0 and await by_text.first.is_visible():
                            await by_text.first.click(timeout=3000)
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to click Remove: {e}")
                    continue

                # Confirm deletion (Okay)
                try:
                    await asyncio.sleep(0.5)
                    ok_btn = page.locator(confirm_selector)
                    if await ok_btn.count() > 0 and await ok_btn.first.is_visible():
                        await ok_btn.first.click(timeout=4000)
                    else:
                        import re
                        ok_text = page.get_by_text(re.compile(r"\bok(ay)?\b", re.I))
                        if await ok_text.count() > 0 and await ok_text.first.is_visible():
                            await ok_text.first.click(timeout=3000)
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to confirm deletion: {e}")

                await asyncio.sleep(1.2)
                removed += 1
                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Removed address #{removed}")

            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Address removal completed. Total removed: {removed}")
            return True
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to remove addresses: {str(e)}")
            return False

    async def add_address_mobile(self, job_id: int, address_id: Optional[int] = None) -> bool:
        """Add address using mobile Flipkart interface"""
        context = await self.browser_manager.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot add address: No browser context.")
            return False

        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            await job_queue.log_job(job_id, LogLevel.INFO, "Starting mobile add address process")
            
            # Load address configuration from database
            address_config = await self._load_address_config(address_id, job_id)
            if not address_config:
                await job_queue.log_job(job_id, LogLevel.ERROR, "❌ AUTOMATION CANCELLED: Failed to load address configuration from database")
                return False
            
            # Navigate to mobile add address page
            await job_queue.log_job(job_id, LogLevel.INFO, "Navigating to mobile add address page")
            await page.goto('https://www.flipkart.com/rv/accounts/addaddress')
            await asyncio.sleep(1.0)
            
            # Quickly dismiss any common permission/overlay prompts (best-effort, non-blocking)
            try:
                for sel in ['button:has-text("Not now")', 'button:has-text("Cancel")', 'button:has-text("Deny")']:
                    btn = page.locator(sel)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click()
                        await asyncio.sleep(0.2)
                        break
            except Exception:
                pass
            
            # Wait for form to load completely
            await job_queue.log_job(job_id, LogLevel.INFO, "Waiting for address form to load...")
            await page.wait_for_selector('#addressform', timeout=10000)
            await asyncio.sleep(0.3)
            
            # Generate randomized address details using database configuration
            address_details = self._generate_random_address_details(address_config)
            
            # Fill Full Name with user-provided selector first
            await job_queue.log_job(job_id, LogLevel.INFO, f"Entering full name: {address_details['full_name']}")
            full_name_selectors = [
                'input[name="name"]',
                '#name',
                'input[data-elementtype="text"]',
                '#addressform input[type="text"]:first',
                "#addressform > div > div._29c-ns._1CtMQn._19jXxw > div._3ZEfqN._2N_AyM._3ud9K-._39Cuz8 > div._3xNCye > input"
            ]
            await self._fill_field_with_fallback(page, full_name_selectors, address_details['full_name'], job_id, "Full Name")
            
            # Fill Phone Number with user-provided selector first
            await job_queue.log_job(job_id, LogLevel.INFO, f"Entering phone number: {address_details['phone']}")
            phone_selectors = [
                'input[name="phone"]',
                '#phone',
                'input[data-elementtype="tel"]',
                'input[type="tel"]',
                "#addressform > div > div._29c-ns._1CtMQn._19jXxw > div:nth-child(2) > div._3xNCye > input"
            ]
            await self._fill_field_with_fallback(page, phone_selectors, address_details['phone'], job_id, "Phone Number")
            
            # Fill Pin Code with user-provided selector first
            await job_queue.log_job(job_id, LogLevel.INFO, f"Entering pincode: {address_details['pincode']}")
            pincode_selectors = [
                'input[name="pincode"]',
                '#pincode',
                'input[data-elementtype="number"]',
                'input[type="number"]:first',
                "#addressform > div > div._29c-ns._3sVoLS._19jXxw > div > div:nth-child(1) > div._3fhcTO > div._226P_g.D7u1cs._1uOoge > div > div._3xNCye > input"
            ]
            await self._fill_field_with_fallback(page, pincode_selectors, address_details['pincode'], job_id, "Pincode")
            await asyncio.sleep(1.0)  # Short wait for auto-populate
            
            # Fill Address Line 1 (House No., Building Name) with user-provided selector first
            await job_queue.log_job(job_id, LogLevel.INFO, f"Entering address line 1: {address_details['address_line1']}")
            address_line1_selectors = [
                'textarea[name="addressLine1"]',
                '#addressLine1',
                'textarea[data-elementtype="textarea"]:first',
                "#addressform > div > div._29c-ns._3sVoLS._19jXxw > div > div > div.NOHJeo > div._3ZEfqN > div._3xNCye > textarea"
            ]
            await self._fill_field_with_fallback(page, address_line1_selectors, address_details['address_line1'], job_id, "Address Line 1")
            
            # Fill Address Line 2 (Road name, Area, Colony) with user-provided selector first
            await job_queue.log_job(job_id, LogLevel.INFO, f"Entering address line 2: {address_details['address_line2']}")
            address_line2_selectors = [
                'textarea[name="addressLine2"]',
                '#addressLine2',
                'textarea[data-elementtype="textarea"]:nth-child(2)',
                "#addressform > div > div._29c-ns._3sVoLS._19jXxw > div > div > div.NOHJeo > div._3ZEfqN > div._3xNCye._19sjab > textarea"
            ]
            await self._fill_field_with_fallback(page, address_line2_selectors, address_details['address_line2'], job_id, "Address Line 2")
            
            # Select Address Type (Home by default)
            home_radio_selector = 'input[name="locationTypeTag"][value="HOME"]'
            await job_queue.log_job(job_id, LogLevel.INFO, "Selecting address type: Home")
            await page.click(home_radio_selector)
            await asyncio.sleep(0.5)
            
            # Click Save Address button
            save_button_selector = 'input[type="submit"][value="Save Address"]'
            await job_queue.log_job(job_id, LogLevel.INFO, "Clicking Save Address button")
            await page.click(save_button_selector)
            await asyncio.sleep(0.5)
            # Quick success check: form disappears on success
            try:
                await page.wait_for_selector('#addressform', state='detached', timeout=4000)
            except Exception:
                pass
            
            # Check for validation errors after clicking save
            error_messages = []
            
            # Check for error messages on the page (red text, error messages)
            error_selectors = [
                'text=/please provide a valid/i',
                'text=/is currently unavailable/i',
                'text=/required/i',
                '.error-message',
                '[class*="error"]'
            ]
            
            for selector in error_selectors:
                try:
                    error_elements = page.locator(selector)
                    count = await error_elements.count()
                    if count > 0:
                        for i in range(count):
                            error_text = await error_elements.nth(i).text_content()
                            if error_text and error_text.strip():
                                error_messages.append(error_text.strip())
                except Exception:
                    continue
            
            # Check if we're still on the add address page (form still visible)
            # If successful, we should be redirected away from the form
            try:
                form_still_visible = await page.locator('#addressform').is_visible(timeout=2000)
                if form_still_visible:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "⚠️ Address form is still visible after save attempt")
            except Exception:
                # Form not visible anymore, which is good
                form_still_visible = False
            
            # If there are validation errors, report them and return False
            if error_messages:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Address validation failed with errors:")
                for error in error_messages:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"   - {error}")
                return False
            
            # If form is still visible and we found no specific errors, check URL
            if form_still_visible:
                current_url = page.url
                if 'addaddress' in current_url.lower():
                    await job_queue.log_job(job_id, LogLevel.ERROR, "❌ Address save failed: Still on add address page with no specific errors captured")
                    # Try to capture any visible text that might indicate an error
                    try:
                        page_content = await page.content()
                        if 'please provide' in page_content.lower() or 'required' in page_content.lower() or 'unavailable' in page_content.lower():
                            await job_queue.log_job(job_id, LogLevel.ERROR, "Validation errors detected in page content")
                    except Exception:
                        pass
                    return False
            
            await job_queue.log_job(job_id, LogLevel.INFO, "✅ Mobile address added successfully")
            return True
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to add mobile address: {str(e)}")
            import traceback
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Stack trace: {traceback.format_exc()}")
            return False

    async def _load_address_config(self, address_id: Optional[int], job_id: int) -> dict:
        """Load address configuration from database"""
        try:
            from database import DATABASE_URL
            import asyncpg
            
            conn = await asyncpg.connect(DATABASE_URL)
            
            # DEBUG: Log the received address_id
            await job_queue.log_job(job_id, LogLevel.INFO, f"🔍 DEBUG: Received address_id parameter: {address_id} (type: {type(address_id)})")
            
            # Load address configuration
            if address_id:
                address = await conn.fetchrow('''
                    SELECT * FROM addresses 
                    WHERE id = $1 AND is_active = TRUE
                ''', address_id)
                await job_queue.log_job(job_id, LogLevel.INFO, f"📍 Attempting to load SPECIFIC address with ID: {address_id}")
                
                if not address:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Address with ID {address_id} not found or inactive, falling back to default")
            else:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ No address_id provided (address_id is {address_id}), using fallback logic")
                address = None
            
            # Fallback logic if specific address not found or no address_id provided
            if not address:
                # Use default address
                address = await conn.fetchrow('''
                    SELECT * FROM addresses 
                    WHERE is_default = TRUE AND is_active = TRUE
                    LIMIT 1
                ''')
                await job_queue.log_job(job_id, LogLevel.INFO, "📍 Loading DEFAULT address configuration")
                
                if not address:
                    # Fallback to first active address
                    address = await conn.fetchrow('''
                        SELECT * FROM addresses 
                        WHERE is_active = TRUE
                        ORDER BY created_at ASC
                        LIMIT 1
                    ''')
                    await job_queue.log_job(job_id, LogLevel.INFO, "📍 Loading FIRST AVAILABLE address configuration")
            
            await conn.close()
            
            if not address:
                await job_queue.log_job(job_id, LogLevel.ERROR, "❌ No active address found in database")
                return None
                
            # Convert to dict and log the loaded configuration
            address_config = dict(address)
            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ FINAL LOADED ADDRESS: '{address_config['name']}' (ID: {address_config['id']})")
            await job_queue.log_job(job_id, LogLevel.INFO, f"Address template: {address_config['address_template']}")
            await job_queue.log_job(job_id, LogLevel.INFO, f"Phone prefix: {address_config['phone_prefix']}, Pincode: {address_config['pincode']}")
            
            return address_config
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Failed to load address configuration: {str(e)}")
            return None

    async def _fill_field_with_fallback(self, page, selectors: list, value: str, job_id: int, field_name: str):
        """Try multiple selectors to fill a field with fallback logic"""
        for i, selector in enumerate(selectors):
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    await element.first.wait_for(state='visible', timeout=2500)
                    await element.first.fill(value)
                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ {field_name} filled using selector #{i+1}: {selector}")
                    await asyncio.sleep(0.15)
                    return True
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"❌ {field_name} selector #{i+1} failed: {str(e)}")
                continue
        
        await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ All selectors failed for {field_name}")
        return False

    def _generate_random_address_details(self, address_data: dict) -> dict:
        """Generate randomized address details based on address template"""
        import random
        import string
        import os
        
        # Extract address configuration
        name_postfix = address_data.get('name_postfix', '')
        phone_prefix = address_data.get('phone_prefix', '6000')
        pincode = address_data.get('pincode', '400010')
        address_template = address_data.get('address_template', 'Office {office_no}, Building Name')
        office_no_min = address_data.get('office_no_min', 101)
        office_no_max = address_data.get('office_no_max', 999)
        
        # Generate random office number within range
        office_no = random.randint(office_no_min, office_no_max)
        
        # Load first names from names.txt file
        names_file_path = '/home/watso/Vulncure/Project/Order_Auto/backend/names.txt'
        first_names = []
        
        try:
            if os.path.exists(names_file_path):
                with open(names_file_path, 'r', encoding='utf-8') as f:
                    first_names = [name.strip() for name in f.readlines() if name.strip()]
            else:
                # Fallback to hardcoded names if file not found
                first_names = ['Abhishek', 'Rajesh', 'Suresh', 'Ramesh', 'Mahesh', 'Dinesh', 'Mukesh', 'Naresh']
        except Exception:
            # Fallback to hardcoded names if file reading fails
            first_names = ['Abhishek', 'Rajesh', 'Suresh', 'Ramesh', 'Mahesh', 'Dinesh', 'Mukesh', 'Naresh']
        
        # Generate random name with postfix from database address config
        first_name = random.choice(first_names)
        full_name = f"{first_name} {name_postfix}".strip()
        
        # Generate random phone number with prefix
        phone_suffix = ''.join(random.choices(string.digits, k=6))  # Generate 6 random digits
        phone = f"{phone_prefix}{phone_suffix}"
        
        # Generate address lines with office number
        address_line1 = address_template.replace('{office_no}', str(office_no))
        address_line2 = address_template.replace('{office_no}', str(office_no))  # Same as line 1 as requested
        
        return {
            'full_name': full_name,
            'phone': phone,
            'pincode': pincode,
            'address_line1': address_line1,
            'address_line2': address_line2,
            'office_no': office_no
        }
