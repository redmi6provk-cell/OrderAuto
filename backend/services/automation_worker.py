"""
Automation Worker Service - Clean Refactored Version
Handles Flipkart automation jobs using Playwright with modular structure
"""

import asyncio
import re
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List
import traceback
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Add the parent directory to Python path to import automation modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from services.job_queue import register_worker, job_queue, LogLevel
from services.gmail_service import gmail_service
from database import DATABASE_URL
import asyncpg
from services.automation_tasks.add_address_task import fill_address_form

# Import the new modular components
from services.automation_tasks.core_worker import AutomationWorker as CoreWorker


class AutomationWorker(CoreWorker):
    """Legacy wrapper that inherits from the new modular CoreWorker"""
    def __init__(self):
        super().__init__()
        
    # Additional legacy methods specific to this automation worker
    async def add_new_address(self, address_data: Dict[str, Any], job_id: int) -> bool:
        """Add a new address to the Flipkart account"""
        context = await self.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot add address: No browser context.")
            return False
        
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Navigate to address management page
            await page.goto('https://www.flipkart.com/account/addresses')
            await asyncio.sleep(3)
            
            # Use the existing fill_address_form function
            success = await fill_address_form(page, address_data, job_id)
            
            if success:
                await job_queue.log_job(job_id, LogLevel.INFO, "Address added successfully")
            else:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to add address")
            
            return success
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error adding address: {str(e)}")
            return False


# Create a global instance for the worker functions
automation_worker = AutomationWorker()


