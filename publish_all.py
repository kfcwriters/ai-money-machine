import os, sys, json, logging, requests, time
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

ALLOWED_SAMESITE = {'Strict', 'Lax', 'None'}
GUMROAD_TOKEN = os.environ.get("GUMROAD_TOKEN", "")   # optional, for listing products

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
    """Use the Gumroad API to get all unpublished product IDs (optional but faster)."""
    if not GUMROAD_TOKEN:
        return []
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    resp = requests.get("https://api.gumroad.com/v2/products", headers=headers)
    if resp.status_code == 200:
        products = resp.json()["products"]
        return [p["id"] for p in products if not p["published"]]
    return []

def publish_via_edit_page(page, product_id):
    """Open a single product's edit page and click the Publish button."""
    edit_url = f"https://app.gumroad.com/products/{product_id}/edit"
    page.goto(edit_url, wait_until="networkidle")
    page.wait_for_timeout(3000)
    # Click the green "Publish" button (usually at the top)
    try:
        page.click("button:has-text('Publish')", timeout=10000)
        logging.info(f"Product {product_id} published.")
        time.sleep(2)
        return True
    except:
        # Maybe it's already published, or button not found
        logging.warning(f"Could not click Publish for {product_id}.")
        return False

def run():
    cookies_raw = os.environ["GUMROAD_COOKIES"]
    cookies = json.loads(cookies_raw)
    cookies = sanitize_cookies(cookies)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        # -------- Try bulk publish first (if it works) ---------
        page.goto("https://app.gumroad.com/products", wait_until="networkidle")
        page.wait_for_timeout(5000)

        # Select all checkboxes
        page.evaluate("""() => {
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        logging.info("Checkboxes selected. Trying bulk Edit...")

        # Try multiple selectors for the bulk edit button
        edit_selectors = [
            "button:has-text('Edit')",
            "button:has-text('Actions')",
            "button:has-text('Bulk edit')",
            "[aria-label='Edit']",
        ]
        bulk_published = False
        for sel in edit_selectors:
            try:
                page.click(sel, timeout=5000)
                page.wait_for_timeout(2000)
                # Now try to click "Publish all" or similar
                publish_selectors = [
                    "text=Publish all",
                    "text=Publish all products",
                    "text=Publish selected",
                ]
                for psel in publish_selectors:
                    try:
                        page.click(psel, timeout=5000)
                        logging.info("Bulk publish succeeded!")
                        bulk_published = True
                        break
                    except:
                        continue
                if bulk_published:
                    break
            except:
                continue

        if bulk_published:
            page.wait_for_timeout(5000)
            page.screenshot(path="publish_after.png")
            logging.info("All drafts published via bulk action.")
            browser.close()
            return

        # -------- Fallback: Publish one by one ---------
        logging.info("Bulk publish not available. Switching to individual publish...")
        product_ids = get_unpublished_product_ids()
        if not product_ids:
            # If API token not set, we can scrape product links from the products page
            logging.warning("No GUMROAD_TOKEN – trying to scrape product links from page.")
            product_links = page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/products/"]');
                return [...new Set(links.map(a => a.href))];
            }""")
            product_ids = [url.split("/")[-1] for url in product_links if url.split("/")[-1].isalnum()]

        if not product_ids:
            logging.error("No product IDs found. Take a screenshot of the products page to debug.")
            page.screenshot(path="products_page.png")
            browser.close()
            sys.exit(1)

        logging.info(f"Found {len(product_ids)} products. Publishing each...")
        for pid in product_ids:
            publish_via_edit_page(page, pid)

        page.screenshot(path="publish_after.png")
        logging.info("Individual publishing finished.")
        browser.close()

if __name__ == "__main__":
    run()
