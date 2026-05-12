import os, sys, logging, requests, json, random

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]

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
    url = "https://text.pollinations.ai/openai"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 2048
    }
    resp = requests.post(url, headers=headers, json=data, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

keyword = random.choice(KEYWORDS)

title_prompt = f"Generate a catchy, SEO-optimized blog title targeting the keyword '{keyword}'. The title should appeal to researchers, PhD students, or doctors. Return only the title."
title = llm_generate(title_prompt).strip().strip('"')

body_intro = (
    "Need help with your medical thesis, manuscript, or journal submission? "
    "I provide end‑to‑end medical writing services—from synopsis planning and complete thesis writing to article preparation and publication support. "
    "Below, we share practical advice for navigating academic writing efficiently.\n\n"
)

body_prompt = f"""Write a 500‑word blog article with the title "{title}". Start with a brief empathetic paragraph about the challenges of academic medical writing. Then provide 3‑4 practical tips (e.g., structuring a thesis synopsis, choosing the right journal, improving manuscript clarity). End with a clear call‑to‑action: 'Need professional help with your medical writing project? Visit {HIRE_ME_URL} to learn more about my services.' Write in Markdown."""
body = llm_generate(body_prompt)
full_body = body_intro + body

payload = {
    "article": {
        "title": title,
        "body_markdown": full_body,
        "published": True,
        "tags": ["medical", "writing", "research"]
    }
}
headers = {"Content-Type": "application/json", "api-key": DEVTO_API_KEY}
resp = requests.post("https://dev.to/api/articles", headers=headers, json=payload)

if resp.status_code == 201:
    logging.info(f"Published on Dev.to: {resp.json()['url']}")
else:
    logging.error(f"Dev.to error: {resp.status_code} - {resp.text}")
