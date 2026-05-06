import os, requests, logging, sys, feedparser, re

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
HASKNODE_HOST = os.environ["HASKNODE_PUBLICATION_ID"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]

def get_latest_article():
    rss_url = f"https://{HASKNODE_HOST}/rss.xml"
    feed = feedparser.parse(rss_url)
    if feed.entries:
        entry = feed.entries[0]
        title = entry.title
        link = entry.link
        content = re.sub(r'<[^>]+>', '', entry.get("summary", ""))
        return title, content, link
    return None, None, None

def generate_intro(title):
    prompt = f"""Write a 1‑sentence compelling intro for a Dev.to article titled "{title}" to encourage readers to keep reading. Keep it under 100 characters."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 100
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code == 200:
        result = resp.json()
        return result["choices"][0]["message"]["content"].strip()
    return ""

def main():
    title, content, link = get_latest_article()
    if not title:
        logging.error("No article found on Hashnode.")
        sys.exit(1)
    intro = generate_intro(title)
    body = f"*Originally published on [my blog]({link})*\n\n{intro}\n\n{content}\n\n---\n*Need help with medical writing? Visit my [services page]({HIRE_ME_URL}).*"
    payload = {
        "article": {"title": title, "body_markdown": body, "published": True, "tags": ["productivity", "writing", "medical"]}
    }
    headers = {"Content-Type": "application/json", "api-key": DEVTO_API_KEY}
    resp = requests.post("https://dev.to/api/articles", headers=headers, json=payload)
    if resp.status_code == 201:
        logging.info(f"Published on Dev.to: {resp.json()['url']}")
    else:
        logging.error(f"Dev.to error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    main()
