import os, sys, logging, requests, random
from fpdf import FPDF

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]

TOPICS = [
    "Manuscript Submission Checklist",
    "Thesis Editing Checklist",
    "Case Report Writing Checklist",
    "Literature Review Checklist",
    "Journal Formatting Checklist",
    "Medical Abstract Checklist",
    "Peer Review Response Checklist",
    "Research Paper Structure Checklist",
]

def generate_checklist():
    topic = random.choice(TOPICS)
    prompt = f"""You are a medical writing expert. Create a practical, actionable 1‑page checklist titled "{topic}".

Return it as a simple numbered list with exactly 10 items. Each item should be one concise sentence (max 15 words). Do NOT include any introduction or closing text. Just the 10 numbered items, one per line."""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500
    }
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return topic, resp.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"OpenRouter error {resp.status_code}")

def create_pdf(title, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)
    pdf.set_font("DejaVu", "B", 18)
    pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    pdf.set_font("DejaVu", "", 12)
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output("checklist.pdf")
    return "checklist.pdf"

def publish_to_gumroad(title, pdf_path):
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    data = {
        "name": title,
        "description": f"A practical, 10‑step {title.lower()} to save you time and mistakes. Instant PDF download.",
        "price": "399",
        "published": True,   # <-- boolean, not string
    }
    resp = requests.post("https://api.gumroad.com/v2/products", headers=headers, data=data, timeout=30)
    if resp.status_code != 200 or not resp.json().get("success"):
        raise Exception(f"Gumroad product creation failed: {resp.text}")

    product_id = resp.json()["product"]["id"]
    short_url = resp.json()["product"].get("short_url", "no-url")
    logging.info(f"Product created: {short_url}")

    # Upload the file (required for digital products)
    upload_url = f"https://api.gumroad.com/v2/products/{product_id}/variant_files"
    with open(pdf_path, "rb") as f:
        files = {"file": ("checklist.pdf", f, "application/pdf")}
        resp2 = requests.post(upload_url, headers=headers, files=files, timeout=60)
    if resp2.status_code != 200:
        logging.warning(f"File upload failed: {resp2.text}")
    else:
        logging.info("File uploaded successfully.")

    # Extra safety: explicitly set product as published (in case it was ignored)
    publish_url = f"https://api.gumroad.com/v2/products/{product_id}"
    requests.put(publish_url, headers=headers, data={"published": True})

def main():
    logging.info("=== Weekly Checklist Generator ===")
    try:
        title, content = generate_checklist()
        pdf = create_pdf(title, content)
        publish_to_gumroad(title, pdf)
        logging.info("=== Run Complete ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
