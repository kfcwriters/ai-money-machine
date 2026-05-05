import os, logging, sys, requests

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
HIRE_ME_URL = os.environ["HIRE_ME_URL"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHANNEL_ID"]   # @username or numeric ID

def generate_press_release():
    prompt = f"""Write a 250‑word press release about a comprehensive medical and academic writing service that covers: thesis synopsis planning, complete thesis writing, manuscript/article writing, journal formatting, and publication support. The service is available at {HIRE_ME_URL}. Include a quote about helping researchers from idea to publication, and end with contact information."""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_completion_tokens": 400
    }
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
                         headers=headers, json=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    else:
        raise Exception(f"Groq error: {resp.status_code} {resp.text}")

def post_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    resp = requests.post(url, json=payload)
    if resp.status_code == 200:
        logging.info("Press release posted to Telegram channel!")
    else:
        raise Exception(f"Telegram error: {resp.text}")

def main():
    pr_text = generate_press_release()
    post_to_telegram(pr_text)

if __name__ == "__main__":
    main()
