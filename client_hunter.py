import os, sys, logging, json, requests, time
from pathlib import Path
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

SERPER_API_KEY = os.environ["SERPER_API_KEY"]
MINELEAD_API_KEY = os.environ["MINELEAD_API_KEY"]
BREVO_API_KEY = os.environ["BREVO_API_KEY"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
YOUR_EMAIL = os.environ["YOUR_EMAIL"]

SENT_LOG = ".sent_emails_log.json"
MAX_EMAILS_PER_DAY = 5

def search_leads():
    queries = [
        '"medical writer needed" OR "medical writing services" OR "manuscript editing"',
        '"need a medical writer" OR "looking for medical editor" OR "help with case report"',
        '"thesis writing service" OR "medical manuscript help" OR "journal submission help"',
    ]
    all_leads = []
    for query in queries:
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        payload = {"q": query, "num": 5}
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            logging.warning(f"Serper error {resp.status_code} for query: {query}")
            continue
        results = resp.json().get("organic", [])
        for r in results:
            link = r.get("link", "")
            if link:
                domain = urlparse(link).netloc
                all_leads.append({
                    "domain": domain,
                    "source_url": link,
                    "snippet": r.get("snippet", "")[:300]
                })
    seen = set()
    unique = [lead for lead in all_leads if not (lead["domain"] in seen or seen.add(lead["domain"]))]
    logging.info(f"Found {len(unique)} unique leads.")
    return unique[:MAX_EMAILS_PER_DAY]

def find_email_minelead(domain):
    url = f"https://api.minelead.io/v1/search/?domain={domain}&key={MINELEAD_API_KEY}&max-emails=1"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            logging.warning(f"Minelead error {resp.status_code} for {domain}")
            return None
        data = resp.json()
        emails = data if isinstance(data, list) else data.get("emails", [])
        if emails and len(emails) > 0:
            return emails[0].get("email") or emails[0].get("value")
    except Exception as e:
        logging.warning(f"Minelead exception for {domain}: {e}")
    return None

def generate_email(domain, snippet):
    prompt = f"""You are an outreach specialist for KFC - Knowledge Framework Consulting, a professional medical writing service.

We found a potential lead:
- Company/Website: {domain}
- Context from their page: {snippet}

Write a short, warm, personalized cold email to pitch our medical writing services (thesis writing, manuscript editing, journal submission, case reports, literature reviews).

Rules:
- Keep it under 150 words, sound human
- Mention something specific from their context
- MUST include our website: kfcwriters.github.io
- Include WhatsApp: +91 9812018036
- End with: "Would you be open to a quick chat?"
- Return ONLY the email body, no subject line."""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "openrouter/auto", "messages": [{"role":"user","content":prompt}], "temperature":0.8, "max_tokens":500}
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    return None

def send_email_via_brevo(to_email, subject, html_body):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"api-key": BREVO_API_KEY, "Content-Type": "application/json"}
    payload = {
        "sender": {"email": YOUR_EMAIL, "name": "KFC - Knowledge Framework Consulting"},
        "to": [{"email": to_email}],
        "bcc": [{"email": YOUR_EMAIL}],
        "subject": subject,
        "htmlContent": html_body
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code == 201:
        logging.info(f"Email sent to {to_email}")
        return True
    else:
        logging.error(f"Brevo error: {resp.status_code} {resp.text}")
        return False

def main():
    logging.info("=== Daily Client Hunter ===")
    sent = {}
    if Path(SENT_LOG).exists():
        with open(SENT_LOG) as f:
            sent = json.load(f)

    leads = search_leads()
    sent_count = 0

    skip_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
                    "reddit.com", "quora.com", "youtube.com", "facebook.com",
                    "twitter.com", "instagram.com", "linkedin.com"]

    for lead in leads:
        domain = lead["domain"]
        if domain in sent or any(s in domain for s in skip_domains):
            continue

        logging.info(f"Processing: {domain}")
        email_addr = find_email_minelead(domain)
        if not email_addr:
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
        if send_email_via_brevo(email_addr, "Medical writing support for your team", html):
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
