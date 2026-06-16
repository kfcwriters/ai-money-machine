import os

def get_latest_product_link(fallback=None):
    if fallback is None:
        fallback = os.environ.get("AMAZON_AFFILIATE_LINK", "https://amazon.com")
    return fallback
