import os, sys, logging, requests, json, random

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
HASKNODE_TOKEN = os.environ["HASKNODE_TOKEN"]
HASKNODE_HOST = os.environ["HASKNODE_PUBLICATION_ID"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]

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
    "Master biochemistry with one‑on‑one online tutoring tailored to your syllabus. "
    "I help medical, pharmacy, and life science students build a strong conceptual foundation in biochemistry. "
    "Below, discover study strategies and exam tips for biochemistry.\n\n"
)

body_prompt = f"""Write a 500‑word blog article with the title "{title}". Start with a brief empathetic paragraph about why biochemistry feels overwhelming. Then provide 3‑4 practical study or exam tips (e.g., understanding pathways, mnemonics, integrating clinical relevance). End with a call‑to‑action: 'Need personalised biochemistry tutoring? Visit {HIRE_ME_URL} to book a free trial session.' Write in Markdown."""
body = llm_generate(body_prompt)
full_body = body_intro + body

cache_file = ".pubid_biochem"
pub_id = None
if os.path.exists(cache_file):
    with open(cache_file) as f: pub_id = f.read().strip()
if not pub_id:
    query = """query($host: String!) { publication(host: $host) { id } }"""
    variables = {"host": HASKNODE_HOST}
    headers = {"Authorization": HASKNODE_TOKEN, "Content-Type": "application/json"}
    resp = requests.post("https://gql.hashnode.com/", json={"query": query, "variables": variables}, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("data", {}).get("publication"):
            pub_id = data["data"]["publication"]["id"]
            with open(cache_file, "w") as f: f.write(pub_id)
        else:
            raise Exception(f"Publication not found for host {HASKNODE_HOST}. Check the domain and token.")
if not pub_id:
    raise Exception("Cannot get publication ID")

mutation = """mutation PublishPost($input: PublishPostInput!) { publishPost(input: $input) { post { slug, url } } }"""
variables = {"input": {
    "title": title,
    "contentMarkdown": full_body,
    "publicationId": pub_id,
    "tags": [
        {"slug": "biochemistry", "name": "Biochemistry"},
        {"slug": "tutoring", "name": "Tutoring"},
        {"slug": "medical-education", "name": "Medical Education"}
    ]
}}
headers = {"Authorization": HASKNODE_TOKEN, "Content-Type": "application/json"}
resp = requests.post("https://gql.hashnode.com/", json={"query": mutation, "variables": variables}, headers=headers)
if resp.status_code == 200:
    data = resp.json()
    if "errors" in data:
        logging.error(json.dumps(data["errors"]))
    else:
        slug = data["data"]["publishPost"]["post"]["slug"]
        logging.info(f"Article published: {HASKNODE_HOST}/{slug}")
else:
    logging.error(resp.text)
