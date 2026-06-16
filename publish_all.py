import os, sys, json, logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

ALLOWED_SAMESITE = {'Strict', 'Lax', 'None'}

def sanitize_cookies(cookies):
    for c in cookies:
        # Ensure sameSite is valid
        if 'sameSite' not in c or c['sameSite'] not in ALLOWED_SAMESITE:
            c['sameSite'] = 'Lax'
        # Set required defaults if missing
        c.setdefault('domain', '.gumroad.com')
        c.setdefault('path', '/')
        c.setdefault('httpOnly', False)
        c.setdefault('secure', True)
        # Remove fields that Playwright may reject
        for field in ['hostOnly', 'session', 'storeId']:
            c.pop(field, None)
    return cookies

def run():
    cookies_raw = os.environ["GUMROAD_COOKIES"]
    cookies = json.loads(cookies_raw)
    cookies = sanitize_cookies(cookies)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(5000)

        # Select all checkboxes via JavaScript
        page.evaluate("""() => {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        logging.info("All checkboxes selected via JavaScript.")

        # Click "Edit" dropdown → "Publish all"
        page.click("button:has-text('Edit')")
        page.click("text=Publish all")
        logging.info("'Publish all' clicked. Waiting...")
        page.wait_for_timeout(5000)

        page.screenshot(path="publish_after.png")
        logging.info("Screenshot saved. All drafts should now be published.")
        browser.close()

if __name__ == "__main__":
    run()
