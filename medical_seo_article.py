import os, sys, logging, requests, json, random
from get_link import get_latest_product_link

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
HIRE_ME_URL = os.environ.get("HIRE_ME_URL", "https://kfcwriters.github.io")
PRODUCT_LINK = get_latest_product_link()   # <-- FIX: use product link

KEYWORDS = [
    "telemedicine benefits",
    "medical writing for beginners",
    "how to publish a case report",
    "medical manuscript editing tips",
    "thesis writing help medical",
]

def llm_generate(prompt):
    url = "https://text.pollinations.ai/openai"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 2048
    }
    resp = requests.post(url, headers=headers, json=data, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"Pollinations error {resp.status_code}: {resp.text}")
    result = resp.json()
    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, TypeError):
        return str(result["choices"][0].get("text", ""))

keyword = random.choice(KEYWORDS)

title_prompt = f"Generate a catchy, SEO-optimized blog title targeting the keyword '{keyword}'. Return only the title."
title = llm_generate(title_prompt).strip().strip('"')

body_intro = (
    "Master medical writing with one‑on‑one online tutoring tailored to your syllabus. "
    "I help medical, pharmacy, and life science students build a strong conceptual foundation. "
    "Below, discover study strategies and exam tips.\n\n"
)

# The prompt now includes the product link as a natural call‑to‑action
body_prompt = f"""Write a 500‑word blog article with the title "{title}". Start with a brief empathetic paragraph about why medical writing feels overwhelming. Then provide 3‑4 practical tips (e.g., structuring a manuscript, avoiding common mistakes). End with a very short, neutral note: 'Need a step‑by‑step guide? Grab my [medical writing checklist]({PRODUCT_LINK}) for only $4.99.' Write in Markdown. Do NOT mention any other services or prices."""
body = llm_generate(body_prompt)
full_body = body_intro + body

payload = {
    "article": {
        "title": title,
        "body_markdown": full_body,
        "published": True,
        "tags": ["medical", "writing", "education"]
    }
}
headers = {"Content-Type": "application/json", "api-key": DEVTO_API_KEY}
resp = requests.post("https://dev.to/api/articles", headers=headers, json=payload)

if resp.status_code == 201:
    logging.info(f"Published on Dev.to: {resp.json()['url']}")
else:
    logging.error(f"Dev.to error: {resp.status_code} - {resp.text}")
