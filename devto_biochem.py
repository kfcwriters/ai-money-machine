import os, requests, logging, sys, json

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DEVTO_API_KEY = os.environ["DEVTO_API_KEY"]
HASKNODE_HOST = os.environ["HASKNODE_PUBLICATION_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]

def get_latest_article():
    query = """
    query($host: String!) {
      publication(host: $host) {
        posts(first: 1) {
          edges {
            node {
              title
              slug
              content {
                markdown
              }
            }
          }
        }
      }
    }
    """
    variables = {"host": HASKNODE_HOST}
    resp = requests.post("https://gql.hashnode.com/", json={"query": query, "variables": variables}, timeout=30)
    if resp.status_code != 200:
        logging.error(f"Hashnode API error: {resp.status_code}")
        return None, None, None

    data = resp.json()
    posts = data.get("data", {}).get("publication", {}).get("posts", {}).get("edges", [])
    if not posts:
        return None, None, None

    post = posts[0]["node"]
    title = post["title"]
    slug = post["slug"]
    content = post["content"]["markdown"]
    link = f"https://{HASKNODE_HOST}/{slug}"
    return title, content, link

def generate_intro(title):
    prompt = f"""Write a 1‑sentence compelling intro for a Dev.to article titled "{title}" about biochemistry tutoring. Keep it under 100 characters."""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role":"user","content":prompt}], "temperature":0.7, "max_completion_tokens":100}
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    return ""

def main():
    title, content, link = get_latest_article()
    if not title:
        logging.error("No published posts found on BioChemTutor Hashnode. Ensure the SEO article ran first.")
        sys.exit(1)

    intro = generate_intro(title)
    body = f"*Originally published on [BioChemTutor Blog]({link})*\n\n{intro}\n\n{content}\n\n---\n*Need biochemistry tutoring? Visit [BioChemTutor]({HIRE_ME_URL}).*"

    payload = {
        "article": {
            "title": title,
            "body_markdown": body,
            "published": True,
            "tags": ["biochemistry", "tutoring", "medical"]
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

if __name__ == "__main__":
    main()
