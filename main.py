import os, sys, logging, textwrap, requests, random, re, html
import xml.etree.ElementTree as ET
from fpdf import FPDF
from ai_helper import llm_generate

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ---------- EVERGREEN TOPICS ----------
EVERGREEN_TOPICS = [
    "How to build a morning routine that actually sticks",
    "5‑minute daily journaling template for mental clarity",
    "Beginner's guide to investing with just $5",
    "Meal planning on a budget: the ultimate checklist",
    "Job interview cheat sheet (questions & answers)",
    "How to stop procrastinating: a simple 5‑step system",
    "Minimalist home decluttering checklist",
    "Freelance writing pitch template (land your first client)",
    "10 prompts to fix your resume in 30 minutes",
    "Email template for negotiating salary (exact words)",
    "Travel packing list for one‑bag minimalists",
    "Online course launch checklist for creators",
    "Social media content calendar (fill‑in‑the‑blanks)",
    "First‑time homebuyer checklist (avoid hidden costs)",
    "How to train a puppy in 7 days (printable schedule)",
    "30‑day plank challenge tracker",
    "Password manager setup guide for total beginners",
    "Weekly reset routine template (Notion ready)",
    "How to ask for a letter of recommendation (email scripts)",
    "Side hustle idea validator (quick scorecard)",
]

def get_real_trend():
    try:
        rss = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        resp = requests.get(rss, timeout=30)
        clean_text = html.unescape(resp.text)
        root = ET.fromstring(clean_text)
        titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
        if titles:
            chosen = random.choice(titles)
            logging.info(f"Google Trend: {chosen}")
            return chosen
    except Exception as e:
        logging.warning(f"Google Trends failed ({e}), using evergreen topic list.")
    return random.choice(EVERGREEN_TOPICS)

def generate_product(problem_title):
    prompt = f"""You are a top‑selling digital product creator. Write a 500‑word beginner‑friendly guide that solves: "{problem_title}".

CRITICAL: The guide's title (the first line starting with #) MUST contain the exact phrase "{problem_title}" or a very close, natural rewording of it.

Use this exact structure in Markdown:
# [Title that includes "{problem_title}"]
## Introduction (1 empathetic paragraph)
## 5 Actionable Steps (bulleted)
## Quick Checklist (5‑7 items)
## One‑line encouragement

Make it sound like a ready‑to‑use $5 download. Use simple language. No links or service references."""
    raw = llm_generate(prompt)
    title_match = re.search(r"^#\s*(.+?)$", raw, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = f"The Complete Guide to {problem_title}"
    topic_words = set(problem_title.lower().split())
    title_words = set(title.lower().split())
    common = topic_words & title_words
    if len(common) < max(1, len(topic_words) * 0.3):
        logging.warning(f"Title mismatch, forcing: {problem_title}")
        title = f"The Complete Guide to {problem_title}"
    body = re.sub(r"^#\s*.+?\n", "", raw, count=1).strip()
    return title, body

def sanitize_text(text):
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--', '\u2026': '...', '\u2022': '-',
        '\u2023': '-', '\u25e6': '-', '\u00a0': ' ', '\u00ad': '',
        '\u00b7': '-'
    }
    for orig, new in replacements.items():
        text = text.replace(orig, new)
    return ''.join(ch if ord(ch) < 128 or ch == '\n' else '?' for ch in text)

