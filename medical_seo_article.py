import os, sys, logging, requests, json, random

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
HASKNODE_TOKEN = os.environ["HASKNODE_TOKEN"]
HASKNODE_HOST = os.environ["HASKNODE_PUBLICATION_ID"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]

KEYWORDS = [
    "hire a medical writer for manuscript editing",
    "case report writing service for doctors",
    "medical literature review writer for hire",
    "professional medical writing services for pharma",
    "help with journal submission and formatting",
    "medical editor needed for clinical research",
    "freelance medical writer for hire",
    "manuscript editing and proofreading service",
    "medical writing help for busy clinicians",
    "expert medical writer for case reports",
    "thesis synopsis planning service",
    "complete thesis writing help",
    "research article writing for journals",
    "journal submission and formatting support",
    "literature review writing for PhD",
    "medical writing services for clinicians",
    "hire a medical writer for thesis",
    "case report writing and publishing",
    "help with manuscript editing and submission",
    "medical thesis writer for hire",
    "academic medical writing services",
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

cache_file = ".pubid"
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
        {"slug": "medical-writing", "name": "Medical Writing"},
        {"slug": "thesis", "name": "Thesis"},
        {"slug": "research", "name": "Research"}
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
