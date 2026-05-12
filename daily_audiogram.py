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

CLIENT_ID = os.environ["YOUTUBE_CLIENT_ID"]
CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
FONT_PATH = "font.ttf"
WEBSITE_REPO_TOKEN = os.environ["WEBSITE_REPO_TOKEN"]
YOUR_EMAIL = os.environ["YOUR_EMAIL"]
GMAIL_CLIENT_ID = os.environ["GMAIL_CLIENT_ID"]
GMAIL_CLIENT_SECRET = os.environ["GMAIL_CLIENT_SECRET"]
GMAIL_REFRESH_TOKEN = os.environ["GMAIL_REFRESH_TOKEN"]

VIDEO_WIDTH, VIDEO_HEIGHT = 1920, 1080
OUTPUT_FILE = "audiogram.mp4"
AUDIO_FILE = "audiogram_audio.mp3"
VOICE_NAME = "en-US-AriaNeural"

GITHUB_API = "https://api.github.com"
WEBSITE_REPO = "kfcwriters/kfcwriters.github.io"
AUDIO_FOLDER = "audio"
RSS_FILE = "podcast.xml"
PODCAST_TITLE = "KFC Medical Writing Tips"
PODCAST_DESCRIPTION = "Daily medical writing tips, tools, and strategies for researchers and clinicians."
PODCAST_LINK = "https://kfcwriters.github.io"
PODCAST_IMAGE_URL = "https://kfcwriters.github.io/logo.png"
PODCAST_AUTHOR = "KFC - Knowledge Framework Consulting"
PODCAST_EMAIL = "kfcwriters@gmail.com"
PODCAST_EXPLICIT = "no"
PODCAST_LANGUAGE = "en-us"

def llm_generate(prompt):
    url = "https://text.pollinations.ai/openai"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 800
    }
    resp = requests.post(url, headers=headers, json=data, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# ... (rest of the functions: github_put, github_get, upload_file_to_website, get_existing_rss,
#      create_new_rss, add_episode_to_rss, update_podcast_feed, get_latest_article,
#      generate_summary, generate_tts, create_background, create_video, upload_to_youtube)
# The rest of the script is identical to the version you already have.
# Only the AI call inside generate_summary changes to llm_generate.
