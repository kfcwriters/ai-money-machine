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

# ... rest of the functions (generate_tts, fetch_stock_clip, create_subtitle_image, create_video, upload_to_youtube) unchanged.