@register_worker("flipkart_login")
async def run_full_automation(job_data: Dict[str, Any], job_id: int) -> Dict[str, Any]:
    """
    Handles the complete automation flow:
    1. Login to Flipkart
    2. Add products to cart (if provided)
    3. Complete checkout process (if requested)
    """
    try:
        email = job_data.get("email")
        products = job_data.get("products", [])
        view_mode = job_data.get("view_mode", "desktop")
        enable_checkout = job_data.get("enable_checkout", True)
        # Apply headless preference for this job
        try:
            headless_pref = bool(job_data.get("headless"))
        except Exception:
            headless_pref = False
        automation_worker.browser_manager.set_headless(headless_pref)
        await automation_worker.initialize_browser()

        if not email:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "no_email_provided")
            return {"success": False, "error": "Email not provided in job data"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting full automation for {email}")

        # Phase 1: Login to Flipkart
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1: Logging in to Flipkart")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)

        if not login_success:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "login_failed")
            return {"success": False, "error": "Phase 1 failed: Login was unsuccessful"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1 completed successfully")

        # If no products provided, this is just a login test - stop here
        if not products:
            await job_queue.log_job(job_id, LogLevel.INFO, "✅ Login-only mode - automation completed successfully")
            return {"success": True, "message": "Login test successful"}

        # Phase 1.2: Remove all addresses from account
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.2: Removing all existing addresses")
        remove_success = await automation_worker.remove_all_addresses(job_id)
        if not remove_success:
            await job_queue.log_job(job_id, LogLevel.ERROR, "❌ AUTOMATION CANCELLED: Failed to remove addresses")
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "remove_addresses_failed")
            return {"success": False, "error": "Failed to remove addresses"}
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.2 completed successfully")

        # Phase 1.3: Add one fresh randomized address
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.3: Adding fresh randomized address")
        address_id = job_data.get('address_id')
        add_success = await automation_worker.add_address_mobile(job_id, address_id)
        if not add_success:
            await job_queue.log_job(job_id, LogLevel.ERROR, "❌ AUTOMATION CANCELLED: Failed to add address")
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "add_address_failed")
            return {"success": False, "error": "Failed to add address"}
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.3 completed successfully")

        # Phase 1.4: Ensure cart is empty before proceeding
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.4: Ensuring cart is empty before proceeding")
        preclear_result = await automation_worker.cart_manager.clear_cart_if_needed(job_id)
        if not preclear_result.get("success"):
            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ AUTOMATION CANCELLED: Failed to clear cart: {preclear_result.get('error')}")
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "clear_cart_failed")
            return {"success": False, "error": "Failed to clear cart"}
        else:
            if preclear_result.get("performed"):
                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Cart cleared (removed={preclear_result.get('removed',0)}, decremented={preclear_result.get('decremented',0)})")
            else:
                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Cart already empty (no action)")
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.4 completed successfully")

        # Phase 2: Add products to cart and configure quantities
        await job_queue.log_job(job_id, LogLevel.INFO, f"Phase 2: Adding {len(products)} products to cart")
        max_cart_value = job_data.get('max_cart_value')
        products_result = await automation_worker.add_and_configure_products_in_cart(products, job_id, max_cart_value)

        if not products_result["success"]:
            # Log the specific cancellation reason for account failure tracking
            cancel_reason = products_result.get("cancel_reason", "unknown")
            error_msg = products_result.get("error", "Error during product processing")

            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ ACCOUNT AUTOMATION FAILED - Reason: {cancel_reason}")
            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Error Details: {error_msg}")

            # Final (failure) summary
            await job_queue.log_job(job_id, LogLevel.INFO, "\n📊 FINAL SUMMARY (FAILED):")
            await job_queue.log_job(job_id, LogLevel.INFO, f"   Account: {email}")
            await job_queue.log_job(job_id, LogLevel.INFO, f"   Status: FAIL")
            await job_queue.log_job(job_id, LogLevel.INFO, f"   Message: {error_msg}")
            await job_queue.log_job(job_id, LogLevel.INFO, f"   Products meet quantity: False")
            await job_queue.log_job(job_id, LogLevel.INFO, f"   Products total: {len(products)}")
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, f"phase2_failed_{cancel_reason}")

            return {"success": False, "error": f"Phase 2 failed: {error_msg}", "cancel_reason": cancel_reason}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2 completed successfully")

        # Phase 3: Complete checkout process (if enabled)
        if enable_checkout:
            await job_queue.log_job(job_id, LogLevel.INFO, "Phase 3: Starting checkout process")
            address_id = job_data.get("address_id")  # Get address_id from job data
            # Optional GST details for order summary
            gstin = job_data.get("gstin")
            business_name = job_data.get("business_name")
            # Optional steal deal product name
            steal_deal_product = job_data.get("steal_deal_product")
            checkout_result = await automation_worker.complete_checkout_process(job_id, max_cart_value, address_id, gstin, business_name, steal_deal_product)

            if checkout_result.get("success"):
                await job_queue.log_job(job_id, LogLevel.INFO, "Phase 3 completed successfully - Order placed!")

                # Compose final summary (only after successful order placement)
                added_products = products_result.get("added_products")
                total_products = products_result.get("total_products")
                products_meet_quantity = (
                    isinstance(added_products, int) and isinstance(total_products, int) and added_products == total_products
                )

                await job_queue.log_job(job_id, LogLevel.INFO, "\n📊 FINAL ORDER SUMMARY:")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Account: {email}")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Status: SUCCESS")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Message: {checkout_result.get('message', 'Order placed successfully')}")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Order ID: {checkout_result.get('order_id')}")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Cart total: ₹{checkout_result.get('cart_total')}")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Basket items: {checkout_result.get('basket_items')}")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Expected delivery: {checkout_result.get('expected_delivery')}")
                if checkout_result.get('delivery_address_name'):
                    await job_queue.log_job(job_id, LogLevel.INFO, f"   Delivery address: {checkout_result.get('delivery_address_name')}")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Products total: {total_products}")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Products meet quantity: {products_meet_quantity}")

                # Return enriched success payload
                payload = {
                    "success": True,
                    "message": "Full automation completed successfully. Order placed!",
                    "order_id": checkout_result.get("order_id"),
                    "cart_total": checkout_result.get("cart_total"),
                    "basket_items": checkout_result.get("basket_items"),
                    "expected_delivery": checkout_result.get("expected_delivery"),
                    "delivery_address_name": checkout_result.get("delivery_address_name"),
                    "account": email,
                    "products_total": total_products,
                    "products_meet_quantity": products_meet_quantity,
                }
                return payload
            else:
                # Failure summary for checkout
                await job_queue.log_job(job_id, LogLevel.INFO, "\n📊 FINAL SUMMARY (FAILED):")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Account: {email}")
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Status: FAIL")
                failure_msg = checkout_result.get('message', 'Checkout process unsuccessful')
                await job_queue.log_job(job_id, LogLevel.INFO, f"   Message: {failure_msg}")
                await automation_worker.browser_manager.capture_failure_screenshot(job_id, "checkout_failed")
                return {"success": False, "error": f"FAILED: {failure_msg}"}
        else:
            await job_queue.log_job(job_id, LogLevel.INFO, "Checkout disabled - automation completed with products in cart")
            return {"success": True, "message": "Products added to cart successfully. Checkout not enabled."}

    except Exception as e:
        error_message = f"An unexpected error occurred in automation: {str(e)}"
        await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
        logging.error(error_message)
        await automation_worker.browser_manager.capture_failure_screenshot(job_id, "unexpected_exception")
        return {"success": False, "error": error_message}
    finally:
        # Conditionally keep the browser open for login tests if requested
        keep_open = False
        try:
            keep_open = bool(job_data.get("keep_browser_open"))
        except Exception:
            keep_open = False
        if keep_open:
            await job_queue.log_job(job_id, LogLevel.INFO, "Keeping browser open for manual closure (login test). Close the browser window to end the session.")
        else:
            # This is crucial: ensures the browser context is always closed for this job.
            await automation_worker.cleanup_job_context(job_id)


