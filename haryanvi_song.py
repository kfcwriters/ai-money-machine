import os, sys, logging, json, random, textwrap, requests, subprocess, asyncio, time
from pathlib import Path
import numpy as np
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip
from PIL import Image, ImageDraw, ImageFont

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ---------- API KEYS ----------
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
PIXABAY_API_KEY = os.environ["PIXABAY_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]   # @username or numeric ID

# ---------- CONFIG ----------
VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920  # 9:16 vertical
OUTPUT_FILE = "haryanvi_song.mp4"
FONT_PATH = "font.ttf"   # <-- must exist in repo root
SUNO_API_BASE = "https://suno-api.vercel.app"   # public instance (no auth needed)

# ---------- 1. GENERATE HARYANVI ROMANTIC LYRICS ----------
def generate_lyrics():
    prompt = """You are a talented Haryanvi songwriter. Write a romantic Haryanvi song in Hindi script. 
    The song should be about love, villages, fields, and traditional relationships. 
    Format: 4 lines per stanza, total 2-3 stanzas + a repeating chorus. 
    Keep it simple, emotional, and rhyme wherever possible. 
    Return the lyrics only, no extra text."""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": 500
    }
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    lyrics = resp.json()["choices"][0]["message"]["content"].strip()
    lines = [line.strip() for line in lyrics.split("\n") if line.strip()]
    logging.info(f"Lyrics generated: {len(lines)} lines")
    return lines, lyrics   # return list of lines and the full text

# ---------- 2. GENERATE SONG AUDIO VIA SUNO API (custom_generate) ----------
def generate_suno_song(lyrics_text):
    url = f"{SUNO_API_BASE}/api/custom_generate"
    payload = {
        "title": "Haryanvi Romantic Song",
        "lyrics": lyrics_text,
        "style": "Haryanvi romantic, Indian folk, soft male vocals, acoustic guitar",
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

# ---------- 3. FETCH ROMANTIC STOCK FOOTAGE ----------
def fetch_stock_videos(script_lines):
    video_paths = []
    # A mix of romantic / Indian village keywords for variety
    search_terms = [
        "romantic couple village",
        "haryanvi culture",
        "Indian wedding couple",
        "sunset fields love",
        "hand in hand couple",
    ]
    for i, _ in enumerate(script_lines):
        query = random.choice(search_terms)
        url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={requests.utils.quote(query)}&per_page=3&min_width=1920"
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            logging.warning(f"Pixabay search failed for '{query}': {resp.status_code}")
            continue
        data = resp.json()
        hits = data.get("hits", [])
        if hits:
            best = max(hits, key=lambda h: h.get("likes", 0))
            videos = best.get("videos", {})
            video_url = videos.get("large", {}).get("url") or videos.get("medium", {}).get("url")
            if video_url:
                local_path = f"stock_{i}.mp4"
                vresp = requests.get(video_url, timeout=60)
                with open(local_path, "wb") as f:
                    f.write(vresp.content)
                video_paths.append(local_path)
                logging.info(f"Downloaded stock footage for scene {i}")
        else:
            # fallback: try a very generic search
            fallback_url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q=love&per_page=1&min_width=1920"
            fresp = requests.get(fallback_url, timeout=30)
            if fresp.status_code == 200:
                fdata = fresp.json()
                fhits = fdata.get("hits", [])
                if fhits:
                    fbest = fhits[0]
                    videos = fbest.get("videos", {})
                    fvurl = videos.get("large", {}).get("url") or videos.get("medium", {}).get("url")
                    if fvurl:
                        local_path = f"stock_{i}.mp4"
                        vresp = requests.get(fvurl, timeout=60)
                        with open(local_path, "wb") as f:
                            f.write(vresp.content)
                        video_paths.append(local_path)
                        logging.info(f"Fallback footage downloaded for scene {i}.")
    logging.info(f"Downloaded {len(video_paths)} romantic stock clips.")
    return video_paths

# ---------- 4. CREATE LYRIC SUBTITLE IMAGE (PINK ROMANTIC STYLE) ----------
def create_subtitle_image(text, width, height):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 42)
    except:
        font = ImageFont.load_default()
    wrapped = textwrap.wrap(text, width=30)
    y_offset = height - (len(wrapped) * 65) - 80
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) / 2
        bg_bbox = (x - 15, y_offset - 5, x + text_width + 15, y_offset + 55)
        draw.rectangle(bg_bbox, fill=(0, 0, 0, 160))   # dark semi-transparent background
        draw.text((x, y_offset), line, font=font, fill=(255, 182, 193))  # pink color
        y_offset += 65
    return np.array(img)

# ---------- 5. ASSEMBLE FINAL VIDEO ----------
def assemble_video(script_lines, video_paths, audio_path):
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    segment_duration = total_duration / max(len(script_lines), 1)

    clips = []
    for i, line in enumerate(script_lines):
        if i < len(video_paths) and Path(video_paths[i]).exists():
            vclip = VideoFileClip(video_paths[i]).without_audio()
            vclip = vclip.resized(height=VIDEO_HEIGHT)
            if vclip.w > VIDEO_WIDTH:
                vclip = vclip.with_position("center")
        else:
            vclip = VideoFileClip("fallback_black.mp4").without_audio().resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))

        vclip = vclip.with_duration(segment_duration)
        if vclip.duration < segment_duration:
            vclip = vclip.loop(duration=segment_duration)

        sub_img = create_subtitle_image(line, VIDEO_WIDTH, VIDEO_HEIGHT)
        sub_clip = ImageClip(sub_img, duration=segment_duration)

        comp = CompositeVideoClip([vclip, sub_clip])
        comp = comp.with_start(i * segment_duration)
        clips.append(comp)

    final = CompositeVideoClip(clips)
    final.audio = audio
    final.write_videofile(OUTPUT_FILE, fps=24, codec="libx264", audio_codec="aac",
                          preset="ultrafast", threads=2)
    logging.info(f"Video saved to {OUTPUT_FILE}")

# ---------- 6. UPLOAD TO TELEGRAM ----------
def upload_to_telegram(video_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    with open(video_path, "rb") as f:
        files = {"video": f}
        data = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "caption": "💕 नया हरियाणवी रोमांटिक गाना तैयार है! #HaryanviSong"
        }
        resp = requests.post(url, data=data, files=files, timeout=60)
    if resp.status_code == 200:
        logging.info("Song video posted to Telegram!")
    else:
        logging.error(f"Telegram upload failed: {resp.status_code} {resp.text}")

# ---------- MAIN ----------
async def main():
    logging.info("=== Haryanvi Romantic Song Generator ===")
    try:
        # 1. Generate lyrics
        lines, full_lyrics = generate_lyrics()

        # 2. Generate song audio via Suno API
        audio_file = generate_suno_song(full_lyrics)

        # 3. Fetch romantic stock footage
        video_paths = fetch_stock_videos(lines)

        # 4. Create fallback black video if it doesn't exist
        if not Path("fallback_black.mp4").exists():
            subprocess.run(["ffmpeg", "-f", "lavfi", "-i",
                            f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=10",
                            "-c:v", "libx264", "-t", "10", "fallback_black.mp4"], check=True)

        # 5. Assemble final video
        assemble_video(lines, video_paths, audio_file)

        # 6. Upload to Telegram
        upload_to_telegram(OUTPUT_FILE)

        logging.info("=== Song Video Generation Complete ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
