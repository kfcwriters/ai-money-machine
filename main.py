import os
import sys
import json
import logging
import textwrap

import requests
import tweepy
from fpdf import FPDF

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- API KEYS ----------
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]
TWITTER_API_KEY = os.environ["TWITTER_API_KEY"]
TWITTER_API_KEY_SECRET = os.environ["TWITTER_API_KEY_SECRET"]
TWITTER_ACCESS_TOKEN = os.environ["TWITTER_ACCESS_TOKEN"]
TWITTER_ACCESS_TOKEN_SECRET = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]
HASKNODE_TOKEN = os.environ["HASKNODE_TOKEN"]
HASKNODE_PUBLICATION_HOST = os.environ["HASKNODE_PUBLICATION_ID"]  # still the domain
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")

# ---------- GROQ ----------
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

def llm_generate(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_completion_tokens": 2048
    }
    resp = requests.post(GROQ_BASE_URL, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        logging.error(f"Groq error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    result = resp.json()
    return result["choices"][0]["message"]["content"]

# ---------- TRENDING PROBLEM ----------
def get_trending_problem():
    prompt = """You are a market researcher. Suggest ONE specific, popular problem people are actively searching for in the self-improvement, productivity, or side hustle space. It should be something that could be solved with a short $5 digital guide.
Only return the problem title as a single sentence. Do not add any extra text.

Example: "How to create a morning routine that actually sticks"
"""
    problem = llm_generate(prompt).strip()
    problem = problem.strip('"').strip()
    logging.info(f"AI trending problem: {problem}")
    return problem

# ---------- PRODUCT CONTENT ----------
def generate_product(problem_title):
    prompt = f"""You are a top digital product creator. Based on the problem below, write a high-value, actionable eBook (about 500 words) that solves it. Write in Markdown format. Include a catchy title, introduction, 5 practical steps, and a summary checklist.

Problem: "{problem_title}"

Title of eBook:
(Now write the full eBook content below in Markdown)
"""
    full_text = llm_generate(prompt)
    lines = full_text.strip().split("\n")
    ebook_title = lines[0].strip("#* ").strip()
    content = "\n".join(lines[1:]).strip()
    if not ebook_title:
        ebook_title = "Ultimate Guide to " + problem_title
    return ebook_title, content

# ---------- TEXT SANITIZER ----------
def sanitize_text(text):
    replacements = {
        '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--',
        '\u2026': '...',
        '\u2022': '-', '\u2023': '-',
        '\u25e6': '-',
        '\u00a0': ' ',
        '\u00ad': '',
        '\u00b7': '-',
    }
    for orig, new in replacements.items():
        text = text.replace(orig, new)
    cleaned = []
    for ch in text:
        if ord(ch) < 128 or ch == '\n':
            cleaned.append(ch)
        else:
            cleaned.append('?')
    return ''.join(cleaned)

# ---------- PDF ----------
def create_pdf(title, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, sanitize_text(title), ln=True, align="C")
    pdf.ln(10)

    effective_width = pdf.w - pdf.l_margin - pdf.r_margin
    max_chars = int(effective_width / 2)

    for raw_line in content.split("\n"):
        line = sanitize_text(raw_line).strip()
        if not line:
            continue

        if line.startswith("## "):
            pdf.set_font("DejaVu", "B", 13)
            pdf.cell(0, 8, line[3:], ln=True)
            pdf.set_font("DejaVu", size=11)
        elif line.startswith("# "):
            pdf.set_font("DejaVu", "B", 15)
            pdf.cell(0, 8, line[2:], ln=True)
            pdf.set_font("DejaVu", size=11)
        elif line.startswith("- "):
            pdf.set_font("DejaVu", size=11)
            pdf.cell(0, 6, "  - " + line[2:], ln=True)
        else:
            pdf.set_font("DejaVu", size=11)
            if len(line) > max_chars and " " not in line:
                for part in textwrap.wrap(line, width=max_chars):
                    pdf.cell(0, 6, part, ln=True)
            else:
                try:
                    pdf.multi_cell(0, 6, line)
                except Exception as e:
                    logging.warning(f"PDF error on line: {line[:80]}... {e}")
                    pdf.cell(0, 6, line, ln=True)

    filename = "product.pdf"
    pdf.output(filename)
    return filename

# ---------- GUMROAD (published as lowercase "true" string) ----------
def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}

    create_url = "https://api.gumroad.com/v2/products"
    product_data = {
        "name": sanitize_text(ebook_title),
        "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download – your action plan inside.",
        "price": "499",
        "published": "true",   # <-- lowercase string, works with form data
    }
    resp1 = requests.post(create_url, headers=headers, data=product_data, timeout=30)
    if resp1.status_code != 200 or not resp1.json().get("success"):
        logging.error(f"Gumroad product creation failed: {resp1.text}")
        resp1.raise_for_status()
    product_info = resp1.json()["product"]
    product_id = product_info["id"]
    short_url = product_info.get("short_url", "no-url")
    logging.info(f"Gumroad product created: {short_url}")

    upload_url = f"https://api.gumroad.com/v2/products/{product_id}/variant_files"
    with open(pdf_path, "rb") as f:
        files = {"file": ("product.pdf", f, "application/pdf")}
        resp2 = requests.post(upload_url, headers=headers, files=files, timeout=60)
    if resp2.status_code != 200:
        logging.warning(f"File upload failed: {resp2.text}")
    else:
        logging.info("File uploaded successfully.")

    return short_url

# ---------- HELPER: get real publication ID from host ----------
def get_hasnode_publication_id():
    query = """
    query($host: String!) {
      publication(host: $host) {
        id
      }
    }
    """
    variables = {"host": HASKNODE_PUBLICATION_HOST}
    headers = {"Authorization": HASKNODE_TOKEN, "Content-Type": "application/json"}
    resp = requests.post("https://gql.hashnode.com/", json={"query": query, "variables": variables}, headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        pub_id = data.get("data", {}).get("publication", {}).get("id")
        if pub_id:
            logging.info(f"Resolved publication ID: {pub_id}")
            return pub_id
    logging.error("Could not fetch publication ID. Using host as fallback.")
    return HASKNODE_PUBLICATION_HOST

# ---------- HASKNODE (publish live) ----------
def publish_hashnode_article(ebook_title, problem_title, gumroad_url):
    publication_id = get_hasnode_publication_id()

    query = """
    mutation PublishPost($input: PublishPostInput!) {
      publishPost(input: $input) {
        post {
          id
          slug
          url
        }
      }
    }
    """
    blog_prompt = f"""Write a helpful 300‑word blog article about solving this problem: "{problem_title}". At the end, naturally recommend a $4.99 guide that solves it, with a link placeholder [GUIDE_LINK]. Use a friendly tone."""
    blog_body = llm_generate(blog_prompt)
    blog_body = blog_body.replace("[GUIDE_LINK]", gumroad_url)

    variables = {
        "input": {
            "title": f"How to {sanitize_text(ebook_title)}",
            "contentMarkdown": blog_body,
            "publicationId": publication_id,
            "tags": [],
            "disableComments": False
        }
    }
    headers = {
        "Authorization": HASKNODE_TOKEN,
        "Content-Type": "application/json"
    }
    response = requests.post(
        "https://gql.hashnode.com/",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30
    )
    logging.info(f"Hashnode status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            logging.error("Hashnode GraphQL errors: %s", json.dumps(data["errors"]))
        else:
            post_info = data.get("data", {}).get("publishPost", {}).get("post", {})
            slug = post_info.get("slug", "")
            url = post_info.get("url", "")
            if slug:
                logging.info(f"Hashnode post published: {slug}")
            if url:
                logging.info(f"Public URL: {url}")
    else:
        logging.error(f"Hashnode request failed: {response.text}")

# ---------- TWITTER ----------
def send_tweet(ebook_title, gumroad_url):
    client = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_KEY_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )
    tweet_text = f"💡 Just created a quick fix for: {sanitize_text(ebook_title)}\n\nInstant $4.99 guide → {gumroad_url}"
    client.create_tweet(text=tweet_text)
    logging.info("Tweet sent.")

# ---------- PINTEREST ----------
def create_pin(gumroad_url, ebook_title):
    if not PINTEREST_ACCESS_TOKEN:
        logging.info("Pinterest token not set. Skipping pin.")
        return
    logging.info("Pinterest pin creation skipped (needs image).")

# ---------- MAIN ----------
def main():
    logging.info("=== AI Money Machine Run Starting ===")
    problem = None
    ebook_title = None
    gumroad_url = None

    try:
        problem = get_trending_problem()
        logging.info(f"Problem: {problem}")
    except Exception as e:
        logging.exception("Failed to get trending problem. Stopping.")
        sys.exit(1)

    try:
        ebook_title, ebook_md = generate_product(problem)
        logging.info(f"Product title: {ebook_title}")
    except Exception as e:
        logging.exception("Failed to generate product content.")
        sys.exit(1)

    try:
        pdf_path = create_pdf(ebook_title, ebook_md)
        logging.info("PDF generated.")
    except Exception as e:
        logging.exception("Failed to create PDF.")
        sys.exit(1)

    try:
        gumroad_url = publish_to_gumroad(ebook_title, pdf_path, problem)
        logging.info(f"Gumroad URL: {gumroad_url}")
    except Exception as e:
        logging.exception("Failed to publish to Gumroad.")
        sys.exit(1)

    # Optional steps
    try:
        publish_hashnode_article(ebook_title, problem, gumroad_url)
    except Exception as e:
        logging.exception("Hashnode publishing failed, continuing anyway.")

    try:
        send_tweet(ebook_title, gumroad_url)
    except Exception as e:
        logging.exception(f"Tweet failed: {e}")

    try:
        create_pin(gumroad_url, ebook_title)
    except Exception as e:
        logging.exception(f"Pinterest failed: {e}")

    logging.info("=== AI Money Machine Run Completed Successfully ===")
    if gumroad_url:
        logging.info(f"🌟 Your new product is live at: {gumroad_url}")

if __name__ == "__main__":
    main()
