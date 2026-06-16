import os, sys, json, logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def run():
    cookies_raw = os.environ["GUMROAD_COOKIES"]
    cookies = json.loads(cookies_raw)

    allowed_same_site = {'Strict', 'Lax', 'None'}
    for c in cookies:
        if 'sameSite' not in c or c['sameSite'] not in allowed_same_site:
            c['sameSite'] = 'Lax'
        c.setdefault('domain', '')
        c.setdefault('path', '/')
        c.setdefault('httpOnly', False)
        c.setdefault('secure', False)
        for field in ['hostOnly', 'session', 'storeId']:
            c.pop(field, None)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(5000)  # let the table fully render

        # Save a screenshot BEFORE any click so we can inspect the page
        page.screenshot(path="before_click.png")
        logging.info("Screenshot saved as before_click.png. Check artifact.")

        # Try multiple possible selectors for the "select all" checkbox
        selectors = [
            "input[type='checkbox']",
            "thead input",
            "table input[type='checkbox']",
            "div[role='row'] input[type='checkbox']",
            "#products-list thead input[type='checkbox']"
        ]

        clicked = False
        for sel in selectors:
            try:
                page.click(sel, timeout=5000)
                logging.info(f"Successfully clicked: {sel}")
                clicked = True
                break
            except:
                logging.warning(f"Could not click: {sel}")

        if not clicked:
            logging.error("Could not find any checkbox. Uploading screenshot for inspection.")
            browser.close()
            sys.exit(1)

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
