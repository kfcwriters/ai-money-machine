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
            "tags": ["medical writing", "podcast", "audiogram", "thesis help", "manuscript editing"],
            "categoryId": "27"
        },
        "status": {"privacyStatus": "public"}   # <-- Public, not unlisted
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    logging.info(f"Audiogram uploaded: https://youtu.be/{response['id']}")
