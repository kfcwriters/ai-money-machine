import requests, logging, time

def llm_generate(prompt, max_tokens=800, temperature=0.8, fallback_model="google/flan-t5-base"):
    """Call free AI providers with automatic retry and fallback."""

    # ── Primary: Pollinations (free, no key) ──
    for attempt in range(1, 4):
        try:
            url = "https://text.pollinations.ai/openai"
            headers = {"Content-Type": "application/json"}
            data = {
                "model": "openai",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            resp = requests.post(url, headers=headers, json=data, timeout=45)
            if resp.status_code == 200:
                result = resp.json()
                try:
                    return result["choices"][0]["message"]["content"]
                except (KeyError, TypeError):
                    pass   # fall through to retry
            logging.warning(f"Pollinations attempt {attempt} failed (status {resp.status_code}). Retrying…")
            time.sleep(2)
        except Exception as e:
            logging.warning(f"Pollinations attempt {attempt} exception: {e}. Retrying…")
            time.sleep(2)

    # ── Fallback: Hugging Face free public API (no key) ──
    logging.info("Pollinations failed after 3 attempts. Switching to Hugging Face fallback…")
    try:
        hf_url = f"https://api-inference.huggingface.co/models/{fallback_model}"
        headers = {"Content-Type": "application/json"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": max_tokens, "temperature": temperature}}
        resp = requests.post(hf_url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            result = resp.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "")
        raise Exception(f"Hugging Face fallback failed: {resp.status_code} {resp.text}")
    except Exception as e:
        raise Exception(f"All AI providers failed: {e}")
