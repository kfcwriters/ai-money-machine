import os, sys, json, logging, textwrap, requests, tweepy
from fpdf import FPDF
from ai_helper import llm_generate

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- API KEYS ----------
GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]
TWITTER_API_KEY = os.environ["TWITTER_API_KEY"]
TWITTER_API_KEY_SECRET = os.environ["TWITTER_API_KEY_SECRET"]
TWITTER_ACCESS_TOKEN = os.environ["TWITTER_ACCESS_TOKEN"]
TWITTER_ACCESS_TOKEN_SECRET = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]
HASKNODE_TOKEN = os.environ["HASKNODE_TOKEN"]
HASKNODE_PUBLICATION_HOST = os.environ["HASKNODE_PUBLICATION_ID"]
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
HIRE_ME_URL = os.environ.get("HIRE_ME_URL", "")

# ---------- GET PUBLICATION ID (with proper error handling) ----------
CACHED_PUB_ID = None

def get_hasnode_publication_id():
    global CACHED_PUB_ID
    if CACHED_PUB_ID:
        return CACHED_PUB_ID
    query = """query($host: String!) { publication(host: $host) { id } }"""
    variables = {"host": HASKNODE_PUBLICATION_HOST}
    headers = {"Authorization": HASKNODE_TOKEN, "Content-Type": "application/json"}
    resp = requests.post("https://gql.hashnode.com/", json={"query": query, "variables": variables}, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Hashnode API returned status {resp.status_code}: {resp.text}")
    try:
        data = resp.json()
        pub_id = data["data"]["publication"]["id"]
        CACHED_PUB_ID = pub_id
        return pub_id
    except Exception as e:
        raise Exception(f"Invalid Hashnode response: {resp.text}")

# ---------- HASKNODE PUBLISH (unchanged) ----------
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

# ... (rest of the functions: sanitize_text, create_pdf, publish_to_gumroad, send_tweet, create_pin, main) remain exactly as they were in the last working main.py

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
        # Hashnode is now safe – failures are logged, machine continues
        try:
            publish_hashnode_article(ebook_title, problem, gumroad_url)
        except Exception as e:
            logging.exception("Hashnode publishing failed, continuing anyway.")
        send_tweet(ebook_title, gumroad_url)
        create_pin(gumroad_url, ebook_title)
        logging.info("=== AI Money Machine Run Completed Successfully ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
