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

    headers = {"Authorization": f"Bearer {BUFFER_TOKEN}"}

    # 1. Get all profiles (new endpoint)
    r = requests.get("https://api.buffer.com/1/profiles.json", headers=headers)
    if r.status_code != 200:
        logging.error(f"Buffer profiles error: {r.text[:150]}")
        return

    profiles = r.json()
    for profile in profiles:
        pid = profile["id"]
        service = profile["service"]  # e.g., facebook, twitter, pinterest

        # Build the post text
        if service == "twitter":
            text = f"{title} 👉 {LINK}"
            text = text[:280]
        else:
            text = f"{title}\n\n{body[:300]}...\n👉 {LINK}"

        data = {
            "profile_ids": [pid],
            "text": text,
        }
        # Pinterest needs an image
        if service == "pinterest":
            data["media"] = [{
                "link": "https://via.placeholder.com/1000x1500.png/0d47a1/ffffff?text=Best+Deals"
            }]

        # Create the update
        post_r = requests.post("https://api.buffer.com/1/updates/create.json",
                               json=data, headers=headers)
        if post_r.status_code == 200:
            logging.info(f"Buffer: queued for {service}")
        else:
            logging.error(f"Buffer {service} error: {post_r.text[:150]}")

# LinkedIn and Reddit functions (unchanged – include your existing ones below)
# ...

if __name__ == "__main__":
    logging.info("Posting to Buffer (FB, TW, PIN)...")
    post_to_buffer()
    # post_linkedin()
    # post_reddit()
    logging.info("All done.")
