import os, sys, logging, textwrap, requests, json
from fpdf import FPDF
from ai_helper import llm_generate

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- API KEYS ----------
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

# ---------- GUMROAD (presigned upload – FIXED) ----------
def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    
    # 1. Presign – use `filename` (not `file_name`)
    file_size = os.path.getsize(pdf_path)
    presign_url = "https://api.gumroad.com/v2/files/presign"
    presign_data = {
        "filename": "product.pdf",          # <-- corrected
        "file_size": file_size,
        "resource_type": "product",
        "content_type": "application/pdf"
    }
    resp = requests.post(presign_url, headers=headers, json=presign_data, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Presign failed: {resp.status_code} {resp.text}")
    presign_info = resp.json()
    upload_url = presign_info["upload_url"]
    file_url = presign_info["file_url"]

    # 2. Upload file to presigned S3 URL (PUT with raw data)
    with open(pdf_path, "rb") as f:
        put_resp = requests.put(upload_url, data=f, timeout=120)
    if put_resp.status_code not in (200, 201, 204):
        raise Exception(f"File upload to S3 failed: {put_resp.status_code}")

    # 3. Create product and attach the file URL
    create_url = "https://api.gumroad.com/v2/products"
    product_data = {
        "name": sanitize_text(ebook_title),
        "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download.",
        "price": "499",
        "published": "true",
        "files": json.dumps([{"url": file_url}])
    }
    resp = requests.post(create_url, headers=headers, data=product_data, timeout=30)
    if resp.status_code == 200 and resp.json().get("success"):
        short_url = resp.json()["product"].get("short_url", "no-url")
        logging.info(f"Gumroad product created with file: {short_url}")
        return short_url
    else:
        msg = resp.json().get("message", "Unknown error") if resp.headers.get("content-type","").startswith("application/json") else resp.text
        logging.error(f"Product creation failed: {msg}")
        raise Exception(f"Gumroad API error: {msg}")

# ---------- MAIN ----------
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
