import asyncio
from playwright.async_api import async_playwright
import os

OUT_DIR = r"C:\Users\LJPS\.gemini\antigravity-ide\brain\fc29dcc2-6037-416a-959e-b536d80b193c"
USERNAME = "user_41c5ed4e"
PASSWORD = "password123"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Desktop Context
        context_desktop = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context_desktop.new_page()
        
        await page.goto("http://localhost:5173")
        await page.wait_for_selector("text=Sign in to your account")
        
        # Register Screenshots
        await page.click("text=Register")
        await page.wait_for_selector("text=Create a new account")
        await page.screenshot(path=os.path.join(OUT_DIR, "register_1280.png"))
        
        # Mobile Context for Register
        context_mobile = await browser.new_context(viewport={'width': 390, 'height': 844})
        page_mobile = await context_mobile.new_page()
        await page_mobile.goto("http://localhost:5173")
        await page_mobile.click("text=Register")
        await page_mobile.wait_for_selector("text=Create a new account")
        await page_mobile.screenshot(path=os.path.join(OUT_DIR, "register_390.png"))
        await context_mobile.close()
        
        # Back to Login
        await page.click("text=Sign in")
        await page.fill("input#username", USERNAME)
        await page.fill("input#password", PASSWORD)
        await page.click("button[type='submit']")
        
        # Dashboard
        await page.wait_for_selector("text=Your Files")
        
        # Verify Files
        verify_buttons = await page.locator("button[title='Verify integrity']").all()
        for btn in verify_buttons:
            await btn.click()
            await page.wait_for_selector("text=Verification Report")
            await page.click("text=Verification Report >> xpath=../button") # Close modal
        
        # Wait for badge to appear
        await page.wait_for_selector("text=Tampered / Alert")
        
        # Dashboard Screenshots
        await page.screenshot(path=os.path.join(OUT_DIR, "dashboard_real_1280.png"))
        
        # Mobile context logic is a bit tricky with login state. We can just resize the desktop page.
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_timeout(500)
        await page.screenshot(path=os.path.join(OUT_DIR, "dashboard_real_390.png"))
        
        # Access History Screenshots
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.click("text=Access History")
        await page.wait_for_selector("text=Audit Trail")
        await page.screenshot(path=os.path.join(OUT_DIR, "history_real_1280.png"))
        
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_timeout(500)
        await page.screenshot(path=os.path.join(OUT_DIR, "history_real_390.png"))
        
        # Security Alerts Screenshots
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.click("text=Security Alerts")
        await page.wait_for_selector("text=Monitoring")
        await page.screenshot(path=os.path.join(OUT_DIR, "alerts_real_1280.png"))
        
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_timeout(500)
        await page.screenshot(path=os.path.join(OUT_DIR, "alerts_real_390.png"))
        
        # Test Upload, Download, Delete, Logout
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.click("text=Dashboard")
        await page.wait_for_selector("text=Your Files")
        
        # Upload
        with open("test_upload.txt", "w") as f:
            f.write("Hello world")
        async with page.expect_file_chooser() as fc_info:
            await page.click("input[type='file']", force=True)
        file_chooser = await fc_info.value
        await file_chooser.set_files("test_upload.txt")
        await page.wait_for_selector("text=test_upload.txt")
        
        # Download
        async with page.expect_download() as download_info:
            # Click first download button
            await page.locator("button[title='Download']").first.click()
        download = await download_info.value
        await download.path() # Wait for download
        
        # Delete
        page.on("dialog", lambda dialog: dialog.accept())
        await page.locator("button[title='Delete']").first.click()
        await page.wait_for_timeout(1000)
        
        # Logout
        await page.click("button[title='Sign out']")
        await page.wait_for_selector("text=Sign in to your account")
        
        print("All E2E checks passed and screenshots captured.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
