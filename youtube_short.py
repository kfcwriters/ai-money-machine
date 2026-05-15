#!/usr/bin/env python3
import os
import sys
import subprocess
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------- Load credentials from environment variables ----------
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
    print("ERROR: Missing Google API credentials. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
    sys.exit(1)

OUTPUT_FILE = "output.mp4"

# ---------- Ensure video exists ----------
if not os.path.exists(OUTPUT_FILE):
    print(f"⚠️ {OUTPUT_FILE} not found. Creating a simple 5-second test video...")
    try:
        # Create a vertical black video with text using ffmpeg
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=5",
            "-vf", "drawtext=text='Medical Writing Tip':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            OUTPUT_FILE
        ], check=True, capture_output=True)
        print(f"✅ Video created: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Failed to create video: {e}")
        print("   Please generate output.mp4 before running this script.")
        sys.exit(1)

# ---------- YouTube authentication ----------
def get_authenticated_service():
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

# ---------- Upload function ----------
def upload_to_youtube(video_path, title, description):
    youtube = get_authenticated_service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["medical", "writing", "shorts"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "madeForKids": False
        }
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    response = request.execute()
    print(f"✅ Uploaded! https://youtu.be/{response['id']}")
    return response

# ---------- Main ----------
if __name__ == "__main__":
    upload_to_youtube(OUTPUT_FILE, "Medical Writing Tip #Shorts", "Quick medical writing tip #Shorts")
