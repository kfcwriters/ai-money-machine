import os, sys, logging, requests, subprocess, asyncio, random, textwrap
from pathlib import Path
import numpy as np
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

PIXABAY_API_KEY = os.environ["PIXABAY_API_KEY"]
CLIENT_ID = os.environ["YOUTUBE_CLIENT_ID"]
CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
FONT_PATH = "font.ttf"

VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920
OUTPUT_FILE = "youtube_short.mp4"
VOICE_NAME = "en-US-AriaNeural"

def generate_tip():
    prompt = (
        "Write a short medical writing tip (1‑2 sentences) for a YouTube short. "
        "Include a call to action: 'Need professional medical writing help? Visit kfcwriters.github.io'. "
        "Keep under 100 words."
    )
    url = "https://text.pollinations.ai/openai"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 150
    }
    resp = requests.post(url, headers=headers, json=data, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    return "Write clearly and concisely. Need help? Visit kfcwriters.github.io"

async def generate_tts(text):
    audio_file = "tip_audio.mp3"
    cmd = ["edge-tts", "--text", text, "--voice", VOICE_NAME, "--write-media", audio_file]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    if process.returncode != 0:
        raise Exception("TTS failed")
    return audio_file

def fetch_stock_clip():
    queries = ["medical research", "writing", "doctor", "library", "laboratory"]
    query = random.choice(queries)
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={requests.utils.quote(query)}&per_page=3&min_width=1080"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        logging.warning(f"Pixabay search failed: {resp.status_code}")
        return None
    data = resp.json()
    hits = data.get("hits", [])
    if not hits:
        logging.warning("No stock footage found.")
        return None
    best = max(hits, key=lambda h: h.get("likes", 0))
    video_url = None
    for size in ("large", "medium"):
        v = best.get("videos", {}).get(size, {})
        if v.get("url"):
            video_url = v["url"]
            break
    if not video_url:
        logging.warning("No suitable video URL found.")
        return None
    local_path = "stock_clip.mp4"
    r = requests.get(video_url, timeout=60)
    with open(local_path, "wb") as f:
        f.write(r.content)
    logging.info("Stock clip downloaded.")
    return local_path

def create_subtitle_image(text, w, h):
    img = Image.new("RGBA", (w, h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 48)
    except:
        font = ImageFont.load_default()
    lines = textwrap.wrap(text, width=25)
    y = h - (len(lines) * 75) - 120
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) / 2
        draw.rectangle((x-15, y-5, x+tw+15, y+65), fill=(0,0,0,180))
        draw.text((x, y), line, font=font, fill=(255,255,255))
        y += 75
    cta = "kfcwriters.github.io"
    cta_font = ImageFont.truetype(FONT_PATH, 32) if FONT_PATH else ImageFont.load_default()
    bbox = draw.textbbox((0,0), cta, font=cta_font)
    cta_w = bbox[2] - bbox[0]
    draw.text(((w - cta_w)/2, h-80), cta, font=cta_font, fill="#bbdefb")
    return np.array(img)

def create_video(text, audio_path, stock_path):
    audio = AudioFileClip(audio_path)
    duration = audio.duration

    if stock_path and Path(stock_path).exists():
        video_bg = VideoFileClip(stock_path).without_audio()
        video_bg = video_bg.resized(height=VIDEO_HEIGHT)
        if video_bg.w > VIDEO_WIDTH:
            video_bg = video_bg.with_position("center")
    else:
        img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), "#0d47a1")
        draw = ImageDraw.Draw(img)
        for i in range(VIDEO_HEIGHT):
            draw.line([(0, i), (VIDEO_WIDTH, i)], fill=(13, 71, 161, i//4))
        video_bg = ImageClip(np.array(img)).with_duration(duration)

    video_bg = video_bg.with_duration(duration)
    if video_bg.duration < duration:
        video_bg = video_bg.loop(duration=duration)

    sub_img = create_subtitle_image(text, VIDEO_WIDTH, VIDEO_HEIGHT)
    sub_clip = ImageClip(sub_img, duration=duration)

    final = CompositeVideoClip([video_bg, sub_clip])
    final.audio = audio
    final.write_videofile(OUTPUT_FILE, fps=24, codec="libx264", audio_codec="aac",
                          preset="ultrafast", threads=2, bitrate="800k")
    return OUTPUT_FILE

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
            "tags": ["medical writing", "thesis help", "research publication", "shorts",
                     "medical manuscript", "journal submission", "PhD writing", "case report"],
            "categoryId": "27"
        },
        "status": {"privacyStatus": "public"}   # <-- Public, not unlisted
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    logging.info(f"YouTube video uploaded: https://youtu.be/{response['id']}")
    return f"https://youtu.be/{response['id']}"

async def main():
    tip = generate_tip()
    audio = await generate_tts(tip)
    stock = fetch_stock_clip()
    create_video(tip, audio, stock)
    description = f"{tip}\n\nNeed professional medical writing help? Visit: https://kfcwriters.github.io"
    upload_to_youtube(OUTPUT_FILE, "Medical Writing Tip #Shorts", description)
    logging.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
