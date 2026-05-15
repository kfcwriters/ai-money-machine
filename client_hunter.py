#!/usr/bin/env python3
import time
import requests
import json

def llm_generate(prompt, max_retries=5):
    """
    Generate text using Pollinations.ai (new OpenAI-compatible endpoint).
    Retries on failure.
    """
    # New API endpoint (OpenAI compatible)
    url = "https://enter.pollinations.ai/v1/chat/completions"
    
    # Request payload
    payload = {
        "model": "openai",  # you can also use "mistral", "llama", etc.
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            
            if resp.status_code == 200:
                data = resp.json()
                # Extract the assistant's reply
                content = data["choices"][0]["message"]["content"]
                return content.strip()
            
            # Log error and retry
            print(f"Attempt {attempt+1}: HTTP {resp.status_code}, response: {resp.text[:200]}")
            time.sleep(3 * (attempt + 1))  # longer wait each retry
            
        except Exception as e:
            print(f"Attempt {attempt+1} exception: {e}")
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
