import os, sys, logging, requests, json, random

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
HIRE_ME_URL = os.environ["HIRE_ME_URL_NUTRITION"]   # NutriAid Carrd page

KEYWORDS = [
    "healthy eating tips for diabetes",
    "PCOS diet management",
    "obesity weight loss nutrition",
    "hypertension diet plan",
    "thyroid diet recommendations",
    "insulin resistance meal planning",
    "renal diet for kidney health",
    "gout diet foods to avoid",
    "anti-inflammatory foods list",
    "balanced diet for metabolic syndrome"
]

def llm_generate(prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role":"user","content":prompt}],
               "temperature":0.8, "max_completion_tokens":2048}
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    raise Exception(f"Groq error {resp.status_code}")

keyword = random.choice(KEYWORDS)

title_prompt = f"Generate a catchy, SEO-optimized blog title targeting the keyword '{keyword}'. Return only the title."
title = llm_generate(title_prompt).strip().strip('"')

body_intro = (
    "Managing your diet when you have a medical condition can be confusing. "
    "This article provides science‑backed nutrition tips to help you make informed choices and improve your well‑being.\n\n"
)

body_prompt = f"""Write a 500‑word purely educational blog article with the title "{title}". Start with an empathetic note about the struggle of eating right with a health condition. Then provide 3‑4 practical dietary tips (e.g., what to eat, what to avoid, meal timing). Do NOT mention any services, products, or prices. End with a very short, neutral note: 'For more nutrition resources, you can visit {HIRE_ME_URL}.' Write in Markdown."""
body = llm_generate(body_prompt)
full_body = body_intro + body

# Publish directly to Dev.to
payload = {
    "article": {
        "title": title,
        "body_markdown": full_body,
        "published": True,
        "tags": ["nutrition", "diet", "health"]
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
