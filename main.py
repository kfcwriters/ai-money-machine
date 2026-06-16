import os, sys, logging, textwrap, requests, random, re, html
import xml.etree.ElementTree as ET
from fpdf import FPDF
from ai_helper import llm_generate

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

KOFI_API_KEY = os.environ["KOFI_API_KEY"]

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

def publish_to_kofi(title, price, pdf_path):
    """Create and instantly publish a digital product on Ko‑fi."""
    headers = {"Authorization": f"Bearer {KOFI_API_KEY}"}
    data = {
        "title": title,
        "price": str(price),          # e.g., "5.00"
        "type": "digital",
        "description": title,
        "published": "true"           # this actually works on Ko‑fi
    }
    with open(pdf_path, "rb") as f:
        files = {"file": ("product.pdf", f, "application/pdf")}
        resp = requests.post(
            "https://api.ko-fi.com/v1/shop/products",
            headers=headers,
            data=data,
            files=files,
            timeout=30
        )
    if resp.status_code in (200, 201):
        result = resp.json()
        product_url = result.get("url") or result.get("product", {}).get("url")
        if product_url:
            logging.info(f"Ko‑fi product published: {product_url}")
            return product_url
    raise Exception(f"Ko‑fi upload failed: {resp.status_code} {resp.text}")

def main():
    logging.info("=== AI Money Machine (Ko‑fi) Run Starting ===")
    try:
        problem = get_real_trend()
        logging.info(f"Selected topic: {problem}")
        ebook_title, ebook_md = generate_product(problem)
        logging.info(f"Product title: {ebook_title}")
        pdf_path = create_pdf(ebook_title, ebook_md)
        logging.info("PDF generated.")
        product_url = publish_to_kofi(ebook_title, 5.00, pdf_path)
        logging.info(f"Ko‑fi URL: {product_url}")
        with open(".latest_product_url", "w") as f:
            f.write(product_url)
        logging.info("=== Run Completed Successfully ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
