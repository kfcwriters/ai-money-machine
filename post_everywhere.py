import os, sys, logging, requests, tweepy, praw

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- Read article ----------
try:
    with open(".latest_article_title", "r") as f: title = f.read().strip()
    with open(".latest_article_body", "r") as f: body = f.read().strip()
except:
    logging.error("Article files missing. Run main.py first.")
    sys.exit(1)

LINK = os.environ.get("AMAZON_AFFILIATE_LINK", "")

# ---------- Facebook Page (permanent token) ----------
def post_facebook():
    pid = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN")
    if not pid or not token: return
    msg = f"{title}\n\n{body[:500]}...\n👉 {LINK}"
    r = requests.post(f"https://graph.facebook.com/v22.0/{pid}/feed",
                      data={"message": msg, "access_token": token})
    logging.info("Facebook: "+("ok" if r.status_code==200 else r.text[:100]))

# ---------- LinkedIn (using permanent access token) ----------
def post_linkedin():
    cid = os.environ.get("LINKEDIN_CLIENT_ID")
    sec = os.environ.get("LINKEDIN_CLIENT_SECRET")
    tok = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not all([cid, sec, tok]): return
    # Get user URN
    u = requests.get("https://api.linkedin.com/v2/userinfo",
                     headers={"Authorization": f"Bearer {tok}"})
    if u.status_code != 200:
        logging.error("LinkedIn userinfo failed"); return
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
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    r = requests.post("https://api.linkedin.com/v2/ugcPosts",
                      headers={"Authorization": f"Bearer {tok}",
                               "X-Restli-Protocol-Version":"2.0.0",
                               "Content-Type":"application/json"},
                      json=payload)
    logging.info("LinkedIn: "+("ok" if r.status_code in [200,201] else r.text[:100]))

# ---------- Twitter (using free API) ----------
def post_twitter():
    keys = [os.environ.get(k) for k in ["TWITTER_API_KEY","TWITTER_API_KEY_SECRET",
                                        "TWITTER_ACCESS_TOKEN","TWITTER_ACCESS_TOKEN_SECRET"]]
    if not all(keys): return
    client = tweepy.Client(consumer_key=keys[0], consumer_secret=keys[1],
                           access_token=keys[2], access_token_secret=keys[3])
    tweet = f"{title}\n👉 {LINK}"
    if len(tweet) > 280: tweet = tweet[:277] + "..."
    try:
        client.create_tweet(text=tweet)
        logging.info("Twitter: ok")
    except Exception as e:
        logging.error(f"Twitter: {e}")

# ---------- Reddit ----------
def post_reddit():
    cid = os.environ.get("REDDIT_CLIENT_ID")
    sec = os.environ.get("REDDIT_CLIENT_SECRET")
    usr = os.environ.get("REDDIT_USERNAME")
    pwd = os.environ.get("REDDIT_PASSWORD")
    if not all([cid, sec, usr, pwd]): return
    reddit = praw.Reddit(client_id=cid, client_secret=sec,
                         username=usr, password=pwd, user_agent="bot")
    try:
        reddit.subreddit("ProductPicks").submit(title=title, url=LINK)
        logging.info("Reddit: ok")
    except Exception as e:
        logging.error(f"Reddit: {e}")

# ---------- (Pinterest will be added when your app is approved) ----------

if __name__ == "__main__":
    logging.info("Posting to Facebook, LinkedIn, Twitter, Reddit...")
    post_facebook()
    post_linkedin()
    post_twitter()
    post_reddit()
    logging.info("All done.")
