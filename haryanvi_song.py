import os, sys, logging, json, random, textwrap, requests, subprocess, asyncio
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
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]

# ---------- CONFIG ----------
VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920
OUTPUT_FILE = "haryanvi_song.mp4"
FONT_PATH = "font.ttf"
VOICE_NAME = "hi-IN-SwaraNeural"                 # ✅ Correct Hindi female voice
SUNO_API_BASE = "https://suno-api.vercel.app"

# ─────────────────────────────── 1. LYRICS ───────────────────────────────
def generate_lyrics():
    prompt = """You are a talented Haryanvi songwriter. Write a romantic Haryanvi song in Hindi script.
The song should be about love, villages, fields, and traditional relationships.
Format: 4 lines per stanza, total 2-3 stanzas + a repeating chorus.
Keep it simple, emotional, and rhyme wherever possible.
Return the lyrics only, no extra text."""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "openrouter/auto",
        "messages": [{"role":"user","content":prompt}],
        "temperature":0.9,
        "max_tokens":500
    }
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    lyrics = resp.json()["choices"][0]["message"]["content"].strip()
    lines = [line.strip() for line in lyrics.split("\n") if line.strip()]
    logging.info(f"Lyrics generated: {len(lines)} lines")
    return lines, lyrics

# ─────────────────────────────── 2. AUDIO (SUNO or TTS fallback) ─────────
def generate_suno_song(lyrics_text):
    """Try Suno; if it fails, return None so we use TTS."""
    url = f"{SUNO_API_BASE}/api/custom_generate"
    payload = {
        "title": "Haryanvi Romantic Song",
        "prompt": lyrics_text,
        "tags": "Haryanvi romantic, Indian folk, soft male vocals, acoustic guitar",
        "wait_audio": True
    }
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=300)
        if resp.status_code != 200:
            logging.warning(f"Suno failed with {resp.status_code}. Will use TTS fallback.")
            return None
        data = resp.json()
        audio_url = None
        if isinstance(data, list) and len(data) > 0:
            audio_url = data[0].get("audio_url")
        elif isinstance(data, dict):
            audio_url = data.get("audio_url")
        if not audio_url:
            logging.warning("Suno response missing audio_url. Using TTS.")
            return None
        # Download
        r = requests.get(audio_url, timeout=120)
        with open("song_audio.mp3", "wb") as f:
            f.write(r.content)
        logging.info("Suno song downloaded.")
        return "song_audio.mp3"
    except Exception as e:
        logging.warning(f"Suno exception: {e}. Using TTS.")
        return None

async def generate_tts_narration(script_lines):
    """Fallback: Edge TTS narration with Hindi voice."""
    full_text = " ".join(script_lines)
    audio_file = "fallback_audio.mp3"
    cmd = ["edge-tts", "--text", full_text, "--voice", VOICE_NAME, "--write-media", audio_file]
    process = await asyncio.create_subprocess_exec(*cmd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"edge-tts failed: {stderr.decode()}")
    logging.info("TTS fallback audio generated.")
    return audio_file

# ─────────────────────────────── 3. STOCK FOOTAGE ────────────────────────
def fetch_stock_videos(script_lines):
    video_paths = []
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
            continue
        data = resp.json()
        hits = data.get("hits", [])
        if hits:
            best = max(hits, key=lambda h: h.get("likes", 0))
            video_url = (best.get("videos", {}).get("large", {}) or {}).get("url") or \
                        (best.get("videos", {}).get("medium", {}) or {}).get("url")
            if video_url:
                local_path = f"stock_{i}.mp4"
                r = requests.get(video_url, timeout=60)
                with open(local_path, "wb") as f:
                    f.write(r.content)
                video_paths.append(local_path)
                logging.info(f"Stock {i} downloaded.")
                continue
        # fallback generic search
        fallback_url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q=love&per_page=1&min_width=1920"
        fresp = requests.get(fallback_url, timeout=30)
        if fresp.status_code == 200:
            fdata = fresp.json()
            fhits = fdata.get("hits", [])
            if fhits:
                fbest = fhits[0]
                fvideo_url = (fbest.get("videos", {}).get("large", {}) or {}).get("url") or \
                             (fbest.get("videos", {}).get("medium", {}) or {}).get("url")
                if fvideo_url:
                    local_path = f"stock_{i}.mp4"
                    r = requests.get(fvideo_url, timeout=60)
                    with open(local_path, "wb") as f:
                        f.write(r.content)
                    video_paths.append(local_path)
                    logging.info(f"Fallback stock {i} downloaded.")
    logging.info(f"Total stock clips: {len(video_paths)}")
    return video_paths

