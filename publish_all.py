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
        # Wait for dashboard to load
        page.wait_for_url("https://app.gumroad.com/dashboard")
        logging.info("Logged in successfully.")

        # 2. Go to Products page
        page.goto("https://app.gumroad.com/products")
        # Wait for the products table to appear
        page.wait_for_selector("table", timeout=15000)

        # 3. Select all products (the checkbox in the table header)
        # The header checkbox has a specific aria-label or can be selected by its position
        page.click("thead input[type='checkbox']")
        logging.info("All products selected.")

        # 4. Click the "Edit" dropdown button (it appears above the table when items are selected)
        page.click("button:has-text('Edit')")
        # 5. Click "Publish all" in the dropdown menu
        page.click("text=Publish all")
        logging.info("'Publish all' clicked.")

        # Wait a moment for the action to complete
        page.wait_for_timeout(5000)

        # Optional: take a screenshot for verification
        page.screenshot(path="publish_after.png")
        logging.info("Screenshot saved. All products should now be published.")

        browser.close()

if __name__ == "__main__":
    run()
