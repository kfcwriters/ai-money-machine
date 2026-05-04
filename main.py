import os
import sys
import json
import logging
import textwrap
import unicodedata

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
HASKNODE_PUBLICATION_ID = os.environ["HASKNODE_PUBLICATION_ID"]
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

# ---------- GUMROAD (WITH FULL LOGGING) ----------
def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    url = "https://api.gumroad.com/v2/products"
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}

    fields = {
        "name": sanitize_text(ebook_title),
        "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download – your action plan inside.",
        "price": "499",
        "published": "true",
    }
    with open(pdf_path, "rb") as f:
        files = {"file": ("product.pdf", f, "application/pdf")}
        resp = requests.post(url, headers=headers, data=fields, files=files, timeout=60)

    logging.info(f"Gumroad status code: {resp.status_code}")
    logging.info(f"Gumroad response: {resp.text}")

    if resp.status_code != 200:
        logging.error("Gumroad creation failed.")
        resp.raise_for_status()

    resp_json = resp.json()

    # Try to extract product URL from different possible response structures
    if "product" in resp_json:
        product_data = resp_json["product"]
        short_url = product_data.get("short_url", "no-url")
    elif "short_url" in resp_json:
        short_url = resp_json["short_url"]
    elif "id" in resp_json:
        # Manually construct the Gumroad product URL (typical pattern)
        product_id = resp_json["id"]
        short_url = f"https://gumroad.com/l/{product_id}"
    else:
        logging.error(f"Unexpected Gumroad response structure: {resp_json}")
        raise KeyError("Could not find product URL in Gumroad response")

    logging.info(f"Gumroad product created: {short_url}")
    return short_url

# ---------- HASKNODE ----------
def publish_hashnode_article(ebook_title, problem_title, gumroad_url):
    query = """
    mutation CreateStory($input: CreateStoryInput!) {
      createStory(input: $input) {
        code
        success
        message
        story {
          slug
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
            "publicationId": HASKNODE_PUBLICATION_ID,
            "tags": [],
            "isHidden": False,
            "isPartOfPublication": {
                "publicationId": HASKNODE_PUBLICATION_ID
            }
        }
    }
    headers = {
        "Authorization": HASKNODE_TOKEN,
        "Content-Type": "application/json"
    }
    resp = requests.post("https://api.hashnode.com/", json={"query": query, "variables": variables}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        logging.error("Hashnode error: %s", json.dumps(data["errors"]))
    else:
        slug = data.get("data", {}).get("createStory", {}).get("story", {}).get("slug", "")
        if slug:
            logging.info(f"Hashnode article published: {HASKNODE_PUBLICATION_ID}/{slug}")

# ---------- TWITTER ----------
def send_tweet(ebook_title, gumroad_url):
    client = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_KEY_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )
    tweet_text = f"💡 Just created a quick fix for: {sanitize_text(ebook_title)}\n\nInstant $4.99 guide → {gumroad_url}"
    try:
        client.create_tweet(text=tweet_text)
        logging.info("Tweet sent.")
    except tweepy.TweepyException as e:
        logging.error(f"Tweet failed: {e}")

# ---------- PINTEREST ----------
def create_pin(gumroad_url, ebook_title):
    if not PINTEREST_ACCESS_TOKEN:
        logging.info("Pinterest token not set. Skipping pin.")
        return
    logging.info("Pinterest pin creation skipped (needs image).")

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

        publish_hashnode_article(ebook_title, problem, gumroad_url)
        send_tweet(ebook_title, gumroad_url)
        create_pin(gumroad_url, ebook_title)

        logging.info("=== AI Money Machine Run Completed Successfully ===")
    except Exception as e:
        logging.exception("Fatal error in automation run.")
        sys.exit(1)

if __name__ == "__main__":
    main()
