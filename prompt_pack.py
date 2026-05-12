import os, sys, logging, requests, textwrap, random
from fpdf import FPDF

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GUMROAD_TOKEN = os.environ["GUMROAD_TOKEN"]

def generate_prompts():
    prompt = """You are an expert in medical and academic writing. Generate 10 high-quality, reusable ChatGPT prompts that help researchers, PhD students, or clinicians with tasks like:
- Writing a thesis synopsis
- Structuring a manuscript
- Preparing a case report
- Creating a literature review outline
- Drafting journal cover letters
- Improving academic tone
- Formatting references
- Summarising research findings
- Generating research questions
- Overcoming writer's block

Format each prompt as:
**Title**: <short descriptive title>
**Prompt**: <the full ChatGPT prompt>

Return them as a numbered list, with clear separation between each. Do not add extra commentary."""
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

# ... rest of create_pdf and publish_to_gumroad unchanged.
