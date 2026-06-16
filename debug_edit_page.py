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

        # Go to the products page and get one unpublished product ID
        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(5000)

        # Get first product link
        product_id = page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/products/"]');
            for (const link of links) {
                const href = link.getAttribute('href');
                const match = href.match(/\\/products\\/([a-zA-Z0-9_-]+)/);
                if (match) return match[1];
            }
            return null;
        }""")

        if not product_id:
            logging.error("Could not find any product ID on the products page.")
            browser.close()
            return

        logging.info(f"Using product ID: {product_id}")

        # Open the edit page
        edit_url = f"https://app.gumroad.com/products/{product_id}/edit"
        page.goto(edit_url, wait_until="networkidle")
        page.wait_for_timeout(5000)

        # Log ALL text from buttons and clickable elements
        all_clickable = page.evaluate("""() => {
            const elems = document.querySelectorAll('button, a, [role="button"], [role="menuitem"], input[type="submit"], input[type="button"]');
            const result = [];
            elems.forEach(el => {
                const tag = el.tagName.toLowerCase();
                const text = el.innerText.trim().replace(/\\s+/g, ' ').substring(0, 100);
                const id = el.id || '';
                const cls = el.className || '';
                const type = el.getAttribute('type') || '';
                result.push({tag, text, id, cls, type});
            });
            return result;
        }""")

        logging.info("=== All clickable elements on edit page ===")
        for i, el in enumerate(all_clickable):
            logging.info(f"{i+1}. <{el['tag']}> text='{el['text']}' id='{el['id']}' class='{el['cls']}' type='{el['type']}'")

        # Also log the full page text (first 2000 chars) to see context
        full_text = page.inner_text('body')
        logging.info("=== Page body text (first 2000 chars) ===")
        logging.info(full_text[:2000])

        browser.close()

if __name__ == "__main__":
    run()
