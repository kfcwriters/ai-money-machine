import os, logging, sys, requests
from get_link import get_latest_product_link

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHANNEL_ID"]
PRODUCT_LINK = get_latest_product_link("https://kfcwriters.github.io")   # <-- FIX

def generate_announcement():
    prompt = f"""Write a short Telegram announcement (2–3 sentences) about a new digital guide for medical writers. The guide is a checklist/template that helps researchers avoid common manuscript mistakes. Mention that it’s available for only $4.99 at {PRODUCT_LINK}. Keep it enthusiastic but professional. No emojis."""
    url = "https://text.pollinations.ai/openai"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 200
    }
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def post_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    resp = requests.post(url, json=payload)
    if resp.status_code == 200:
        logging.info("Telegram announcement posted!")
    else:
        raise Exception(f"Telegram error: {resp.text}")

def main():
    try:
        text = generate_announcement()
        post_to_telegram(text)
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    main()
