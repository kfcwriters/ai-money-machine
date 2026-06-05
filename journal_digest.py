import os, sys, logging, requests, urllib.parse, datetime, base64, re, json
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

WEBSITE_REPO_TOKEN = os.environ["WEBSITE_REPO_TOKEN"]
REPO = "kfcwriters/kfcwriters.github.io"
BRANCH = "main"
GITHUB_API = "https://api.github.com"
JOURNAL_FOLDER = "Journal"   # <-- changed from "reviews"

# Import your existing AI helper (uses Pollinations.ai, no key needed)
from ai_helper import llm_generate

# ---------- PubMed fetch (unchanged) ----------
def fetch_pubmed_articles(topic, count=8):
    query = urllib.parse.quote(topic)
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmax={count}&sort=date&retmode=json"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"PubMed search failed: {resp.status_code}")
    ids = resp.json()["esearchresult"]["idlist"]
    if not ids:
        raise Exception(f"No articles found for '{topic}'")
    
    articles = []
    for pmid in ids:
        details_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
        details_resp = requests.get(details_url, timeout=30)
        if details_resp.status_code != 200:
            continue
        result = details_resp.json()["result"][pmid]
        title = result["title"]
        abstract = result.get("abstract", "")
        if not abstract or abstract.strip() == "":
            efetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml&rettype=abstract"
            efetch_resp = requests.get(efetch_url, timeout=30)
            if efetch_resp.status_code == 200:
                match = re.search(r"<Abstract>(.*?)</Abstract>", efetch_resp.text, re.DOTALL)
                if match:
                    abstract = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        if abstract and abstract.strip() != "":
            journal = result.get("fulljournalname", "Unknown Journal")
            pub_date = result.get("pubdate", "2026")
            authors = ", ".join([a["name"] for a in result.get("authors", [])[:3]])
            articles.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "pub_date": pub_date,
                "authors": authors
            })
        if len(articles) >= count:
            break
    if not articles:
        raise Exception("No suitable articles found.")
    return articles

def generate_original_review(articles, topic):
    summaries = []
    for a in articles[:8]:
        summaries.append(f"PMID {a['pmid']}: {a['title']} ({a['journal']}, {a['pub_date']}) - {a['abstract'][:300]}")
    combined = "\n".join(summaries)
    
    prompt = f"""You are a medical writer. Write an **original review article** on the topic '{topic}'. 
Base your review on the following recent PubMed papers, but do NOT simply copy their abstracts. 
Instead, synthesise the information into a coherent, critical review with the following sections:

1. **Introduction** – background and why this topic is important.
2. **Summary of Current Evidence** – key findings from the literature.
3. **Clinical Implications** – what this means for practice or research.
4. **Conclusion** – a brief summary and future directions.

After the conclusion, list the **References** in Vancouver style (numbered, with authors, title, journal, year, PMID).

The article should be approximately 800–1000 words. Use clear, professional language suitable for clinicians and researchers.

Here are the papers:
{combined}

Return ONLY the review article content (including the references list), no extra commentary."""
    return llm_generate(prompt, max_tokens=2000)

