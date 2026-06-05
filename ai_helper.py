import requests, logging, time

def llm_generate(prompt, max_tokens=800, temperature=0.8):
    """Call free AI providers with automatic retry. If all fail, return a helpful placeholder."""
    # ── Primary: Pollinations ──
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
                    pass
            logging.warning(f"Pollinations attempt {attempt} failed (status {resp.status_code}). Retrying…")
            time.sleep(2)
        except Exception as e:
            logging.warning(f"Pollinations attempt {attempt} exception: {e}. Retrying…")
            time.sleep(2)

    # ── Fallback: Hugging Face ──
    try:
        hf_url = "https://api-inference.huggingface.co/models/google/flan-t5-base"
        headers = {"Content-Type": "application/json"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": max_tokens, "temperature": temperature}}
        resp = requests.post(hf_url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            result = resp.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "")
    except Exception as e:
        logging.warning(f"Hugging Face fallback exception: {e}")

    # ── Ultimate fallback: provide a useful placeholder ──
    fallback_message = (
        "We’re currently unable to generate an automatic summary for this paper. "
        "Please read the original abstract on PubMed (ID provided above) for detailed information. "
        "For help with your own medical writing or manuscript preparation, visit kfcwriters.github.io "
        "or WhatsApp +91 9812018036."
    )
    logging.error("All AI providers failed. Returning fallback message.")
    return fallback_message
