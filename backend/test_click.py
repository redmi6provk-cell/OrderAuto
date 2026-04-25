import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()
        page.set_default_timeout(15000)
        
        print("Navigating to Flipkart GROCERY product...")
        # Using the product the user was just trying
        url = "https://www.flipkart.com/fortune-sunlite-refined-sunflower-oil-can/p/itm90bc3b5c7f004?pid=EDOET83F38NQEFYF&lid=LSTEDOET83F38NQEFYFZTAGHC&marketplace=GROCERY"
        await page.goto(url, timeout=60000)
        
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(3)
        
        print("Setting Pincode 400050...")
        try:
            # Look for pincode/delivery area
            pincode_trigger = page.locator('div:has-text("Deliver to"), div:has-text("Select Pincode"), div:has-text("Enter Pincode")').last
            if await pincode_trigger.count() > 0:
                print("Clicking pincode trigger...")
                await pincode_trigger.click()
                await asyncio.sleep(2)
                
                # Look for input
                pin_input = page.locator('input[placeholder*="pincode"], input[type="tel"], input[type="text"]').last
                if await pin_input.count() > 0:
                    print("Entering 400050...")
                    await pin_input.fill("400050")
                    await asyncio.sleep(1)
                    # Click Apply/Submit
                    apply_btn = page.locator('div:text-is("Apply"), div:text-is("Submit"), div:text-is("Save")').last
                    await apply_btn.click()
                    print("Pincode applied.")
                    await asyncio.sleep(3)
        except Exception as e:
            print(f"Pincode setting error: {e}")

        # Now try to Add to Cart
        print("Locating Add button...")
        # Based on subagent HTML: div.r-1w0ad5y contains "Add"
        add_btn = page.locator('div.css-g5y9jx:has-text("Add")').filter(has_text="Add").last
        
        if await add_btn.count() > 0:
            print(f"Found Add button. Inner text: {await add_btn.inner_text()}")
            await add_btn.scroll_into_view_if_needed()
            await asyncio.sleep(1)
            
            # Record current state
            print("Tapping Add button...")
            await add_btn.tap()
            
            print("Waiting 5 seconds for update...")
            await asyncio.sleep(5)
            
            # Check if "+" shows up
            plus_btn = page.locator('div:text-is("+")')
            if await plus_btn.count() > 0:
                print("SUCCESS: Plus button appeared!")
            else:
                print("FAILED: No plus button.")
                # Maybe a popup?
                popups = await page.locator('div:has-text("Basket")').count()
                print(f"Remaining 'Add' text count: {await page.locator('text=\"Add\"').count()}")
                
            await page.screenshot(path="test_result.png", full_page=True)
            print("Saved full page screenshot to test_result.png")
        else:
            print("Add button NOT found.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