def create_pdf(title, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, sanitize_text(title), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    for raw_line in content.split("\n"):
        line = sanitize_text(raw_line).strip()
        if not line:
            continue
        if line.startswith("## "):
            pdf.set_font("DejaVu", "B", 13)
            print_line = line[3:]
        elif line.startswith("# "):
            pdf.set_font("DejaVu", "B", 15)
            print_line = line[2:]
        elif line.startswith("- "):
            pdf.set_font("DejaVu", size=11)
            print_line = "  - " + line[2:]
        else:
            pdf.set_font("DejaVu", size=11)
            print_line = line
        for chunk in textwrap.wrap(print_line, width=90):
            pdf.cell(0, 6, chunk, new_x="LMARGIN", new_y="NEXT")
    pdf.output("product.pdf")
    return "product.pdf"

def upload_file_to_gumroad(pdf_path):
    file_name = "product.pdf"
    file_size = os.path.getsize(pdf_path)
    presign_url = "https://api.gumroad.com/v2/files/presign"
    presign_headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    resp = requests.post(presign_url, headers=presign_headers,
                         json={"filename": file_name, "file_size": file_size}, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Presign failed: {resp.status_code} {resp.text}")
    data = resp.json()
    upload_id = data["upload_id"]
    part = data["parts"][0]
    presigned_url = part["presigned_url"]
    with open(pdf_path, "rb") as f:
        put_resp = requests.put(presigned_url, data=f, headers={"Content-Type": "application/pdf"}, timeout=60)
    if put_resp.status_code not in (200, 201, 204):
        raise Exception(f"S3 upload failed: {put_resp.status_code}")
    etag = put_resp.headers.get("ETag", "")
    complete_url = "https://api.gumroad.com/v2/files/complete"
    complete_body = {
        "upload_id": upload_id,
        "key": data["key"],
        "parts": [{"part_number": part["part_number"], "etag": etag}]
    }
    resp = requests.post(complete_url, headers=presign_headers, json=complete_body, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"File completion failed: {resp.status_code} {resp.text}")
    file_url = resp.json().get("file_url") or data["file_url"]
    logging.info("File uploaded to Gumroad successfully.")
    return file_url

def send_telegram_notification(product_name, product_id, short_url):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    edit_url = f"https://app.gumroad.com/products/{product_id}/edit"
    message = f"📦 New draft: **{product_name}**\n🔗 [Publish now]({edit_url})\n🌐 {short_url}"
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=10
        )
    except:
        pass

def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    file_url = upload_file_to_gumroad(pdf_path)
    headers = {
        "Authorization": f"Bearer {GUMROAD_TOKEN}",
        "Content-Type": "application/json"
    }
    product_data = {
        "name": sanitize_text(ebook_title),
        "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download.",
        "price": 499,
        "published": True,                # Let's try again with payment details added
        "files": [{"url": file_url}]
    }
    resp = requests.post("https://api.gumroad.com/v2/products",
                         headers=headers, json=product_data, timeout=30)
    if resp.status_code == 200 and resp.json().get("success"):
        product = resp.json()["product"]
        short_url = product.get("short_url", "no-url")
        product_id = product["id"]
        published_status = product.get("published", False)
        logging.info(f"Product created: {short_url} (published={published_status})")

        # If not published, attempt a PUT update
        if not published_status:
            update_url = f"https://api.gumroad.com/v2/products/{product_id}"
            update_data = {"published": True}
            update_resp = requests.put(update_url, headers=headers, json=update_data, timeout=30)
            if update_resp.status_code == 200:
                new_published = update_resp.json().get("product", {}).get("published", False)
                if new_published:
                    logging.info("✅ Product published via PUT update.")
                else:
                    logging.warning("PUT update succeeded but published still False.")
            else:
                logging.warning(f"PUT update failed ({update_resp.status_code}). Product remains unpublished.")

        # Save link for traffic scripts
        with open(".latest_product_url", "w") as f:
            f.write(short_url)
        # Send Telegram publish reminder (even if published, as confirmation)
        send_telegram_notification(ebook_title, product_id, short_url)
        return short_url
    else:
        msg = resp.json().get("message", "Unknown error") if resp.headers.get("content-type","").startswith("application/json") else resp.text
        raise Exception(f"Gumroad product creation failed: {msg}")

def main():
    logging.info("=== AI Money Machine Run Starting ===")
    try:
        problem = get_real_trend()
        logging.info(f"Selected topic: {problem}")
        ebook_title, ebook_md = generate_product(problem)
        logging.info(f"Product title: {ebook_title}")
        pdf_path = create_pdf(ebook_title, ebook_md)
        logging.info("PDF generated.")
        gumroad_url = publish_to_gumroad(ebook_title, pdf_path, problem)
        logging.info(f"Gumroad URL: {gumroad_url}")
        logging.info("=== Run Completed Successfully ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
