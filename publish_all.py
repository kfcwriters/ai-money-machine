import os, sys, json, logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

ALLOWED_SAMESITE = {'Strict', 'Lax', 'None'}

def sanitize_cookies(cookies):
    for c in cookies:
        if 'sameSite' not in c or c['sameSite'] not in ALLOWED_SAMESITE:
            c['sameSite'] = 'Lax'
        c.setdefault('domain', '.gumroad.com')
        c.setdefault('path', '/')
        c.setdefault('httpOnly', False)
        c.setdefault('secure', True)
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

        # Take a screenshot to see what buttons are visible
        page.screenshot(path="after_checkboxes.png")
        logging.info("Screenshot saved as after_checkboxes.png (download artifact).")

        # Try multiple selectors for the bulk-action button
        edit_selectors = [
            "button:has-text('Edit')",
            "button:has-text('Actions')",
            "button:has-text('Bulk edit')",
            "[data-testid='bulk-edit-button']",
            "[aria-label='Edit selected']",
            "text=Edit",
        ]

        clicked = False
        for sel in edit_selectors:
            try:
                page.click(sel, timeout=5000)
                logging.info(f"Clicked bulk-action button: {sel}")
                clicked = True
                break
            except:
                continue

        if not clicked:
            logging.error("Could not find the bulk-action button. Check after_checkboxes.png")
            browser.close()
            sys.exit(1)

        # Click "Publish all" (may need to wait for the dropdown)
        page.wait_for_timeout(2000)
        publish_selectors = [
            "text=Publish all",
            "text=Publish all products",
            "text=Publish selected",
            "[data-testid='publish-all']",
        ]
        for sel in publish_selectors:
            try:
                page.click(sel, timeout=5000)
                logging.info(f"Clicked publish option: {sel}")
                break
            except:
                continue

        page.wait_for_timeout(5000)
        page.screenshot(path="publish_after.png")
        logging.info("Final screenshot saved. All drafts should now be published.")
        browser.close()

if __name__ == "__main__":
    run()
