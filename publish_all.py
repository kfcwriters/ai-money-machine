import os, sys, json, logging, requests, time
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

ALLOWED_SAMESITE = {'Strict', 'Lax', 'None'}
GUMROAD_TOKEN = os.environ.get("GUMROAD_TOKEN", "")

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

def get_unpublished_product_ids():
    if not GUMROAD_TOKEN:
        return []
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    resp = requests.get("https://api.gumroad.com/v2/products", headers=headers)
    if resp.status_code == 200:
        products = resp.json()["products"]
        return [p["id"] for p in products if not p["published"]]
    return []

def click_text(page, text):
    """Use JavaScript to click the first element containing exactly the given text."""
    result = page.evaluate(f"""(text) => {{
        const elements = document.querySelectorAll('button, a, [role="tab"], span, div');
        for (const el of elements) {{
            if (el.innerText.trim() === text) {{
                el.click();
                return 'clicked';
            }}
        }}
        return 'not found';
    }}""", text)
    return result

def run():
    cookies_raw = os.environ["GUMROAD_COOKIES"]
    cookies = json.loads(cookies_raw)
    cookies = sanitize_cookies(cookies)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        # ====== Bulk publish attempt (unchanged) ======
        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(5000)
        page.evaluate("""() => {
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        logging.info("Checkboxes selected. Trying bulk Edit...")
        bulk_published = False
        for edit_sel in ["button:has-text('Edit')", "button:has-text('Actions')"]:
            try:
                page.click(edit_sel, timeout=5000)
                page.wait_for_timeout(2000)
                res = page.evaluate("""() => {
                    const elems = document.querySelectorAll('button, a, [role="menuitem"]');
                    for (const el of elems) {
                        if (el.innerText.includes('Publish all')) {
                            el.click();
                            return 'clicked';
                        }
                    }
                    return 'not found';
                }""")
                if res == 'clicked':
                    bulk_published = True
                    logging.info("Bulk publish succeeded!")
                    break
            except:
                continue

        if bulk_published:
            page.wait_for_timeout(5000)
            logging.info("All drafts published via bulk action.")
            browser.close()
            return

        # ====== Individual publish ======
        logging.info("Bulk publish unavailable. Publishing individually...")
        product_ids = get_unpublished_product_ids()
        if not product_ids:
            # Scrape product links from the page
            product_links = page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/products/"]');
                return [...new Set(links.map(a => a.href))];
            }""")
            product_ids = [url.split("/")[-1] for url in product_links if url.split("/")[-1].isalnum()]

        if not product_ids:
            logging.error("No product IDs found.")
            page.screenshot(path="products_page.png")
            browser.close()
            return

        logging.info(f"Found {len(product_ids)} products. Publishing each...")
        success = 0
        for pid in product_ids:
            edit_url = f"https://app.gumroad.com/products/{pid}/edit"
            page.goto(edit_url, wait_until="networkidle")
            page.wait_for_timeout(6000)   # extra time for dynamic content

            # 1. Click "Content" tab
            content_result = click_text(page, "Content")
            logging.info(f"Content click: {content_result}")
            page.wait_for_timeout(3000)

            # 2. Click "Publish" button (may have appeared after clicking Content)
            publish_result = click_text(page, "Publish")
            logging.info(f"Publish click: {publish_result}")
            if publish_result == 'clicked':
                success += 1
                time.sleep(2)
            else:
                # Try "Publish now" or other variations
                for alt_text in ["Publish now", "Go live"]:
                    if click_text(page, alt_text) == 'clicked':
                        success += 1
                        logging.info(f"Clicked '{alt_text}' for {pid}")
                        time.sleep(2)
                        break
                else:
                    logging.warning(f"Could not publish {pid}")

        logging.info(f"Publishing complete. Success: {success}/{len(product_ids)}")
        browser.close()

if __name__ == "__main__":
    run()
