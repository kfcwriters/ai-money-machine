import os, requests, logging, sys, feedparser, re

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
HASKNODE_HOST = os.environ["HASKNODE_PUBLICATION_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
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
    prompt = f"""Write a 1‑sentence compelling intro for a Dev.to article titled "{title}" about biochemistry tutoring. Keep it under 100 characters."""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_completion_tokens": 100}
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    return ""

def main():
    title, content, link = get_latest_article()
    if not title:
        logging.error("No article found on BioChemTutor Hashnode.")
        sys.exit(1)

    intro = generate_intro(title)
    body = f"*Originally published on [BioChemTutor Blog]({link})*\n\n{intro}\n\n{content}\n\n---\n*Need biochemistry tutoring? Visit [BioChemTutor]({HIRE_ME_URL}).*"

    payload = {
        "article": {
            "title": title,
            "body_markdown": body,
            "published": True,
            "tags": ["biochemistry", "tutoring", "medical"]
        }
    }
    headers = {
        "Content-Type": "application/json",
        "api-key": DEVTO_API_KEY
    }
    resp = requests.post("https://dev.to/api/articles", headers=headers, json=payload)

    if resp.status_code == 201:
        logging.info(f"Published on Dev.to: {resp.json()['url']}")
    else:
        logging.error(f"Dev.to error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    main()
