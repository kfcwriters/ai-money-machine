import os, sys, logging, textwrap, requests, xml.etree.ElementTree as ET, random
from fpdf import FPDF
from ai_helper import llm_generate

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]
HIRE_ME_URL = os.environ.get("HIRE_ME_URL", "https://kfcwriters.github.io")

# ---------- REAL TRENDING TOPIC (Google Trends) ----------
def get_real_trend():
    """Fetch trending searches from Google Trends daily RSS (free, no key)."""
    try:
        rss = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        resp = requests.get(rss, timeout=30)
        root = ET.fromstring(resp.text)
        titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
        if titles:
            chosen = random.choice(titles)
            logging.info(f"Google Trend found: {chosen}")
            return chosen
    except Exception as e:
        logging.warning(f"Google Trends failed ({e}), falling back to AI generated")
    # fallback to AI hallucination
    return get_trending_problem()

def get_trending_problem():
    prompt = "You are a market researcher. Suggest ONE specific, popular problem people are actively searching for in the self-improvement, productivity, or side hustle space. It should be something that could be solved with a short $5 digital guide. Only return the problem title as a single sentence."
    return llm_generate(prompt).strip().strip('"')

# ---------- PRODUCT CONTENT ----------
def generate_product(problem_title):
    prompt = f"You are a top digital product creator. Based on the problem below, write a high-value, actionable eBook (about 500 words) that solves it. Write in Markdown format. Include a catchy title, introduction, 5 practical steps, and a summary checklist.\n\nProblem: \"{problem_title}\"\n\nTitle of eBook:\n(Write the full eBook content below in Markdown)"
    full_text = llm_generate(prompt)
    lines = full_text.strip().split("\n")
    title = lines[0].strip("#* ").strip()
    if not title:
        title = "Ultimate Guide to " + problem_title
    return title, "\n".join(lines[1:]).strip()

# ---------- SANITIZE ----------
def sanitize_text(text):
    for orig, new in {'\u2018':"'", '\u2019':"'", '\u201c':'"', '\u201d':'"', '\u2013':'-', '\u2014':'--', '\u2026':'...', '\u2022':'-', '\u2023':'-', '\u25e6':'-', '\u00a0':' ', '\u00ad':'', '\u00b7':'-'}.items():
        text = text.replace(orig, new)
    return ''.join(ch if ord(ch) < 128 or ch == '\n' else '?' for ch in text)

# ---------- PDF ----------
def create_pdf(title, content):
    pdf = FPDF()
    pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, sanitize_text(title), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    max_chars = 90
    for raw_line in content.split("\n"):
        line = sanitize_text(raw_line).strip()
        if not line: continue
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
        for chunk in textwrap.wrap(print_line, width=max_chars):
            pdf.cell(0, 6, chunk, new_x="LMARGIN", new_y="NEXT")
    pdf.output("product.pdf")
    return "product.pdf"

# ---------- GUMROAD PUBLISH + ATTACH PDF ----------
def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    data = {
        "name": sanitize_text(ebook_title),
        "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download.",
        "price": "499",
        "published": "true",
    }
    resp = requests.post("https://api.gumroad.com/v2/products", headers=headers, data=data, timeout=30)
    if resp.status_code != 200 or not resp.json().get("success"):
        msg = resp.json().get("message", "Unknown error") if resp.headers.get("content-type","").startswith("application/json") else resp.text
        logging.error(f"Product creation failed: {msg}")
        raise Exception(f"Gumroad API error: {msg}")

    product_id = resp.json()["product"]["id"]
    short_url = resp.json()["product"].get("short_url", "no-url")
    logging.info(f"Gumroad product created: {short_url}")

    # --- ATTACH THE PDF FILE (FIX #1) ---
    upload_url = f"https://api.gumroad.com/v2/products/{product_id}/variant_files"
    with open(pdf_path, "rb") as f:
        files = {"file": ("product.pdf", f, "application/pdf")}
        upload_resp = requests.post(upload_url, headers=headers, files=files, timeout=60)
    if upload_resp.status_code == 200:
        logging.info("PDF file attached successfully!")
    else:
        logging.warning(f"File upload failed: {upload_resp.text} – product is live but without file")
    # --- SAVE LINK FOR OTHER SCRIPTS ---
    with open(".latest_product_url", "w") as f:
        f.write(short_url)
    return short_url

# ---------- MAIN ----------
def main():
    logging.info("=== AI Money Machine Run Starting ===")
    try:
        problem = get_real_trend()          # now uses real trends
        logging.info(f"Trend/Problem: {problem}")
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
