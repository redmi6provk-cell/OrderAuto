import asyncio
from typing import Dict, Any
from services.job_queue import job_queue, LogLevel

async def fill_address_form(page, address_data: Dict[str, Any], job_id: int, save_button: bool = True) -> bool:
    """
    Fills out the 'Add a New Address' form on Flipkart.
    
    Args:
        page: Playwright page object
        address_data: Dictionary containing address data
        job_id: Job ID for logging
        save_button: Whether to click save button and validate (default: True)
    
    Returns:
        bool: True if form filled and saved successfully (or just filled if save_button=False), False otherwise
    """
    try:
        await job_queue.log_job(job_id, LogLevel.INFO, "Filling the new address form...")

        # --- Fill Text Fields ---
        field_map = {
            "name": ('input[name="name"]', "Name"),
            "phone": ('input[name="phone"]', "10-digit mobile number"),
            "pincode": ('input[name="pincode"]', "400010"),
            "locality": ('input[name="addressLine2"]', "Locality"),
            "address": ('textarea[name="addressLine1"]', "metha chamber, Dana Bunder, Masjid Bandar East,"),
            "landmark": ('input[name="landmark"]', "Landmark (Optional)"),
            "alternatePhone": ('input[name="alternatePhone"]', "Alternate Phone (Optional)"),
        }

        for key, (selector, description) in field_map.items():
            if address_data.get(key):
                await page.fill(selector, str(address_data[key]))
                await job_queue.log_job(job_id, LogLevel.INFO, f"Filled {description}: {address_data[key]}")
                if key == "pincode":
                    # Wait for city/state to auto-populate
                    await asyncio.sleep(0.8)

        # --- Select Address Type (Radio Button) ---
        address_type = address_data.get("addressType", "HOME").upper()
        if address_type in ["HOME", "WORK"]:
            # Use the label selector which is more robust for radio buttons
            await page.locator(f'label[for="{address_type}"]').click()
            await job_queue.log_job(job_id, LogLevel.INFO, f"Selected address type: {address_type}")
        else:
            await job_queue.log_job(job_id, LogLevel.WARNING, f"Invalid address type '{address_type}', defaulting to HOME.")
            await page.locator('label[for="HOME"]').click()

        await job_queue.log_job(job_id, LogLevel.INFO, "Address form filled successfully.")
        
        # If save_button is False, just return True after filling
        if not save_button:
            return True
        
        # --- Click Save Button and Validate ---
        save_selectors = [
            'button:has-text("Save")',
            'input[type="submit"][value="Save Address"]',
            'button[type="submit"]:has-text("Save")'
        ]
        
        save_clicked = False
        for selector in save_selectors:
            try:
                save_btn = page.locator(selector)
                if await save_btn.count() > 0:
                    await job_queue.log_job(job_id, LogLevel.INFO, f"Clicking Save button using selector: {selector}")
                    try:
                        await save_btn.first.wait_for(state='visible', timeout=2000)
                    except Exception:
                        pass
                    await save_btn.click()
                    save_clicked = True
                    break
            except Exception:
                continue
        
        if not save_clicked:
            await job_queue.log_job(job_id, LogLevel.ERROR, "Could not find Save button")
            return False
        
        # Wait briefly for submission and prefer a fast success signal
        await asyncio.sleep(0.6)
        try:
            # Form should detach/hidden on success
            await page.wait_for_selector('#addressform', state='detached', timeout=3500)
        except Exception:
            pass
        
        # --- Validate if address was saved successfully ---
        error_messages = []
        
        # Check for error messages on the page
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
        
        # If there are validation errors, report them
        if error_messages:
            await job_queue.log_job(job_id, LogLevel.ERROR, f"❌ Address validation failed with errors:")
            for error in error_messages:
                await job_queue.log_job(job_id, LogLevel.ERROR, f"   - {error}")
            return False
        
        # Check if we're redirected to addresses page (success)
        current_url = page.url
        if "account/addresses" in current_url and "addaddress" not in current_url.lower():
            await job_queue.log_job(job_id, LogLevel.INFO, "✅ Address saved successfully - redirected to addresses page")
            return True
        
        # Check if form is still visible (potential failure)
        try:
            form_still_visible = await page.locator('#addressform').is_visible(timeout=2000)
            if form_still_visible or 'addaddress' in current_url.lower():
                await job_queue.log_job(job_id, LogLevel.ERROR, "❌ Address save may have failed - still on add address page")
                # Try to capture any errors in page content
                try:
                    page_content = await page.content()
                    if 'please provide' in page_content.lower() or 'required' in page_content.lower() or 'unavailable' in page_content.lower():
                        await job_queue.log_job(job_id, LogLevel.ERROR, "Validation errors detected in page content")
                except Exception:
                    pass
                return False
        except Exception:
            # Form not visible, probably success
            pass
        
        # If we reach here, assume success (form not visible, no errors)
        await job_queue.log_job(job_id, LogLevel.INFO, "✅ Address appears to be saved successfully")
        return True

    except Exception as e:
        await job_queue.log_job(job_id, LogLevel.ERROR, f"An error occurred while filling the address form: {str(e)}")
        return False
