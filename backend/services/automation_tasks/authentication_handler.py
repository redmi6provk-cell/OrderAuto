"""
Authentication Handler Module
Handles all                  login-related operations for Flipkart automation
"""
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
import asyncio                                                                                          
import json
import logging
import os
import re
from typing import Any, Optional
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from services.job_queue import job_queue, LogLevel
from services.gmail_service import gmail_service
from database import db


class AuthenticationHandler:
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager

    async def try_cookie_login(self, email: str, job_id: int, view_mode: str = 'desktop') -> bool:
        """Try to login using saved cookies first"""
        try:
            async with db.get_connection() as conn:
                # Get saved cookies for this email
                user_data = await conn.fetchrow(
                    "SELECT id, cookies FROM flipkart_users WHERE email = $1 AND cookies IS NOT NULL",
                    email
                )
            
            if not user_data or not user_data['cookies']:
                await job_queue.log_job(job_id, LogLevel.INFO, f"No saved cookies found for {email}, will use OTP login")
                return False
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"Found saved cookies for {email}, attempting cookie login")
            
            # Create isolated browser context for this job
            context = await self.browser_manager.create_isolated_context(job_id, email, view_mode)
            if not context:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to create isolated browser context")
                return False
            
            # Parse and validate cookies
            try:
                cookies = json.loads(user_data['cookies'])
                
                # Validate that we have essential cookies
                if not self.browser_manager.validate_essential_cookies(cookies):
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"Saved cookies for {email} missing 'at' or 'rt' tokens, will use OTP login")
                    await self.browser_manager.capture_failure_screenshot(job_id, "cookie_validation_failed")
                    await self.browser_manager.cleanup_job_context(job_id)
                    return False
                
                await context.add_cookies(cookies)
                cookie_names = [cookie['name'] for cookie in cookies]
                await job_queue.log_job(job_id, LogLevel.INFO, f"Applied {len(cookies)} saved cookies ({', '.join(cookie_names)})")
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to parse/apply cookies: {e}")
                await self.browser_manager.capture_failure_screenshot(job_id, "cookie_parse_failed")
                await self.browser_manager.cleanup_job_context(job_id)
                return False
            
            page = await context.new_page()
            login_verified = False
            
            # --- Verification Logic ---
            if view_mode == 'mobile':
                await job_queue.log_job(job_id, LogLevel.INFO, "Verifying mobile cookie login via redirect check...")
                await page.goto('https://www.flipkart.com/login?type=email', wait_until='networkidle')
                await asyncio.sleep(3) # Give time for redirect to happen
                
                current_url = page.url
                if 'login' not in current_url.lower():
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Mobile cookie login successful. Redirected to: {current_url}")
                    login_verified = True
                else:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Mobile cookie login failed. Still on login page.")
                    await self.browser_manager.capture_failure_screenshot(job_id, "mobile_cookie_login_failed")
            
            else: # Desktop view verification
                await job_queue.log_job(job_id, LogLevel.INFO, "Verifying desktop cookie login via account page access...")
                await page.goto('https://www.flipkart.com/account', wait_until='networkidle')
                await asyncio.sleep(2)
                
                current_url = page.url
                if 'login' not in current_url.lower():
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Desktop cookie login successful. Landed on: {current_url}")
                    login_verified = True
                else:
                    await job_queue.log_job(job_id, LogLevel.WARNING, "Desktop cookie login failed. Redirected to login page.")
                    await self.browser_manager.capture_failure_screenshot(job_id, "desktop_cookie_login_failed")

            # --- Result Handling ---
            if login_verified:
                await job_queue.log_job(job_id, LogLevel.INFO, f"Cookie login confirmed for {email}.")
                # Update last login time
                async with db.get_connection() as conn:
                    await conn.execute("UPDATE flipkart_users SET last_login = NOW() WHERE email = $1", email)
                # Important: Do not close the page or context, the worker needs it for subsequent steps.
                return True
            else:
                await job_queue.log_job(job_id, LogLevel.INFO, f"Cookie login failed for {email}. Proceeding to OTP.")
                await page.close()
                await self.browser_manager.cleanup_job_context(job_id)
                return False
                
        except Exception as e:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"Cookie login error for {email}: {str(e)}")
            await self.browser_manager.capture_failure_screenshot(job_id, "cookie_login_exception")
            return False

    async def login_to_flipkart(self, email: str, job_id: int, view_mode: str = 'desktop') -> bool:
        """Login to Flipkart - try cookies first, then OTP if needed"""
        
        # First try to login with saved cookies
        cookie_login_success = await self.try_cookie_login(email, job_id, view_mode)
        if cookie_login_success:
            return True
        
        # If cookie login failed, proceed with OTP login
        if view_mode == 'mobile':
            return await self._login_mobile_otp(email, job_id)
        else:
            return await self._login_desktop_otp(email, job_id)
            
    async def _login_mobile_otp(self, email: str, job_id: int) -> bool:
        """Handle the mobile OTP login flow"""
        await job_queue.log_job(job_id, LogLevel.INFO, f"Starting Mobile OTP-based login for {email}")
        context = await self.browser_manager.create_isolated_context(job_id, email, view_mode='mobile')
        if not context:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to create mobile browser context")
            return False

        try:
            page = await context.new_page()
            await page.goto('https://www.flipkart.com/login?type=email', wait_until='networkidle')

            # Enter email - try multiple selectors for robustness
            await job_queue.log_job(job_id, LogLevel.INFO, "Attempting to find email input field")
            email_filled = False
            
            # Multiple selector strategies for email input
            email_selectors = [
                '#\\31',  # New selector (escaped CSS for #1)
                'input[type="email"]._1i5zkb',  # Old selector
                'input[type="email"]',  # Generic email input
                'input[placeholder*="Email" i]',  # Placeholder-based (case-insensitive)
                'input[placeholder*="email" i]',  # Lowercase variant
                'input[name*="email" i]',  # Name attribute
                'input[id="1"]',  # Direct ID without escape
                '#container input[type="email"]',  # Container scoped
            ]
            
            for selector in email_selectors:
                try:
                    email_input = page.locator(selector)
                    if await email_input.count() > 0 and await email_input.first.is_visible():
                        await email_input.first.click()
                        await email_input.first.fill(email)
                        email_filled = True
                        await job_queue.log_job(job_id, LogLevel.INFO, f"✓ Email filled using selector: {selector}")
                        break
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Email input selector failed ({selector}): {e}")
                    continue
            
            if not email_filled:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Could not find email input field with any selector")
                await self.browser_manager.capture_failure_screenshot(job_id, "email_input_not_found")
                return False
            

            # Click Continue (role/text-based with fallbacks)
            await job_queue.log_job(job_id, LogLevel.INFO, "Attempting to click Continue button (role/text-based)")
            continue_button_user_selector = '#container > div > div:nth-child(1) > div:nth-child(2) > div:nth-child(3) > div > button'

            clicked = False

            # 1) Role-based match for accessible button name "Continue"
            try:
                cont_role = page.get_by_role("button", name=re.compile(r'^\s*continue\s*$', re.I))
                if await cont_role.count() > 0 and await cont_role.first.is_visible():
                    await cont_role.first.click()
                    clicked = True
                    await job_queue.log_job(job_id, LogLevel.INFO, "Clicked Continue (role)")
            except Exception as e:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Role-based Continue click failed: {str(e)}")

            # 2) Text-based match if role-based didn't work
            if not clicked:
                try:
                    cont_text = page.get_by_text(re.compile(r'^\s*continue\s*$', re.I))
                    if await cont_text.count() > 0 and await cont_text.first.is_visible():
                        await cont_text.first.click()
                        clicked = True
                        await job_queue.log_job(job_id, LogLevel.INFO, "Clicked Continue (text)")
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"Text-based Continue click failed: {str(e)}")

            # 3) Fallback to CSS selectors, including legacy uppercase and user-specific
            if not clicked:
                fallback_selectors = [
                    'button:has-text("Continue")',
                    'button:has-text("CONTINUE")',
                    continue_button_user_selector,
                ]
                for sel in fallback_selectors:
                    try:
                        el = page.locator(sel)
                        if await el.count() > 0 and await el.first.is_visible():
                            await el.first.click()
                            clicked = True
                            await job_queue.log_job(job_id, LogLevel.INFO, f"Clicked Continue (fallback: {sel})")
                            break
                    except Exception as e:
                        await job_queue.log_job(job_id, LogLevel.DEBUG, f"Fallback selector failed ({sel}): {str(e)}")

            if not clicked:
                await self.browser_manager.capture_failure_screenshot(job_id, "continue_button_not_found")
                raise Exception("Could not find or click Continue button via any strategy.")

            await job_queue.log_job(job_id, LogLevel.INFO, "Clicked Continue. Waiting for OTP page to load.")

            # Wait for OTP input fields to appear - try multiple selectors
            await job_queue.log_job(job_id, LogLevel.INFO, "Waiting for OTP input fields to appear...")
            otp_fields_found = False
            
            # Multiple OTP field selector strategies
            otp_selectors = [
                'div.H6gpAI input',  # New structure with H6gpAI container
                'input[type="number"]',  # Generic number inputs
                'input.b62cxd[type="number"]',  # Old selector
                '#container input[type="number"]',  # Container scoped
                'input[type="tel"]',  # Sometimes uses tel type
            ]
            
            for selector in otp_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    # Verify we have multiple OTP fields (should be 6)
                    otp_count = await page.locator(selector).count()
                    if otp_count >= 6:
                        otp_fields_found = True
                        await job_queue.log_job(job_id, LogLevel.INFO, f"✓ Found {otp_count} OTP input fields using selector: {selector}")
                        break
                    else:
                        await job_queue.log_job(job_id, LogLevel.DEBUG, f"Found {otp_count} fields with {selector}, need 6")
                except Exception as e:
                    await job_queue.log_job(job_id, LogLevel.DEBUG, f"OTP selector failed ({selector}): {e}")
                    continue
            
            if not otp_fields_found:
                await self.browser_manager.capture_failure_screenshot(job_id, "otp_fields_not_found")
                raise Exception("OTP input fields did not appear after clicking Continue.")
            
            await job_queue.log_job(job_id, LogLevel.INFO, "OTP input fields detected. Flipkart should now send an OTP.")

            # Add a delay before fetching OTP as requested
            await job_queue.log_job(job_id, LogLevel.INFO, "Waiting 4 seconds before fetching OTP...")
            await asyncio.sleep(4)

            # OTP Fetching and input
            await job_queue.log_job(job_id, LogLevel.INFO, f"Fetching OTP for {email} from Gmail service...")
            await job_queue.log_job(job_id, LogLevel.INFO, f"Gmail service configured: Email={'✓' if gmail_service.gmail_email else '✗'}, Password={'✓' if gmail_service.gmail_password else '✗'}")
            
            
            otp = await asyncio.to_thread(gmail_service.fetch_flipkart_otp, target_email=email, max_wait_time=120)
            if not otp or len(otp) != 6:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to fetch valid 6-digit OTP. Received: {otp}")
                await self.browser_manager.capture_failure_screenshot(job_id, "otp_fetch_failed")
                raise Exception("Failed to fetch valid 6-digit OTP.")
            
            await job_queue.log_job(job_id, LogLevel.INFO, f"OTP received: {otp}")

            # Use the same selectors that worked for detection
            otp_inputs = None
            for selector in otp_selectors:
                try:
                    inputs = await page.locator(selector).all()
                    if len(inputs) >= 6:
                        otp_inputs = inputs[:6]  # Take first 6
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Using {len(otp_inputs)} OTP inputs from selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not otp_inputs or len(otp_inputs) != 6:
                await self.browser_manager.capture_failure_screenshot(job_id, "otp_input_count_mismatch")
                raise Exception(f"Expected 6 OTP input fields, but found {len(otp_inputs) if otp_inputs else 0}.")

            for i, otp_char in enumerate(otp):
                await otp_inputs[i].fill(otp_char)
                await page.wait_for_timeout(100)

            # Click Verify
            verify_button = page.locator('button:has-text("Verify")')
            await verify_button.click()
            
            # Check if we're already redirected or need to wait
            await asyncio.sleep(2)  # Give page a moment to start redirecting
            current_url = page.url
            
            if "flipkart.com" in current_url and "login" not in current_url.lower():
                await job_queue.log_job(job_id, LogLevel.INFO, f"Already redirected to {current_url}. Verifying login status.")
            else:
                await job_queue.log_job(job_id, LogLevel.INFO, f"Still on {current_url}, waiting for redirect...")
                await page.wait_for_url("**/flipkart.com**", timeout=15000)
                await job_queue.log_job(job_id, LogLevel.INFO, f"Redirected to {page.url}. Verifying login status.")
            
            # Explicitly verify login success with header-based detection and short retries
            # Log header text if available for diagnostics
            try:
                hdr = page.locator('div.uiU-ZX')
                if await hdr.count() > 0:
                    txt = (await hdr.first.inner_text()).strip()
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Header (div.uiU-ZX) text: '{txt}'")
            except Exception:
                pass

            login_verified = False
            for _ in range(12):  # ~6 seconds
                if await self._is_logged_in(page):
                    login_verified = True
                    break
                await asyncio.sleep(0.5)

            # If still not verified, navigate to homepage and retry briefly
            if not login_verified:
                try:
                    await page.goto('https://www.flipkart.com/', wait_until='domcontentloaded')
                except Exception:
                    pass
                for _ in range(10):  # ~5 seconds
                    if await self._is_logged_in(page):
                        login_verified = True
                        break
                    await asyncio.sleep(0.5)

            if login_verified:
                await job_queue.log_job(job_id, LogLevel.INFO, f"Mobile login successful for {email}")
                await self.browser_manager.save_cookies_to_db(job_id, await context.cookies())
                return True
            else:
                await self.browser_manager.capture_failure_screenshot(job_id, "mobile_login_verification_failed")
                raise Exception("Mobile login failed after OTP submission. Account indicators not found.")

        except Exception as e:
            error_msg = f"Mobile login error: {str(e)}"
            await job_queue.log_job(job_id, LogLevel.ERROR, error_msg)
            # Take screenshot on failure (centralized, lighter JPEG)
            await self.browser_manager.capture_failure_screenshot(job_id, "mobile_login_exception")
            
            await self.browser_manager.cleanup_job_context(job_id)
            return False

    async def _login_desktop_otp(self, email: str, job_id: int) -> bool:
        """Handle the desktop OTP login flow (original logic)"""
        context = None
        try:
            await job_queue.log_job(job_id, LogLevel.INFO, f"Starting OTP-based login for {email}")
            
            # Create isolated browser context for this job
            context = await self.browser_manager.create_isolated_context(job_id, email)
            if not context:
                await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to create isolated browser context")
                await self.browser_manager.capture_failure_screenshot(job_id, "desktop_context_creation_failed")
                return False
            
            page = await context.new_page()
            
            # Navigate to Flipkart login
            await page.goto('https://www.flipkart.com/account/login')
            await asyncio.sleep(3)
            
            # Enter email using the correct selector
            await job_queue.log_job(job_id, LogLevel.INFO, "Entering email address")
            email_selector = '#container > div > div.VCR99n > div > div.Sm1-5F.col.col-3-5 > div > form > div.I-qZ4M.vLRlQb > input'
            await page.wait_for_selector(email_selector, timeout=10000)
            await page.fill(email_selector, email)
            await asyncio.sleep(1)
            
            # Click Request OTP button
            await job_queue.log_job(job_id, LogLevel.INFO, "Clicking Request OTP button")
            request_otp_selector = '#container > div > div.VCR99n > div > div.Sm1-5F.col.col-3-5 > div > form > div.LSOAQH > button'
            await page.wait_for_selector(request_otp_selector, timeout=10000)
            await page.click(request_otp_selector)
            await asyncio.sleep(3)
            
            # Check if OTP input fields are present and enter OTP digit by digit
            try:
                await job_queue.log_job(job_id, LogLevel.INFO, "Waiting for OTP input fields")
                
                # Wait for OTP input container
                otp_container_selector = 'div.XDRRi5'
                await page.wait_for_selector(otp_container_selector, timeout=15000)
                
                # Wait for first OTP input field with the correct class
                first_otp_input = 'input.r4vIwl.IX3CMV'
                await page.wait_for_selector(first_otp_input, timeout=15000)
                
                await job_queue.log_job(job_id, LogLevel.INFO, "OTP input fields detected, waiting 5 seconds for email delivery")
                
                # Wait 5 seconds for better email delivery reliability
                await asyncio.sleep(5)
                
                await job_queue.log_job(job_id, LogLevel.INFO, "Now fetching OTP from email")
                await job_queue.log_job(job_id, LogLevel.INFO, f"Gmail service configured: Email={'✓' if gmail_service.gmail_email else '✗'}, Password={'✓' if gmail_service.gmail_password else '✗'}")
                
                # Fetch OTP from Gmail for this specific email
                otp = gmail_service.fetch_flipkart_otp(target_email=email, max_wait_time=120)  # Wait up to 2 minutes
                
                if not otp:
                    await job_queue.log_job(job_id, LogLevel.ERROR, "Failed to fetch OTP from email")
                    await self.browser_manager.capture_failure_screenshot(job_id, "desktop_otp_fetch_failed")
                    await page.close()
                    return False
                
                await job_queue.log_job(job_id, LogLevel.INFO, f"OTP received: {otp}")
                
                # Enter OTP digit by digit in the 6 input fields
                if len(otp) >= 6:
                    # Get all OTP input fields
                    otp_inputs = await page.query_selector_all('input.r4vIwl.IX3CMV')
                    
                    if len(otp_inputs) >= 6:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found {len(otp_inputs)} OTP input fields, entering digits")
                        
                        for i in range(6):
                            try:
                                # Click to focus and enter the digit
                                await otp_inputs[i].click()
                                await asyncio.sleep(0.1)
                                await otp_inputs[i].fill(otp[i])
                                await asyncio.sleep(0.2)
                                await job_queue.log_job(job_id, LogLevel.INFO, f"Entered digit {i+1}: {otp[i]}")
                            except Exception as e:
                                await job_queue.log_job(job_id, LogLevel.WARNING, f"Error entering digit {i+1}: {e}, trying keyboard input")
                                try:
                                    await otp_inputs[i].click()
                                    await page.keyboard.type(otp[i])
                                    await asyncio.sleep(0.2)
                                except Exception as e2:
                                    await job_queue.log_job(job_id, LogLevel.ERROR, f"Failed to enter digit {i+1}: {e2}")
                    else:
                        await job_queue.log_job(job_id, LogLevel.ERROR, f"Expected 6 OTP fields, found {len(otp_inputs)}")
                        await self.browser_manager.capture_failure_screenshot(job_id, "desktop_otp_field_count_mismatch")
                        await page.close()
                        return False
                else:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"OTP too short: {len(otp)} digits")
                    await self.browser_manager.capture_failure_screenshot(job_id, "desktop_otp_too_short")
                    await page.close()
                    return False
                
                await job_queue.log_job(job_id, LogLevel.INFO, "OTP entered. Assuming auto-submit and waiting for redirect.")
                
                # Wait for page to redirect after OTP verification
                await job_queue.log_job(job_id, LogLevel.INFO, "Waiting for login redirect...")
                
                # Wait for either redirect to main page or login failure
                try:
                    # Wait up to 10 seconds for URL to change (indicating success or failure)
                    await page.wait_for_function(
                        "() => !window.location.href.includes('/account/login')",
                        timeout=10000
                    )
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Page redirected to: {page.url}")
                except Exception as redirect_error:
                    await job_queue.log_job(job_id, LogLevel.WARNING, f"No redirect detected: {redirect_error}")
                    # Continue anyway to check current state
                
                # Wait for login result
                await job_queue.log_job(job_id, LogLevel.INFO, "Waiting for login to complete...")
                await asyncio.sleep(5)
                
                # Check current URL first - if we're on main Flipkart page, login was successful
                current_url = page.url
                await job_queue.log_job(job_id, LogLevel.INFO, f"Current URL after OTP: {current_url}")
                
                # Check if we're successfully logged in based on URL
                is_logged_in_by_url = (
                    'flipkart.com' in current_url.lower() and 
                    'account/login' not in current_url.lower() and
                    'otp' not in current_url.lower()
                )
                
                if is_logged_in_by_url:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Login successful - redirected to main Flipkart page: {current_url}")
                    
                    # Get all cookies after successful login
                    all_cookies = await context.cookies()
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Found {len(all_cookies)} total cookies after successful login")
                    
                    # Log which cookies we found
                    cookie_names = [cookie['name'] for cookie in all_cookies]
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Available cookies: {', '.join(cookie_names)}")
                    
                    # Look for essential cookies
                    at_cookie = next((cookie for cookie in all_cookies if cookie['name'] == 'at'), None)
                    rt_cookie = next((cookie for cookie in all_cookies if cookie['name'] == 'rt'), None)
                    
                    if at_cookie:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found 'at' cookie: {at_cookie['value'][:20]}...")
                    if rt_cookie:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"Found 'rt' cookie: {rt_cookie['value'][:20]}...")
                    
                    if at_cookie and rt_cookie:
                        await job_queue.log_job(job_id, LogLevel.INFO, f"OTP login successful for {email} - 'at' and 'rt' tokens found")
                        
                        # Save only the essential cookies (at, rt) to database for future use
                        essential_cookies = [at_cookie, rt_cookie]
                        await self.browser_manager.save_cookies_to_db(job_id, essential_cookies)
                    else:
                        await job_queue.log_job(job_id, LogLevel.WARNING, f"Login successful but missing 'at'/'rt' cookies - saving all cookies as fallback")
                        
                        # Save all cookies as fallback
                        await self.browser_manager.save_cookies_to_db(job_id, all_cookies)
                    
                    # The job is complete, the 'finally' block in the worker will handle cleanup.
                    return True
                    
                else:
                    await job_queue.log_job(job_id, LogLevel.ERROR, f"OTP login failed for {email} - still on login/OTP page: {current_url}")
                    await self.browser_manager.capture_failure_screenshot(job_id, "desktop_otp_login_failed")
                    await page.close()
                    await self.browser_manager.cleanup_job_context(job_id)
                    return False
                    
            except Exception as otp_error:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"OTP process error: {str(otp_error)}")
                await self.browser_manager.capture_failure_screenshot(job_id, "desktop_otp_process_error")
                await page.close()
                await self.browser_manager.cleanup_job_context(job_id)
                return False
                
        except Exception as e:
            error_msg = f"Login error for {email}: {str(e)}"
            await job_queue.log_job(job_id, LogLevel.ERROR, error_msg)
            logging.error(error_msg)
            await self.browser_manager.capture_failure_screenshot(job_id, "desktop_login_exception")
            if context:
                await self.browser_manager.cleanup_job_context(job_id)
            return False

    async def _is_logged_in(self, page: Any) -> bool:
        """Check if user is logged in by looking for account indicators."""
        try:
            # 1) Preferred mobile header check: div.uiU-ZX
            # If it shows 'Login' -> NOT logged in. If it shows anything else (e.g., account name) -> logged in.
            try:
                ui_header = page.locator('div.uiU-ZX')
                if await ui_header.count() > 0:
                    try:
                        await ui_header.first.wait_for(state='visible', timeout=3000)
                    except Exception:
                        pass
                    try:
                        header_text = (await ui_header.first.inner_text()).strip()
                    except Exception:
                        header_text = ''
                    if header_text:
                        if 'login' in header_text.lower():
                            return False
                        # Any other non-empty text means logged in
                        return True
            except Exception:
                # Continue to fallbacks
                pass

            # 2) Fallback indicators (desktop/mobile)
            account_indicators = [
                'text=My Account',
                'text=Account',
                '[data-testid="account-menu"]',
                'button[aria-label="Account"]',
                'a[href="/account/"]'
            ]
            for indicator in account_indicators:
                if await page.locator(indicator).count() > 0:
                    return True
            return False
        except Exception:
            return False
