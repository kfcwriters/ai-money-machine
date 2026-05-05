import os, sys, logging, requests, json
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
HASKNODE_TOKEN = os.environ["HASKNODE_TOKEN"]
HASKNODE_HOST = os.environ["HASKNODE_PUBLICATION_ID"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]

def llm_generate(prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role":"user","content":prompt}], "temperature":0.8, "max_completion_tokens":2048}
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    raise Exception(f"Groq error {resp.status_code}")

title_prompt = """Generate a catchy, SEO-optimized title for a blog article that targets researchers, doctors, or PhD students looking to hire a medical writer. The article should promise practical advice on choosing a medical writer, writing case reports, or preparing manuscripts. Return only the title."""
title = llm_generate(title_prompt).strip().strip('"')

body_prompt = f"""Write a 500-word blog article with the title "{title}". The article should provide genuine value and naturally position my medical writing services as the solution. Include a call-to-action at the end: "Need professional help with your medical manuscript? Visit {HIRE_ME_URL} to learn more." Write in Markdown."""
body = llm_generate(body_prompt)

# Publish via Hashnode GraphQL (using publishPost mutation as before)
# First, get publication ID
cache_file = ".pubid"
pub_id = None
if os.path.exists(cache_file):
    with open(cache_file) as f: pub_id = f.read().strip()
else:
    query = """query($host: String!) { publication(host: $host) { id } }"""
    variables = {"host": HASKNODE_HOST}
    headers = {"Authorization": HASKNODE_TOKEN, "Content-Type": "application/json"}
    resp = requests.post("https://gql.hashnode.com/", json={"query": query, "variables": variables}, headers=headers)
    if resp.status_code == 200:
        pub_id = resp.json()["data"]["publication"]["id"]
        with open(cache_file, "w") as f: f.write(pub_id)

if not pub_id:
    raise Exception("Cannot get publication ID")

mutation = """mutation PublishPost($input: PublishPostInput!) { publishPost(input: $input) { post { slug, url } } }"""
variables = {"input": {"title": title, "contentMarkdown": body, "publicationId": pub_id, "tags": []}}
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
