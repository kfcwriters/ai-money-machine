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

        # 1. Go to products list
        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(5000)

        # 2. Find the edit link for the first product (any link with "/edit" in href)
        edit_link = page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/edit"]');
            for (const link of links) {
                const href = link.getAttribute('href');
                if (href && href.includes('/products/') && href.includes('/edit')) {
                    return href;
                }
            }
            return null;
        }""")

        if not edit_link:
            # Try getting any product link and append /edit
            product_link = page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/products/"]');
                for (const link of links) {
                    const href = link.getAttribute('href');
                    if (href && !href.includes('/l/') && !href.includes('/edit')) {
                        return href;
                    }
                }
                return null;
            }""")
            if product_link:
                edit_link = product_link.rstrip('/') + '/edit'
            else:
                logging.error("No product links found on products page.")
                page.screenshot(path="products_page.png")
                browser.close()
                return

        logging.info(f"Found edit link: {edit_link}")

        # 3. Navigate to the edit page
        full_url = f"https://app.gumroad.com{edit_link}" if edit_link.startswith('/') else edit_link
        page.goto(full_url, wait_until="networkidle")
        page.wait_for_timeout(5000)

        # 4. Log all clickable elements
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

        # 5. Log page title and main heading
        title = page.title()
        h1 = page.inner_text('h1').strip() if page.locator('h1').count() > 0 else ''
        logging.info(f"Page title: {title}")
        logging.info(f"Main heading: {h1}")

        browser.close()

if __name__ == "__main__":
    run()
