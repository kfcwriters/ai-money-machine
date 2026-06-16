import os, sys, logging, requests
from get_link import get_latest_product_link

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

FB_PAGE_ID = os.environ["FB_PAGE_ID"]
FB_PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]
AFFILIATE_LINK = get_latest_product_link()

def main():
    try:
        with open(".latest_article_title") as f: title = f.read().strip()
    except:
        logging.error("No generated article found. Run main.py first.")
        sys.exit(1)

    message = f"{title}\n\nCheck out my recommended pick: {AFFILIATE_LINK}"
    url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/feed"
    payload = {"message": message, "access_token": FB_PAGE_TOKEN}
    resp = requests.post(url, data=payload, timeout=30)
    if resp.status_code == 200:
        logging.info("Facebook post published.")
    else:
        logging.error(f"Facebook error: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    main()
