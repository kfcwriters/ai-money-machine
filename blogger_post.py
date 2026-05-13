import os, requests, logging, sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

CLIENT_ID = os.environ["BLOGGER_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]
BLOG_ID = os.environ["BLOGGER_BLOG_ID"]

# Get latest medical article from Dev.to
def get_latest_article():
    username = "kfc_writers_12f474fa70382"
    url = f"https://dev.to/api/articles?username={username}&per_page=5&tag=medical"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    articles = resp.json()
    if not articles:
        raise Exception("No medical articles found on Dev.to.")
    article = articles[0]
    return article["title"], article["description"] or article["title"], article["url"]

title, snippet, original_url = get_latest_article()

html_content = f"""<p><em>Originally published on <a href="{original_url}">Dev.to</a></em></p>
<p>{snippet}</p>
<p><strong>Need professional help with your medical writing?</strong> Visit <a href="https://kfcwriters.github.io">KFC Writers</a> or WhatsApp +91 9812018036.</p>
"""

# Refresh access token
creds = Credentials(
    None,
    refresh_token=REFRESH_TOKEN,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)
creds.refresh(Request())
service = build("blogger", "v3", credentials=creds)

post_body = {
    "kind": "blogger#post",
    "title": title,
    "content": html_content,
    "labels": ["medical writing", "research", "manuscript"]
}
service.posts().insert(blogId=BLOG_ID, body=post_body, isDraft=False).execute()
logging.info(f"Published on Blogger: {title[:60]}...")
