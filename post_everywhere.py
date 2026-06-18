import os, sys, logging, requests

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- Read article ----------
try:
    with open(".latest_article_title", "r") as f: title = f.read().strip()
    with open(".latest_article_body", "r") as f: body = f.read().strip()
except:
    logging.error("Article files missing. Run main.py first.")
    sys.exit(1)

LINK = os.environ.get("AMAZON_AFFILIATE_LINK", "")
BUFFER_TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN", "")

def post_to_buffer():
    if not BUFFER_TOKEN:
        logging.warning("Buffer token missing.")
        return

    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json",
    }

    # 1. Get profiles – using the NEW API
    r = requests.get(
        "https://api.buffer.com/1/profiles.json",
        headers=headers
    )
    if r.status_code != 200:
        logging.error(f"Buffer profiles error: {r.text[:200]}")
        return

    profiles = r.json()
    for profile in profiles:
        pid = profile["id"]
        service = profile["service"]

        # Build the post text
        if service == "twitter":
            text = f"{title} 👉 {LINK}"
            text = text[:280]
        else:
            text = f"{title}\n\n{body[:300]}...\n👉 {LINK}"

        update_data = {
            "profile_ids": [pid],
            "text": text,
        }
        # Pinterest needs an image
        if service == "pinterest":
            update_data["media"] = [{
                "link": "https://via.placeholder.com/1000x1500.png/0d47a1/ffffff?text=Best+Deals"
            }]

        # 2. Create the update – using JSON body
        post_r = requests.post(
            "https://api.buffer.com/1/updates/create.json",
            json=update_data,          # <-- THIS sends proper JSON
            headers=headers
        )
        if post_r.status_code == 200:
            logging.info(f"Buffer: queued for {service}")
        else:
            logging.error(f"Buffer {service} error: {post_r.text[:200]}")

if __name__ == "__main__":
    logging.info("Posting to Buffer (FB, TW, PIN)...")
    post_to_buffer()
    logging.info("All done.")
