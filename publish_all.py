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
    """Use Gumroad API to fetch draft product IDs."""
    if not GUMROAD_TOKEN:
        return []
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    resp = requests.get("https://api.gumroad.com/v2/products", headers=headers)
    if resp.status_code == 200:
        products = resp.json()["products"]
        return [p["id"] for p in products if not p["published"]]
    return []

def publish_single_product(page, product_id):
    """Open a product edit page, click Content tab, then click Publish."""
    edit_url = f"https://app.gumroad.com/products/{product_id}/edit"
    page.goto(edit_url, wait_until="networkidle")
    page.wait_for_timeout(3000)

    # 1. Click the "Content" tab
    content_selectors = [
        "button:has-text('Content')",
        "a:has-text('Content')",
        "[role='tab']:has-text('Content')",
        "text=Content",
        "[aria-label='Content']",
        ".tab-content",
        "#tab-content",
    ]
    content_clicked = False
    for sel in content_selectors:
        try:
            page.click(sel, timeout=5000)
            content_clicked = True
            logging.info("Clicked Content tab.")
            break
        except:
            continue

    if not content_clicked:
        logging.warning(f"Could not click Content tab for {product_id}. Trying direct Publish anyway...")

    page.wait_for_timeout(2000)

    # 2. Click the "Publish" button (usually green)
    publish_selectors = [
        "button:has-text('Publish')",
        "a:has-text('Publish')",
        "[role='button']:has-text('Publish')",
        "text=Publish",
        "text=Publish now",
        "text=Go live",
        "[aria-label='Publish']",
        "[data-testid='publish-button']",
        ".publish-button",
        "#publish-button",
    ]
    for sel in publish_selectors:
        try:
            page.click(sel, timeout=5000)
            logging.info(f"Published product {product_id} via selector: {sel}")
            return True
        except:
            continue

    # JavaScript fallback: click any element containing 'publish'
    try:
        page.evaluate("""() => {
            const elements = document.querySelectorAll('button, a, [role="button"]');
            for (const el of elements) {
                if (el.innerText.toLowerCase().includes('publish')) {
                    el.click();
                    return true;
                }
            }
            return false;
        }""")
        logging.info(f"Published product {product_id} via JavaScript fallback.")
        return True
    except:
        pass

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

        # --- Try bulk publish first ---
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
                for pub_sel in ["text=Publish all", "text=Publish all products"]:
                    try:
                        page.click(pub_sel, timeout=5000)
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
            logging.info("All drafts published via bulk action.")
            browser.close()
            return

        # --- Fallback: publish one by one ---
        logging.info("Bulk publish not available. Publishing individually...")
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
            if publish_single_product(page, pid):
                success += 1
                time.sleep(2)
            else:
                logging.warning(f"Failed to publish {pid}")

        logging.info(f"Publishing complete. Success: {success}/{len(product_ids)}")
        browser.close()

if __name__ == "__main__":
    run()
