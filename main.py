import os
import sys
import json
import logging

import requests
import tweepy
from fpdf import FPDF

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- API KEYS ----------
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]
TWITTER_API_KEY = os.environ["TWITTER_API_KEY"]
TWITTER_API_KEY_SECRET = os.environ["TWITTER_API_KEY_SECRET"]
TWITTER_ACCESS_TOKEN = os.environ["TWITTER_ACCESS_TOKEN"]
TWITTER_ACCESS_TOKEN_SECRET = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]
HASKNODE_TOKEN = os.environ["HASKNODE_TOKEN"]
HASKNODE_PUBLICATION_ID = os.environ["HASKNODE_PUBLICATION_ID"]
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")

# ---------- GEMINI (CORRECT URL + PARSING) ----------
def gemini_generate(prompt):
    # This is the CORRECT URL – one word, no spaces
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 2048}
    }
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    try:
        # Correctly navigate the JSON structure
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        logging.error("Unexpected Gemini response: %s", json.dumps(result, indent=2))
        raise

# ---------- TRENDING PROBLEM (no Reddit) ----------
def get_trending_problem():
    prompt = """You are a market researcher. Suggest ONE specific, popular problem people are actively searching for in the self-improvement, productivity, or side hustle space. It should be something that could be solved with a short $5 digital guide.
Only return the problem title as a single sentence. Do not add any extra text.

Example: "How to create a morning routine that actually sticks"
"""
    problem = gemini_generate(prompt).strip()
    problem = problem.strip('"').strip()
    logging.info(f"Gemini trending problem: {problem}")
    return problem

# ---------- PRODUCT CONTENT ----------
def generate_product(problem_title):
    prompt = f"""You are a top digital product creator. Based on the problem below, write a high-value, actionable eBook (about 500 words) that solves it. Write in Markdown format. Include a catchy title, introduction, 5 practical steps, and a summary checklist.

Problem: "{problem_title}"

Title of eBook:
(Now write the full eBook content below in Markdown)
"""
    full_text = gemini_generate(prompt)
    lines = full_text.strip().split("\n")
    ebook_title = lines[0].strip("#* ").strip()
    content = "\n".join(lines[1:]).strip()
    if not ebook_title:
        ebook_title = "Ultimate Guide to " + problem_title
    return ebook_title, content

# ---------- PDF ----------
def create_pdf(title, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", size=11)
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, line[3:], ln=True)
            pdf.set_font("Helvetica", size=11)
        elif line.startswith("# "):
            pdf.set_font("Helvetica", "B", 15)
            pdf.cell(0, 8, line[2:], ln=True)
            pdf.set_font("Helvetica", size=11)
        elif line.startswith("- "):
            pdf.cell(0, 6, "  • " + line[2:], ln=True)
        else:
            pdf.multi_cell(0, 6, line)
    filename = "product.pdf"
    pdf.output(filename)
    return filename

# ---------- GUMROAD ----------
def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    url = "https://api.gumroad.com/v2/products"
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    data = {
        "name": ebook_title,
        "description": f"This powerful guide solves: **{problem_title}**. Instant download – your action plan inside.",
        "price": 499,
        "published": "true",
    }
    resp = requests.post(url, headers=headers, data=data, timeout=30)
    resp.raise_for_status()
    product_info = resp.json()["product"]
    product_id = product_info["id"]

    upload_url = f"https://api.gumroad.com/v2/products/{product_id}/variant_files"
    with open(pdf_path, "rb") as f:
        files = {"file": ("product.pdf", f, "application/pdf")}
        resp2 = requests.post(upload_url, headers={"Authorization": f"Bearer {GUMROAD_TOKEN}"}, files=files, timeout=30)
        resp2.raise_for_status()

    short_url = product_info.get("short_url", "no-url")
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
    blog_body = gemini_generate(blog_prompt)
    blog_body = blog_body.replace("[GUIDE_LINK]", gumroad_url)

    variables = {
        "input": {
            "title": f"How to {ebook_title}",
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
    tweet_text = f"💡 Just created a quick fix for: {ebook_title}\n\nInstant $4.99 guide → {gumroad_url}"
    try:
        client.create_tweet(text=tweet_text)
        logging.info("Tweet sent.")
    except tweepy.TweepyException as e:
        logging.error(f"Tweet failed: {e}")

# ---------- PINTEREST (skip) ----------
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
