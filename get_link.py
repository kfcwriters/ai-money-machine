def get_latest_product_link(fallback=None):
    if fallback is None:
        fallback = "https://your-payhip-store.payhip.com"
    try:
        with open(".latest_product_url", "r") as f:
            link = f.read().strip()
            if link.startswith("http"):
                return link
    except:
        pass
    return fallback
