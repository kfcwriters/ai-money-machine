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
    # Force the AI to write about the EXACT topic and product category
    prompt = f"""You are a product reviewer. Your task is to write a blog post about "{topic}".

RULES:
- The title must be a catchy, original title about "{topic}" (do NOT repeat the topic word-for-word, rephrase it nicely).
- Start with an introduction that explains why this product category matters.
- Then give 3–4 practical features or tips someone should look for when buying such a product.
- At the end, include this exact sentence: "If you're looking for a great option, check out [this highly-rated pick on Amazon]({AMAZON_AFFILIATE_LINK})."
- Do NOT mention medicine, hypertension, clinical trials, or any medical topic. This is a consumer product review.
- Write in Markdown. No links to other sites.
- Total length: around 500 words."""

    raw = llm_generate(prompt)
    # Extract title from first Markdown heading
    title_match = re.search(r"^#\s*(.+?)$", raw, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        # Fix duplication like "Best best ..."
        words = title.split()
        seen = set()
        cleaned = []
        for w in words:
            low = w.lower()
            if low not in seen:
                cleaned.append(w)
                seen.add(low)
        title = " ".join(cleaned)
    else:
        title = f"Best {topic}"
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