# ---------- GitHub upload helper (now targets Journal/ folder) ----------
def upload_file_to_website(file_path, remote_path, commit_message):
    headers = {"Authorization": f"token {WEBSITE_REPO_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    get_url = f"{GITHUB_API}/repos/{REPO}/contents/{remote_path}"
    resp = requests.get(get_url, headers=headers, timeout=30)
    sha = None
    if resp.status_code == 200:
        sha = resp.json().get("sha")
    with open(file_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()
    payload = {"message": commit_message, "content": content_b64, "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    put_url = f"{GITHUB_API}/repos/{REPO}/contents/{remote_path}"
    put_resp = requests.put(put_url, headers=headers, json=payload, timeout=30)
    if put_resp.status_code in (201, 200):
        logging.info(f"Uploaded {remote_path} to website repo.")
    else:
        raise Exception(f"Failed to upload {remote_path}: {put_resp.status_code} {put_resp.text}")

# ---------- Attractive HTML template (matches your journal design) ----------
def create_attractive_html(title, review_content, topic, today):
    # Build a simple Vancouver reference list (if not already included by AI)
    # We assume review_content already contains "References" section.
    # If not, we could extract from the generated text.
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Original Review: {title[:80]}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f4f8; color: #1e2a3a; line-height: 1.5; }}
        .navbar {{ background: #0d47a1; padding: 15px 20px; text-align: center; }}
        .navbar a {{ color: white; text-decoration: none; margin: 0 15px; font-weight: 500; }}
        .journal-header {{ background: linear-gradient(135deg, #0a2b4e, #1e4a76); color: white; text-align: center; padding: 50px 20px; }}
        .journal-header h1 {{ font-size: 2.5rem; margin-bottom: 10px; }}
        .container {{ max-width: 1100px; margin: 30px auto; padding: 0 20px; display: flex; flex-wrap: wrap; gap: 30px; }}
        .main {{ flex: 3; background: white; border-radius: 16px; padding: 35px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .sidebar {{ flex: 1; background: white; border-radius: 16px; padding: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); align-self: start; }}
        .sidebar h3 {{ background: #0d47a1; color: white; padding: 10px; margin: -25px -25px 20px -25px; border-radius: 16px 16px 0 0; }}
        h1 {{ color: #0d47a1; font-size: 1.8rem; margin-bottom: 15px; }}
        .meta {{ color: #5a7e9a; margin-bottom: 20px; font-size: 0.9rem; }}
        .review-body {{ font-size: 1.05rem; line-height: 1.7; }}
        .review-body h2 {{ color: #0d47a1; margin: 25px 0 10px; font-size: 1.4rem; }}
        .review-body p {{ margin-bottom: 1rem; text-align: justify; }}
        .review-body .references {{ margin-top: 30px; border-top: 1px solid #ddd; padding-top: 20px; font-size: 0.9rem; }}
        .cta {{ background: #e3f2fd; padding: 15px; border-radius: 12px; margin-top: 30px; text-align: center; }}
        .footer {{ background: #0f2a38; color: #8aaec0; text-align: center; padding: 20px; margin-top: 30px; }}
        .footer a {{ color: #ffaa33; }}
        @media (max-width: 800px) {{ .container {{ flex-direction: column; }} }}
    </style>
</head>
<body>
    <div class="navbar">
        <a href="index.html">Home</a>
        <a href="aims-scope.html">Aims & Scope</a>
        <a href="editorial-board.html">Editorial Board</a>
        <a href="author-guidelines.html">Author Guidelines</a>
        <a href="submit.html">Submit Article</a>
    </div>
    <div class="journal-header">
        <h1>Global Journal of Medical Research</h1>
        <p>Published by Knowledge Framework Consulting | ISSN: Applied for | Volume 1, Issue 1 | June 2026</p>
    </div>
    <div class="container">
        <div class="main">
            <h1>{title}</h1>
            <div class="meta">Published: {today} | Co-Chief Editors: Abhishek Bansal & Dr. Praveen Parshant</div>
            <div class="review-body">
                {review_content}
            </div>
            <div class="cta">
                <strong>Need help with your own medical manuscript?</strong><br>
                Visit <a href="https://kfcwriters.github.io">kfcwriters.github.io</a> or WhatsApp +91 9812018036.
            </div>
        </div>
        <div class="sidebar">
            <h3>Journal Information</h3>
            <p><strong>Publisher:</strong> Knowledge Framework Consulting</p>
            <p><strong>Co-Chief Editors:</strong> Abhishek Bansal & Dr. Praveen Parshant</p>
            <p><strong>Email:</strong> kfcwriters@gmail.com</p>
            <hr>
            <h3>For Authors</h3>
            <ul>
                <li><a href="aims-scope.html">Aims & Scope</a></li>
                <li><a href="author-guidelines.html">Author Guidelines</a></li>
                <li><a href="submit.html">Submit an Article</a></li>
            </ul>
        </div>
    </div>
    <div class="footer">
        <p>© 2026 Knowledge Framework Consulting. All rights reserved. | <a href="https://kfcwriters.github.io">Main Site</a> | <a href="mailto:kfcwriters@gmail.com">Contact</a></p>
    </div>
</body>
</html>"""
    return html_template

def main():
    logging.info("=== Daily Medical Journal Digest (Attractive Version) ===")
    try:
        topic = "recent advances in acne treatment OR post-inflammatory hyperpigmentation OR dermatology clinical practice"
        articles = fetch_pubmed_articles(topic, count=8)
        review_content = generate_original_review(articles, topic)
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        # Extract a short title from the first sentence of the review
        first_para = review_content.split("\n")[0][:100]
        title = f"Original Review: {topic[:80]}"
        html = create_attractive_html(title, review_content, topic, today)
        
        filename = f"review-{today}.html"
        with open("temp_review.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        # Upload to Journal/ folder
        upload_file_to_website("temp_review.html", f"{JOURNAL_FOLDER}/{filename}", f"Add attractive review for {today}")
        
        logging.info(f"Article published: {filename}")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
