def generate_suno_song(lyrics_text):
    url = f"{SUNO_API_BASE}/api/custom_generate"
    payload = {
        "title": "Haryanvi Romantic Song",
        "prompt": lyrics_text,                         # the lyrics you generated
        "tags": "Haryanvi romantic, Indian folk, soft male vocals, acoustic guitar",
        "wait_audio": True
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=300)
    if resp.status_code != 200:
        raise Exception(f"Suno API error: {resp.status_code} {resp.text}")
    data = resp.json()
    # With wait_audio = True, the response directly contains the audio URL
    if isinstance(data, list) and len(data) > 0:
        audio_url = data[0].get("audio_url")
    else:
        audio_url = data.get("audio_url")
    if not audio_url:
        raise Exception("No audio_url in Suno response")
    # Download the audio
    audio_resp = requests.get(audio_url, timeout=120)
    with open("song_audio.mp3", "wb") as f:
        f.write(audio_resp.content)
    logging.info("Suno song generated and downloaded.")
    return "song_audio.mp3"
