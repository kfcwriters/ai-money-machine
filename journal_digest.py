import os, sys, logging, requests, urllib.parse, datetime
from ai_helper import llm_generate
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

BLOGGER_CLIENT_ID = os.environ["BLOGGER_CLIENT_ID"]
BLOGGER_CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
BLOGGER_REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]
BLOGGER_BLOG_ID = os.environ["BLOGGER_BLOG_ID"]

# ──────────── PubMed fetch (free, no key) ────────────
def fetch_latest_pubmed():
    """Fetch the most recent free article from PubMed for a medical writing related query."""
    # Search for recent articles about medical writing, manuscript preparation, etc.
    query = urllib.parse.quote("medical writing OR manuscript preparation OR journal submission")
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmax=5&sort=date&retmode=json"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise Exception("PubMed search failed")
    ids = resp.json()["esearchresult"]["idlist"]
    if not ids:
        raise Exception("No PubMed articles found")
    # Fetch details of the first article
    pmid = ids[0]
    details_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
    details_resp = requests.get(details_url, timeout=30)
    if details_resp.status_code != 200:
        raise Exception("PubMed details failed")
    result = details_resp.json()["result"][pmid]
    title = result["title"]
    abstract = result.get("abstract", "No abstract available.")
    journal = result.get("fulljournalname", "Unknown Journal")
    pub_date = result.get("pubdate", "2026")
    authors = ", ".join([a["name"] for a in result.get("authors", [])[:3]])
    return pmid, title, abstract, journal, pub_date, authors

# ──────────── AI Summary ────────────
def generate_digest(pmid, title, abstract, journal, pub_date, authors):
    prompt = f"""You are a medical writer. Below is the abstract of a published research paper. Write a 300‑word summary in simple English that a researcher or clinician would find useful. Include:
- What was studied (1 sentence)
- Key findings (2‑3 bullets)
- What this means for medical practice or writing (1‑2 sentences)
- End with: "Need help with your own medical writing or manuscript preparation? Visit kfcwriters.github.io or WhatsApp +91 9812018036."

Paper:
Title: {title}
Authors: {authors}
Journal: {journal}
Date: {pub_date}
Abstract: {abstract[:2000]}

Return only the summary, in plain text, no extra commentary."""
    return llm_generate(prompt, max_tokens=500)

# ──────────── Publish to Blogger ────────────
def post_to_blogger(title, content_html):
    creds = Credentials(None, refresh_token=BLOGGER_REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token",
                        client_id=BLOGGER_CLIENT_ID, client_secret=BLOGGER_CLIENT_SECRET)
    creds.refresh(Request())
    service = build("blogger", "v3", credentials=creds)
    post_body = {
        "kind": "blogger#post",
        "title": f"Research Digest: {title[:80]}...",
        "content": content_html,
        "labels": ["medical research", "journal digest", "medical writing"]
    }
    service.posts().insert(blogId=BLOGGER_BLOG_ID, body=post_body, isDraft=False).execute()
    logging.info(f"Journal digest published: {title[:60]}...")

# ──────────── Main ────────────
def main():
    logging.info("=== Medical Journal Digest ===")
    try:
        pmid, title, abstract, journal, pub_date, authors = fetch_latest_pubmed()
        summary = generate_digest(pmid, title, abstract, journal, pub_date, authors)
        html_content = f"""
        <div style="font-family: Georgia, serif; max-width: 800px; margin: 20px auto; padding: 20px; border-left: 4px solid #0d47a1;">
            <h2 style="color: #0d47a1;">{title}</h2>
            <p><strong>Authors:</strong> {authors} | <strong>Journal:</strong> {journal} | <strong>Date:</strong> {pub_date}</p>
            <p><strong>PubMed ID:</strong> {pmid}</p>
            <hr>
            <p style="white-space: pre-line; font-size: 1.1em;">{summary}</p>
            <p style="font-size: 0.85em; color: #666; margin-top: 20px;">This digest is an AI‑generated summary for educational purposes. Original research should be consulted directly.</p>
        </div>
        """
        post_to_blogger(title, html_content)
        logging.info("=== Done ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
