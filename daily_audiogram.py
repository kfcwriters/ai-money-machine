import os, sys, logging, requests, json, asyncio, textwrap, base64, datetime
from pathlib import Path
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import numpy as np
from moviepy import ImageClip, AudioFileClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
CLIENT_ID = os.environ["YOUTUBE_CLIENT_ID"]
CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
FONT_PATH = "font.ttf"
WEBSITE_REPO_TOKEN = os.environ["WEBSITE_REPO_TOKEN"]   # for pushing to website repo
YOUR_EMAIL = os.environ["YOUR_EMAIL"]   # Gmail address (for Gmail API if needed later, but not used for podcast)
GMAIL_CLIENT_ID = os.environ["GMAIL_CLIENT_ID"]
GMAIL_CLIENT_SECRET = os.environ["GMAIL_CLIENT_SECRET"]
GMAIL_REFRESH_TOKEN = os.environ["GMAIL_REFRESH_TOKEN"]

VIDEO_WIDTH, VIDEO_HEIGHT = 1920, 1080
OUTPUT_FILE = "audiogram.mp4"
AUDIO_FILE = "audiogram_audio.mp3"
VOICE_NAME = "en-US-AriaNeural"

# ─────────────── Helper: GitHub API push & RSS ───────────────
GITHUB_API = "https://api.github.com"
WEBSITE_REPO = "kfcwriters/kfcwriters.github.io"
AUDIO_FOLDER = "audio"
RSS_FILE = "podcast.xml"
PODCAST_TITLE = "KFC Medical Writing Tips"
PODCAST_DESCRIPTION = "Daily medical writing tips, tools, and strategies for researchers and clinicians."
PODCAST_LINK = "https://kfcwriters.github.io"
PODCAST_IMAGE_URL = "https://kfcwriters.github.io/logo.png"  # reuse your website logo
PODCAST_AUTHOR = "KFC - Knowledge Framework Consulting"
PODCAST_EMAIL = "kfcwriters@gmail.com"
PODCAST_EXPLICIT = "no"
PODCAST_LANGUAGE = "en-us"

def github_put(api_url, payload, token=WEBSITE_REPO_TOKEN):
    """PUT request with proper headers."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    return requests.put(api_url, headers=headers, json=payload, timeout=30)

def github_get(api_url, token=WEBSITE_REPO_TOKEN):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    return requests.get(api_url, headers=headers, timeout=30)

def upload_file_to_website(local_path, remote_path, commit_message):
    """Upload a file to the website repo using the GitHub Content API."""
    # Get current file sha if exists
    get_url = f"{GITHUB_API}/repos/{WEBSITE_REPO}/contents/{remote_path}"
    resp = github_get(get_url)
    sha = None
    if resp.status_code == 200:
        sha = resp.json().get("sha")

    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "message": commit_message,
        "content": content_b64,
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    put_url = f"{GITHUB_API}/repos/{WEBSITE_REPO}/contents/{remote_path}"
    put_resp = github_put(put_url, payload)
    if put_resp.status_code in (201, 200):
        logging.info(f"Uploaded {remote_path} to website repo.")
    else:
        logging.error(f"Failed to upload {remote_path}: {put_resp.status_code} {put_resp.text}")

def get_existing_rss():
    """Download the existing RSS feed from the website repo, or return None."""
    get_url = f"{GITHUB_API}/repos/{WEBSITE_REPO}/contents/{RSS_FILE}"
    resp = github_get(get_url)
    if resp.status_code == 200:
        import base64 as b64
        content = resp.json().get("content", "")
        if content:
            return b64.b64decode(content).decode("utf-8")
    return None

def create_new_rss():
    """Create a new RSS 2.0 feed (iTunes compatible) with no items."""
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{PODCAST_TITLE}</title>
    <link>{PODCAST_LINK}</link>
    <description>{PODCAST_DESCRIPTION}</description>
    <language>{PODCAST_LANGUAGE}</language>
    <itunes:author>{PODCAST_AUTHOR}</itunes:author>
    <itunes:summary>{PODCAST_DESCRIPTION}</itunes:summary>
    <itunes:image href="{PODCAST_IMAGE_URL}"/>
    <itunes:explicit>{PODCAST_EXPLICIT}</itunes:explicit>
    <itunes:owner>
      <itunes:name>{PODCAST_AUTHOR}</itunes:name>
      <itunes:email>{PODCAST_EMAIL}</itunes:email>
    </itunes:owner>
    <itunes:category text="Education"/>
    <itunes:category text="Science &amp; Medicine"/>
  </channel>
</rss>"""
    return rss

