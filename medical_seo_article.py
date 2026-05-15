#!/usr/bin/env python3
import time
import requests

def llm_generate(prompt, max_retries=5):
    """Generate text from Pollinations.ai with automatic retries on failure."""
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                "https://text.pollinations.ai/",
                json={"prompt": prompt},
                timeout=60
            )
            if resp.status_code == 200:
                return resp.text.strip()
            # If server error (including ENOSPC), wait and retry
            print(f"Attempt {attempt+1}: HTTP {resp.status_code}, retrying...")
            time.sleep(3)  # wait 3 seconds before retry
        except Exception as e:
            print(f"Attempt {attempt+1} error: {e}, retrying...")
            time.sleep(3)
    raise Exception("Pollinations API failed after multiple retries")

# ========== YOUR EXISTING ARTICLE GENERATION LOGIC ==========
# Keep all your original functions – just replace the old llm_generate
# with the one above.

def main():
    title_prompt = "Write an SEO-friendly title for a medical SEO article about telemedicine"
    title = llm_generate(title_prompt).strip('"')
    print(f"Generated title: {title}")
    # ... rest of your article generation code

if __name__ == "__main__":
    main()
