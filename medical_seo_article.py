#!/usr/bin/env python3
import time
import requests

def llm_generate(prompt, max_retries=5):
    """
    Generate text using Pollinations.ai (simple GET endpoint).
    Retries on failure.
    """
    # Simple GET endpoint – works without API key
    url = "https://text.pollinations.ai/"
    
    for attempt in range(max_retries):
        try:
            # Pass prompt as query parameter
            resp = requests.get(url, params={"text": prompt}, timeout=60)
            
            if resp.status_code == 200:
                return resp.text.strip()
            
            # If server error, wait and retry
            print(f"Attempt {attempt+1}: HTTP {resp.status_code}, retrying...")
            time.sleep(3 * (attempt + 1))  # longer wait each retry
            
        except Exception as e:
            print(f"Attempt {attempt+1} error: {e}, retrying...")
            time.sleep(3 * (attempt + 1))
    
    raise Exception("Pollinations API failed after multiple retries")

# ========== YOUR EXISTING ARTICLE GENERATION LOGIC ==========
# Keep your original functions – just replace the old llm_generate
# with the one above.

def main():
    title_prompt = "Write an SEO-friendly title for a medical SEO article about telemedicine"
    title = llm_generate(title_prompt).strip('"')
    print(f"Generated title: {title}")
    # ... rest of your code (e.g., generate body, save to file)

if __name__ == "__main__":
    main()
