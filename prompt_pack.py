import os, sys, logging, requests
from fpdf import FPDF

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]

# ---------- GET PROMPTS FROM GROQ ----------
def generate_prompts():
    prompt = """You are an expert in medical and academic writing. Generate 10 high-quality, reusable ChatGPT prompts that help researchers, PhD students, or clinicians with tasks like:
- Writing a thesis synopsis
- Structuring a manuscript
- Preparing a case report
- Creating a literature review outline
- Drafting journal cover letters
- Improving academic tone
- Formatting references
- Summarising research findings
- Generating research questions
- Overcoming writer's block

Format each prompt as:
**Title**: <short descriptive title>
**Prompt**: <the full ChatGPT prompt>

Return them as a numbered list, with clear separation between each. Do not add extra commentary."""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role":"user","content":prompt}], "temperature":0.8, "max_completion_tokens":2048}
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    raise Exception(f"Groq error {resp.status_code}")

# ---------- CREATE PDF ----------
def create_pdf(content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Medical & Academic Writing – Prompt Pack", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(8)
    pdf.set_font("DejaVu", "", 11)
    pdf.multi_cell(0, 6, "10 powerful ChatGPT prompts to accelerate your research and writing workflow.")
    pdf.ln(6)

    pdf.set_font("DejaVu", "", 11)
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Bold for titles
        if line.startswith("**") and line.endswith("**"):
            pdf.set_font("DejaVu", "B", 11)
            pdf.cell(0, 6, line.strip("*"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("DejaVu", "", 11)
        else:
            pdf.multi_cell(0, 6, line)
    pdf.output("prompt_pack.pdf")
    return "prompt_pack.pdf"

# ---------- PUBLISH TO GUMROAD ----------
def publish_to_gumroad(pdf_path):
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    data = {"name": "Medical & Academic Writing – ChatGPT Prompt Pack",
            "description": "10 ready‑to‑use ChatGPT prompts for medical writing, thesis planning, manuscript structuring, and more. Save hours of trial and error.",
            "price": "799",
            "published": "true"}
    resp = requests.post("https://api.gumroad.com/v2/products", headers=headers, data=data, timeout=30)
    if resp.status_code != 200 or not resp.json().get("success"):
        logging.error(f"Gumroad product creation failed: {resp.text}")
        raise Exception("Gumroad product creation error")
    product_id = resp.json()["product"]["id"]
    short_url = resp.json()["product"].get("short_url", "no-url")
    logging.info(f"Product created: {short_url}")

    # Upload file
    upload_url = f"https://api.gumroad.com/v2/products/{product_id}/variant_files"
    with open(pdf_path, "rb") as f:
        files = {"file": ("PromptPack.pdf", f, "application/pdf")}
        resp2 = requests.post(upload_url, headers=headers, files=files, timeout=60)
    if resp2.status_code == 200:
        logging.info("Prompt pack published successfully!")
    else:
        logging.warning(f"File upload failed: {resp2.text}")

# ---------- MAIN ----------
def main():
    logging.info("=== Weekly Prompt Pack Generator ===")
    try:
        prompts = generate_prompts()
        pdf = create_pdf(prompts)
        publish_to_gumroad(pdf)
        logging.info("=== Run Complete ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
