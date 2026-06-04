import os, sys, logging, requests, urllib.parse, datetime, base64, re, json
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

WEBSITE_REPO_TOKEN = os.environ["WEBSITE_REPO_TOKEN"]
REPO = "kfcwriters/kfcwriters.github.io"
BRANCH = "main"
GITHUB_API = "https://api.github.com"

# ─────────── PubMed fetch (multiple articles) ───────────
def fetch_pubmed_articles(topic, count=8):
    """Fetch up to `count` recent PubMed articles for a topic."""
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
        # Fetch summary
        details_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
        details_resp = requests.get(details_url, timeout=30)
        if details_resp.status_code != 200:
            continue
        result = details_resp.json()["result"][pmid]
        title = result["title"]
        abstract = result.get("abstract", "")
        # Try full record if abstract missing
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

# ─────────── AI Original Review (using ai_helper) ───────────
from ai_helper import llm_generate

def generate_original_review(articles, topic):
    """Write a structured original review article synthesising the given papers."""
    # Build a concise summary of each article for the AI prompt
    summaries = []
    for a in articles[:8]:  # use up to 8 papers
        summaries.append(f"PMID {a['pmid']}: {a['title']} ({a['journal']}, {a['pub_date']}) - {a['abstract'][:300]}")
    combined = "\n".join(summaries)
    
    prompt = f"""You are a medical writer. Write a **original review article** on the topic '{topic}'. 
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

# ─────────── GitHub file upload helper (same as before) ───────────
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

def get_existing_articles():
    headers = {"Authorization": f"token {WEBSITE_REPO_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    url = f"{GITHUB_API}/repos/{REPO}/contents/reviews"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 200:
        return [item["name"] for item in resp.json() if item["name"].endswith(".html") and item["name"] != "index.html"]
    return []

def get_titles_log():
    headers = {"Authorization": f"token {WEBSITE_REPO_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    url = f"{GITHUB_API}/repos/{REPO}/contents/reviews/.titles.json"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 200:
        content = resp.json().get("content", "")
        if content:
            return json.loads(base64.b64decode(content).decode())
    return {}

def save_titles_log(titles):
    with open("temp_titles.json", "w") as f:
        json.dump(titles, f)
    upload_file_to_website("temp_titles.json", "reviews/.titles.json", "Update review titles log")

def update_index_page(articles):
    titles = get_titles_log()
    articles.sort(reverse=True)
    links = "\n".join([
        f'<li><a href="{a}">{titles.get(a, a.replace("review-","").replace(".html",""))}</a></li>'
        for a in articles
    ])
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Original Medical Reviews</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
        h1 {{ color: #0d47a1; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ margin: 10px 0; }}
        a {{ text-decoration: none; color: #0d47a1; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Original Medical Reviews</h1>
    <p>Peer‑reviewed, synthesised reviews of the latest medical research.</p>
    <ul>
        {links}
    </ul>
    <p style="margin-top: 30px; font-size: 0.9em;">Need help with your own manuscript? <a href="https://kfcwriters.github.io">Visit our main site</a>.</p>
</body>
</html>"""
    with open("temp_index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    upload_file_to_website("temp_index.html", "reviews/index.html", "Update review index")

# ─────────── Main ───────────
def main():
    logging.info("=== Original Medical Review Generator ===")
    try:
        # Choose a topic – you can rotate these or use a random selection
        topic = "recent advances in acne treatment OR post-inflammatory hyperpigmentation OR dermatology clinical practice"
        articles = fetch_pubmed_articles(topic, count=8)
        if not articles:
            raise Exception("No articles found for the selected topic.")
        
        review_content = generate_original_review(articles, topic)
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"review-{today}.html"
        
        # Build citation block
        current_year = datetime.datetime.utcnow().strftime("%Y")
        month_day = datetime.datetime.utcnow().strftime("%B %d")
        citation = f"KFC Writers. ({current_year}, {month_day}). Original Review: {topic}. KFC Journal of Medical Writing Reviews. Retrieved from https://kfcwriters.github.io/reviews/{filename}"
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Original Review: {topic}</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
        h1 {{ color: #0d47a1; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
        .review-body {{ font-size: 1.1em; white-space: pre-line; }}
        .citation {{ font-size: 0.9em; color: #555; margin-top: 20px; padding: 10px; background: #f0f0f0; border-radius: 5px; }}
        .disclaimer {{ font-size: 0.8em; color: #888; margin-top: 20px; border-top: 1px solid #ddd; padding-top: 10px; }}
        .cta {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; }}
    </style>
</head>
<body>
    <h1>Original Review: {topic}</h1>
    <p class="meta"><strong>Published:</strong> {today} | <strong>Journal:</strong> KFC Journal of Medical Writing Reviews</p>
    <hr>
    <div class="review-body">{review_content}</div>

    <div class="citation">
        <strong>How to Cite This Article:</strong><br>
        {citation}
    </div>

    <div class="cta">
        <strong>Need help with your own medical manuscript?</strong><br>
        Visit <a href="https://kfcwriters.github.io">kfcwriters.github.io</a> or WhatsApp +91 9812018036.
    </div>
    <p class="disclaimer">This article is an original review synthesised from peer‑reviewed literature. It does not replace the original research, which should be consulted directly for clinical decisions.</p>
</body>
</html>"""
        with open("temp_review.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Upload the review
        upload_file_to_website("temp_review.html", f"reviews/{filename}", f"Add original review for {today}")
        
        # Update titles log
        titles = get_titles_log()
        titles[filename] = f"Original Review: {topic}"
        save_titles_log(titles)
        
        # Update index page
        existing = get_existing_articles()
        if filename not in existing:
            existing.append(filename)
        update_index_page(existing)
        logging.info("=== Done ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
