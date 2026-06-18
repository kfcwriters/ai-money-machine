import os, sys, logging, requests

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- Read the generated article ----------
try:
    with open(".latest_article_title", "r") as f: title = f.read().strip()
    with open(".latest_article_body", "r") as f: body = f.read().strip()
except:
    logging.error("Article files missing. Run main.py first.")
    sys.exit(1)

LINK = os.environ.get("AMAZON_AFFILIATE_LINK", "")
BUFFER_TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN", "")

# ---------- Post to Buffer (Facebook, Twitter, Pinterest) ----------
def post_to_buffer():
    if not BUFFER_TOKEN:
        logging.warning("Buffer token missing.")
        return

    # Get all connected profiles
    r = requests.get("https://api.bufferapp.com/1/profiles.json",
                     params={"access_token": BUFFER_TOKEN})
    if r.status_code != 200:
        logging.error(f"Buffer profiles error: {r.text[:150]}")
        return

    profiles = r.json()
    for profile in profiles:
        pid = profile["id"]
        service = profile["service"]  # e.g., facebook, twitter, pinterest

        # Build the post text
        if service == "twitter":
            text = f"{title} 👉 {LINK}"
            text = text[:280]   # Twitter character limit
        else:
            text = f"{title}\n\n{body[:300]}...\n👉 {LINK}"

        data = {
            "access_token": BUFFER_TOKEN,
            "profile_ids[]": pid,
            "text": text,
        }

        # Pinterest needs an image (we use a placeholder)
        if service == "pinterest":
            data["media[link]"] = "https://via.placeholder.com/1000x1500.png/0d47a1/ffffff?text=Best+Deals"

        post_r = requests.post("https://api.bufferapp.com/1/updates/create.json",
                               data=data)
        if post_r.status_code == 200:
            logging.info(f"Buffer: queued for {service}")
        else:
            logging.error(f"Buffer {service} error: {post_r.text[:150]}")

# ---------- LinkedIn (optional) ----------
def post_linkedin():
    tok = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not tok: return
    u = requests.get("https://api.linkedin.com/v2/userinfo",
                     headers={"Authorization": f"Bearer {tok}"})
    if u.status_code != 200: return
    sub = u.json()["sub"]
    text = f"{title}\n\n{body[:500]}...\n👉 {LINK}"
    payload = {
        "author": f"urn:li:person:{sub}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }
    r = requests.post("https://api.linkedin.com/v2/ugcPosts",
                      headers={"Authorization": f"Bearer {tok}",
                               "X-Restli-Protocol-Version":"2.0.0",
                               "Content-Type":"application/json"},
                      json=payload)
    logging.info("LinkedIn: "+("ok" if r.status_code in [200,201] else r.text[:150]))

# ---------- Reddit (optional) ----------
def post_reddit():
    cid = os.environ.get("REDDIT_CLIENT_ID")
    sec = os.environ.get("REDDIT_CLIENT_SECRET")
    usr = os.environ.get("REDDIT_USERNAME")
    pwd = os.environ.get("REDDIT_PASSWORD")
    if not all([cid, sec, usr, pwd]): return
    import praw
    reddit = praw.Reddit(client_id=cid, client_secret=sec,
                         username=usr, password=pwd, user_agent="bot")
    try:
        reddit.subreddit("ProductPicks").submit(title=title, url=LINK)
        logging.info("Reddit: ok")
    except Exception as e:
        logging.error(f"Reddit: {e}")

if __name__ == "__main__":
    logging.info("Posting to Buffer (FB, TW, PIN), LinkedIn, Reddit...")
    post_to_buffer()
    post_linkedin()
    post_reddit()
    logging.info("All done.")