@register_worker("add_coupon")
async def run_add_coupon_automation(job_data: Dict[str, Any], job_id: int) -> Dict[str, Any]:
    """
    Automation to add a coupon to the account via MyRewards.
    Steps:
    1. Login to Flipkart
    2. Navigate to https://www.flipkart.com/myrewards
    3. Open Add Coupon popup
    4. Fill coupon code and click Add Coupon
    """
    try:
        email = job_data.get("email")
        coupon_code = (job_data.get("coupon_code") or "").strip()
        view_mode = job_data.get("view_mode", "mobile")

        # Apply headless preference for this job
        try:
            headless_pref = bool(job_data.get("headless"))
        except Exception:
            headless_pref = False
        automation_worker.browser_manager.set_headless(headless_pref)
        await automation_worker.initialize_browser()

        if not email:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_no_email")
            return {"success": False, "error": "Email not provided in job data"}
        if not coupon_code:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_no_code")
            return {"success": False, "error": "Coupon code not provided"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting 'Add Coupon' automation for {email}")

        # Phase 1: Login
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1: Logging in to Flipkart")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)
        if not login_success:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_login_failed")
            return {"success": False, "error": "Phase 1 failed: Login was unsuccessful"}
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1 (Login) completed successfully.")

        # Use existing context
        context = await automation_worker.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot proceed: No browser context after login.")
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_no_context")
            return {"success": False, "error": "No browser context"}

        page = context.pages[0] if context.pages else await context.new_page()

        # Phase 2: Open MyRewards
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2: Navigating to MyRewards page")
        await page.goto('https://www.flipkart.com/myrewards', wait_until='domcontentloaded')
        await asyncio.sleep(2)

        # Click on Add Coupon action in navbar/header
        await job_queue.log_job(job_id, LogLevel.INFO, "Opening 'Add Coupon' popup")
        open_clicked = False
        open_selectors = [
            # Accessible role/text
            'button:has-text("Add Coupon")',
            'a:has-text("Add Coupon")',
            # Text locator
            'text="Add Coupon"',
            # Provided brittle CSS fallback
            '#_parentCtr_ > div:nth-child(1) > div > div > div.css-175oi2r.r-1awozwy.r-1euycsn > div > div > div'
        ]
        for sel in open_selectors:
            try:
                locator = page.locator(sel)
                if await locator.count() > 0 and await locator.first.is_visible():
                    await locator.first.click()
                    open_clicked = True
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Clicked 'Add Coupon' trigger using selector: {sel}")
                    break
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Failed selector for Add Coupon trigger ({sel}): {e}")

        if not open_clicked:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_popup_not_opened")
            return {"success": False, "error": "Could not open Add Coupon popup"}

        # Wait for popup content
        try:
            await page.wait_for_selector('text="Enter Coupon Code"', timeout=8000)
        except Exception:
            # Continue; rely on input detection below
            pass

        # Find coupon input
        coupon_input = None
        input_selectors = [
            '#_parentCtr_ > div:nth-child(1) > div > div > div > div:nth-child(2) > div > div > div > div > div > div.css-175oi2r.r-13awgt0.r-eqz5dr > div.css-175oi2r > input',
            '#_parentCtr_ input[type="text"]',
            'input[type="text"]',
            'input[placeholder*="coupon" i]'
        ]
        for sel in input_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    coupon_input = loc.first
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Found coupon input using selector: {sel}")
                    break
            except Exception:
                continue

        if not coupon_input:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_input_not_found")
            return {"success": False, "error": "Coupon input field not found"}

        await coupon_input.click()
        await coupon_input.fill(coupon_code)
        await asyncio.sleep(0.5)

        # Click Add Coupon button inside popup
        add_btn_clicked = False
        add_btn_selectors = [
            # New provided selector (most specific)
            'div.css-175oi2r.r-1awozwy.r-18u37iz.r-1777fci.r-1tuna9m.r-eu3ka',
            # Accessible/text fallbacks
            'button:has-text("Add Coupon")',
            'div[role="button"]:has-text("Add Coupon")',
            'text="Add Coupon"',
            # Previously working brittle selector
            '#_parentCtr_ > div:nth-child(2) > div > div > div > div > div > div'
        ]
        for sel in add_btn_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    btn = loc.first
                    # Ensure visible on screen
                    try:
                        await btn.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    # Some buttons are divs; ensure visible and enabled
                    try:
                        is_enabled = await btn.is_enabled()
                    except Exception:
                        is_enabled = True
                    if await btn.is_visible() and is_enabled:
                        try:
                            await btn.click()
                        except Exception:
                            # Fallback to JS click
                            try:
                                elem = await btn.element_handle()
                                if elem:
                                    await page.evaluate('(el) => el.click()', elem)
                            except Exception:
                                pass
                        # Heuristic: consider clicked; we'll validate by outcome below
                        add_btn_clicked = True
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Clicked Add Coupon button using selector: {sel}")
                        break
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Failed to click Add Coupon button ({sel}): {e}")

        # As an extra fallback, try pressing Enter in the input (common to submit forms)
        if not add_btn_clicked:
            try:
                await coupon_input.press('Enter')
                add_btn_clicked = True
                await job_queue.log_job(job_id, LogLevel.INFO, "Pressed Enter in coupon input as fallback for submission")
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Enter key fallback failed: {e}")

        if not add_btn_clicked:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_button_not_clicked")
            return {"success": False, "error": "Could not click Add Coupon button"}

        # Wait briefly for result; attempt to detect success or error
        await asyncio.sleep(2)

        # Try targeted wait for known error container to appear
        error_container_selectors = [
            'div.css-1rynq56.r-13yew0m.r-1et8rh5.r-1enofrn.r-14gqq1x',
            '#_parentCtr_ div.css-1rynq56.r-13yew0m.r-1et8rh5.r-1enofrn.r-14gqq1x',
        ]
        error_container_text = None
        for ecs in error_container_selectors:
            try:
                loc = page.locator(ecs)
                if await loc.count() > 0:
                    # Give it a little time to render message
                    await loc.first.wait_for(state='visible', timeout=2000)
                    try:
                        error_container_text = (await loc.first.inner_text()).strip()
                        if error_container_text:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Detected error container text: {error_container_text}")
                            break
                    except Exception:
                        pass
            except Exception:
                continue

        # Detect common error/success messages within the popup area
        error_messages = [
            "The code you have entered is invalid",
            "invalid",
            "not applicable",
            "expired",
        ]
        success_messages = [
            "Coupon added",
            "success",
            "applied",
            "added successfully",
        ]

        # Scope to popup container if possible
        popup_scope = page.locator('#_parentCtr_').first if await page.locator('#_parentCtr_').count() > 0 else page
        popup_text = ""
        try:
            popup_text = await popup_scope.inner_text()
        except Exception:
            pass

        # Prefer specific error container text if present
        base_text = (error_container_text or popup_text or "")

        detected_error = next((m for m in error_messages if m.lower() in base_text.lower()), None)
        detected_success = next((m for m in success_messages if m.lower() in base_text.lower()), None)

        if detected_error:
            await job_queue.log_job(job_id, LogLevel.WARNING, f"Coupon submission failed: {detected_error}")
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_submission_error")
            return {"success": False, "error": detected_error, "coupon_code": coupon_code}
        elif detected_success:
            await job_queue.log_job(job_id, LogLevel.INFO, f"Coupon submission succeeded: {detected_success}")
            return {"success": True, "message": detected_success, "coupon_code": coupon_code}
        else:
            await job_queue.log_job(job_id, LogLevel.INFO, f"Add Coupon flow attempted for code '{coupon_code}'. No explicit success/error text detected.")
            return {"success": True, "message": "Coupon submission attempted.", "coupon_code": coupon_code}

    except Exception as e:
        error_message = f"An unexpected error occurred in the 'Add Coupon' automation job: {str(e)}"
        await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
        logging.error(error_message)
        await automation_worker.browser_manager.capture_failure_screenshot(job_id, "coupon_exception")
        return {"success": False, "error": error_message}
    finally:
        # Always cleanup context for this job
        await automation_worker.cleanup_job_context(job_id)


@register_worker("clear_cart")
async def run_clear_cart_automation(job_data: Dict[str, Any], job_id: int) -> Dict[str, Any]:
    """
    Clears all items from the Grocery cart - simplified robust version.
    Strategy: Repeatedly find and click any Remove buttons or minus buttons until cart is empty.
    """
    try:
        email = job_data.get("email")
        view_mode = job_data.get("view_mode", "mobile")

        try:
            headless_pref = bool(job_data.get("headless"))
        except Exception:
            headless_pref = False
        automation_worker.browser_manager.set_headless(headless_pref)
        await automation_worker.initialize_browser()

        if not email:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "clear_cart_no_email")
            return {"success": False, "error": "Email not provided"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting Clear Cart automation for {email}")

        # Login
        await job_queue.log_job(job_id, LogLevel.INFO, "Logging in...")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)
        if not login_success:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "clear_cart_login_failed")
            return {"success": False, "error": "Login failed"}

        context = await automation_worker.get_job_context(job_id)
        if not context:
            return {"success": False, "error": "No browser context"}

        page = context.pages[0] if context.pages else await context.new_page()

        # Open cart
        await job_queue.log_job(job_id, LogLevel.INFO, "Opening Grocery cart...")
        await page.goto('https://www.flipkart.com/viewcart?marketplace=GROCERY', wait_until='domcontentloaded')
        await asyncio.sleep(1.2)

        # Check if empty
        async def is_empty():
            try:
                # Check for "Your basket is empty!" text anywhere on page
                if await page.get_by_text("Your basket is empty").count() > 0:
                    return True
                # Check header - if it says just "Grocery basket" with no count
                header = await page.locator('#guidSearch > div > h1').inner_text()
                if "Grocery basket" in header and "item" not in header:
                    return True
            except Exception:
                pass
            return False

        if await is_empty():
            await job_queue.log_job(job_id, LogLevel.INFO, "Cart already empty")
            return {"success": True, "message": "Cart already empty", "removed": 0, "decremented": 0, "account": email}

        removed = 0
        decremented = 0
        max_attempts = 15

        for attempt in range(max_attempts):
            made_progress = False
            
            # Always scroll to top before each attempt to ensure we see the actual cart items
            try:
                await page.evaluate('window.scrollTo(0, 0)')
                await asyncio.sleep(0.2)
            except Exception:
                pass
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Attempt {attempt + 1}/{max_attempts}...")

            # Strategy 1: Click all "Remove" buttons (for out of stock items)
            try:
                # Quick search for Remove buttons - fail fast if none exist
                remove_buttons = []
                
                # Primary method: Exact text match "Remove"
                try:
                    btns = page.get_by_text("Remove", exact=True)
                    count = await btns.count()
                    if count > 0:
                        for i in range(count):
                            remove_buttons.append(btns.nth(i))
                except Exception:
                    pass
                
                # If no exact matches, try role-based search
                if len(remove_buttons) == 0:
                    try:
                        btns = page.get_by_role("button", name=re.compile(r"^Remove$", re.I))
                        count = await btns.count()
                        if count > 0:
                            for i in range(count):
                                remove_buttons.append(btns.nth(i))
                    except Exception:
                        pass

                if len(remove_buttons) > 0:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Found {len(remove_buttons)} Remove button(s)")
                    
                    for btn in remove_buttons:
                        try:
                            # Quick visibility check with short timeout
                            if await btn.is_visible(timeout=500):
                                # Don't scroll - items should be visible at top already
                                await btn.click(timeout=1500)
                                removed += 1
                                made_progress = True
                                await job_queue.log_job(job_id, LogLevel.INFO, f"✓ Clicked Remove button #{removed}")
                                await asyncio.sleep(0.3)
                        except Exception:
                            # Skip this button and continue
                            continue
                else:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, "No Remove buttons found")
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Remove button search error: {e}")

            # Short wait for UI to settle only if we clicked something
            if removed > 0:
                await asyncio.sleep(0.3)

            # Check if empty after removing
            if await is_empty():
                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Cart is now empty!")
                return {"success": True, "message": "Cart cleared", "removed": removed, "decremented": decremented, "account": email}

            # Strategy 2: Click minus buttons to decrement quantities
            try:
                # Find the quantity control containers, then get the first child (minus button)
                # The container pattern is: div with classes r-1awozwy.r-qwd59z.r-18u37iz.r-mabqd8.r-1777fci.r-7bouqp
                # Minus is always the first child, Plus is the third child
                
                # Method 1: Find by container structure and first child, but only within the cart area
                minus_buttons = []
                try:
                    # Scope to the actual cart container to avoid promo sections
                    cart_area = page.locator('#_parentCtr_')
                    containers = cart_area.locator('div.css-175oi2r.r-1awozwy.r-qwd59z.r-18u37iz.r-mabqd8.r-1777fci.r-7bouqp')
                    container_count = await containers.count()
                    for i in range(container_count):
                        try:
                            # Get the first child which is the minus button
                            minus = containers.nth(i).locator('> div:nth-child(1)')
                            if await minus.count() > 0:
                                minus_buttons.append(minus.first)
                        except Exception:
                            continue
                except Exception:
                    pass
                
                # Method 2: Fallback - find minus icon image specifically, but only in cart area
                if len(minus_buttons) == 0:
                    try:
                        # Scope to cart area
                        cart_area = page.locator('#_parentCtr_')
                        # Minus icon has this specific URL pattern
                        minus_imgs = cart_area.locator('img[src*="beb19156-518d-4110-bceb"]')
                        img_count = await minus_imgs.count()
                        for i in range(img_count):
                            try:
                                # Get the clickable parent of the image
                                img = minus_imgs.nth(i)
                                parent = img.locator('xpath=..')
                                if await parent.count() > 0:
                                    minus_buttons.append(parent.first)
                            except Exception:
                                continue
                    except Exception:
                        pass
                
                await job_queue.log_job(job_id, LogLevel.INFO, f"Found {len(minus_buttons)} minus button(s)")
                
                for btn in minus_buttons:
                    try:
                        # Quick visibility check
                        if await btn.is_visible(timeout=500):
                            # Don't scroll - items should be visible at top already
                            await btn.click(timeout=1500)
                            decremented += 1
                            made_progress = True
                            await job_queue.log_job(job_id, LogLevel.INFO, f"✓ Clicked minus button #{decremented}")
                            await asyncio.sleep(0.12)
                    except Exception:
                        # Skip and continue
                        continue
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Minus button search error: {e}")

            # Check if empty after decrementing
            if await is_empty():
                await job_queue.log_job(job_id, LogLevel.INFO, "✅ Cart is now empty!")
                return {"success": True, "message": "Cart cleared", "removed": removed, "decremented": decremented, "account": email}

            # If no progress made, exit to avoid infinite loop
            if not made_progress:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"No progress in attempt {attempt + 1}")
                # Still nothing? Break after a few tries
                if attempt > 2:  # Give at least 3 tries
                    break

        # Final check
        if await is_empty():
            return {"success": True, "message": "Cart cleared", "removed": removed, "decremented": decremented, "account": email}
        else:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "clear_cart_not_empty")
            return {"success": False, "error": "Could not fully clear cart", "removed": removed, "decremented": decremented}

    except Exception as e:
        await job_queue.log_job(job_id, LogLevel.ERROR, f"Clear cart error: {str(e)}")
        logging.error(f"Clear cart error: {str(e)}")
        await automation_worker.browser_manager.capture_failure_screenshot(job_id, "clear_cart_exception")
        return {"success": False, "error": str(e)}
    finally:
        await automation_worker.cleanup_job_context(job_id)


