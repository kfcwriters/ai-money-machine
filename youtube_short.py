#!/usr/bin/env python3
import os
import pickle
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Your credentials (REPLACE AFTER TESTING)
CLIENT_ID = "921929857185-elflpkgmbu39911p2ahgdavc54b7al98.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REFRESH_TOKEN = "1//04DR5kXoXvo9_CgYIARAAGAQSNwF-L9Ir8Pl8wGCejfJCtB4uzKe5NW-2P_OiXgTnEgpohrA7cGlh0s2wKmFztLLGEdO2_ZniqJg"

def get_authenticated_service():
    """Return a YouTube service object using the refresh token."""
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def upload_to_youtube(video_path, title, description):
    """Upload video to YouTube."""
    youtube = get_authenticated_service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["medical", "writing", "shorts"],
            "categoryId": "22"  # "People & Blogs"
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
    print(f"Uploaded: https://youtu.be/{response['id']}")
    return response

if __name__ == "__main__":
    OUTPUT_FILE = "output.mp4"  # or whatever your generated video is
    description = "Medical writing tip for aspiring writers. #Shorts"
    upload_to_youtube(OUTPUT_FILE, "Medical Writing Tip #Shorts", description)
