import os, logging, sys, textwrap, requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from get_link import get_latest_product_link

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
PINTEREST_ACCESS_TOKEN = os.environ["PINTEREST_ACCESS_TOKEN"]
PINTEREST_APP_ID = os.environ.get("PINTEREST_APP_ID", "")
PRODUCT_LINK = get_latest_product_link("https://kfcwriters.github.io")   # <-- FIX

API_BASE = "https://api-sandbox.pinterest.com/v5"  # still sandbox while app pending

def get_tip():
    prompt = f"""You are a medical writing expert. Write a short, interesting tip (1-2 sentences) that helps researchers, doctors, or PhD students improve their medical manuscript. Include a call‑to‑action to download a helpful guide: 'Get the full checklist at {PRODUCT_LINK} for $4.99.' Only return the tip."""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_completion_tokens": 120
    }
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"Groq error: {resp.status_code} {resp.text}")

def create_pin_image(tip):
    width, height = 1000, 1500
    bg_color = (14, 36, 75)
    text_color = (255, 255, 255)
    accent_color = (96, 179, 255)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 45)
    except:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([0, 0, width, 12], fill=accent_color)
    title = "Medical Writing Pro Tip"
    title_w = draw.textlength(title, font=font_title)
    draw.text(((width - title_w) / 2, 100), title, font=font_title, fill=text_color)

    lines = textwrap.wrap(tip, width=35)
    y = 280
    for line in lines:
        line_w = draw.textlength(line, font=font_body)
        draw.text(((width - line_w) / 2, y), line, font=font_body, fill=text_color)
        y += 75

    url_text = f" Grab the guide: {PRODUCT_LINK[:50]}..."
    url_w = draw.textlength(url_text, font=font_body)
    draw.text(((width - url_w) / 2, height - 150), url_text, font=font_body, fill=accent_color)

    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes

def publish_pin(image_bytes, tip):
    media_url = f"{API_BASE}/media"
    files = {"file": ("pin.png", image_bytes, "image/png")}
    media_resp = requests.post(media_url, headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"}, files=files)
    if media_resp.status_code != 200:
        raise Exception(f"Pinterest media upload failed: {media_resp.status_code} {media_resp.text}")
    media_id = media_resp.json()["id"]
    logging.info(f"Uploaded image, media_id: {media_id}")

    boards_url = f"{API_BASE}/boards?app_id={PINTEREST_APP_ID}"
    boards_resp = requests.get(boards_url, headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"})
    boards = boards_resp.json().get("items", [])
    board_id = None
    for b in boards:
        if b["name"].lower() == "medical writing tips":
            board_id = b["id"]
            break
    if not board_id:
        create_board_data = {
            "name": "Medical Writing Tips",
            "description": "Daily tips + $4.99 checklists for medical writers.",
            "app_id": PINTEREST_APP_ID
        }
        create_resp = requests.post(f"{API_BASE}/boards",
                                    headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"},
                                    json=create_board_data)
        if create_resp.status_code == 200:
            board_id = create_resp.json()["id"]
            logging.info(f"Created board with id: {board_id}")
        else:
            raise Exception(f"Failed to create board: {create_resp.status_code} {create_resp.text}")

    pin_data = {
        "link": PRODUCT_LINK,   # <-- now points to the product, not your Hire Me page
        "title": f"Medical Writing Tip: {tip[:80]}",
        "description": tip,
        "board_id": board_id,
        "media_source": {
            "media_id": media_id,
            "source_type": "media_id"
        }
    }
    pin_resp = requests.post(f"{API_BASE}/pins",
                             headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
                                      "Content-Type": "application/json"},
                             json=pin_data)
    if pin_resp.status_code == 200:
        logging.info("Pin created successfully!")
    else:
        raise Exception(f"Pin creation failed: {pin_resp.status_code} {pin_resp.text}")

def main():
    logging.info("=== Medical Pinterest Pin Generator ===")
    try:
        tip = get_tip()
        logging.info(f"Tip: {tip}")
        img_bytes = create_pin_image(tip)
        publish_pin(img_bytes, tip)
        logging.info("Done – pin posted with product link.")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
