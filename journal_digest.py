import os, sys, logging, requests, urllib.parse, datetime, base64
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

WEBSITE_REPO_TOKEN = os.environ["WEBSITE_REPO_TOKEN"]
REPO = "kfcwriters/kfcwriters.github.io"
BRANCH = "main"
GITHUB_API = "https://api.github.com"

def fetch_latest_pubmed():
    query = urllib.parse.quote("medical writing OR manuscript preparation OR journal submission")
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmax=5&sort=date&retmode=json"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"PubMed search failed: {resp.status_code}")
    ids = resp.json()["esearchresult"]["idlist"]
    if not ids:
        raise Exception("No PubMed articles found today – will try again tomorrow.")
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

def upload_file_to_website(file_path, remote_path, commit_message):
    headers = {"Authorization": f"token {WEBSITE_REPO_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    get_url = f"{GITHUB_API}/repos/{REPO}/contents/{remote_path}"
    resp = requests.get(get_url, headers=headers, timeout=30)
    sha = None
    if resp.status_code == 200:
        sha = resp.json().get("sha")
    with open(file_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()
    payload = {
        "message": commit_message,
        "content": content_b64,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha
    put_url = f"{GITHUB_API}/repos/{REPO}/contents/{remote_path}"
    put_resp = requests.put(put_url, headers=headers, json=payload, timeout=30)
    if put_resp.status_code in (201, 200):
        logging.info(f"Uploaded {remote_path} to website repo.")
    else:
        raise Exception(f"Failed to upload {remote_path}: {put_resp.status_code} {put_resp.text}")

def main():
    logging.info("=== Medical Journal Digest ===")
    try:
        pmid, title, abstract, journal, pub_date, authors = fetch_latest_pubmed()
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"digest-{today}.html"
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
        .disclaimer {{ font-size: 0.8em; color: #888; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }}
        .cta {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p class="meta"><strong>Authors:</strong> {authors} | <strong>Journal:</strong> {journal} | <strong>Date:</strong> {pub_date} | <strong>PubMed ID:</strong> {pmid}</p>
    <hr>
    <h3>Abstract</h3>
    <div class="abstract">{abstract}</div>
    <div class="cta">
        <strong>Need help with your own medical manuscript?</strong><br>
        Visit <a href="https://kfcwriters.github.io">kfcwriters.github.io</a> or WhatsApp +91 9812018036.
    </div>
    <p class="disclaimer">This digest is an educational summary of a published research paper. The original article should be consulted directly for clinical or research purposes.</p>
</body>
</html>"""
        with open("temp_digest.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        upload_file_to_website("temp_digest.html", f"digests/{filename}", f"Add research digest for {today}")
        logging.info("=== Done ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
