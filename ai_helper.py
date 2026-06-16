import requests
import logging
import time

def llm_generate(prompt, max_tokens=800, temperature=0.8):
    """
    Call the free Pollinations AI endpoint.
    Retries up to 3 times, then returns an error message.
    """
    url = "https://text.pollinations.ai/openai"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    for attempt in range(1, 4):
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=45)
            if resp.status_code == 200:
                result = resp.json()
                choices = result.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
            logging.warning(f"Pollinations attempt {attempt} failed (status {resp.status_code}). Retrying…")
            time.sleep(2)
        except Exception as e:
            logging.warning(f"Pollinations attempt {attempt} exception: {e}. Retrying…")
            time.sleep(2)

    # Fallback – a simple, safe response that will at least let the script finish
    return "I'm sorry, I couldn't generate a product review at this moment."