@register_worker("add_address")
async def run_add_address_automation(job_data: Dict[str, Any], job_id: int) -> Dict[str, Any]:
    """
    Handles the full automation flow for adding a new address.
    """
    try:
        email = job_data.get("email")
        address_data = job_data.get("address_data", {})
        view_mode = job_data.get("view_mode", "desktop")

        # Apply headless preference for this job
        try:
            headless_pref = bool(job_data.get("headless"))
        except Exception:
            headless_pref = False
        automation_worker.browser_manager.set_headless(headless_pref)
        await automation_worker.initialize_browser()

        if not email:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "address_no_email")
            return {"success": False, "error": "Email not provided in job data"}
        if not address_data:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "address_no_data")
            return {"success": False, "error": "Address data not provided for the job"}

        # Validate required fields for the address
        required_fields = ["name", "phone", "pincode", "locality", "address"]
        missing_fields = [field for field in required_fields if not address_data.get(field)]
        if missing_fields:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "address_missing_fields")
            return {"success": False, "error": f"Missing required address fields: {', '.join(missing_fields)}"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting 'Add Address' automation for {email}")

        # Phase 1: Login to Flipkart
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1: Logging in to Flipkart")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)

        if not login_success:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "address_login_failed")
            return {"success": False, "error": "Phase 1 failed: Login was unsuccessful"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1 (Login) completed successfully.")

        # Phase 2: Add the new address
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2: Adding the new address")
        
        # Use mobile or desktop flow based on view_mode
        if view_mode == "mobile":
            # Get address_id from job_data for database lookup
            address_id = job_data.get('address_id')
            address_success = await automation_worker.add_address_mobile(job_id, address_id)
        else:
            address_success = await automation_worker.add_new_address(address_data, job_id)

        if not address_success:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "address_add_failed")
            return {"success": False, "error": "Phase 2 failed: Could not add the new address"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2 (Add Address) completed successfully.")
        
        return {"success": True, "message": "New address has been added to the Flipkart account successfully."}

    except Exception as e:
        error_message = f"An unexpected error occurred in the 'Add Address' automation job: {str(e)}"
        await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
        logging.error(error_message)
        await automation_worker.browser_manager.capture_failure_screenshot(job_id, "address_exception")
        return {"success": False, "error": error_message}
    finally:
        # This is crucial: ensures the browser context is always closed for this job.
        await automation_worker.cleanup_job_context(job_id)


@register_worker("remove_addresses")
async def run_remove_addresses_automation(job_data: Dict[str, Any], job_id: int) -> Dict[str, Any]:
    """
    Removes all saved addresses from the account on the mobile Addresses page.
    Steps:
    1) Login
    2) Open https://www.flipkart.com/rv/accounts/addresses
    3) Repeatedly open the 3-dot menu for the first address, click Remove, confirm "Okay"
    4) Stop when there are no addresses left or a max safety iteration is reached
    """
    try:
        email = job_data.get("email")
        view_mode = job_data.get("view_mode", "mobile")

        # Apply headless preference for this job
        try:
            headless_pref = bool(job_data.get("headless"))
        except Exception:
            headless_pref = False
        automation_worker.browser_manager.set_headless(headless_pref)
        await automation_worker.initialize_browser()

        if not email:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "remove_addr_no_email")
            return {"success": False, "error": "Email not provided in job data"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting 'Remove Addresses' automation for {email}")

        # Phase 1: Login
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1: Logging in to Flipkart")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)
        if not login_success:
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "remove_addr_login_failed")
            return {"success": False, "error": "Phase 1 failed: Login was unsuccessful"}
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1 (Login) completed successfully.")

        # Use existing context
        context = await automation_worker.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot proceed: No browser context after login.")
            await automation_worker.browser_manager.capture_failure_screenshot(job_id, "remove_addr_no_context")
            return {"success": False, "error": "No browser context"}

        page = context.pages[0] if context.pages else await context.new_page()

        # Phase 2: Open Addresses page
        target_url = 'https://www.flipkart.com/rv/accounts/addresses'
        await job_queue.log_job(job_id, LogLevel.INFO, f"Phase 2: Navigating to addresses page: {target_url}")
        await page.goto(target_url, wait_until='domcontentloaded')
        await asyncio.sleep(2)

        # Helper locators
        list_container_selector = '#fk-cp-richviews > div > div.Ts1TZW > div._2c9DHk'
        address_items_selector = f"{list_container_selector} > div"

        # Attempt to read the count label (best-effort)
        try:
            count_label = page.locator('#fk-cp-richviews > div > div.Ts1TZW > div._4gathi > div > span')
            if await count_label.count() > 0:
                txt = (await count_label.first.inner_text()).strip()
                await job_queue.log_job(job_id, LogLevel.INFO, f"Address count label: {txt}")
        except Exception:
            pass

        removed = 0
        max_iterations = 25  # safety

        for attempt in range(max_iterations):
            # Count addresses currently visible
            try:
                items = page.locator(address_items_selector)
                count = await items.count()
            except Exception:
                count = 0

            if count == 0:
                await job_queue.log_job(job_id, LogLevel.INFO, "No addresses found - nothing to remove")
                break

            await job_queue.log_job(job_id, LogLevel.INFO, f"Attempt {attempt+1}: {count} address(es) currently listed")

            # Always target the first address to avoid index shifting after deletion
            menu_selector = f"{list_container_selector} > div:nth-child(1) > div > div > div:nth-child(1) > button"
            remove_selector = f"{list_container_selector} > div:nth-child(1) > div > div > div:nth-child(1) > ul > li._3nL9IF"
            confirm_selector = '#fk-cp-richviews > div > div.Ts1TZW > div._2BAM3D > div > div > div.Lz0Ctu > button:nth-child(2)'

            # Ensure the first card is in view (scroll container if present)
            try:
                container = page.locator(list_container_selector)
                if await container.count() > 0:
                    await container.first.scroll_into_view_if_needed()
            except Exception:
                pass

            # Click the 3-dot menu
            try:
                menu = page.locator(menu_selector)
                if await menu.count() == 0 or not await menu.first.is_visible():
                    # Fallback: search by role/text near the first card area
                    menu = page.locator("button:has(svg)").first
                await menu.first.click(timeout=4000)
                await asyncio.sleep(0.4)
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Could not open 3-dot menu for first address: {e}")
                # Try scrolling a bit and retry once
                try:
                    await page.mouse.wheel(0, 300)
                    await asyncio.sleep(0.3)
                    menu = page.locator(menu_selector)
                    await menu.first.click(timeout=3000)
                except Exception:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "3-dot menu still not clickable; stopping.")
                    break

            # Click Remove
            clicked_remove = False
            try:
                rem = page.locator(remove_selector)
                if await rem.count() > 0 and await rem.first.is_visible():
                    await rem.first.click(timeout=3000)
                    clicked_remove = True
                else:
                    # Fallback to text lookup within the menu
                    by_text = page.get_by_text("Remove")
                    if await by_text.count() > 0 and await by_text.first.is_visible():
                        await by_text.first.click(timeout=3000)
                        clicked_remove = True
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to click Remove: {e}")

            if not clicked_remove:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Remove option not found; attempting to continue")
                # Skip this iteration
                continue

            # Confirm deletion (Okay)
            confirmed = False
            try:
                ok_btn = page.locator(confirm_selector)
                if await ok_btn.count() > 0 and await ok_btn.first.is_visible():
                    await ok_btn.first.click(timeout=4000)
                    confirmed = True
                else:
                    # Fallback by role/text
                    ok_role = page.get_by_role("button", name=re.compile(r"^\s*ok(ay)?\s*$", re.I))
                    if await ok_role.count() > 0 and await ok_role.first.is_visible():
                        await ok_role.first.click(timeout=3000)
                        confirmed = True
                    else:
                        ok_text = page.get_by_text(re.compile(r"\bok(ay)?\b", re.I))
                        if await ok_text.count() > 0 and await ok_text.first.is_visible():
                            await ok_text.first.click(timeout=3000)
                            confirmed = True
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to confirm deletion: {e}")

            # Wait a moment for the item to be removed
            await asyncio.sleep(1.2)

            if confirmed:
                removed += 1
                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Removed address #{removed}")
                # Optional: check for success toast/banner
                try:
                    banner = page.get_by_text(re.compile(r"address\s+remove(d)?\s+success", re.I))
                    if await banner.count() > 0:
                        await job_queue.log_job(job_id, LogLevel.DEBUG, "Success banner detected")
                except Exception:
                    pass
            else:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Deletion not confirmed; continuing")

            # Small delay before next iteration
            await asyncio.sleep(0.8)

        # Final recount
        try:
            remaining = await page.locator(address_items_selector).count()
        except Exception:
            remaining = None

        await job_queue.log_job(job_id, LogLevel.INFO, f"Remove Addresses completed. Removed: {removed}, Remaining: {remaining if remaining is not None else 'unknown'}")
        return {
            "success": True,
            "message": f"Removed {removed} addresses",
            "removed": removed,
            "remaining": remaining,
            "account": email,
        }

    except Exception as e:
        error_message = f"An unexpected error occurred in the 'Remove Addresses' automation job: {str(e)}"
        await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
        logging.error(error_message)
        await automation_worker.browser_manager.capture_failure_screenshot(job_id, "remove_addresses_exception")
        return {"success": False, "error": error_message}
    finally:
        # Always cleanup context for this job
        await automation_worker.cleanup_job_context(job_id)
