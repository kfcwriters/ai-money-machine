import os, sys, logging, requests
from ai_helper import llm_generate   # your bulletproof AI helper

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

FB_PAGE_ID = os.environ["FB_PAGE_ID"]
FB_PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]
HIRE_ME_URL = "https://kfcwriters.github.io"

def generate_post():
    prompt = f"""Write a short, helpful Facebook post (2‑3 sentences) about a medical writing tip for researchers and clinicians. Include a soft call‑to‑action at the end: 'Need professional help with your medical writing? Visit {HIRE_ME_URL} or WhatsApp +91 9812018036.' Keep the tone educational, not salesy. Do NOT include any emojis."""
    return llm_generate(prompt, max_tokens=300)

def post_to_facebook(message):
    url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/feed"
    payload = {
        "message": message,
        "access_token": FB_PAGE_TOKEN
    }
    resp = requests.post(url, data=payload, timeout=30)
    if resp.status_code == 200:
        logging.info("Facebook post published successfully!")
    else:
        logging.error(f"Facebook post failed: {resp.status_code} {resp.text}")

def main():
    logging.info("=== Daily Facebook Post ===")
    try:
        post_content = generate_post()
        post_to_facebook(post_content)
        logging.info("=== Done ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