def add_episode_to_rss(rss_str, title, description, audio_url, pub_date, duration):
    """Add a new item to the RSS feed string. Returns updated RSS string."""
    item = f"""
  <item>
    <title>{title}</title>
    <description>{description}</description>
    <enclosure url="{audio_url}" length="0" type="audio/mpeg"/>
    <pubDate>{pub_date}</pubDate>
    <itunes:duration>{duration}</itunes:duration>
    <itunes:explicit>no</itunes:explicit>
  </item>
"""
    # Insert before </channel>
    return rss_str.replace("</channel>", item + "</channel>")

def update_podcast_feed(audio_filename, title, description, duration_seconds):
    """Update the podcast.xml on the website repo with a new episode."""
    # 1. Get existing feed or create new
    rss = get_existing_rss()
    if rss is None:
        rss = create_new_rss()

    # 2. Determine audio public URL
    audio_url = f"https://kfcwriters.github.io/{AUDIO_FOLDER}/{audio_filename}"

    # 3. Format pub date in RFC 2822
    now = datetime.datetime.utcnow()
    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

    # 4. Format duration as HH:MM:SS
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # 5. Add episode
    updated_rss = add_episode_to_rss(rss, title, description, audio_url, pub_date, duration_str)

    # 6. Upload updated RSS to website repo
    with open("temp_rss.xml", "w", encoding="utf-8") as f:
        f.write(updated_rss)
    upload_file_to_website("temp_rss.xml", RSS_FILE, f"Add new podcast episode: {title}")

# ─────────────── Existing Audiogram Functions ───────────────
def get_latest_article():
    username = "kfc_writers_12f474fa70382"
    url = f"https://dev.to/api/articles?username={username}&per_page=5&tag=medical"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Dev.to API error: {resp.status_code}")
    articles = resp.json()
    if not articles:
        raise Exception("No articles found.")
    article = articles[0]
    return article["title"], article["description"] or article["title"], article["url"]

def generate_summary(title, description):
    prompt = f"""Summarize this medical writing article in 3-4 short paragraphs suitable for spoken audio. Keep it under 300 words. Include the title: {title}. Original description: {description}"""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "openrouter/auto", "messages": [{"role":"user","content":prompt}], "temperature":0.7, "max_tokens":500}
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"OpenRouter error {resp.status_code}")

async def generate_tts(text):
    cmd = ["edge-tts", "--text", text, "--voice", VOICE_NAME, "--write-media", AUDIO_FILE]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    if process.returncode != 0:
        raise Exception("TTS failed")
    return AUDIO_FILE

def create_background(title_text):
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), "#0d47a1")
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype(FONT_PATH, 60)
        font_body = ImageFont.truetype(FONT_PATH, 36)
    except:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
    lines = textwrap.wrap(title_text, width=40)
    y = 200
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font_title)
        w = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - w) / 2
        draw.text((x, y), line, font=font_title, fill="white")
        y += 80
    cta = "kfcwriters.github.io"
    cta_font = ImageFont.truetype(FONT_PATH, 30) if FONT_PATH else ImageFont.load_default()
    bbox = draw.textbbox((0,0), cta, font=cta_font)
    cta_w = bbox[2] - bbox[0]
    draw.text(((VIDEO_WIDTH - cta_w)/2, VIDEO_HEIGHT - 100), cta, font=cta_font, fill="#bbdefb")
    return np.array(img)

def create_video(background_img, audio_path):
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    clip = ImageClip(background_img, duration=duration)
    clip = clip.with_audio(audio)
    clip.write_videofile(OUTPUT_FILE, fps=24, codec="libx264", audio_codec="aac",
                         preset="ultrafast", threads=2, bitrate="800k")
    return duration

def upload_to_youtube(video_file, title, description):
    creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token",
                        client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["medical writing", "podcast", "audiogram"],
            "categoryId": "27"
        },
        "status": {"privacyStatus": "unlisted"}
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    logging.info(f"YouTube video uploaded: https://youtu.be/{response['id']}")

async def main():
    logging.info("=== Daily Audiogram with Podcast Feed ===")
    try:
        title, description, url = get_latest_article()
        summary = generate_summary(title, description)
        audio_path = await generate_tts(summary)
        bg = create_background(title)
        duration = create_video(bg, audio_path)
        upload_to_youtube(OUTPUT_FILE, f"{title} – Audiogram", f"{summary}\n\nRead more: {url}\n\nVisit: https://kfcwriters.github.io")

        # ─── Podcast Feed Automation ───
        # Upload MP3 to website
        today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        audio_filename = f"episode-{today_str}.mp3"
        upload_file_to_website(audio_path, f"{AUDIO_FOLDER}/{audio_filename}", f"Add daily audiogram audio: {audio_filename}")

        # Update RSS feed
        episode_description = f"{summary}\n\nRead the full article: {url}\n\nVisit: https://kfcwriters.github.io"
        update_podcast_feed(audio_filename, title, episode_description, int(duration))

        logging.info("=== Podcast feed updated ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
