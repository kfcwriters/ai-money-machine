#!/usr/bin/env python3
import time
import requests
import os

def llm_generate(prompt):
    """Generate text from Pollinations.ai with retries."""
    for attempt in range(5):
        try:
            resp = requests.post(
                "https://text.pollinations.ai/",
                json={"prompt": prompt},
                timeout=60
            )
            if resp.status_code == 200:
                return resp.text.strip()
            print(f"Attempt {attempt+1}: HTTP {resp.status_code}, retrying...")
            time.sleep(3)
        except Exception as e:
            print(f"Attempt {attempt+1} error: {e}, retrying...")
            time.sleep(3)
    raise Exception("Pollinations failed after 5 attempts")

def main():
    title_prompt = "Write an SEO-friendly title for a medical SEO article about telemedicine"
    title = llm_generate(title_prompt).strip('"')
    print(f"Generated title: {title}")
    # ... rest of your article generation

if __name__ == "__main__":
    main()
