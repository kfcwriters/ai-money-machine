import os, sys, logging, requests, random, re, html
import xml.etree.ElementTree as ET
from ai_helper import llm_generate

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

AMAZON_AFFILIATE_LINK = os.environ["AMAZON_AFFILIATE_LINK"]

TOPICS = [
    "best budget laptops for programming",
    "top noise-cancelling headphones for remote work",
    "essential home office gadgets under $50",
    "best standing desk converters for small spaces",
    "top ergonomic mouse for wrist pain",
    "best wireless keyboards for productivity",
    "must-have kitchen gadgets for meal prep",
    "best smart home devices for beginners",
    "top fitness trackers under $100",
    "best portable chargers for travel",
]

def get_topic():
    try:
        rss = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        resp = requests.get(rss, timeout=30)
        clean_text = html.unescape(resp.text)
        root = ET.fromstring(clean_text)
        titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
        if titles:
            return random.choice(titles)
    except:
        pass
    return random.choice(TOPICS)

def generate_article(topic):
    prompt = f"""You are a helpful product reviewer. Write a 500‑word blog post about "{topic}".
Structure:
# [Catchy title about {topic}]
## Introduction (explain why this product category matters)
## 3–4 practical tips or features to look for (bulleted)
## One natural product recommendation: "If you're looking for a great option, I recommend checking out [this highly-rated choice on Amazon]({AMAZON_AFFILIATE_LINK}). It's the one I suggest to friends."
## Encouraging conclusion.
Write in Markdown. No pushy sales language."""
    raw = llm_generate(prompt)
    title_match = re.search(r"^#\s*(.+?)$", raw, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else f"Best {topic}"
    body = re.sub(r"^#\s*.+?\n", "", raw, count=1).strip()
    return title, body

def main():
    logging.info("=== Amazon Affiliate Content Machine ===")
    topic = get_topic()
    logging.info(f"Topic: {topic}")
    title, body = generate_article(topic)
    with open(".latest_article_title", "w") as f: f.write(title)
    with open(".latest_article_body", "w") as f: f.write(body)
    logging.info("Article generated and saved.")
    logging.info("=== Done ===")

if __name__ == "__main__":
    main()
