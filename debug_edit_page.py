import os, sys, json, logging, requests
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

ALLOWED_SAMESITE = {'Strict', 'Lax', 'None'}
GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]   # required

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
    # 1. Get the first unpublished product ID via API
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    resp = requests.get("https://api.gumroad.com/v2/products", headers=headers)
    if resp.status_code != 200:
        logging.error("Failed to fetch products via API.")
        return
    products = resp.json()["products"]
    draft = next((p for p in products if not p["published"]), None)
    if not draft:
        logging.info("No unpublished products found. All are already published!")
        return
    product_id = draft["id"]
    logging.info(f"Unpublished product: {draft['name']} (id={product_id})")

    # 2. Load cookies and open the edit page
    cookies_raw = os.environ["GUMROAD_COOKIES"]
    cookies = json.loads(cookies_raw)
    cookies = sanitize_cookies(cookies)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        edit_url = f"https://app.gumroad.com/products/{product_id}/edit"
        page.goto(edit_url, wait_until="networkidle")
        page.wait_for_timeout(5000)

        # Log all clickable elements
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

        # Also log the page title and main heading
        title = page.title()
        h1 = page.inner_text('h1').strip() if page.locator('h1').count() > 0 else ''
        logging.info(f"Page title: {title}")
        logging.info(f"Main heading: {h1}")

        browser.close()

if __name__ == "__main__":
    run()
