import os, sys, logging, requests, json, random

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]   # KFC Writers Carrd page

KEYWORDS = [
    "how to write a medical manuscript",
    "medical case report structure",
    "literature review tips for PhD",
    "journal submission process explained",
    "thesis synopsis planning guide",
    "research article writing advice",
    "medical editing best practices",
    "academic writing for clinicians",
    "scientific writing techniques",
    "getting published in medical journals"
]

def llm_generate(prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",          # ← known working model
        "messages": [{"role":"user","content":prompt}],
        "temperature":0.8,
        "max_completion_tokens":2048
    }
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    raise Exception(f"Groq error {resp.status_code}: {resp.text}")

keyword = random.choice(KEYWORDS)
title_prompt = f"Generate a catchy, SEO-optimized blog title targeting the keyword '{keyword}'. Return only the title."
title = llm_generate(title_prompt).strip().strip('"')

body_intro = (
    "Writing a strong medical manuscript or thesis can be challenging, but with the right approach you can make your work shine. "
    "In this article, we share practical, actionable advice to help you plan, structure, and polish your medical and scientific writing.\n\n"
)

body_prompt = f"""Write a 500‑word purely educational blog article with the title "{title}". Start by acknowledging the difficulty of medical writing. Then give 3‑4 concrete tips (e.g., outline first, use clear language, follow journal guidelines, revise ruthlessly). Do NOT mention any services, products, or prices. End with a very short, neutral note: 'For more writing resources, you can visit {HIRE_ME_URL}.' Write in Markdown."""
body = llm_generate(body_prompt)
full_body = body_intro + body

# Publish directly to Dev.to
payload = {
    "article": {
        "title": title,
        "body_markdown": full_body,
        "published": True,
        "tags": ["medical", "writing", "research"]
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
