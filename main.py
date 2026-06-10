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
    """Return a trending search from Google Trends RSS, or fallback to evergreen."""
    try:
        rss = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        resp = requests.get(rss, timeout=30)
        # sometimes the response contains HTML entities that break XML; strip them
        text = resp.text.replace("&", "&amp;")  # crude fix
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
    prompt = f"""You are a top‑selling digital product creator. I need a 500‑word beginner‑friendly guide that solves this problem: "{problem_title}".

Format the answer in Markdown with the following structure:
# [Catchy Title Here]
## Introduction (1 paragraph, empathetic)
## 5 Actionable Steps (each as a bullet list or numbered)
## Quick Checklist (5‑7 items)
## One‑line encouragement

Make it feel like a ready‑to‑use $5 download. Do NOT reference links, websites, or services. Use clear, simple language."""
    raw = llm_generate(prompt)
    # extract title from first # heading
    title_match = re.search(r"^#\s*(.+?)$", raw, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        # fallback: take first non‑empty line
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        title = lines[0] if lines else problem_title
    # remove the title line from the content so it doesn't appear twice in PDF
    body = re.sub(r"^#\s*.+?\n", "", raw, count=1).strip()
    return title, body

# ---------- SANITIZE TEXT ----------
def sanitize_text(text):
    replacements = {
        '\u2018':"'", '\u2019':"'", '\u201c':'"', '\u201d':'"',
        '\u2013':'-', '\u2014':'--', '\u2026':'...', '\u2022':'-',
        '\u2023':'-', '\u25e6':'-', '\u00a0':' ', '\u00ad':'',
        '\u00b7':'-'
    }
    for orig, new in replacements.items():
        text = text.replace(orig, new)
    return ''.join(ch if ord(ch) < 128 or ch == '\n' else '?' for ch in text)

# ---------- PDF CREATION (no uni deprecation) ----------
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

# ---------- GUMROAD: CREATE + ATTACH FILE IN ONE REQUEST ----------
def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    url = "https://api.gumroad.com/v2/products"
    data = {
        "name": sanitize_text(ebook_title),
        "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download.",
        "price": "499",
        "published": "true",
    }
    # Send multipart form with the file attached
    with open(pdf_path, "rb") as f:
        files = {"file": (f"{sanitize_text(ebook_title)[:50]}.pdf", f, "application/pdf")}
        resp = requests.post(url, headers=headers, data=data, files=files, timeout=30)

    if resp.status_code == 200 and resp.json().get("success"):
        short_url = resp.json()["product"].get("short_url", "no-url")
        logging.info(f"Gumroad product created with file: {short_url}")
        # Save latest product link for traffic scripts
        with open(".latest_product_url", "w") as f:
            f.write(short_url)
        return short_url
    else:
        msg = resp.json().get("message", "Unknown error") if resp.headers.get("content-type","").startswith("application/json") else resp.text
        logging.error(f"Product creation failed: {msg}")
        raise Exception(f"Gumroad API error: {msg}")

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
