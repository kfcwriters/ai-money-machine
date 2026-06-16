import os, sys, logging, requests
from get_link import get_latest_product_link

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHANNEL_ID"]
AFFILIATE_LINK = get_latest_product_link()

def main():
    try:
        with open(".latest_article_title") as f: title = f.read().strip()
        with open(".latest_article_body") as f: body = f.read().strip()
    except:
        logging.error("No generated article found. Run main.py first.")
        sys.exit(1)

    text = f"📝 {title}\n\n{body[:300]}...\n👉 {AFFILIATE_LINK}"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    resp = requests.post(url, json=payload)
    if resp.status_code == 200:
        logging.info("Telegram message sent.")
    else:
        logging.error(f"Telegram error: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    main()
