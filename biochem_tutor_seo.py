import os, sys, logging, requests, json, random

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
HIRE_ME_URL = os.environ["HIRE_ME_URL_BIOCHEM"]

KEYWORDS = [
    "biochemistry tutor online",
    "biochemistry help for medical students",
    "enzyme kinetics tutoring",
    "metabolism Made Easy biochemistry",
    "molecular biology tutoring",
    "clinical biochemistry exam prep",
    "USMLE biochemistry coaching",
    "NEET PG biochemistry online tutor",
    "protein structure and function help",
    "biochemistry for nursing students tutoring"
]

def llm_generate(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com",       # optional, can be anything
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-3-8b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 2048
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"OpenRouter error {resp.status_code}: {resp.text}")
    result = resp.json()
    return result["choices"][0]["message"]["content"]

keyword = random.choice(KEYWORDS)
title_prompt = f"Generate a catchy, SEO-optimized blog title targeting the keyword '{keyword}'. Return only the title."
title = llm_generate(title_prompt).strip().strip('"')

body_intro = (
    "Master biochemistry with one‑on‑one online tutoring tailored to your syllabus. "
    "I help medical, pharmacy, and life science students build a strong conceptual foundation in biochemistry. "
    "Below, discover study strategies and exam tips for biochemistry.\n\n"
)

body_prompt = f"""Write a 500‑word blog article with the title "{title}". Start with a brief empathetic paragraph about why biochemistry feels overwhelming. Then provide 3‑4 practical study or exam tips (e.g., understanding pathways, mnemonics, integrating clinical relevance). End with a very short, neutral note: 'For more biochemistry resources, visit {HIRE_ME_URL}.' Write in Markdown. Do NOT mention any services or prices."""
body = llm_generate(body_prompt)
full_body = body_intro + body

payload = {
    "article": {
        "title": title,
        "body_markdown": full_body,
        "published": True,
        "tags": ["biochemistry", "tutoring", "medical"]
    }
}
headers = {"Content-Type": "application/json", "api-key": DEVTO_API_KEY}
resp = requests.post("https://dev.to/api/articles", headers=headers, json=payload)

if resp.status_code == 201:
    logging.info(f"Published on Dev.to: {resp.json()['url']}")
else:
    logging.error(f"Dev.to error: {resp.status_code} - {resp.text}")
