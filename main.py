import os, sys, logging, textwrap, requests
from fpdf import FPDF
from ai_helper import llm_generate   # your bulletproof AI

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- API KEYS (only what we actually use) ----------
GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]
HIRE_ME_URL = os.environ.get("HIRE_ME_URL", "")

# ---------- TRENDING PROBLEM ----------
def get_trending_problem():
    prompt = "You are a market researcher. Suggest ONE specific, popular problem people are actively searching for in the self-improvement, productivity, or side hustle space. It should be something that could be solved with a short $5 digital guide. Only return the problem title as a single sentence. Example: \"How to create a morning routine that actually sticks\""
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

# ---------- GUMROAD (product only, file upload retried) ----------
def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}

    create_url = "https://api.gumroad.com/v2/products"
    product_data = {
        "name": sanitize_text(ebook_title),
        "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download.",
        "price": "499",
        "published": "true",
    }
    # Step 1: Create product
    resp1 = requests.post(create_url, headers=headers, data=product_data, timeout=30)
    if resp1.status_code != 200 or not resp1.json().get("success"):
        msg = resp1.json().get("message", "Unknown error")
        logging.error(f"Gumroad product creation failed: {msg}")
        raise Exception(f"Gumroad API error: {msg}")

    product_id = resp1.json()["product"]["id"]
    short_url = resp1.json()["product"].get("short_url", "no-url")
    logging.info(f"Gumroad product created: {short_url}")

    # Step 2: Upload file (with retry)
    upload_url = f"https://api.gumroad.com/v2/products/{product_id}/variant_files"
    for attempt in range(2):
        with open(pdf_path, "rb") as f:
            files = {"file": ("product.pdf", f, "application/pdf")}
            resp2 = requests.post(upload_url, headers=headers, files=files, timeout=60)
        if resp2.status_code == 200:
            logging.info("File uploaded successfully.")
            return short_url
        else:
            logging.warning(f"File upload attempt {attempt+1} failed: {resp2.status_code} – {resp2.text[:100]}")

    logging.warning("File upload failed after 2 attempts – product is live but may be missing the PDF.")
    return short_url

# ---------- MAIN (only Gumroad, no Hashnode/Twitter/Pinterest) ----------
def main():
    logging.info("=== AI Money Machine Run Starting ===")
    try:
        problem = get_trending_problem()
        logging.info(f"Problem: {problem}")
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
