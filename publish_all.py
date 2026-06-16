import os, sys, json, logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def run():
    cookies_raw = os.environ["GUMROAD_COOKIES"]
    cookies = json.loads(cookies_raw)

    # Sanitize cookies for Playwright
    allowed_same_site = {'Strict', 'Lax', 'None'}
    for c in cookies:
        # Set a valid sameSite if missing or invalid
        if 'sameSite' not in c or c['sameSite'] not in allowed_same_site:
            c['sameSite'] = 'Lax'
        # Ensure required defaults
        c.setdefault('domain', '')
        c.setdefault('path', '/')
        c.setdefault('httpOnly', False)
        c.setdefault('secure', False)
        # Remove fields that Playwright doesn't need
        for field in ['hostOnly', 'session', 'storeId']:
            c.pop(field, None)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Select all products
        page.click("thead input[type='checkbox']")
        logging.info("All products selected.")

        # Click "Edit" dropdown → "Publish all"
        page.click("button:has-text('Edit')")
        page.click("text=Publish all")
        logging.info("'Publish all' clicked. Waiting...")
        page.wait_for_timeout(5000)

        page.screenshot(path="publish_after.png")
        logging.info("Screenshot saved. All drafts should be published.")
        browser.close()

if __name__ == "__main__":
    run()
