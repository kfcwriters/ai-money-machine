import os, sys, json, logging, textwrap, requests, tweepy
from fpdf import FPDF

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- API KEYS ----------
GUMROAD_TOKEN  = os.environ["GUMROAD_TOKEN"]
TWITTER_API_KEY = os.environ["TWITTER_API_KEY"]
TWITTER_API_KEY_SECRET = os.environ["TWITTER_API_KEY_SECRET"]
TWITTER_ACCESS_TOKEN = os.environ["TWITTER_ACCESS_TOKEN"]
TWITTER_ACCESS_TOKEN_SECRET = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]
HASKNODE_TOKEN = os.environ["HASKNODE_TOKEN"]
HASKNODE_PUBLICATION_HOST = os.environ["HASKNODE_PUBLICATION_ID"]
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
HIRE_ME_URL = os.environ.get("HIRE_ME_URL", "")

# ---------- Pollinations.AI (free, no API key) ----------
POLLINATIONS_URL = "https://text.pollinations.ai/openai"

def llm_generate(prompt):
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 2048
    }
    resp = requests.post(POLLINATIONS_URL, headers=headers, json=data, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"Pollinations error {resp.status_code}: {resp.text}")
    result = resp.json()
    return result["choices"][0]["message"]["content"]

# ---------- TRENDING ----------
def get_trending_problem():
    prompt = "You are a market researcher. Suggest ONE specific, popular problem people are actively searching for in the self-improvement, productivity, or side hustle space. It should be something that could be solved with a short $5 digital guide. Only return the problem title as a single sentence. Example: \"How to create a morning routine that actually sticks\""
    return llm_generate(prompt).strip().strip('"')

def generate_product(problem_title):
    prompt = f"You are a top digital product creator. Based on the problem below, write a high-value, actionable eBook (about 500 words) that solves it. Write in Markdown format. Include a catchy title, introduction, 5 practical steps, and a summary checklist.\n\nProblem: \"{problem_title}\"\n\nTitle of eBook:\n(Write the full eBook content below in Markdown)"
    full_text = llm_generate(prompt)
    lines = full_text.strip().split("\n")
    title = lines[0].strip("#* ").strip()
    if not title:
        title = "Ultimate Guide to " + problem_title
    return title, "\n".join(lines[1:]).strip()

def sanitize_text(text):
    for orig, new in {'\u2018':"'", '\u2019':"'", '\u201c':'"', '\u201d':'"', '\u2013':'-', '\u2014':'--', '\u2026':'...', '\u2022':'-', '\u2023':'-', '\u25e6':'-', '\u00a0':' ', '\u00ad':'', '\u00b7':'-'}.items():
        text = text.replace(orig, new)
    return ''.join(ch if ord(ch) < 128 or ch == '\n' else '?' for ch in text)

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

def publish_to_gumroad(ebook_title, pdf_path, problem_title):
    headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
    data = {"name": sanitize_text(ebook_title),
            "description": f"This powerful guide solves: **{sanitize_text(problem_title)}**. Instant download.",
            "price": "499", "published": "true"}
    resp = requests.post("https://api.gumroad.com/v2/products", headers=headers, data=data, timeout=30)
    if resp.status_code != 200 or not resp.json().get("success"):
        msg = resp.json().get("message", "Unknown error")
        logging.error(f"Gumroad product creation failed: {msg}")
        raise Exception(f"Gumroad API error: {msg}")
    product_id = resp.json()["product"]["id"]
    short_url = resp.json()["product"].get("short_url", "no-url")
    upload_url = f"https://api.gumroad.com/v2/products/{product_id}/variant_files"
    with open(pdf_path, "rb") as f:
        files = {"file": ("product.pdf", f, "application/pdf")}
        resp2 = requests.post(upload_url, headers=headers, files=files, timeout=60)
    if resp2.status_code != 200:
        logging.warning(f"File upload failed: {resp2.text}")
    else:
        logging.info("File uploaded successfully.")
    return short_url

# ---------- HASKNODE ----------
CACHED_PUB_ID = None

def get_hasnode_publication_id():
    global CACHED_PUB_ID
    if CACHED_PUB_ID: return CACHED_PUB_ID
    query = """query($host: String!) { publication(host: $host) { id } }"""
    variables = {"host": HASKNODE_PUBLICATION_HOST}
    headers = {"Authorization": HASKNODE_TOKEN, "Content-Type": "application/json"}
    resp = requests.post("https://gql.hashnode.com/", json={"query": query, "variables": variables}, headers=headers, timeout=30)
    if resp.status_code == 200:
        CACHED_PUB_ID = resp.json()["data"]["publication"]["id"]
        return CACHED_PUB_ID
    raise Exception("Could not fetch publication ID")

def publish_hashnode_article(ebook_title, problem_title, gumroad_url):
    publication_id = get_hasnode_publication_id()
    service_cta = f" Need professional medical writing help? Visit {HIRE_ME_URL}." if HIRE_ME_URL else ""
    blog_prompt = f"Write a helpful 300‑word blog article about: \"{problem_title}\". End with: 'Get the full $4.99 guide here: [GUIDE_LINK].{service_cta}' Use friendly tone."
    blog_body = llm_generate(blog_prompt).replace("[GUIDE_LINK]", gumroad_url)
    query = """mutation PublishPost($input: PublishPostInput!) { publishPost(input: $input) { post { slug, url } } }"""
    variables = {"input": {"title": f"How to {sanitize_text(ebook_title)}", "contentMarkdown": blog_body, "publicationId": publication_id, "tags": []}}
    headers = {"Authorization": HASKNODE_TOKEN, "Content-Type": "application/json"}
    resp = requests.post("https://gql.hashnode.com/", json={"query": query, "variables": variables}, headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        if "errors" in data:
            logging.error(f"Hashnode errors: {data['errors']}")
        else:
            slug = data["data"]["publishPost"]["post"]["slug"]
            logging.info(f"Hashnode post published: {HASKNODE_PUBLICATION_HOST}/{slug}")
    else:
        logging.error(f"Hashnode request failed: {resp.text}")

def send_tweet(title, url):
    try:
        client = tweepy.Client(consumer_key=TWITTER_API_KEY, consumer_secret=TWITTER_API_KEY_SECRET,
                               access_token=TWITTER_ACCESS_TOKEN, access_token_secret=TWITTER_ACCESS_TOKEN_SECRET)
        client.create_tweet(text=f"💡 {title}\n\nInstant $4.99 guide → {url}")
        logging.info("Tweet sent.")
    except Exception as e: logging.exception("Tweet failed")

def create_pin(url, title):
    if not PINTEREST_ACCESS_TOKEN: return
    logging.info("Pinterest pin skipped (image needed).")

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
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
