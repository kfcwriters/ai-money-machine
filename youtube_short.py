import os, sys, logging, json, requests, subprocess, asyncio, textwrap
from pathlib import Path
import numpy as np
from moviepy import ImageClip, AudioFileClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
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
FONT_PATH = "font.ttf"            # same file you already uploaded

VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920
OUTPUT_FILE = "youtube_short.mp4"
VOICE_NAME = "en-US-AriaNeural"   # clear US female voice

# ─────────────── 1. TIP ───────────────
def generate_tip():
    prompt = (
        "Write a short medical writing tip (1‑2 sentences) for a YouTube short. "
        "Include a call to action: 'Need professional medical writing help? Visit kfcwriters.github.io'. "
        "Keep under 100 words."
    )
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "openrouter/auto", "messages": [{"role":"user","content":prompt}],
               "temperature":0.8, "max_tokens":150}
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    return "Write clearly and concisely. Need help? Visit kfcwriters.github.io"

# ─────────────── 2. TTS ───────────────
async def generate_tts(text):
    audio_file = "tip_audio.mp3"
    cmd = ["edge-tts", "--text", text, "--voice", VOICE_NAME, "--write-media", audio_file]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    if process.returncode != 0:
        raise Exception("TTS failed")
    return audio_file

# ─────────────── 3. VIDEO ───────────────
def create_video(text, audio_path):
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    # Blue gradient background
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), "#0d47a1")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 48)
    except:
        font = ImageFont.load_default()
    lines = textwrap.wrap(text, width=30)
    y = 400
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - w) / 2
        draw.text((x, y), line, font=font, fill="white")
        y += 70
    # Small CTA at bottom
    cta = "kfcwriters.github.io"
    cta_font = ImageFont.truetype(FONT_PATH, 32) if FONT_PATH else ImageFont.load_default()
    bbox = draw.textbbox((0,0), cta, font=cta_font)
    cta_w = bbox[2] - bbox[0]
    draw.text(((VIDEO_WIDTH - cta_w)/2, VIDEO_HEIGHT-100), cta, font=cta_font, fill="#bbdefb")

    img_array = np.array(img)
    clip = ImageClip(img_array, duration=duration)
    clip = clip.with_audio(audio)
    clip.write_videofile(OUTPUT_FILE, fps=24, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2)
    return OUTPUT_FILE

# ─────────────── 4. UPLOAD ───────────────
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
            "tags": ["medical writing", "thesis help", "research publication", "shorts"],
            "categoryId": "27"
        },
        "status": {"privacyStatus": "unlisted"}
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    logging.info(f"YouTube video uploaded: https://youtu.be/{response['id']}")

# ─────────────── MAIN ───────────────
async def main():
    tip = generate_tip()
    audio = await generate_tts(tip)
    create_video(tip, audio)
    upload_to_youtube(OUTPUT_FILE, "Medical Writing Tip #Shorts", tip)
    logging.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