# ─────────────────────────────── 4. SUBTITLES (pink) ────────────────────
def create_subtitle_image(text, w, h):
    img = Image.new("RGBA", (w, h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 42)
    except:
        font = ImageFont.load_default()
    wrapped = textwrap.wrap(text, width=30)
    y = h - (len(wrapped) * 65) - 80
    for line in wrapped:
        bbox = draw.textbbox((0,0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) / 2
        draw.rectangle((x-15, y-5, x+tw+15, y+55), fill=(0,0,0,160))
        draw.text((x, y), line, font=font, fill=(255,182,193))   # pink
        y += 65
    return np.array(img)

# ─────────────────────────────── 5. VIDEO ASSEMBLY ───────────────────────
def assemble_video(lines, video_paths, audio_path):
    audio = AudioFileClip(audio_path)
    seg_dur = audio.duration / max(len(lines), 1)
    clips = []
    for i, line in enumerate(lines):
        if i < len(video_paths) and Path(video_paths[i]).exists():
            v = VideoFileClip(video_paths[i]).without_audio().resized(height=VIDEO_HEIGHT)
        else:
            v = (VideoFileClip("fallback_black.mp4").without_audio()
                 .resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT)))
        v = v.with_duration(seg_dur)
        if v.duration < seg_dur:
            v = v.loop(duration=seg_dur)
        sub = ImageClip(create_subtitle_image(line, VIDEO_WIDTH, VIDEO_HEIGHT), duration=seg_dur)
        comp = CompositeVideoClip([v, sub]).with_start(i * seg_dur)
        clips.append(comp)
    final = CompositeVideoClip(clips)
    final.audio = audio
    final.write_videofile(OUTPUT_FILE, fps=24, codec="libx264", audio_codec="aac",
                          preset="ultrafast", threads=2)
    logging.info(f"Video assembled: {OUTPUT_FILE}")

# ─────────────────────────────── 6. TELEGRAM UPLOAD ──────────────────────
def upload_to_telegram(video_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    with open(video_path, "rb") as f:
        files = {"video": f}
        data = {"chat_id": TELEGRAM_CHANNEL_ID, "caption": "💕 नया हरियाणवी रोमांटिक गाना तैयार है! #HaryanviSong"}
        resp = requests.post(url, data=data, files=files, timeout=60)
    if resp.status_code == 200:
        logging.info("Video uploaded to Telegram!")
    else:
        logging.error(f"Telegram upload failed: {resp.status_code} {resp.text}")

# ─────────────────────────────── MAIN ────────────────────────────────────
async def main():
    logging.info("=== Haryanvi Romantic Song Generator ===")
    try:
        lines, full_lyrics = generate_lyrics()

        # Try Suno first
        audio_file = generate_suno_song(full_lyrics)
        if not audio_file:
            # Fallback to TTS narration
            audio_file = await generate_tts_narration(lines)

        video_paths = fetch_stock_videos(lines)

        # Create fallback black video if needed
        if not Path("fallback_black.mp4").exists():
            subprocess.run(["ffmpeg", "-f", "lavfi", "-i",
                            f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=10",
                            "-c:v", "libx264", "-t", "10", "fallback_black.mp4"], check=True)

        assemble_video(lines, video_paths, audio_file)
        upload_to_telegram(OUTPUT_FILE)

        logging.info("=== Done! ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
