import os, sys, logging, requests, asyncio, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy import ImageClip, AudioFileClip, CompositeVideoClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
CLIENT_ID = os.environ["YOUTUBE_CLIENT_ID"]
CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
FONT_PATH = "font.ttf"   # already in your repo

VIDEO_WIDTH, VIDEO_HEIGHT = 1920, 1080   # landscape for podcasts
OUTPUT_FILE = "audiogram.mp4"
VOICE_NAME = "en-US-AriaNeural"

# ─────────────── 1. FETCH LATEST ARTICLE ───────────────
def get_latest_article():
    """Get the most recent medical article from Dev.to."""
    username = "kfc_writers_12f474fa70382"
    url = f"https://dev.to/api/articles?username={username}&per_page=5&tag=medical"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Dev.to API error: {resp.status_code}")
    articles = resp.json()
    if not articles:
        raise Exception("No articles found.")
    # Return the first (latest) article
    article = articles[0]
    return article["title"], article["description"] or article["title"], article["url"]

# ─────────────── 2. GENERATE A SHORT SPOKEN SUMMARY ───────────────
def generate_summary(title, description):
    prompt = f"""Summarize this medical writing article in 3-4 short paragraphs suitable for spoken audio. Keep it under 300 words. Include the title: {title}. Original description: {description}"""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "openrouter/auto",
        "messages": [{"role":"user","content":prompt}],
        "temperature":0.7,
        "max_tokens":500
    }
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    raise Exception(f"OpenRouter error {resp.status_code}")

# ─────────────── 3. TEXT TO SPEECH ───────────────
async def generate_tts(text):
    audio_file = "audiogram_audio.mp3"
    cmd = ["edge-tts", "--text", text, "--voice", VOICE_NAME, "--write-media", audio_file]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    if process.returncode != 0:
        raise Exception("TTS failed")
    return audio_file

# ─────────────── 4. CREATE BRANDED BACKGROUND ───────────────
def create_background(title_text):
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), "#0d47a1")
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype(FONT_PATH, 60)
        font_body = ImageFont.truetype(FONT_PATH, 36)
    except:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # Draw title
    lines = textwrap.wrap(title_text, width=40)
    y = 200
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font_title)
        w = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - w) / 2
        draw.text((x, y), line, font=font_title, fill="white")
        y += 80

    # Footer
    cta = "kfcwriters.github.io"
    cta_font = ImageFont.truetype(FONT_PATH, 30) if FONT_PATH else ImageFont.load_default()
    bbox = draw.textbbox((0,0), cta, font=cta_font)
    cta_w = bbox[2] - bbox[0]
    draw.text(((VIDEO_WIDTH - cta_w)/2, VIDEO_HEIGHT - 100), cta, font=cta_font, fill="#bbdefb")

    img_array = np.array(img)
    return img_array

# ─────────────── 5. ASSEMBLE VIDEO ───────────────
def create_video(background_img, audio_path):
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    clip = ImageClip(background_img, duration=duration)
    clip = clip.with_audio(audio)
    clip.write_videofile(OUTPUT_FILE, fps=24, codec="libx264", audio_codec="aac",
                         preset="ultrafast", threads=2, bitrate="800k")
    return OUTPUT_FILE

# ─────────────── 6. UPLOAD TO YOUTUBE ───────────────
def upload_to_youtube(video_file, title, description):
    creds = Credentials(
        None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
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
    logging.info(f"Audiogram uploaded: https://youtu.be/{response['id']}")

# ─────────────── MAIN ───────────────
async def main():
    logging.info("=== Daily Audiogram Generator ===")
    try:
        title, description, url = get_latest_article()
        summary = generate_summary(title, description)
        audio = await generate_tts(summary)
        bg = create_background(title)
        create_video(bg, audio)
        upload_to_youtube(OUTPUT_FILE, f"{title} – Audiogram", f"{summary}\n\nRead the full article: {url}\n\nVisit: https://kfcwriters.github.io")
        logging.info("=== Done ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
