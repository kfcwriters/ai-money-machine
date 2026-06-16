import os, sys, json, logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def run():
    cookies = json.loads(os.environ["GUMROAD_COOKIES"])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # Inject the logged‑in session
        context.add_cookies(cookies)

        page = context.new_page()
        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Select all products
        page.click("thead input[type='checkbox']")
        logging.info("All products selected.")

        # Click "Edit" → "Publish all"
        page.click("button:has-text('Edit')")
        page.click("text=Publish all")
        logging.info("'Publish all' clicked. Waiting...")
        page.wait_for_timeout(5000)

        page.screenshot(path="publish_after.png")
        logging.info("Screenshot saved. All drafts should be published.")

        browser.close()

if __name__ == "__main__":
    run()
