import os, sys, logging, random, re, html
import xml.etree.ElementTree as ET

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
    # Create a compelling title
    title_words = topic.split()
    title = " ".join(word.capitalize() for word in title_words)
    title = f"{title} – The One I Recommend to Everyone"

    # Persuasive body that naturally drives clicks
    body = f"""Let’s be honest: finding the right **{topic}** can be overwhelming.  
There are hundreds of choices, each promising the world. But most of them just don’t deliver.

After testing several popular options and reading countless customer reviews, I’ve narrowed it down to one clear winner.  
It stood out not just because of the price, but because it actually **solves the problem** you’re facing.

### Why I recommend this specific {topic}

✅ **Proven performance** – thousands of happy users can’t be wrong.  
✅ **Great value** – you get premium features without the premium price tag.  
✅ **Easy to use** – no complicated setup, works right out of the box.  
✅ **Solid reviews** – consistently rated 4+ stars across multiple platforms.

👉 **[Check it out here and see why everyone’s switching]({AMAZON_AFFILIATE_LINK})**

I’ve been using it myself, and the difference is night and day. Whether you’re a complete beginner or looking to upgrade your current setup, this is the one I’d put my money on.

**What to do next:** Click the link above, take a look at the reviews, and if it feels right, grab it.  
It ships fast, and you can always return it if it’s not what you expected – though I doubt you will.

---

*Happy shopping!*"""

    return title, body

def main():
    logging.info("=== Amazon Affiliate Content Machine ===")
    topic = get_topic()
    logging.info(f"Topic: {topic}")
    title, body = generate_article(topic)
    logging.info(f"Title: {title}")
    with open(".latest_article_title", "w") as f: f.write(title)
    with open(".latest_article_body", "w") as f: f.write(body)
    logging.info("Article generated and saved.")
    logging.info("=== Done ===")

if __name__ == "__main__":
    main()
