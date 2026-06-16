import os, sys, json, logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def run():
    cookies_raw = os.environ["GUMROAD_COOKIES"]
    cookies = json.loads(cookies_raw)

    # sanitize cookies
    for c in cookies:
        c.setdefault('sameSite', 'Lax')
        c.setdefault('domain', '')
        c.setdefault('path', '/')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(5000)

        # ===== 1. Use JavaScript to select all checkboxes =====
        page.evaluate("""() => {
            // Select all checkboxes in the products table
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        logging.info("JavaScript: all checkboxes selected.")

        # ===== 2. Now click the "Edit" button that appears =====
        # The Edit button shows up when items are selected
        try:
            page.click("button:has-text('Edit')", timeout=5000)
        except:
            # maybe the button has a different text
            page.click("text=Edit", timeout=5000)
        logging.info("Clicked 'Edit'.")

        # ===== 3. Click "Publish all" =====
        page.click("text=Publish all", timeout=5000)
        logging.info("Clicked 'Publish all'. Waiting...")
        page.wait_for_timeout(5000)

        page.screenshot(path="publish_after.png")
        logging.info("Screenshot saved. All drafts should now be published.")
        browser.close()

if __name__ == "__main__":
    run()
