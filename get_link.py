# get_link.py
import os

def get_latest_product_link(fallback=None):
    """Return the latest Gumroad product link, or a fallback if none exists."""
    if fallback is None:
        fallback = os.environ.get("HIRE_ME_URL", "https://kfcwriters.github.io")
    try:
        with open(".latest_product_url", "r") as f:
            link = f.read().strip()
            if link and link.startswith("http"):
                return link
    except:
        pass
    return fallback
