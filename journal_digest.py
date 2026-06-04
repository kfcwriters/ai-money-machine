import os, sys, logging, requests, urllib.parse, datetime, base64, re, json
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

WEBSITE_REPO_TOKEN = os.environ["WEBSITE_REPO_TOKEN"]
REPO = "kfcwriters/kfcwriters.github.io"
BRANCH = "main"
GITHUB_API = "https://api.github.com"

# ─────────── PubMed fetch (tries multiple records until one has an abstract) ───────────
def fetch_latest_pubmed():
    query = urllib.parse.quote("medical writing OR manuscript preparation OR journal submission")
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmax=5&sort=date&retmode=json"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"PubMed search failed: {resp.status_code}")
    ids = resp.json()["esearchresult"]["idlist"]
    if not ids:
        raise Exception("No PubMed articles found today – will try again tomorrow.")

    for pmid in ids:
        # 1. PubMed summary
        details_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
        details_resp = requests.get(details_url, timeout=30)
        if details_resp.status_code != 200:
            continue
        result = details_resp.json()["result"][pmid]
        title = result["title"]
        abstract = result.get("abstract", "")
        journal = result.get("fulljournalname", "Unknown Journal")
        pub_date = result.get("pubdate", "2026")
        authors = ", ".join([a["name"] for a in result.get("authors", [])[:3]])

        # 2. PubMed full record (efetch) if abstract missing
        if not abstract or abstract.strip() == "":
            logging.info(f"Abstract not found in summary for PMID {pmid}, trying full record…")
            efetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml&rettype=abstract"
            efetch_resp = requests.get(efetch_url, timeout=30)
            if efetch_resp.status_code == 200:
                match = re.search(r"<Abstract>(.*?)</Abstract>", efetch_resp.text, re.DOTALL)
                if match:
                    abstract = re.sub(r"<[^>]+>", "", match.group(1)).strip()

        # 3. Crossref fallback
        if not abstract or abstract.strip() == "":
            logging.info(f"Trying Crossref for PMID {pmid}…")
            crossref_url = f"https://api.crossref.org/works?query={urllib.parse.quote(title)}&rows=1"
            crossref_resp = requests.get(crossref_url, timeout=30)
            if crossref_resp.status_code == 200:
                items = crossref_resp.json().get("message", {}).get("items", [])
                if items:
                    abstract = items[0].get("abstract", "")
                    abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        if abstract and abstract.strip() != "":
            logging.info(f"Using PMID {pmid} with valid abstract.")
            return pmid, title, abstract, journal, pub_date, authors

    raise Exception("None of today's PubMed articles contained an abstract. Skipping digest.")

# ─────────── GitHub file upload helper ───────────
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

# ─────────── Get existing digest file names ───────────
def get_existing_digests():
    headers = {"Authorization": f"token {WEBSITE_REPO_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    url = f"{GITHUB_API}/repos/{REPO}/contents/digests"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 200:
        return [item["name"] for item in resp.json() if item["name"].endswith(".html") and item["name"] != "index.html"]
    return []

# ─────────── Read / write the titles log file ───────────
def get_titles_log():
    headers = {"Authorization": f"token {WEBSITE_REPO_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    url = f"{GITHUB_API}/repos/{REPO}/contents/digests/.titles.json"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 200:
        content = resp.json().get("content", "")
        if content:
            return json.loads(base64.b64decode(content).decode())
    return {}

def save_titles_log(titles):
    with open("temp_titles.json", "w") as f:
        json.dump(titles, f)
    upload_file_to_website("temp_titles.json", "digests/.titles.json", "Update digest titles log")

# ─────────── Build and upload the digest index page ───────────
def update_index_page(digests):
    titles = get_titles_log()
    digests.sort(reverse=True)
    links = "\n".join([
        f'<li><a href="{d}">{titles.get(d, d.replace("digest-","").replace(".html",""))}</a></li>'
        for d in digests
    ])
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Latest Medical Literature</title>
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
    <h1>Latest Medical Literature</h1>
    <p>Daily summaries of the latest published medical research.</p>
    <ul>
        {links}
    </ul>
    <p style="margin-top: 30px; font-size: 0.9em;">Need help with your own manuscript? <a href="https://kfcwriters.github.io">Visit our main site</a>.</p>
</body>
</html>"""
    with open("temp_index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    upload_file_to_website("temp_index.html", "digests/index.html", "Update digest index")

# ─────────── Main ───────────
def main():
    logging.info("=== Medical Journal Digest ===")
    try:
        pmid, title, abstract, journal, pub_date, authors = fetch_latest_pubmed()
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"digest-{today}.html"

        # ── Build citation string ──
        current_year = datetime.datetime.utcnow().strftime("%Y")
        month_day = datetime.datetime.utcnow().strftime("%B %d")
        citation = f"KFC Writers. ({current_year}, {month_day}). Research Digest: {title}. Retrieved from https://kfcwriters.github.io/digests/{filename}"

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Digest: {title}</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
        h1 {{ color: #0d47a1; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
        .abstract {{ font-size: 1.1em; white-space: pre-line; background: #f9f9f9; padding: 15px; border-radius: 5px; }}
        .citation {{ font-size: 0.9em; color: #555; margin-top: 20px; padding: 10px; background: #f0f0f0; border-radius: 5px; }}
        .disclaimer {{ font-size: 0.8em; color: #888; margin-top: 20px; border-top: 1px solid #ddd; padding-top: 10px; }}
        .cta {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p class="meta"><strong>Authors:</strong> {authors} | <strong>Journal:</strong> {journal} | <strong>Date:</strong> {pub_date} | <strong>PubMed ID:</strong> {pmid}</p>
    <hr>
    <h3>Abstract</h3>
    <div class="abstract">{abstract}</div>

    <div class="citation">
        <strong>How to Cite This Digest:</strong><br>
        {citation}
    </div>

    <div class="cta">
        <strong>Need help with your own medical manuscript?</strong><br>
        Visit <a href="https://kfcwriters.github.io">kfcwriters.github.io</a> or WhatsApp +91 9812018036.
    </div>
    <p class="disclaimer">This digest is an educational summary of a published research paper. The original article should be consulted directly for clinical or research purposes.</p>
</body>
</html>"""
        with open("temp_digest.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        # Upload the digest
        upload_file_to_website("temp_digest.html", f"digests/{filename}", f"Add research digest for {today}")

        # Update the titles log
        titles = get_titles_log()
        titles[filename] = title
        save_titles_log(titles)

        # Update the index page
        existing = get_existing_digests()
        if filename not in existing:
            existing.append(filename)
        update_index_page(existing)
        logging.info("=== Done ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
