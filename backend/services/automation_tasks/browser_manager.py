"""
Browser Management Module
Handles browser initialization, context creation, stealth evasions, and cleanup
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime
from typing import Dict, Any, Optional
import tempfile

from services.job_queue import job_queue, LogLevel
from database import db


class BrowserManager:
    def __init__(self):
        self.browser = None
        self.playwright = None
        self.active_contexts = {}  # Track active browser contexts per job
        self.headless = False  # Default: visible for diagnostics
        self.launched_headless: Optional[bool] = None
        self.enable_stealth: bool = True
        # Screenshot preferences (lighter to improve performance/storage)
        self.screenshot_type: str = 'jpeg'          # jpeg allows quality control
        self.screenshot_quality: int = 60           # 0-100 (lower = smaller file)
        self.screenshot_full_page: bool = False     # capture viewport only by default
        self.keep_browser_on_failure: bool = True  # DEBUG: Keep open on failure
        
    async def initialize_browser(self):
        """Initialize Playwright browser"""
        try:
            from playwright.async_api import async_playwright
            
            # If browser exists and matches desired headless, no-op
            if self.browser is not None and self.launched_headless == self.headless:
                logging.info(f"Browser already initialized (headless={self.launched_headless}), reusing instance")
                return True

            # If browser exists but headless changed, close and restart
            if self.browser is not None and self.launched_headless != self.headless:
                logging.info(f"Headless setting changed (was {self.launched_headless}, now {self.headless}). Reinitializing browser...")
                try:
                    await self.browser.close()
                except Exception:
                    pass
                self.browser = None

            if self.playwright is None:
                from playwright.async_api import async_playwright
                self.playwright = await async_playwright().start()

            # --- Staggered Parallel Launch Delay ---
            # Wait 5 seconds + 1-3 seconds random jitter to avoid CPU spikes on Windows
            delay = 5 + random.uniform(1, 3)
            logging.info(f"Staggering browser launch for 5s + random delay: {delay:.2f}s")
            await asyncio.sleep(delay)

            # Conservative launch args to avoid easy bot flags; avoid overly aggressive flags
            launch_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-infobars',
                '--disable-blink-features=AutomationControlled',
                '--lang=en-US,en',
            ]

            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
            )
            
            logging.info(f"Browser initialized successfully (headless={self.headless})")
            self.launched_headless = self.headless
            return True
            
        except Exception as e:
            logging.error(f"Failed to initialize browser: {e}")
            return False

    def set_headless(self, headless: bool):
        """Set default headless mode for next browser launch. Must be called before first initialization."""
        try:
            self.headless = bool(headless)
            logging.info(f"Headless mode set to: {self.headless}")
        except Exception:
            # Ensure we don't crash due to weird inputs
            self.headless = False
            logging.warning("Invalid headless value provided. Falling back to headless=False")

    def set_stealth(self, enable: bool):
        """Enable or disable stealth evasions."""
        try:
            self.enable_stealth = bool(enable)
            logging.info(f"Stealth evasions enabled: {self.enable_stealth}")
        except Exception:
            self.enable_stealth = True
            logging.warning("Invalid stealth value provided. Falling back to enable_stealth=True")
    
    async def create_isolated_context(self, job_id: int, email: str, view_mode: str = 'desktop'):
        """Create an isolated browser context for a specific job"""
        if not self.browser:
            logging.error("Browser is not initialized. Cannot create context.")
            # Attempt a last-minute initialization
            if not await self.initialize_browser():
                 return None

        try:
            # Create unique user data directory for this session
            safe_email = email.replace('@', '_').replace('.', '_')
            user_data_dir = os.path.join(tempfile.gettempdir(), f"flipkart_automation_job_{job_id}_{safe_email}")
            os.makedirs(user_data_dir, exist_ok=True)
            
            # Build a realistic user agent based on actual Chromium version
            chrome_version = await self._get_chrome_version_for_ua()
            context_options = {}
            if view_mode == 'mobile':
                # Prefer Android Chrome UA on Chromium to avoid Safari/WebKit mismatches
                mobile_ua = (
                    f"Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                    f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Mobile Safari/537.36"
                )
                context_options = {
                    'viewport': {'width': 412, 'height': 915},
                    'user_agent': mobile_ua,
                    'device_scale_factor': 1.75,
                    'is_mobile': True,
                    'has_touch': True,
                    'locale': 'en-IN',
                    'timezone_id': 'Asia/Kolkata',
                    'geolocation': {'longitude': 72.8777, 'latitude': 19.0760},  # Mumbai
                    'color_scheme': 'light',
                }
            else:
                desktop_ua = (
                    f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    f"(KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
                )
                context_options = {
                    'user_agent': desktop_ua,
                    'viewport': {'width': 1920, 'height': 1080},
                    'locale': 'en-IN',
                    'timezone_id': 'Asia/Kolkata',
                    'geolocation': {'longitude': 77.5946, 'latitude': 12.9716},  # Bengaluru
                    'color_scheme': 'light',
                }

            # Create new browser context with isolated storage
            context = await self.browser.new_context(
                **context_options,
                storage_state=None,  # Start with clean state
                accept_downloads=True,
                # Each context gets its own storage
                extra_http_headers={
                    'Accept-Language': 'en-IN,en;q=0.9'
                }
            )
            # Grant geolocation permission for the specified origins
            try:
                await context.grant_permissions(["geolocation"], origin="https://www.flipkart.com")
            except Exception:
                pass

            # Apply stealth evasions
            if self.enable_stealth:
                await self._apply_stealth_evasions(context, view_mode=view_mode)
            
            # Store context reference
            self.active_contexts[job_id] = {
                'context': context,
                'email': email,
                'user_data_dir': user_data_dir,
                'created_at': datetime.now()
            }
            
            logging.info(f"Created isolated context for job {job_id} with email {email}")
            return context
            
        except Exception as e:
            logging.error(f"Failed to create isolated context for job {job_id}: {e}")
            return None
    
    async def cleanup_job_context(self, job_id: int):
        """Clean up browser context for a specific job"""
        try:
            if job_id in self.active_contexts:
                if self.keep_browser_on_failure:
                    logging.info(f"DEBUG: Skipping cleanup for job {job_id} to keep browser open.")
                    return

                context_info = self.active_contexts[job_id]
                context = context_info['context']
                user_data_dir = context_info['user_data_dir']
                
                # Close all pages in this context
                for page in context.pages:
                    await page.close()
                
                # Close the context
                await context.close()
                
                # Clean up user data directory
                import shutil
                if os.path.exists(user_data_dir):
                    shutil.rmtree(user_data_dir, ignore_errors=True)
                
                # Remove from tracking
                del self.active_contexts[job_id]
                
                logging.info(f"Cleaned up context for job {job_id}")
                
        except Exception as e:
            logging.error(f"Failed to cleanup context for job {job_id}: {e}")
    
    async def get_job_context(self, job_id: int):
        """Get existing browser context for a job"""
        return self.active_contexts.get(job_id, {}).get('context', None)
    
    def get_active_contexts_count(self):
        """Get number of active browser contexts"""
        return len(self.active_contexts)
    
    def get_active_contexts_info(self):
        """Get information about active contexts"""
        return {
            job_id: {
                'email': info['email'],
                'created_at': info['created_at'].isoformat(),
                'user_data_dir': info['user_data_dir']
            }
            for job_id, info in self.active_contexts.items()
        }
    
    async def cleanup_browser(self):
        """Cleanup browser resources"""
        try:
            # Clean up all active isolated contexts
            for job_id in list(self.active_contexts.keys()):
                await self.cleanup_job_context(job_id)
            
            # Clean up legacy context if it exists
            if hasattr(self, 'context') and self.context:
                await self.context.close()
                self.context = None
                
            if self.browser:
                await self.browser.close()
                self.browser = None
                
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            self.launched_headless = None
                
            logging.info("Browser cleanup completed")
            
        except Exception as e:
            logging.error(f"Error during browser cleanup: {e}")

    async def create_browser_context(self, user_data: Dict[str, Any]) -> bool:
        """Create a new browser context for a user (legacy method)"""
        try:
            if not self.browser:
                if not await self.initialize_browser():
                    return False
            
            # Create new context
            self.context = await self.browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Load cookies if available
            if user_data.get('cookies'):
                try:
                    cookies = json.loads(user_data['cookies'])
                    await self.context.add_cookies(cookies)
                    logging.info("Loaded existing cookies")
                except Exception as e:
                    logging.warning(f"Failed to load cookies: {e}")
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to create browser context: {e}")
            return False

    async def save_cookies_to_db(self, job_id: int, cookies: list):
        """Save cookies to database for isolated session"""
        try:
            async with db.get_connection() as conn:
                # Get flipkart_user_id from job data
                job_record = await conn.fetchrow(
                    "SELECT job_data FROM job_queue WHERE id = $1", job_id
                )

                if not job_record:
                    logging.error(f"Could not find job with ID {job_id} to save cookies.")
                    return

                raw_job_data = job_record['job_data']
                if isinstance(raw_job_data, (dict, list)):
                    job_data = raw_job_data
                else:
                    try:
                        job_data = json.loads(raw_job_data) if raw_job_data is not None else {}
                    except Exception:
                        job_data = {}

                if job_data and 'flipkart_user_id' in job_data:
                    flipkart_user_id = job_data['flipkart_user_id']

                    # Extract only essential cookies if we have all cookies
                    if len(cookies) > 2:
                        essential_cookies = self.extract_essential_cookies(cookies)
                        if self.validate_essential_cookies(essential_cookies):
                            cookies = essential_cookies
                            logging.info(f"Extracted {len(essential_cookies)} essential cookies (at, rt) from {len(cookies)} total cookies")

                    # Save cookies as JSON
                    await conn.execute(
                        "UPDATE flipkart_users SET cookies = $1, last_login = NOW() WHERE id = $2",
                        json.dumps(cookies), flipkart_user_id
                    )

                    cookie_names = [cookie['name'] for cookie in cookies]
                    logging.info(f"Saved {len(cookies)} cookies ({', '.join(cookie_names)}) for isolated session job {job_id}")
        except Exception as e:
            logging.error(f"Failed to save cookies to database: {e}")

    def extract_essential_cookies(self, all_cookies: list) -> list:
        """Extract only the essential 'at' and 'rt' cookies from all cookies"""
        essential_cookies = []
        
        for cookie in all_cookies:
            if cookie['name'] in ['at', 'rt']:
                essential_cookies.append(cookie)
        
        return essential_cookies
    
    def validate_essential_cookies(self, cookies: list) -> bool:
        """Check if cookies contain both 'at' and 'rt' tokens"""
        if not cookies:
            return False
            
        cookie_names = [cookie['name'] for cookie in cookies]
        return 'at' in cookie_names and 'rt' in cookie_names

    async def capture_failure_screenshot(self, job_id: int, reason: str = "failure") -> Optional[str]:
        """
        Capture a screenshot when a job fails.
        Returns the screenshot path if successful, None otherwise.
        """
        try:
            # Get context info dict from active_contexts
            context_info = self.active_contexts.get(job_id)
            if not context_info:
                return None
            
            # Extract the actual context object from the dict
            context = context_info.get('context')
            if not context:
                return None
            
            # Get the first page from the context
            pages = context.pages
            if not pages or len(pages) == 0:
                return None
            
            page = pages[0]
            if page.is_closed():
                return None
            
            # Create screenshot with descriptive name (use JPEG + reduced quality by default)
            screenshot_path = os.path.join(tempfile.gettempdir(), f"flipkart_mobile_login_fail_{job_id}_{reason}.jpg")
            await page.screenshot(
                path=screenshot_path,
                full_page=self.screenshot_full_page,
                type=self.screenshot_type,
                quality=self.screenshot_quality,
            )
            await job_queue.log_job(job_id, LogLevel.INFO, f"📸 Failure screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            # Silently fail - don't let screenshot errors break the automation
            try:
                await job_queue.log_job(job_id, LogLevel.DEBUG, f"Failed to capture screenshot: {str(e)}")
            except Exception:
                pass
            return None

    async def _get_chrome_version_for_ua(self) -> str:
        """Return the Chromium version string to embed in User-Agent (e.g., '120.0.6099.109')."""
        try:
            ver = self.browser.version
            # ver looks like 'HeadlessChrome/120.0.6099.109' or 'Chrome/120.0.6099.109'
            if '/' in ver:
                return ver.split('/')[-1]
            return ver
        except Exception:
            # Fallback to a reasonable recent version
            return '120.0.6099.109'

    async def _apply_stealth_evasions(self, context, view_mode: str = 'desktop'):
        """Inject JS to reduce automation fingerprints across all pages in the context."""
        try:
            stealth_js = r"""
            // --- navigator.webdriver ---
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // --- window.chrome stub ---
            if (!window.chrome) {
              window.chrome = { runtime: {} };
            }

            // --- plugins and languages ---
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });

            // --- hardwareConcurrency & platform ---
            try {
              Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
            } catch (e) {}
            try {
              Object.defineProperty(navigator, 'platform', { get: () => 'Linux x86_64' });
            } catch (e) {}

            // --- maxTouchPoints (desktop 0, mobile > 0) ---
            try {
              const isMobileUA = /Mobile/.test(navigator.userAgent);
              Object.defineProperty(navigator, 'maxTouchPoints', { get: () => isMobileUA ? 5 : 0 });
            } catch (e) {}

            // --- Permissions API (notifications) ---
            try {
              const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
              if (originalQuery) {
                window.navigator.permissions.query = (parameters) => (
                  parameters && parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
                );
              }
            } catch (e) {}

            // --- Canvas noise ---
            try {
              const toDataURL = HTMLCanvasElement.prototype.toDataURL;
              HTMLCanvasElement.prototype.toDataURL = function(...args) {
                const ctx = this.getContext('2d');
                if (ctx) {
                  ctx.save();
                  ctx.fillStyle = 'rgba(0,0,0,0.01)';
                  ctx.fillRect(0, 0, 1, 1);
                  ctx.restore();
                }
                return toDataURL.apply(this, args);
              };
            } catch (e) {}
            """

            await context.add_init_script(stealth_js)
        except Exception as e:
            logging.warning(f"Failed to apply stealth evasions: {e}")
