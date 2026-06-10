import os, sys, logging, textwrap, requests, random, re, xml.etree.ElementTree as ET
from fpdf import FPDF
from ai_helper import llm_generate

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]
HIRE_ME_URL = os.environ.get("HIRE_ME_URL", "https://kfcwriters.github.io")

# ---------- EVERGREEN TOPICS (fallback if trends fail) ----------
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

# ---------- TREND SOURCING ----------
def get_real_trend():
    """Try Google Trends RSS; if it fails, return a random evergreen topic."""
    try:
        rss = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        resp = requests.get(rss, timeout=30)
        # The RSS often contains unescaped HTML entities – fix them
        text = resp.text.replace("&", "&amp;")
        root = ET.fromstring(text)
        titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
        if titles:
            chosen = random.choice(titles)
            logging.info(f"Google Trend: {chosen}")
            return chosen
    except Exception as e:
        logging.warning(f"Google Trends failed ({e}), using evergreen topic list.")
    return random.choice(EVERGREEN_TOPICS)

# ---------- PRODUCT GENERATION (improved prompt) ----------
def generate_product(problem_title):
    prompt = f"""You are a top‑selling digital product creator. Write a 500‑word beginner‑friendly guide that solves: "{problem_title}".

Use this exact structure in Markdown:
# [Catchy Title Here – must include the main topic]
## Introduction (1 empathetic paragraph)
## 5 Actionable Steps (bulleted)
## Quick Checklist (5‑7 items)
## One‑line encouragement

Make it feel like a ready‑to‑use $5 download. Use simple language. No links or service references."""
    raw = llm_generate(prompt)
    # Extract title from first Markdown heading
    title_match = re.search(r"^#\s*(.+?)$", raw, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        # Fallback: take first non‑empty line
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        title = lines[0] if lines else problem_title
    # Remove the title line from the body so it doesn’t appear twice in the PDF
    body = re.sub(r"^#\s*.+?\n", "", raw, count=1).strip()
    return title, body

# ---------- SANITIZE TEXT ----------
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

# ---------- PDF CREATION ----------
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

# ---------- GUMROAD FILE UPLOAD (presigned flow – WORKING) ----------
def upload_file_to_gumroad(pdf_path):
    """Upload a file via Gumroad’s presigned S3 flow. Returns the final file URL."""
    file_name = "product.pdf"
    file_size = os.path.getsize(pdf_path)

    # 1. Request a presigned upload
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

    # 2. Upload the file to the S3 presigned URL
    with open(pdf_path, "rb") as f:
        put_resp = requests.put(presigned_url, data=f, headers={"Content-Type": "application/pdf"}, timeout=60)
    if put_resp.status_code not in (200, 201, 204):
        raise Exception(f"S3 upload failed: {put_resp.status_code}")
    etag = put_resp.headers.get("ETag", "")

    # 3. Complete the multipart upload
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

# ---------- PUBLISH PRODUCT WITH FILE ----------
def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    file_url = upload_file_to_gumroad(pdf_path)

    headers = {
        "Authorization": f"Bearer {GUMROAD_TOKEN}",
        "Content-Type": "application/json"
    }
    product_data = {
        "name": sanitize_text(ebook_title),
        "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download.",
        "price": "499",
        "published": "true",
        "files": [{"url": file_url}]
    }
    resp = requests.post("https://api.gumroad.com/v2/products",
                         headers=headers, json=product_data, timeout=30)
    if resp.status_code == 200 and resp.json().get("success"):
        short_url = resp.json()["product"].get("short_url", "no-url")
        logging.info(f"Gumroad product created with file: {short_url}")
        # Save latest product link for traffic scripts
        with open(".latest_product_url", "w") as f:
            f.write(short_url)
        return short_url
    else:
        msg = resp.json().get("message", "Unknown error") if resp.headers.get("content-type","").startswith("application/json") else resp.text
        raise Exception(f"Gumroad product creation failed: {msg}")

# ---------- MAIN ----------
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
        logging.info("=== AI Money Machine Run Completed Successfully ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
