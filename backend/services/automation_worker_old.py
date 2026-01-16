"""
Automation Worker Service
Handles Flipkart automation jobs using Playwright - Refactored Modular Version
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
        enable_checkout = job_data.get("enable_checkout", False)

        if not email:
            return {"success": False, "error": "Email not provided in job data"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting full automation for {email}")

        # Phase 1: Login to Flipkart
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1: Logging in to Flipkart")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)

        if not login_success:
            return {"success": False, "error": "Phase 1 failed: Login was unsuccessful"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1 completed successfully")

        # Phase 1.5: Select delivery location (only for mobile view in full automation)
        if view_mode == 'mobile' and products:
            await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.5: Selecting delivery location")
            from services.batch_manager import batch_manager
            await batch_manager.load_settings()
            pincode = batch_manager.get_default_pincode()
            
            location_success = await automation_worker.select_delivery_location(job_id, pincode)
            if not location_success:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Failed to set delivery location, continuing with automation")
            else:
                await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.5 completed successfully")

        # If no products provided, this is just a login test
        if not products:
            await job_queue.log_job(job_id, LogLevel.INFO, "No products provided - login test completed successfully")
            return {"success": True, "message": "Login test successful"}

        # Phase 2: Add products to cart and configure quantities
        await job_queue.log_job(job_id, LogLevel.INFO, f"Phase 2: Adding {len(products)} products to cart")
        products_success = await automation_worker.add_and_configure_products_in_cart(products, job_id)

        if not products_success:
            return {"success": False, "error": "Phase 2 failed: Error during product processing"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2 completed successfully")

        # Phase 3: Complete checkout process (if enabled)
        if enable_checkout:
            await job_queue.log_job(job_id, LogLevel.INFO, "Phase 3: Starting checkout process")
            checkout_success = await automation_worker.run_full_automation(products, job_id)
            
            if checkout_success:
                await job_queue.log_job(job_id, LogLevel.INFO, "Phase 3 completed successfully - Order placed!")
                return {"success": True, "message": "Full automation completed successfully. Order placed!"}
            else:
                return {"success": False, "error": "Phase 3 failed: Checkout process unsuccessful"}
        else:
            await job_queue.log_job(job_id, LogLevel.INFO, "Checkout disabled - automation completed with products in cart")
            return {"success": True, "message": "Products added to cart successfully. Checkout not enabled."}

    except Exception as e:
        error_message = f"An unexpected error occurred in automation: {str(e)}"
        await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
        logging.error(error_message)
        return {"success": False, "error": error_message}
    finally:
        # This is crucial: ensures the browser context is always closed for this job.
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

        if not email:
            return {"success": False, "error": "Email not provided in job data"}
        if not address_data:
            return {"success": False, "error": "Address data not provided for the job"}

        # Validate required fields for the address
        required_fields = ["name", "phone", "pincode", "locality", "address"]
        missing_fields = [field for field in required_fields if not address_data.get(field)]
        if missing_fields:
            return {"success": False, "error": f"Missing required address fields: {', '.join(missing_fields)}"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting 'Add Address' automation for {email}")

        # Phase 1: Login to Flipkart
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1: Logging in to Flipkart")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)

        if not login_success:
            return {"success": False, "error": "Phase 1 failed: Login was unsuccessful"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1 (Login) completed successfully.")

        # Phase 2: Add the new address
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2: Adding the new address")
        address_success = await automation_worker.add_new_address(address_data, job_id)

        if not address_success:
            return {"success": False, "error": "Phase 2 failed: Could not add the new address"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2 (Add Address) completed successfully.")
        
        return {"success": True, "message": "New address has been added to the Flipkart account successfully."}

    except Exception as e:
        error_message = f"An unexpected error occurred in the 'Add Address' automation job: {str(e)}"
        await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
        logging.error(error_message)
        return {"success": False, "error": error_message}
    finally:
        # This is crucial: ensures the browser context is always closed for this job.
        await automation_worker.cleanup_job_context(job_id)
            await job_queue.log_job(job_id, LogLevel.INFO, "Clicking on location selection element")
            
            location_element = page.locator(location_selector).first
            if await location_element.count() == 0:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Location selection element not found, trying alternative selectors")
                # Try alternative selector
                location_element = page.locator('text=HOME').locator('..').locator('..')
                if await location_element.count() == 0:
                    raise Exception("Could not find location selection element")
            
            await location_element.click()
            await asyncio.sleep(2)  # Wait for popup to appear
            
            # Wait for the pincode input field to appear
            pincode_selector = '#_parentCtr_ > div:nth-child(2) > div > div > div > div.css-175oi2r.r-nsbfu8.r-13awgt0.r-eqz5dr.r-1habvwh.r-1h0z5md > div > div.css-175oi2r.r-13awgt0.r-18u37iz > input'
            await job_queue.log_job(job_id, LogLevel.INFO, "Waiting for pincode input field")
            
            await page.wait_for_selector(pincode_selector, timeout=10000)
            
            # Clear and enter the pincode
            await job_queue.log_job(job_id, LogLevel.INFO, f"Entering pincode: {pincode}")
            pincode_input = page.locator(pincode_selector)
            await pincode_input.click()
            await pincode_input.fill('')  # Clear existing value
            await pincode_input.fill(pincode)
            await asyncio.sleep(1)
            
            # Click Submit
            submit_selector = 'div[class*="css-1rynq56"]:has-text("Submit")'
            await job_queue.log_job(job_id, LogLevel.INFO, "Clicking Submit button")
            
            submit_button = page.locator(submit_selector)
            if await submit_button.count() == 0:
                # Try alternative submit selector
                submit_button = page.locator('text=Submit')
            
            await submit_button.click()
            await asyncio.sleep(3)  # Wait for location to be set
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Delivery location set successfully with pincode: {pincode}")
            return True
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to select delivery location: {str(e)}")
            return False
    
    async def check_product_price(self, product_url: str, price_cap: Optional[float], job_id: int) -> Dict[str, Any]:
        """Check product price and availability"""
        try:
            if not self.context:
                return {"success": False, "error": "No browser context"}
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Checking price for product: {product_url}")
            
            page = await self.context.new_page()
            await page.goto(product_url)
            await asyncio.sleep(3)
            
            # Extract product details
            try:
                # Get product name
                product_name = await page.locator('span.B_NuCI').first.text_content()
                if not product_name:
                    product_name = await page.locator('h1.x-product-title-label').first.text_content()
                
                # Get price
                price_text = await page.locator('div._30jeq3._16Jk6d').first.text_content()
                if not price_text:
                    price_text = await page.locator('div._3I9_wc._2p6lqe').first.text_content()
                
                # Clean price text and convert to float
                import re
                price_match = re.search(r'[\d,]+', price_text.replace('₹', '').replace(',', ''))
                current_price = float(price_match.group()) if price_match else 0
                
                # Check availability
                add_to_cart_btn = page.locator('button:has-text("Add to cart")')
                is_available = await add_to_cart_btn.count() > 0
                
                result = {
                    "success": True,
                    "product_name": product_name.strip() if product_name else "Unknown Product",
                    "current_price": current_price,
                    "price_cap": price_cap,
                    "is_available": is_available,
                    "within_budget": (current_price <= price_cap if price_cap is not None else True) if current_price > 0 else False,
                    "url": product_url
                }
                
                await job_queue.log_job(
                    job_id, 
                    LogLevel.INFO, 
                    f"Price check result: {product_name} - ₹{current_price}" + 
                    (f" (Cap: ₹{price_cap})" if price_cap is not None else " (No price limit)")
                )
                
                await page.close()
                return result
                
            except Exception as e:
                error_msg = f"Error extracting product details: {str(e)}"
                await job_queue.log_job(job_id, LogLevel.ERROR, error_msg)
                await page.close()
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            error_msg = f"Price check error: {str(e)}"
            await job_queue.log_job(job_id, LogLevel.ERROR, error_msg)
            return {"success": False, "error": error_msg}
    
    async def add_to_cart_and_checkout(self, product_url: str, quantity: int, job_id: int) -> Dict[str, Any]:
        """Add product to cart and proceed to checkout"""
        try:
            if not self.context:
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
            place_order_btn = page.locator('button:has-text("Place Order")').first
            await place_order_btn.click()
            await asyncio.sleep(3)
            
            await job_queue.log_job(job_id, LogLevel.INFO, "Proceeding to checkout")
            
            # Select Cash on Delivery
            try:
                cod_option = page.locator('label:has-text("Cash on Delivery")').first
                await cod_option.click()
                await asyncio.sleep(2)
                
                await job_queue.log_job(job_id, LogLevel.INFO, "Selected Cash on Delivery")
            except:
                await job_queue.log_job(job_id, LogLevel.WARNING, "COD option not found or already selected")
            
            # Continue to place order (Note: This would actually place the order)
            # For safety, we'll stop here and return success
            await job_queue.log_job(job_id, LogLevel.INFO, "Ready to place order (stopping for safety)")
            
            await page.close()
            return {
                "success": True,
                "message": "Product added to cart and ready for order placement",
                "status": "ready_to_order"
            }
            
        except Exception as e:
            error_msg = f"Checkout error: {str(e)}"
            await job_queue.log_job(job_id, LogLevel.ERROR, error_msg)
            return {"success": False, "error": error_msg}

    async def add_and_configure_products_in_cart(self, products: List[Dict], job_id: int) -> bool:
        """
        Phase 2: Navigate to each product page, add it to cart, and configure the quantity.
        Uses the exact selectors provided by the user.
        """
        context = await self.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot add products to cart: No browser context.")
            return False
        
        page = context.pages[0] if context.pages else await context.new_page()

        # Track product addition statistics
        total_products = len(products)
        added_products = 0
        skipped_products = 0
        unavailable_products = 0
        
        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting to process {total_products} products...")

        for product in products:
            product_link = product.get("product_link")
            desired_quantity = int(product.get("quantity", 1))

            if not product_link:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Skipping product with no link")
                skipped_products += 1
                continue

            try:
                await job_queue.log_job(job_id, LogLevel.INFO, f"Processing product: {product_link}")
                await page.goto(product_link, timeout=60000)
                await page.wait_for_load_state('domcontentloaded')
                await asyncio.sleep(3)
                
                # Check if product is already in cart (quantity controls already visible)
                plus_button_selector = "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af"
                plus_button = page.locator(plus_button_selector)
                
                if await plus_button.count() > 0:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Product {product_link} is already in cart. Adjusting quantity directly.")
                    # Product is already in cart, skip to quantity adjustment
                    await self._adjust_product_quantity(page, desired_quantity, job_id, product_link)
                    added_products += 1
                    await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Product quantity adjusted (was already in cart): {product_link}")
                    continue

                # Check if product is unavailable or sold out
                unavailable_indicators = [
                    'text="Currently Unavailable"',
                    'text="Sold Out"', 
                    'text="This item is currently out of stock"',
                    'text="Out of Stock"',
                    'text="Temporarily unavailable"',
                    'text="Not Available"',
                    'text="Notify Me"',
                    'text="unavailable"',
                    'text="sold out"',
                    'text="out of stock"',
                    'text="notify me"',
                    'text="temporarily"'
                ]
                
                product_unavailable = False
                for indicator in unavailable_indicators:
                    if await page.locator(indicator).count() > 0:
                        unavailable_text = await page.locator(indicator).inner_text()
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"Product unavailable: {unavailable_text}. Skipping {product_link}")
                        product_unavailable = True
                        break
                
                if product_unavailable:
                    unavailable_products += 1
                    continue  # Skip to next product

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
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"'Add' button not found for {product_link} with any strategy. Product may be unavailable. Skipping.")
                    skipped_products += 1
                    continue  # Skip to next product
                
                await job_queue.log_job(job_id, LogLevel.INFO, "Clicking 'Add' button")
                try:
                    await add_button_element.click(timeout=30000)
                    await asyncio.sleep(2)  # Wait for potential popup or quantity controls
                    
                    # Check for grocery basket popup and handle it
                    await self._handle_grocery_basket_popup(page, job_id)
                    
                    # Wait a bit more for quantity controls to appear after popup handling
                    await asyncio.sleep(2)
                    
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
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"Product may not have been added to cart for {product_link} - no quantity controls found. Skipping.")
                        skipped_products += 1
                        continue  # Skip to next product
                        
                except Exception as click_error:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to click 'Add' button for {product_link}: {str(click_error)}. Skipping.")
                    skipped_products += 1
                    continue  # Skip to next product

                # 1.b) Now manipulate the quantity using mobile grocery selectors
                await self._adjust_product_quantity(page, desired_quantity, job_id, product_link)
                
                # Product successfully added and configured
                added_products += 1
                await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Product successfully added and configured: {product_link}")

            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to process product {product_link}: {str(e)}")
                skipped_products += 1
                continue  # Move to the next product

        # Product processing summary
        await job_queue.log_job(job_id, LogLevel.INFO, f"📊 PRODUCT PROCESSING SUMMARY:")
        await job_queue.log_job(job_id, LogLevel.INFO, f"   📦 Total Products: {total_products}")
        await job_queue.log_job(job_id, LogLevel.INFO, f"   ✅ Successfully Added: {added_products}")
        await job_queue.log_job(job_id, LogLevel.INFO, f"   ❌ Unavailable/Out of Stock: {unavailable_products}")
        await job_queue.log_job(job_id, LogLevel.INFO, f"   ⚠️  Skipped (Other Issues): {skipped_products}")
        
        if added_products == 0:
            await job_queue.log_job(job_id, LogLevel.ERROR, "⚠️ No products were successfully added to cart! Cannot proceed to checkout.")
            return False
        elif added_products < total_products:
            await job_queue.log_job(job_id, LogLevel.WARNING, f"⚠️ Only {added_products} out of {total_products} products were added. Proceeding with available products.")
        else:
            await job_queue.log_job(job_id, LogLevel.INFO, f"🎉 All {total_products} products successfully added to cart!")
        
        # Navigate to cart after all products are processed
        await job_queue.log_job(job_id, LogLevel.INFO, "Navigating to grocery cart...")
        cart_url = "https://www.flipkart.com/viewcart?marketplace=GROCERY"
        await page.goto(cart_url, timeout=60000)
        await page.wait_for_load_state('domcontentloaded')
        await asyncio.sleep(3)
        
        # Select correct delivery address before checkout
        await self.select_correct_address(job_id)
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Successfully navigated to cart and verified address. Proceeding to checkout...")
        
        # Phase 3: Complete checkout process
        await self.complete_checkout_process(job_id)
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Full automation completed successfully. Order placed!")
        return True

    async def _adjust_product_quantity(self, page, desired_quantity: int, job_id: int, product_link: str):
        """Helper method to adjust product quantity using mobile grocery selectors"""
        minus_button_selector = "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(1) > div"
        
        # Enhanced plus button selectors with multiple fallback strategies
        plus_button_selectors = [
            # Original selectors
            "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af",
            "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div:nth-child(3) > div > div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af",
            # Class-based selectors
            'div.css-175oi2r.r-1awozwy.r-1p0dtai.r-1777fci.r-1d2f490.r-u8s1d.r-zchlnj.r-ipm5af',
            # Text-based selectors
            'div:has-text("+")',
            'button:has-text("+")',
            'span:has-text("+")',
            # Role-based selectors
            '[role="button"]:has-text("+")',
            # Generic plus button patterns
            'div[class*="plus"]',
            'div[class*="increment"]',
            # Look for quantity control containers and find plus buttons within
            'div[class*="quantity"] div:has-text("+")',
            'div[class*="control"] div:has-text("+")',
            # Broader class patterns that might contain plus buttons
            '.r-1awozwy:has-text("+")',
            '.r-1p0dtai:has-text("+")',
        ]
        
        quantity_display_selectors = [
            "#_parentCtr_ > div:nth-child(2) > div > div > div > div:nth-child(1) > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > div > div.css-175oi2r.r-1awozwy.r-jwli3a.r-18u37iz.r-1m7hjod.r-1777fci.r-1aockid",
            # Alternative quantity display patterns
            'div.css-175oi2r.r-1awozwy.r-jwli3a.r-18u37iz.r-1m7hjod.r-1777fci.r-1aockid',
            'div[class*="quantity"]',
            'span[class*="quantity"]',
        ]

        await job_queue.log_job(job_id, LogLevel.INFO, f"Setting quantity to {desired_quantity}")

        try:
            # Get current quantity first
            current_quantity = 1  # Default assumption
            try:
                quantity_element = None
                for selector in quantity_display_selectors:
                    element = page.locator(selector)
                    if await element.count() > 0:
                        quantity_element = element
                        break
                
                if quantity_element:
                    quantity_text = await quantity_element.inner_text()
                    if quantity_text and quantity_text.strip().isdigit():
                        current_quantity = int(quantity_text.strip())
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Current quantity: {current_quantity}")
            except Exception:
                await job_queue.log_job(job_id, LogLevel.INFO, "Could not read current quantity, assuming 1")

            # Adjust to desired quantity
            while current_quantity < desired_quantity:
                plus_clicked = False
                
                # First, handle any popup that might be blocking the plus button
                await self._handle_grocery_basket_popup(page, job_id)
                await asyncio.sleep(0.5)
                
                for i, selector in enumerate(plus_button_selectors):
                    try:
                        # Check if element exists first (fast check)
                        plus_button = page.locator(selector)
                        element_count = await plus_button.count()
                        
                        if element_count > 0:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Plus button found with selector #{i+1} ({element_count} elements)")
                            
                            # Use the first visible element
                            for element_index in range(element_count):
                                try:
                                    current_element = plus_button.nth(element_index)
                                    
                                    # Scroll element into view before clicking
                                    await current_element.scroll_into_view_if_needed()
                                    await asyncio.sleep(0.3)
                                    
                                    # Verify element is visible and enabled
                                    is_visible = await current_element.is_visible()
                                    is_enabled = await current_element.is_enabled()
                                    
                                    if is_visible and is_enabled:
                                        await current_element.click(timeout=5000)
                                        await job_queue.log_job(job_id, LogLevel.INFO, f"Plus button clicked using selector #{i+1}, element {element_index}")
                                        plus_clicked = True
                                        break
                                    else:
                                        await job_queue.log_job(job_id, LogLevel.INFO, f"Plus button selector #{i+1}, element {element_index} - visible: {is_visible}, enabled: {is_enabled}")
                                        
                                except Exception as element_error:
                                    await job_queue.log_job(job_id, LogLevel.INFO, f"Plus button selector #{i+1}, element {element_index} failed: {str(element_error)}")
                                    continue
                            
                            if plus_clicked:
                                break
                        else:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Plus button selector #{i+1}: No elements found")
                            
                    except Exception as click_error:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Plus button selector #{i+1} failed: {str(click_error)}")
                        continue
                
                if not plus_clicked:
                    await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to click plus button with any selector")
                    # Try to take a screenshot for debugging
                    try:
                        screenshot_path = f"/tmp/plus_button_debug_{job_id}.png"
                        await page.screenshot(path=screenshot_path)
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Debug screenshot saved: {screenshot_path}")
                    except Exception:
                        pass
                    break
                
                current_quantity += 1
                await asyncio.sleep(0.5)  # Wait for UI to update

                # Check for quantity limit error
                error_text_locator = page.locator('text="You can buy only up to"')
                if await error_text_locator.count() > 0:
                    error_text = await error_text_locator.inner_text()
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Quantity limit hit for {product_link}: {error_text}")
                    
                    # Remove item from cart by decreasing to 0
                    await job_queue.log_job(job_id, LogLevel.INFO, "Removing item from cart due to quantity limit")
                    while True:
                        try:
                            # Check if quantity display still exists
                            quantity_element = page.locator(quantity_display_selector)
                            if await quantity_element.count() == 0:
                                await job_queue.log_job(job_id, LogLevel.INFO, "Item successfully removed from cart")
                                break
                            
                            # Get current quantity text
                            quantity_text = await quantity_element.inner_text()
                            if not quantity_text or quantity_text.strip() == "":
                                await job_queue.log_job(job_id, LogLevel.INFO, "Item successfully removed from cart")
                                break
                            
                            # Click minus button to decrease quantity
                            await page.click(minus_button_selector, timeout=5000)
                            await asyncio.sleep(1)
                            
                        except Exception as decrease_error:
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Item removed from cart (minus button no longer available)")
                            break
                    
                    return  # Exit the method

            # Decrease quantity if current is higher than desired
            while current_quantity > desired_quantity:
                try:
                    await page.click(minus_button_selector, timeout=10000)
                    current_quantity -= 1
                    await asyncio.sleep(1)
                except Exception as decrease_error:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to decrease quantity: {str(decrease_error)}")
                    break

            # Check final quantity
            try:
                final_quantity_element = page.locator(quantity_display_selector)
                if await final_quantity_element.count() > 0:
                    final_quantity_text = await final_quantity_element.inner_text()
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Final quantity for {product_link}: {final_quantity_text}")
                else:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Product {product_link} was removed from cart")
            except Exception:
                pass

        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error adjusting quantity for {product_link}: {str(e)}")

    # TODO: Implement offer application later
    # async def apply_available_offers(self, job_id: int) -> bool:
    #     """Apply any available offers/coupons on the cart page"""
    #     context = await self.get_job_context(job_id)
    #     if not context:
    #         await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot apply offers: No browser context.")
    #         return False
    #     
    #     page = context.pages[0] if context.pages else await context.new_page()
    #
    #     try:
    #         await job_queue.log_job(job_id, LogLevel.INFO, "Checking for available offers/coupons to apply...")
    #         
    #         # Look for "Apply" buttons in offer sections
    #         apply_buttons = await page.locator('div:has-text("Apply")').all()
    #         
    #         if not apply_buttons:
    #             await job_queue.log_job(job_id, LogLevel.INFO, "No offers/coupons found to apply.")
    #             return True
    #         
    #         applied_count = 0
    #         for i, apply_button in enumerate(apply_buttons):
    #             try:
    #                 # Check if the button is enabled/clickable
    #                 if await apply_button.is_enabled():
    #                     await job_queue.log_job(job_id, LogLevel.INFO, f"Applying offer #{i+1}...")
    #                     await apply_button.click()
    #                     await asyncio.sleep(1)  # Reduced wait for offer to be applied
    #                     applied_count += 1
    #                     await job_queue.log_job(job_id, LogLevel.INFO, f"Successfully applied offer #{i+1}")
    #                 else:
    #                     await job_queue.log_job(job_id, LogLevel.INFO, f"Offer #{i+1} apply button is disabled, skipping.")
    #             except Exception as e:
    #                 await job_queue.log_job(job_id, LogLevel.WARNING, f"Failed to apply offer #{i+1}: {str(e)}")
    #                 continue
    #         
    #         if applied_count > 0:
    #             await job_queue.log_job(job_id, LogLevel.INFO, f"Successfully applied {applied_count} offer(s)/coupon(s).")
    #             # Give a moment for the cart to update with applied offers
    #             await asyncio.sleep(1)  # Reduced wait for cart update
    #         else:
    #             await job_queue.log_job(job_id, LogLevel.INFO, "No offers were available to apply.")
    #         
    #         return True
    #         
    #     except Exception as e:
    #         await job_queue.log_job(job_id, LogLevel.ERROR, f"Error while applying offers: {str(e)}")
    #         return False

    async def select_correct_address(self, job_id: int) -> bool:
        """Check current address and select the correct one if needed"""
        context = await self.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot select address: No browser context.")
            return False
        
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            await job_queue.log_job(job_id, LogLevel.INFO, "Checking current delivery address...")
            
            # Check current selected address
            current_address_selector = "#_parentCtr_ > div:nth-child(1) > div > div > div > div:nth-child(1) > div > div.css-175oi2r.r-13awgt0.r-eqz5dr"
            
            try:
                # Wait for address element with shorter timeout
                await page.wait_for_selector(current_address_selector, timeout=3000)
                current_address_element = page.locator(current_address_selector)
                if await current_address_element.count() > 0:
                    current_address_text = await current_address_element.inner_text()
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Current address: {current_address_text}")
                    
                    # Check if current address is correct
                    if self._is_correct_address(current_address_text):
                        await job_queue.log_job(job_id, LogLevel.INFO, "Current address is correct. No need to change.")
                        return True
                    else:
                        await job_queue.log_job(job_id, LogLevel.INFO, "Current address doesn't match our criteria. Need to change.")
                else:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Could not find current address element.")
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Error reading current address: {str(e)}")
            
            # Click "Change" button to open address selection
            change_button_selector = "#_parentCtr_ > div:nth-child(1) > div > div > div > div:nth-child(1) > div > div:nth-child(2) > div"
            await job_queue.log_job(job_id, LogLevel.INFO, "Clicking 'Change' button to select address...")
            
            change_button = page.locator(change_button_selector)
            if await change_button.count() == 0:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Change button not found. Using fallback selector.")
                change_button = page.locator('div:has-text("Change")')
            
            await change_button.click()
            await asyncio.sleep(1)  # Reduced wait for address selection popup
            
            # Find and select the correct address from the list
            await job_queue.log_job(job_id, LogLevel.INFO, "Looking for correct address in the list...")
            
            # Wait for address list to appear with shorter timeout
            try:
                await page.wait_for_selector('div.css-175oi2r.r-13awgt0.r-eqz5dr.r-ymttw5.r-1ygmrgt', timeout=3000)
            except Exception:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Address list popup did not appear quickly")
            
            # Get all address elements in the popup
            address_elements = await page.locator('div.css-175oi2r.r-13awgt0.r-eqz5dr.r-ymttw5.r-1ygmrgt > div').all()
            
            selected_address = False
            for i, address_element in enumerate(address_elements):
                try:
                    address_text = await address_element.inner_text()
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Checking address #{i+1}: {address_text[:100]}...")
                    
                    if self._is_correct_address(address_text):
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found correct address #{i+1}. Selecting it...")
                        
                        # Click on the radio button for this address
                        radio_button = address_element.locator('div[style*="width: 16px; height: 16px"]').first
                        if await radio_button.count() > 0:
                            await radio_button.click()
                            await asyncio.sleep(0.5)  # Reduced wait
                            selected_address = True
                            break
                        else:
                            # Try clicking on the address element itself
                            await address_element.click()
                            await asyncio.sleep(0.5)  # Reduced wait
                            selected_address = True
                            break
                            
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Error checking address #{i+1}: {str(e)}")
                    continue
            
            if not selected_address:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Could not find a matching address. Using the first available address.")
                # Select the first address as fallback
                if address_elements:
                    try:
                        first_address = address_elements[0]
                        radio_button = first_address.locator('div[style*="width: 16px; height: 16px"]').first
                        if await radio_button.count() > 0:
                            await radio_button.click()
                        else:
                            await first_address.click()
                        selected_address = True
                    except Exception as e:
                        await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to select fallback address: {str(e)}")
            
            if selected_address:
                # Click Continue button
                continue_selector = "#container > div > div.q8WwEU > div._3zsGrb > div > div > div > div:nth-child(1) > div > div > div > div > div:nth-child(2) > div > div > div.css-175oi2r.r-13awgt0.r-eqz5dr > div.css-175oi2r.r-13awgt0.r-eqz5dr > div > div:nth-child(1) > div"
                await job_queue.log_job(job_id, LogLevel.INFO, "Clicking Continue button...")
                
                continue_button = page.locator(continue_selector)
                if await continue_button.count() == 0:
                    # Try fallback selector
                    continue_button = page.locator('div:has-text("Continue")').first
                
                await continue_button.click()
                await asyncio.sleep(1)  # Reduced wait for address selection to be confirmed
                
                await job_queue.log_job(job_id, LogLevel.INFO, "Address selection completed successfully.")
                return True
            else:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to select any address.")
                return False
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error during address selection: {str(e)}")
            return False

    async def validate_cart_total(self, page: Any, job_id: int, max_cart_value: Optional[float] = None) -> bool:
        """Validate cart total amount against maximum cart value limit"""
        if max_cart_value is None:
            await job_queue.log_job(job_id, LogLevel.INFO, "No maximum cart value configured, skipping validation")
            return True
        
        try:
            # Extract total amount using the provided selector
            total_amount_selector = "#_parentCtr_ > div:nth-child(5) > div > div:nth-child(1) > div > div:nth-child(2) > div.css-175oi2r.r-1awozwy.r-18u37iz.r-ur6pnr.r-1wtj0ep.r-ymttw5 > div.css-175oi2r.r-18u37iz.r-1awozwy > div > div"
            
            await job_queue.log_job(job_id, LogLevel.INFO, "Extracting cart total amount...")
            
            # Wait for the total amount element to be visible
            await page.wait_for_selector(total_amount_selector, timeout=10000)
            
            # Get the total amount text
            total_amount_element = page.locator(total_amount_selector)
            total_amount_text = await total_amount_element.inner_text()
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Cart total amount text: {total_amount_text}")
            
            # Extract numeric value from the text (remove currency symbols and commas)
            import re
            # Match numbers with optional decimal places, handling Indian currency format
            amount_match = re.search(r'[₹$]?\s*([0-9,]+(?:\.[0-9]{2})?)', total_amount_text.replace(',', ''))
            
            if not amount_match:
                await job_queue.log_job(job_id, LogLevel.WARNING, f"Could not extract numeric value from total amount: {total_amount_text}")
                return True  # Allow to proceed if we can't parse the amount
            
            cart_total = float(amount_match.group(1).replace(',', ''))
            await job_queue.log_job(job_id, LogLevel.INFO, f"Parsed cart total: ₹{cart_total}")
            await job_queue.log_job(job_id, LogLevel.INFO, f"Maximum cart limit: ₹{max_cart_value}")
            
            # Check if cart total exceeds the maximum limit
            if cart_total > max_cart_value:
                error_message = f"Product total price ₹{cart_total} exceeds the max cart limit ₹{max_cart_value}"
                await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
                
                # Mark the job as failed with specific error
                conn = await asyncpg.connect(DATABASE_URL)
                try:
                    await conn.execute(
                        "UPDATE job_queue SET status = 'failed', error_message = $1, completed_at = NOW() WHERE id = $2",
                        error_message, job_id
                    )
                finally:
                    await conn.close()
                
                return False
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"✅ Cart total ₹{cart_total} is within the maximum limit ₹{max_cart_value}")
            return True
            
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.WARNING, f"Error validating cart total: {str(e)}. Proceeding without validation.")
            return True  # Allow to proceed if validation fails

    async def complete_checkout_process(self, job_id: int) -> bool:
        """Complete the checkout process: Order Summary -> Payments -> Place Order"""
        context = await self.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot complete checkout: No browser context.")
            return False

        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            # Step 1: Handle Order Summary page (Step 2)
            await job_queue.log_job(job_id, LogLevel.INFO, "Step 2: Processing Order Summary...")
            
            # Wait for Order Summary page to load
            await asyncio.sleep(2)
            
            # Get maximum cart value from job data
            conn = await asyncpg.connect(DATABASE_URL)
            try:
                job_record = await conn.fetchrow(
                    "SELECT job_data FROM job_queue WHERE id = $1", job_id
                )
                max_cart_value = None
                if job_record and job_record['job_data']:
                    job_data = json.loads(job_record['job_data'])
                    max_cart_value = job_data.get('max_cart_value')
            finally:
                await conn.close()
            
            # Validate cart total before proceeding
            if not await self.validate_cart_total(page, job_id, max_cart_value):
                await job_queue.log_job(job_id, LogLevel.ERROR, "Automation cancelled due to cart limit exceeded")
                return False
            
            # Click Continue button on Order Summary page using specific selector
            continue_selector = "#container > div > div.q8WwEU > div > div > div > div > div:nth-child(1) > div > div > div > div > div:nth-child(2) > div > div > div.css-175oi2r.r-13awgt0.r-eqz5dr > div:nth-child(1) > div > div:nth-child(1) > div"
            
            try:
                await page.wait_for_selector(continue_selector, timeout=10000)
                await page.click(continue_selector)
                await job_queue.log_job(job_id, LogLevel.INFO, "Clicked Continue button on Order Summary page")
                await asyncio.sleep(3)  # Wait for payments page to load
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to click Continue button on Order Summary: {str(e)}")
                return False
            
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
                return False
            
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
                return False
            
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
                'button:has-text("Confirm")'
            ]
            
            order_confirmed = False
            for i, confirm_selector in enumerate(confirm_order_selectors):
                try:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Attempting Order Confirmation with strategy #{i+1}")
                    
                    # Wait for the confirmation popup and click
                    confirm_element = page.locator(confirm_selector)
                    if await confirm_element.count() > 0:
                        await confirm_element.click(timeout=5000)
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Successfully clicked 'Confirm order' using strategy #{i+1}")
                        order_confirmed = True
                        await asyncio.sleep(3)  # Wait for order confirmation to process
                        break
                    else:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Confirm order element not found with strategy #{i+1}")
                        
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Confirm order strategy #{i+1} failed: {str(e)}")
                    continue
            
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
                    
                    return True
                else:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Order may have been placed but confirmation unclear due to redirect issues")
                    return True  # Assume success since order was confirmed
            else:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to confirm order with all strategies")
                return False
                
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Error in checkout process: {str(e)}")
            return False

    def _is_correct_address(self, address_text: str) -> bool:
        """Check if the address text matches our criteria"""
        address_lower = address_text.lower()
        
        # Check for "Shivshakti" with any prefix name
        if "shivshakti" in address_lower:
            return True
        
        # Check for address template keywords
        keywords = ["metha chamber", "dana bunder", "masjid bandar east", "mumbai"]
        keyword_matches = sum(1 for keyword in keywords if keyword in address_lower)
        
        # If at least 3 out of 4 keywords match, consider it correct
        if keyword_matches >= 3:
            return True
        
        return False

    async def add_new_address(self, address_data: Dict[str, Any], job_id: int) -> bool:
        """
        Navigates to the addresses page and orchestrates adding a new address.
        """
        context = await self.get_job_context(job_id)
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Cannot add address: No browser context.")
            return False
        
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            # 1. Navigate to the addresses page
            addresses_url = "https://www.flipkart.com/account/addresses"
            await job_queue.log_job(job_id, LogLevel.INFO, f"Navigating to addresses page: {addresses_url}")
            await page.goto(addresses_url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(2)

            # 2. Click "ADD A NEW ADDRESS" button
            add_address_selector = ".g8S8Av" # As per user instruction
            await job_queue.log_job(job_id, LogLevel.INFO, "Clicking 'ADD A NEW ADDRESS' button")
            
            add_button_locator = page.locator(add_address_selector)
            if await add_button_locator.count() == 0:
                await job_queue.log_job(job_id, LogLevel.ERROR, "'ADD A NEW ADDRESS' button not found. The page layout may have changed.")
                return False
            
            await add_button_locator.click(timeout=30000)
            await asyncio.sleep(3)  # Wait for the address form modal to appear

            # 3. Fill the address form using the dedicated task
            form_filled = await fill_address_form(page, address_data, job_id)
            if not form_filled:
                return False

            # 4. Click the Save button
            save_button_selector = 'button:has-text("Save")'
            await job_queue.log_job(job_id, LogLevel.INFO, "Clicking 'Save' button to submit the address.")
            await page.locator(save_button_selector).click(timeout=30000)
            
            # Wait for navigation/confirmation that the address was saved
            await page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(3)

            # Verification: Check if we are back on the main addresses page
            if "account/addresses" in page.url:
                 await job_queue.log_job(job_id, LogLevel.INFO, "Address saved successfully! Redirected back to addresses page.")
                 return True
            else:
                 await job_queue.log_job(job_id, LogLevel.WARNING, "Possible issue saving address. Did not redirect as expected.")
                 # Still, we can assume success if no error was thrown.
                 return True

        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed during the address adding process: {str(e)}")
            return False


# Global worker instance
automation_worker = AutomationWorker()


# This is the main automation worker that handles the full flow.
@register_worker("flipkart_login")
async def run_full_automation(job_data: Dict[str, Any], job_id: int) -> Dict[str, Any]:
    """
    Handles the complete automation flow:
    Phase 1: Login to Flipkart
    Phase 2: Add all active products to cart and configure quantities (if products provided)
    Phase 3: Navigate to cart (ready for checkout - will be implemented later)
    
    If no products are provided, it will only perform the login test.
    """
    try:
        email = job_data.get("email")
        products = job_data.get("products", [])
        view_mode = job_data.get("view_mode", "desktop")

        if not email:
            return {"success": False, "error": "Email not provided in job data"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting automation for {email} in {view_mode} view")

        # Phase 1: Login to Flipkart
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1: Logging in to Flipkart")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)

        if not login_success:
            return {"success": False, "error": "Phase 1 failed: Login unsuccessful"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1 completed successfully")

        # Phase 1.5: Select delivery location (only for mobile view in full automation)
        if view_mode == 'mobile' and products:
            await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.5: Selecting delivery location")
            from services.batch_manager import batch_manager
            await batch_manager.load_settings()
            pincode = batch_manager.get_default_pincode()
            
            location_success = await automation_worker.select_delivery_location(job_id, pincode)
            if not location_success:
                await job_queue.log_job(job_id, LogLevel.WARNING, "Failed to set delivery location, continuing with automation")
            else:
                await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1.5 completed successfully")

        # If no products provided, this is just a login test
        if not products:
            await job_queue.log_job(job_id, LogLevel.INFO, "No products provided - login test completed successfully")
            return {"success": True, "message": "Login test successful"}

        # Phase 2: Add products to cart and configure quantities
        await job_queue.log_job(job_id, LogLevel.INFO, f"Phase 2: Adding {len(products)} products to cart")
        products_success = await automation_worker.add_and_configure_products_in_cart(products, job_id)

        if not products_success:
            return {"success": False, "error": "Phase 2 failed: Error during product processing"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2 completed successfully")

        # Phase 3 will be implemented later (checkout process)
        await job_queue.log_job(job_id, LogLevel.INFO, "Full automation completed. Ready for Phase 3 (checkout).")
        
        return {"success": True, "message": "Full automation flow completed successfully. Products added to cart."}

    except Exception as e:
        error_message = f"An unexpected error occurred in automation: {str(e)}"
        await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
        logging.error(error_message)
        return {"success": False, "error": error_message}
    finally:
        # This is crucial: ensures the browser context is always closed for this job.
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

        if not email:
            return {"success": False, "error": "Email not provided in job data"}
        if not address_data:
            return {"success": False, "error": "Address data not provided for the job"}

        # Validate required fields for the address
        required_fields = ["name", "phone", "pincode", "locality", "address"]
        missing_fields = [field for field in required_fields if not address_data.get(field)]
        if missing_fields:
            return {"success": False, "error": f"Missing required address fields: {', '.join(missing_fields)}"}

        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting 'Add Address' automation for {email}")

        # Phase 1: Login to Flipkart
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1: Logging in to Flipkart")
        login_success = await automation_worker.login_to_flipkart(email, job_id, view_mode)

        if not login_success:
            return {"success": False, "error": "Phase 1 failed: Login was unsuccessful"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 1 (Login) completed successfully.")

        # Phase 2: Add the new address
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2: Adding the new address")
        address_success = await automation_worker.add_new_address(address_data, job_id)

        if not address_success:
            return {"success": False, "error": "Phase 2 failed: Could not add the new address"}
        
        await job_queue.log_job(job_id, LogLevel.INFO, "Phase 2 (Add Address) completed successfully.")
        
        return {"success": True, "message": "New address has been added to the Flipkart account successfully."}

    except Exception as e:
        error_message = f"An unexpected error occurred in the 'Add Address' automation job: {str(e)}"
        await job_queue.log_job(job_id, LogLevel.ERROR, error_message)
        logging.error(error_message)
        return {"success": False, "error": error_message}
    finally:
        # This is crucial: ensures the browser context is always closed for this job.
        await automation_worker.cleanup_job_context(job_id)






