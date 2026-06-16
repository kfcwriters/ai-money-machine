import os, sys, logging, requests
from get_link import get_latest_product_link

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
AFFILIATE_LINK = get_latest_product_link()

def main():
    try:
        with open(".latest_article_title") as f: title = f.read().strip()
        with open(".latest_article_body") as f: body = f.read().strip()
    except:
        logging.error("No generated article found. Run main.py first.")
        sys.exit(1)

    full_body = body + f"\n\n---\n*Disclosure: Some links are affiliate links. If you make a purchase, I may earn a small commission at no extra cost to you.*"
    payload = {
        "article": {
            "title": title,
            "body_markdown": full_body,
            "published": True,
            "tags": ["productivity", "reviews", "shopping"]
        }
    }
    headers = {"Content-Type": "application/json", "api-key": DEVTO_API_KEY}
    resp = requests.post("https://dev.to/api/articles", headers=headers, json=payload)
    if resp.status_code == 201:
        logging.info(f"Published: {resp.json()['url']}")
    else:
        logging.error(f"Dev.to error: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    main()
