import os, sys, logging, requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from get_link import get_latest_product_link

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

PINTEREST_ACCESS_TOKEN = os.environ["PINTEREST_ACCESS_TOKEN"]
PINTEREST_APP_ID = os.environ.get("PINTEREST_APP_ID", "")
AFFILIATE_LINK = get_latest_product_link()
API_BASE = "https://api-sandbox.pinterest.com/v5"

def create_pin_image(title):
    width, height = 1000, 1500
    img = Image.new("RGB", (width, height), (14, 36, 75))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except:
        font = ImageFont.load_default()
    lines = [title[i:i+30] for i in range(0, len(title), 30)]
    y = 200
    for line in lines[:5]:
        draw.text((100, y), line, font=font, fill=(255,255,255))
        y += 100
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes

def main():
    try:
        with open(".latest_article_title") as f: title = f.read().strip()
    except:
        logging.error("No generated article found.")
        sys.exit(1)

    image_bytes = create_pin_image(title)
    media_url = f"{API_BASE}/media"
    files = {"file": ("pin.png", image_bytes, "image/png")}
    media_resp = requests.post(media_url, headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"}, files=files)
    if media_resp.status_code != 200:
        logging.error(f"Media upload failed: {media_resp.status_code} {media_resp.text}")
        sys.exit(1)
    media_id = media_resp.json()["id"]

    boards_url = f"{API_BASE}/boards?app_id={PINTEREST_APP_ID}"
    boards_resp = requests.get(boards_url, headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"})
    boards = boards_resp.json().get("items", [])
    board_id = boards[0]["id"] if boards else None
    if not board_id:
        logging.error("No board found.")
        sys.exit(1)

    pin_data = {
        "link": AFFILIATE_LINK,
        "title": title[:80],
        "description": title,
        "board_id": board_id,
        "media_source": {"media_id": media_id, "source_type": "media_id"}
    }
    pin_resp = requests.post(f"{API_BASE}/pins",
                             headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
                                      "Content-Type": "application/json"},
                             json=pin_data)
    if pin_resp.status_code == 200:
        logging.info("Pin created successfully!")
    else:
        logging.error(f"Pin creation failed: {pin_resp.status_code} {pin_resp.text}")

if __name__ == "__main__":
    main()
