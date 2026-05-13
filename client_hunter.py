import os, sys, logging, json, requests, time, base64, re
from pathlib import Path
from urllib.parse import urlparse, quote_plus
from email.message import EmailMessage

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

SERPER_API_KEY = os.environ["SERPER_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]   # for AI email generation (free)
YOUR_EMAIL = os.environ["YOUR_EMAIL"]
GMAIL_CLIENT_ID = os.environ["GMAIL_CLIENT_ID"]
GMAIL_CLIENT_SECRET = os.environ["GMAIL_CLIENT_SECRET"]
GMAIL_REFRESH_TOKEN = os.environ["GMAIL_REFRESH_TOKEN"]

SENT_LOG = ".sent_emails_log.json"
MAX_EMAILS_PER_DAY = 8

# ─────────────── Gmail token helper ───────────────
def get_access_token():
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": GMAIL_CLIENT_ID,
        "client_secret": GMAIL_CLIENT_SECRET,
        "refresh_token": GMAIL_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    })
    if resp.status_code != 200:
        raise Exception(f"Failed to get access token: {resp.text}")
    return resp.json()["access_token"]

# ─────────────── 1. FIND CONTACT PAGES ───────────────
def search_contact_pages():
    """Find contact pages of sites that also mention medical writing, editing, or research services."""
    queries = [
        'site:.edu "medical writing" OR "manuscript editing" OR "thesis writing" contact us',
        'site:.org "medical writing services" OR "research editing" contact OR email',
        'site:.ac.in "medical writer" OR "journal submission" contact us',
        'site:.gov "medical writing" OR "manuscript editing" contact',
    ]
    leads = []
    for query in queries:
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        payload = {"q": query, "num": 8}
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            logging.warning(f"Serper error {resp.status_code} for query: {query}")
            continue
        for r in resp.json().get("organic", []):
            link = r.get("link", "")
            if link:
                domain = urlparse(link).netloc
                leads.append({"domain": domain, "contact_url": link, "snippet": r.get("snippet", "")[:300]})
    # Remove duplicate domains
    seen = set()
    unique = []
    for lead in leads:
        if lead["domain"] not in seen:
            seen.add(lead["domain"])
            unique.append(lead)
    logging.info(f"Found {len(unique)} unique contact pages.")
    return unique[:MAX_EMAILS_PER_DAY]

# ─────────────── 2. EXTRACT EMAIL FROM CONTACT PAGE ───────────────
def extract_email_from_page(url):
    """Scrape the contact page and return the first email address found."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            # Common email patterns
            emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", resp.text)
            if emails:
                # Exclude obvious non-personal emails
                for email in emails:
                    if not any(x in email.lower() for x in ["noreply", "no-reply", "admin", "support", "info@"]):
                        return email
    except Exception as e:
        logging.debug(f"Could not scrape {url}: {e}")
    return None

# ─────────────── 3. GENERATE PERSONALISED PITCH ───────────────
def generate_email(domain, snippet):
    prompt = f"""You are an outreach specialist for KFC - Knowledge Framework Consulting, a professional medical writing service.

We found a potential lead:
- Company/Website: {domain}
- Context from their page: {snippet}

Write a short, warm, personalised cold email to pitch our medical writing services (thesis writing, manuscript editing, journal submission, case reports, literature reviews).

Rules:
- Keep it under 150 words, sound human
- Mention something specific from their context
- MUST include our website: kfcwriters.github.io
- Include WhatsApp: +91 9812018036
- End with: "Would you be open to a quick chat?"
- Return ONLY the email body, no subject line."""
    url = "https://text.pollinations.ai/openai"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 500
    }
    resp = requests.post(url, headers=headers, json=data, timeout=60)
    if resp.status_code == 200:
        result = resp.json()
        try:
            return result["choices"][0]["message"]["content"].strip()
        except (KeyError, TypeError):
            return None
    return None

# ─────────────── 4. SEND VIA GMAIL ───────────────
def send_email_via_gmail(to_email, subject, html_body):
    token = get_access_token()
    msg = EmailMessage()
    msg["From"] = f"KFC - Knowledge Framework Consulting <{YOUR_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content("Please view this email in HTML format.")
    msg.add_alternative(html_body, subtype="html")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"raw": raw})
    if resp.status_code == 200:
        logging.info(f"Email sent to {to_email}")
        return True
    else:
        logging.error(f"Gmail API error: {resp.status_code} {resp.text}")
        return False

# ─────────────── MAIN ───────────────
def main():
    logging.info("=== Enhanced Client Hunter ===")
    sent = {}
    if Path(SENT_LOG).exists():
        with open(SENT_LOG) as f:
            sent = json.load(f)

    leads = search_contact_pages()
    sent_count = 0

    for lead in leads:
        domain = lead["domain"]
        if domain in sent:
            continue
        logging.info(f"Processing: {domain}")
        email_addr = extract_email_from_page(lead["contact_url"])
        if not email_addr:
            logging.info(f"No email found on {domain}, skipping.")
            continue

        body = generate_email(domain, lead["snippet"])
        if not body:
            continue

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <p style="white-space: pre-line;">{body}</p>
            <br>
            <p style="color: #888; font-size: 12px;">
                --<br>
                KFC - Knowledge Framework Consulting<br>
                📞 WhatsApp: +91 9812018036<br>
                🌐 kfcwriters.github.io
            </p>
        </div>
        """
        send_email_via_gmail(email_addr, "Medical writing support for your team", html)
        sent[domain] = True
        sent_count += 1
        time.sleep(3)
        if sent_count >= MAX_EMAILS_PER_DAY:
            break

    with open(SENT_LOG, "w") as f:
        json.dump(sent, f)
    logging.info(f"=== Done: {sent_count} emails sent ===")

if __name__ == "__main__":
    main()
