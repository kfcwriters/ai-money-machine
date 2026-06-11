import os, sys, logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

EMAIL = os.environ["GUMROAD_EMAIL"]
PASSWORD = os.environ["GUMROAD_PASSWORD"]

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Login
        page.goto("https://app.gumroad.com/login")
        page.fill('input[name="email"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url("https://app.gumroad.com/dashboard")
        logging.info("Logged in.")

        # 2. Go to Products page
        page.goto("https://app.gumroad.com/products")
        page.wait_for_selector("table", timeout=10000)

        # 3. Click the top checkbox to select all
        # The checkbox in the header row
        page.click("thead input[type='checkbox']")
        logging.info("All products selected.")

        # 4. Click Edit dropdown → Publish all
        page.click("button:has-text('Edit')")
        page.click("text=Publish all")
        logging.info("Publish all triggered.")

        # 5. Wait a moment and take a screenshot for verification
        page.wait_for_timeout(3000)
        page.screenshot(path="gumroad_after_publish.png")
        logging.info("Screenshot saved. All products should be published.")

        browser.close()

if __name__ == "__main__":
    run()
