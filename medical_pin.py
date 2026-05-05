import os
import logging
import sys
import textwrap
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- API KEYS ----------
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
PINTEREST_ACCESS_TOKEN = os.environ["PINTEREST_ACCESS_TOKEN"]
PINTEREST_APP_ID = os.environ.get("PINTEREST_APP_ID", "")
HIRE_ME_URL = os.environ["HIRE_ME_URL"]

# ---------- GROQ ----------
def get_tip():
    prompt = """You are a medical writing expert. Write a short, interesting tip (1-2 sentences) that helps researchers, doctors, or PhD students improve their medical manuscript, case report, or journal submission. Make it sound like a reason to click for more help.

Example: "Struggling with your case report? Start with the CARE checklist to ensure you don’t miss any critical section."

Only return the tip, nothing else."""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_completion_tokens": 100
    }
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    else:
        raise Exception(f"Groq error: {resp.status_code} {resp.text}")

# ---------- CREATE IMAGE ----------
def create_pin_image(tip):
    width, height = 1000, 1500   # Pinterest vertical ratio
    bg_color = (14, 36, 75)      # Dark medical blue
    text_color = (255, 255, 255)
    accent_color = (96, 179, 255) # Light blue accent

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 45)
    except:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # Accent line at top
    draw.rectangle([0, 0, width, 12], fill=accent_color)

    # Title
    title = "Medical Writing Pro Tip"
    title_w = draw.textlength(title, font=font_title)
    draw.text(((width - title_w) / 2, 100), title, font=font_title, fill=text_color)

    # Wrap the tip text
    lines = textwrap.wrap(tip, width=35)
    y = 280
    for line in lines:
        line_w = draw.textlength(line, font=font_body)
        draw.text(((width - line_w) / 2, y), line, font=font_body, fill=text_color)
        y += 75

    # Add a small URL at bottom
    url_text = " Learn more at the link below"
    url_w = draw.textlength(url_text, font=font_body)
    draw.text(((width - url_w) / 2, height - 150), url_text, font=font_body, fill=accent_color)

    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes

# ---------- POST TO PINTEREST ----------
def publish_pin(image_bytes, tip):
    # Step 1: Upload image to get media_id
    media_url = "https://api.pinterest.com/v5/media"
    files = {"file": ("pin.png", image_bytes, "image/png")}
    media_resp = requests.post(media_url, headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"}, files=files)
    if media_resp.status_code != 200:
        raise Exception(f"Pinterest media upload failed: {media_resp.status_code} {media_resp.text}")
    media_id = media_resp.json()["id"]
    logging.info(f"Uploaded image, media_id: {media_id}")

    # Step 2: Find or create the board "Medical Writing Tips"
    boards_url = f"https://api.pinterest.com/v5/boards?app_id={PINTEREST_APP_ID}"
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
            "description": "Daily tips for medical writers and researchers. Professional services available at the link.",
            "app_id": PINTEREST_APP_ID
        }
        create_resp = requests.post("https://api.pinterest.com/v5/boards",
                                    headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"},
                                    json=create_board_data)
        if create_resp.status_code == 200:
            board_id = create_resp.json()["id"]
            logging.info(f"Created board 'Medical Writing Tips' with id: {board_id}")
        else:
            raise Exception(f"Failed to create board: {create_resp.status_code} {create_resp.text}")

    # Step 3: Create pin
    pin_url = "https://api.pinterest.com/v5/pins"
    pin_data = {
        "link": HIRE_ME_URL,
        "title": f"Medical Writing Tip: {tip[:80]}",
        "description": tip,
        "board_id": board_id,
        "media_source": {
            "media_id": media_id,
            "source_type": "media_id"
        }
    }
    pin_resp = requests.post(pin_url, headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}", "Content-Type": "application/json"}, json=pin_data)
    if pin_resp.status_code == 200:
        logging.info("Pin created successfully!")
    else:
        raise Exception(f"Pin creation failed: {pin_resp.status_code} {pin_resp.text}")

# ---------- MAIN ----------
def main():
    logging.info("=== Medical Pinterest Pin Generator ===")
    try:
        tip = get_tip()
        logging.info(f"Tip: {tip}")
        img_bytes = create_pin_image(tip)
        publish_pin(img_bytes, tip)
        logging.info("✅ Done – pin posted.")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
