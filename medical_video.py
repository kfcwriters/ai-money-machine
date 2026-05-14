import os, sys, logging, json, random, textwrap, requests, subprocess, asyncio, time
from pathlib import Path
import numpy as np
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip
from PIL import Image, ImageDraw, ImageFont
from ai_helper import llm_generate   # <-- bulletproof AI

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

OPENROUTER_API_KEY = None   # no longer used, kept for backward compatibility if needed elsewhere
PIXABAY_API_KEY = os.environ["PIXABAY_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]

VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920  # 9:16 vertical for shorts
OUTPUT_FILE = "final_video.mp4"
FONT_PATH = "font.ttf"
VOICE_NAME = "en-US-AriaNeural"
TARGET_DURATION = 60

TOPICS = [
    "How to write a medical case report that gets accepted",
    "Common mistakes in medical manuscript writing",
    "Tips for faster journal submission and acceptance",
    "How to structure a literature review for your thesis",
    "Medical writing tips for beginners – where to start",
    "How to choose the right journal for your research paper",
    "The importance of editing and proofreading in medical writing",
    "How to write an effective abstract for your research paper",
]

# ─────────────── 1. GENERATE SCRIPT (using bulletproof AI) ───────────────
def generate_script(topic):
    prompt = f"""You are a professional scriptwriter for short educational videos. Write a 60-second video script about: "{topic}"

Rules:
- Format as plain text with 5-8 short lines (each line one sentence).
- Each line will become one scene with its own stock footage.
- Keep sentences short and punchy. Use simple language.
- Start with a hook. End with a call-to-action: "Need professional medical writing help? Visit kfcwriters.github.io"
- Do NOT include scene numbers, timestamps, or any formatting. Just the sentences.

Script:"""
    response = llm_generate(prompt, max_tokens=500)
    lines = [line.strip() for line in response.split("\n") if line.strip()]
    logging.info(f"Script generated: {len(lines)} lines")
    return lines

# ─────────────── 2. TTS (unchanged) ───────────────
async def generate_voiceover(script_lines):
    full_text = " ".join(script_lines)
    audio_file = "voiceover.mp3"
    cmd = ["edge-tts", "--text", full_text, "--voice", VOICE_NAME, "--write-media", audio_file]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"edge-tts failed: {stderr.decode()}")
    logging.info("Voiceover generated.")
    return audio_file

# ─────────────── 3. STOCK FOOTAGE (unchanged) ───────────────
def fetch_stock_videos(script_lines):
    video_paths = []
    for i, line in enumerate(script_lines):
        query = line[:80]
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
                vresp = requests.get(video_url, timeout=60)
                with open(local_path, "wb") as f:
                    f.write(vresp.content)
                video_paths.append(local_path)
                logging.info(f"Stock {i} downloaded.")
                continue
        # fallback
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
                    vresp = requests.get(fvideo_url, timeout=60)
                    with open(local_path, "wb") as f:
                        f.write(vresp.content)
                    video_paths.append(local_path)
    logging.info(f"Total stock clips: {len(video_paths)}")
    return video_paths

# ─────────────── 4. SUBTITLES (unchanged) ───────────────
def create_subtitle_image(text, width, height):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 52)
    except:
        font = ImageFont.load_default()
    wrapped = textwrap.wrap(text, width=25)
    y_offset = height - (len(wrapped) * 70) - 80
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) / 2
        bg_bbox = (x - 15, y_offset - 5, x + text_width + 15, y_offset + 60)
        draw.rectangle(bg_bbox, fill=(0, 0, 0, 160))
        draw.text((x, y_offset), line, font=font, fill=(255, 255, 255, 255))
        y_offset += 70
    arr = np.array(img)
    return arr

# ─────────────── 5. ASSEMBLE VIDEO (unchanged) ───────────────
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

# ─────────────── 6. UPLOAD TO TELEGRAM (unchanged) ───────────────
def upload_to_telegram(video_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    with open(video_path, "rb") as f:
        files = {"video": f}
        data = {"chat_id": TELEGRAM_CHANNEL_ID, "caption": "📹 New daily medical writing video is ready!"}
        resp = requests.post(url, data=data, files=files, timeout=60)
    if resp.status_code == 200:
        logging.info("Video posted to Telegram channel!")
    else:
        logging.error(f"Telegram upload failed: {resp.status_code} {resp.text}")

# ─────────────── MAIN ───────────────
async def main():
    logging.info("=== Medical Writing Video Generator ===")
    try:
        topic = random.choice(TOPICS)
        logging.info(f"Topic: {topic}")

        script = generate_script(topic)
        audio = await generate_voiceover(script)
        videos = fetch_stock_videos(script)

        if not Path("fallback_black.mp4").exists():
            subprocess.run(["ffmpeg", "-f", "lavfi", "-i",
                            f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=10",
                            "-c:v", "libx264", "-t", "10", "fallback_black.mp4"], check=True)

        assemble_video(script, videos, audio)
        upload_to_telegram(OUTPUT_FILE)

        logging.info("=== Video Generation Complete ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
