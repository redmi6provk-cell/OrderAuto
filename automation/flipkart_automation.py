#!/usr/bin/env python3
"""
Flipkart Automation Script using Playwright
Handles login, price checking, and order placement
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import logging

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
import asyncpg
from dataclasses import dataclass

@dataclass
class FlipkartAccount:
    email: str
    password: str
    cookies: Optional[str] = None
    proxy: Optional[Dict] = None

@dataclass
class Product:
    id: int
    url: str
    name: Optional[str]
    price_cap: Optional[Decimal]
    quantity: int

@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    price: Optional[Decimal] = None
    error: Optional[str] = None

class FlipkartAutomation:
    def __init__(self, database_url: str, headless: bool = True, view_mode: str = 'desktop'):
        self.database_url = database_url
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright: Optional[Playwright] = None
        self.view_mode = view_mode
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def create_context(self, account: FlipkartAccount) -> BrowserContext:
        """Create browser context with proxy and cookies"""
        
        if self.view_mode == 'mobile':
            # Use custom mobile viewport dimensions
            context_options = {
                'viewport': {'width': 412, 'height': 930},
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                'device_scale_factor': 2.75,
                'is_mobile': True,
                'has_touch': True
            }
        else:
            # Desktop user agent
            context_options = {
                'viewport': {'width': 1366, 'height': 768},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        
        if account.proxy:
            context_options['proxy'] = account.proxy
        
        context = await self.browser.new_context(**context_options)
        
        # Load cookies if available
        if account.cookies:
            try:
                cookies = json.loads(account.cookies)
                await context.add_cookies(cookies)
            except json.JSONDecodeError:
                print(f"Invalid cookies for account {account.email}")
        
        return context
    
    async def login(self, context: BrowserContext, account: FlipkartAccount) -> bool:
        """Login to Flipkart account based on view mode"""
        if self.view_mode == 'mobile':
            return await self._login_mobile(context, account)
        else:
            return await self._login_desktop(context, account)

    async def _login_desktop(self, context: BrowserContext, account: FlipkartAccount) -> bool:
        """Login to Flipkart account (Desktop View)"""
        page = await context.new_page()
        
        try:
            # Navigate to Flipkart
            await page.goto('https://www.flipkart.com', wait_until='networkidle')
            
            # Check if already logged in
            if await self._is_logged_in(page):
                print(f"Account {account.email} already logged in")
                return True
            
            # Click login button
            await page.click('text=Login', timeout=10000)
            await page.wait_for_timeout(2000)
            
            # Enter email/phone
            email_input = page.locator('input[type="text"]').first
            await email_input.fill(account.email)
            await page.wait_for_timeout(1000)
            
            # Enter password
            password_input = page.locator('input[type="password"]').first
            await password_input.fill(account.password)
            await page.wait_for_timeout(1000)
            
            # Click login
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(5000)
            
            # Handle OTP if required
            if await page.locator('text=OTP').count() > 0:
                print(f"OTP required for {account.email}")
                # TODO: Implement OTP handling via Gmail API
                return False
            
            # Check if login successful
            if await self._is_logged_in(page):
                # Save cookies
                cookies = await context.cookies()
                await self._save_cookies(account.email, cookies)
                print(f"Login successful for {account.email}")
                return True
            else:
                print(f"Login failed for {account.email}")
                return False
                
        except Exception as e:
            print(f"Login error for {account.email}: {str(e)}")
            return False
        finally:
            await page.close()
            
    async def _login_mobile(self, context: BrowserContext, account: FlipkartAccount) -> bool:
        """Login to Flipkart account (Mobile View)"""
        page = await context.new_page()
        
        try:
            # Navigate to the mobile-friendly login page
            await page.goto('https://www.flipkart.com/login?type=email', wait_until='networkidle')
            
            # Check if we are already logged in by being redirected
            if "login" not in page.url:
                logging.info(f"Account {account.email} already logged in (redirected).")
                await self._save_cookies(account.email, await context.cookies())
                return True

            # Enter email - try multiple selectors for robustness
            logging.info("Attempting to find email input field")
            email_filled = False
            
            # Multiple selector strategies for email input
            email_selectors = [
                '#\\31',  # New selector (escaped CSS for #1)
                'input[type="email"]._1i5zkb',  # Old selector
                'input[type="email"]',  # Generic email input
                'input[placeholder*="Email" i]',  # Placeholder-based
                'input[name*="email" i]',  # Name-based
                'input[id="1"]',  # Direct ID without escape
            ]
            
            for selector in email_selectors:
                try:
                    email_input = page.locator(selector)
                    if await email_input.count() > 0 and await email_input.first.is_visible():
                        await email_input.first.click()
                        await email_input.first.fill(account.email)
                        email_filled = True
                        logging.info(f"Email filled using selector: {selector}")
                        break
                except Exception as e:
                    logging.debug(f"Email input selector failed ({selector}): {e}")
                    continue
            
            if not email_filled:
                logging.error("Could not find email input field with any selector")
                return False
            
            await page.wait_for_timeout(1000)

            # Click Continue (role/text-based with fallbacks)
            logging.info("Attempting to click Continue button (role/text-based)")
            clicked = False

            # 1) Role-based match for accessible button name "Continue"
            try:
                cont_role = page.get_by_role("button", name=re.compile(r'^\s*continue\s*$', re.I))
                if await cont_role.count() > 0 and await cont_role.first.is_visible():
                    await cont_role.first.click()
                    clicked = True
                    logging.info("Clicked Continue (role)")
            except Exception as e:
                logging.debug(f"Role-based Continue click failed: {e}")

            # 2) Text-based match if role-based didn't work
            if not clicked:
                try:
                    cont_text = page.get_by_text(re.compile(r'^\s*continue\s*$', re.I))
                    if await cont_text.count() > 0 and await cont_text.first.is_visible():
                        await cont_text.first.click()
                        clicked = True
                        logging.info("Clicked Continue (text)")
                except Exception as e:
                    logging.debug(f"Text-based Continue click failed: {e}")

            # 3) Fallback to CSS selectors (legacy uppercase and user-specific)
            if not clicked:
                fallback_selectors = [
                    'button:has-text("Continue")',
                    'button:has-text("CONTINUE")',
                    '#container > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(3) > div > button',
                ]
                for sel in fallback_selectors:
                    try:
                        el = page.locator(sel)
                        if await el.count() > 0 and await el.first.is_visible():
                            await el.first.click()
                            clicked = True
                            logging.info(f"Clicked Continue (fallback: {sel})")
                            break
                    except Exception as e:
                        logging.debug(f"Fallback selector failed ({sel}): {e}")

            if not clicked:
                logging.error("Could not find or click Continue button via any strategy.")
                return False

            await page.wait_for_timeout(1500)
            
            # --- OTP Handling ---
            logging.info(f"Waiting for OTP for {account.email}")
            
            # This is a placeholder for your OTP fetching logic.
            # You would replace this with a call to your Gmail API or other OTP service.
            otp = await self._fetch_otp_from_service(account.email) # This function needs to be implemented
            
            if not otp or len(otp) != 6:
                logging.error(f"Failed to fetch a valid 6-digit OTP for {account.email}")
                return False
            
            logging.info(f"Received OTP {otp} for {account.email}")

            # Fill OTP
            otp_inputs = await page.locator('input[type="tel"]').all()
            if len(otp_inputs) == 6:
                for i, otp_char in enumerate(otp):
                    await otp_inputs[i].fill(otp_char)
                    await page.wait_for_timeout(200) # Small delay between inputs
            else:
                logging.error("Could not find 6 OTP input fields.")
                return False

            await page.wait_for_timeout(1000)
            
            # Click Verify
            verify_button = page.locator('button:has-text("Verify")')
            if await verify_button.count() == 0:
                # Fallback to user's selector
                verify_button = page.locator('#container > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(2) > div > button')

            await verify_button.click()
            
            # Wait for navigation to homepage or account page, indicating successful login
            await page.wait_for_url("**/flipkart.com**", timeout=15000)

            if "login" not in page.url and await self._is_logged_in(page):
                logging.info(f"Mobile login successful for {account.email}")
                await self._save_cookies(account.email, await context.cookies())
                return True
            else:
                logging.error(f"Mobile login failed for {account.email} after OTP submission.")
                return False

        except Exception as e:
            logging.error(f"Mobile login error for {account.email}: {str(e)}")
            return False
        finally:
            await page.close()

    async def _fetch_otp_from_service(self, email: str) -> Optional[str]:
        """
        Placeholder function to fetch OTP.
        Replace this with your actual OTP fetching logic (e.g., Gmail API).
        """
        logging.warning("OTP fetching is not implemented. Using placeholder logic.")
        # In a real scenario, you would query your service here.
        # For now, let's simulate a delay and return a dummy OTP for testing.
        await asyncio.sleep(15) # Simulate waiting for OTP email
        
        # This is where you would connect to DB or service to get the latest OTP
        # For example: return await get_latest_otp_from_db(email)
        
        return "123456" # Dummy OTP for testing flow
    
    async def _is_logged_in(self, page: Page) -> bool:
        """Check if user is logged in"""
        try:
            # Check if explicit Login buttons are visible
            login_buttons = [
                'text="Login"',
                'a[href*="/login"]'
            ]
            for login_btn in login_buttons:
                if await page.locator(login_btn).count() > 0 and await page.locator(login_btn).first.is_visible():
                    return False
                    
            # Look for user account indicators
            account_indicators = [
                'text="My Account"',
                'text="Account"',
                '[data-testid="account-menu"]',
                'button[aria-label="Account"]'
            ]
            
            for indicator in account_indicators:
                if await page.locator(indicator).count() > 0:
                    return True
            return False
        except:
            return False
    
    async def check_price(self, context: BrowserContext, product: Product) -> Tuple[Optional[Decimal], bool]:
        """Check current price of a product"""
        page = await context.new_page()
        
        try:
            await page.goto(product.url, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # Extract price using multiple selectors
            price_selectors = [
                '._30jeq3._16Jk6d',  # Main price selector
                '._3I9_wc._27UcVY',  # Alternative price
                '.CEmiEU',           # Another price format
                '[data-testid="price"]'
            ]
            
            price_text = None
            for selector in price_selectors:
                price_element = page.locator(selector).first
                if await price_element.count() > 0:
                    price_text = await price_element.text_content()
                    break
            
            if not price_text:
                print(f"Could not find price for product {product.id}")
                return None, False
            
            # Extract numeric price
            price_match = re.search(r'₹([\d,]+)', price_text.replace(' ', ''))
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                current_price = Decimal(price_str)
                
                # Check availability
                is_available = await self._check_availability(page)
                
                price_cap_str = f"₹{product.price_cap}" if product.price_cap is not None else "No limit"
                print(f"Product {product.id}: ₹{current_price} (Cap: {price_cap_str})")
                return current_price, is_available
            
            return None, False
            
        except Exception as e:
            print(f"Price check error for product {product.id}: {str(e)}")
            return None, False
        finally:
            await page.close()
    
    async def _check_availability(self, page: Page) -> bool:
        """Check if product is available for purchase"""
        try:
            # Check for out of stock indicators
            out_of_stock_indicators = [
                'text=Out of Stock',
                'text=Currently Unavailable',
                'text=Notify Me',
                'text=Coming Soon'
            ]
            
            for indicator in out_of_stock_indicators:
                if await page.locator(indicator).count() > 0:
                    return False
            
            # Check for add to cart button
            add_to_cart_selectors = [
                'text=Add to Cart',
                'text=ADD TO CART',
                'text="Add"',
                'button[class*="cart"]'
            ]
            
            for selector in add_to_cart_selectors:
                if await page.locator(selector).count() > 0:
                    return True
            
            return False
            
        except:
            return False
    
    async def place_order(self, context: BrowserContext, product: Product) -> OrderResult:
        """Place an order for a product"""
        page = await context.new_page()
        
        try:
            await page.goto(product.url, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # Check availability
            is_available = await self._check_availability(page)
            if not is_available:
                return OrderResult(success=False, error="Product not available")
            
            # Add to cart
            add_to_cart_selectors = [
                'text=Add to Cart',
                'text=ADD TO CART',
                'text="Add"',
                'button[class*="cart"]'
            ]
            added = False
            for selector in add_to_cart_selectors:
                add_to_cart_btn = page.locator(selector).first
                if await add_to_cart_btn.count() > 0:
                    await add_to_cart_btn.click()
                    added = True
                    break
            
            if not added:
                return OrderResult(success=False, error="Could not find Add to Cart button")
                
            await page.wait_for_timeout(3000)
            
            # Go to cart
            await page.goto('https://www.flipkart.com/viewcart', wait_until='networkidle')
            await page.wait_for_timeout(2000)
            
            # Update quantity if needed
            if product.quantity > 1:
                quantity_selector = page.locator('select[class*="quantity"]').first
                await quantity_selector.select_option(str(product.quantity))
                await page.wait_for_timeout(2000)
            
            # Proceed to checkout
            place_order_btn = page.locator('text=Place Order').first
            await place_order_btn.click()
            await page.wait_for_timeout(3000)
            
            # Select Cash on Delivery
            cod_option = page.locator('text=Cash on Delivery').first
            if await cod_option.count() > 0:
                await cod_option.click()
                await page.wait_for_timeout(2000)
            
            # Final order placement
            confirm_btn = page.locator('text=Confirm Order').first
            await confirm_btn.click()
            await page.wait_for_timeout(5000)
            
            # Extract order ID
            order_id = await self._extract_order_id(page)
            
            if order_id:
                return OrderResult(success=True, order_id=order_id)
            else:
                return OrderResult(success=False, error="Order placement failed")
                
        except Exception as e:
            print(f"Order placement error for product {product.id}: {str(e)}")
            return OrderResult(success=False, error=str(e))
        finally:
            await page.close()
    
    async def _extract_order_id(self, page: Page) -> Optional[str]:
        """Extract order ID from order confirmation page"""
        try:
            # Wait for order confirmation
            await page.wait_for_timeout(5000)
            
            # Look for order ID patterns
            order_id_selectors = [
                'text=Order ID',
                'text=Order #',
                '[data-testid="order-id"]'
            ]
            
            for selector in order_id_selectors:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.text_content()
                    order_match = re.search(r'(\w+\d+\w*)', text)
                    if order_match:
                        return order_match.group(1)
            
            return None
            
        except:
            return None
    
    async def _save_cookies(self, email: str, cookies: List[Dict]) -> None:
        """Save cookies to database"""
        try:
            conn = await asyncpg.connect(self.database_url)
            cookies_json = json.dumps(cookies)
            
            await conn.execute(
                """
                UPDATE flipkart_users 
                SET cookies = $1, last_login = CURRENT_TIMESTAMP 
                WHERE email = $2
                """,
                cookies_json, email
            )
            
            await conn.close()
            
        except Exception as e:
            print(f"Failed to save cookies for {email}: {str(e)}")

# Example usage
async def main():
    """Example automation workflow"""
    database_url = "postgresql://postgres:password@localhost:5432/flipkart_automation"
    
    # Sample account and product (replace with real data)
    account = FlipkartAccount(
        email="test@example.com",
        password="password123"
    )
    
    product = Product(
        id=1,
        url="https://www.flipkart.com/sample-product",
        name="Sample Product",
        price_cap=Decimal("1000.00"),
        quantity=1
    )
    
    async with FlipkartAutomation(database_url, headless=False) as automation:
        context = await automation.create_context(account)
        
        # Login
        if await automation.login(context, account):
            print("Login successful!")
            
            # Check price
            current_price, is_available = await automation.check_price(context, product)
            
            if current_price and is_available and current_price <= product.price_cap:
                print(f"Price {current_price} is within cap {product.price_cap}")
                
                # Place order
                result = await automation.place_order(context, product)
                if result.success:
                    print(f"Order placed successfully! Order ID: {result.order_id}")
                else:
                    print(f"Order failed: {result.error}")
            else:
                print("Price not favorable or product unavailable")
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(main()) 