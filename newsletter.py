import os, sys, logging, requests, json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
BUTTONDOWN_API_KEY = os.environ["BUTTONDOWN_API_KEY"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]

def get_weekly_articles():
    username = "kfc_writers_12f474fa70382"
    url = f"https://dev.to/api/articles?username={username}&per_page=20&tag=medical"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Dev.to API error: {resp.status_code}")
    articles = resp.json()
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent = []
    for a in articles:
        pub = a.get("published_at")
        if pub:
            pub_date = datetime.strptime(pub, "%Y-%m-%dT%H:%M:%SZ")
            if pub_date >= cutoff:
                recent.append(a)
    return recent[:3]

def generate_newsletter(articles):
    if not articles:
        return None, "No medical writing articles this week. Check back next Sunday!"
    summaries = []
    for a in articles:
        title = a["title"]
        url = a["url"]
        prompt = f"Write a 2‑sentence summary of this article that makes the reader want to click: {title}\n\n{url}"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "openrouter/auto", "messages": [{"role":"user","content":prompt}], "temperature":0.7, "max_tokens":100}
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            summaries.append({
                "title": title,
                "url": url,
                "summary": resp.json()["choices"][0]["message"]["content"].strip()
            })
    html = "<h2>This Week's Best Medical Writing Tips</h2><p>Here are your top articles for the week:</p>"
    for s in summaries:
        html += f'<h3><a href="{s["url"]}">{s["title"]}</a></h3><p>{s["summary"]}</p>'
    html += f'<hr><p>Need help with your medical writing? <a href="{HIRE_ME_URL}">Contact us</a> or WhatsApp: +91 9812018036</p>'
    subject = f"Medical Writing Tips – {datetime.utcnow().strftime('%B %d, %Y')}"
    return subject, html

def send_to_buttondown(subject, body_html):
    url = "https://api.buttondown.email/v1/emails"
    headers = {
        "Authorization": f"Token {BUTTONDOWN_API_KEY}",
        "Content-Type": "application/json"
    }
    # Schedule for 1 minute in the future – Buttondown sends it immediately
    send_time = (datetime.utcnow() + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "subject": subject,
        "body": body_html,
        "status": "scheduled",
        "scheduled_at": send_time
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code == 201:
        logging.info("Newsletter scheduled (will send within 1 minute).")
    else:
        logging.error(f"Buttondown API error: {resp.status_code} {resp.text}")

def main():
    logging.info("=== Weekly Newsletter ===")
    try:
        articles = get_weekly_articles()
        subject, body = generate_newsletter(articles)
        send_to_buttondown(subject, body)
        logging.info("=== Done ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
