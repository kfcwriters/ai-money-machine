import os, sys, logging, requests

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

CACHE_FILE = ".latest_product_id"

def get_latest_product():
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    resp = requests.get("https://api.gumroad.com/v2/products", headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Gumroad API error: {resp.status_code} {resp.text}")
    products = resp.json()["products"]
    if not products:
        raise Exception("No products found.")
    latest = products[0]
    return latest["id"], latest["name"], latest["short_url"]

def post_to_discord(product_name, product_url):
    message = {
        "content": f"📚 **New $4.99 Guide Just Launched!**\n\n"
                   f"**{product_name}**\n"
                   f"{product_url}\n"
                   f"Grab it before it disappears into the library. 🚀"
    }
    resp = requests.post(DISCORD_WEBHOOK, json=message)
    if resp.status_code == 204:
        logging.info("Announcement posted to Discord.")
    else:
        raise Exception(f"Discord webhook failed: {resp.status_code} {resp.text}")

def main():
    try:
        latest_id, latest_name, latest_url = get_latest_product()
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                last_id = f.read().strip()
            if last_id == latest_id:
                logging.info("Product already announced. Skipping.")
                return
        post_to_discord(latest_name, latest_url)
        with open(CACHE_FILE, "w") as f:
            f.write(latest_id)
        logging.info("Product announcement complete.")
    except Exception as e:
        logging.exception(e)
        sys.exit(1)

if __name__ == "__main__":
    main()
