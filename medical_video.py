import os, sys, logging, json, random, textwrap, requests, subprocess, asyncio
from pathlib import Path
import numpy as np
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, vfx
from moviepy.video.tools.subtitles import SubtitlesClip
from PIL import Image, ImageDraw, ImageFont

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- API KEYS ----------
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
PIXABAY_API_KEY = os.environ["PIXABAY_API_KEY"]

# ---------- CONFIG ----------
VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920  # 9:16 vertical for shorts
OUTPUT_FILE = "final_video.mp4"
FONT_PATH = "font.ttf"
VOICE_NAME = "en-US-AriaNeural"          # Natural US female voice
TARGET_DURATION = 60                     # ~60 seconds

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

# ---------- STEP 1: GENERATE SCRIPT ----------
def generate_script(topic):
    prompt = f"""You are a professional scriptwriter for short educational videos. Write a 60-second video script about: "{topic}"

Rules:
- Format as plain text with 5-8 short lines (each line one sentence).
- Each line will become one scene with its own stock footage.
- Keep sentences short and punchy. Use simple language.
- Start with a hook. End with a call-to-action: "Need professional medical writing help? Visit kfcwriters.github.io"
- Do NOT include scene numbers, timestamps, or any formatting. Just the sentences.

Script:"""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 500
    }
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"OpenRouter error {resp.status_code}: {resp.text}")
    script = resp.json()["choices"][0]["message"]["content"].strip()
    lines = [line.strip() for line in script.split("\n") if line.strip()]
    logging.info(f"Script generated: {len(lines)} lines")
    return lines

# ---------- STEP 2: GENERATE VOICEOVER ----------
async def generate_voiceover(script_lines):
    full_text = " ".join(script_lines)
    audio_file = "voiceover.mp3"
    # edge-tts is a CLI tool; we call it via subprocess
    cmd = ["edge-tts", "--text", full_text, "--voice", VOICE_NAME, "--write-media", audio_file]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"edge-tts failed: {stderr.decode()}")
    logging.info("Voiceover generated.")
    return audio_file

# ---------- STEP 3: FETCH STOCK FOOTAGE ----------
def fetch_stock_videos(script_lines):
    video_paths = []
    for i, line in enumerate(script_lines):
        # Use the line as search query (take first 80 chars)
        query = line[:80]
        url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={requests.utils.quote(query)}&per_page=3&min_width=1920"
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            logging.warning(f"Pixabay search failed for '{query}': {resp.status_code}")
            continue
        data = resp.json()
        hits = data.get("hits", [])
        if hits:
            # Pick the best-quality video
            best = max(hits, key=lambda h: h.get("likes", 0))
            # Get the large size video URL
            videos = best.get("videos", {})
            if "large" in videos:
                video_url = videos["large"]["url"]
            elif "medium" in videos:
                video_url = videos["medium"]["url"]
            else:
                continue
            # Download
            local_path = f"stock_{i}.mp4"
            vresp = requests.get(video_url, timeout=60)
            with open(local_path, "wb") as f:
                f.write(vresp.content)
            video_paths.append(local_path)
            logging.info(f"Downloaded stock footage for scene {i}: {best.get('id')}")
        else:
            # Fallback: request without query to get any video
            fallback_url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&per_page=1&min_width=1920"
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

    logging.info(f"Downloaded {len(video_paths)} stock clips.")
    return video_paths

# ---------- STEP 4: CREATE SUBTITLE IMAGE ----------
def create_subtitle_image(text, width, height):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 52)
    except:
        font = ImageFont.load_default()
    # Word wrap
    wrapped = textwrap.wrap(text, width=25)
    y_offset = height - (len(wrapped) * 70) - 80
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) / 2
        # Semi-transparent background
        bg_bbox = (x - 15, y_offset - 5, x + text_width + 15, y_offset + 60)
        draw.rectangle(bg_bbox, fill=(0, 0, 0, 160))
        draw.text((x, y_offset), line, font=font, fill=(255, 255, 255, 255))
        y_offset += 70
    arr = np.array(img)
    return arr

# ---------- STEP 5: ASSEMBLE VIDEO ----------
def assemble_video(script_lines, video_paths, audio_path):
    # Load audio
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    segment_duration = total_duration / max(len(script_lines), 1)

    # Process each scene
    clips = []
    for i, line in enumerate(script_lines):
        # Video clip
        if i < len(video_paths) and Path(video_paths[i]).exists():
            vclip = VideoFileClip(video_paths[i]).without_audio()
            # Resize to fill vertical frame (crop to center)
            vclip = vclip.resized(height=VIDEO_HEIGHT)
            if vclip.w > VIDEO_WIDTH:
                vclip = vclip.with_position("center")
        else:
            # Black fallback
            vclip = VideoFileClip("fallback_black.mp4").without_audio().resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))

        # Trim to segment duration
        vclip = vclip.with_duration(segment_duration)
        if vclip.duration < segment_duration:
            vclip = vclip.loop(duration=segment_duration)

        # Subtitle image
        sub_img = create_subtitle_image(line, VIDEO_WIDTH, VIDEO_HEIGHT)
        sub_clip = ImageClip(sub_img, duration=segment_duration)

        # Composite
        comp = CompositeVideoClip([vclip, sub_clip])
        comp = comp.with_start(i * segment_duration)
        clips.append(comp)

    final = CompositeVideoClip(clips)
    final.audio = audio
    final.write_videofile(OUTPUT_FILE, fps=24, codec="libx264", audio_codec="aac",
                          preset="ultrafast", threads=2)
    logging.info(f"Video saved to {OUTPUT_FILE}")

# ---------- MAIN ----------
async def main():
    logging.info("=== Medical Writing Video Generator ===")
    try:
        # 1. Pick topic
        topic = random.choice(TOPICS)
        logging.info(f"Topic: {topic}")

        # 2. Generate script
        script = generate_script(topic)

        # 3. Generate voiceover
        audio = await generate_voiceover(script)

        # 4. Fetch stock footage
        videos = fetch_stock_videos(script)

        # 5. Create fallback black video if needed
        if not Path("fallback_black.mp4").exists():
            subprocess.run(["ffmpeg", "-f", "lavfi", "-i", f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=10",
                            "-c:v", "libx264", "-t", "10", "fallback_black.mp4"], check=True)

        # 6. Assemble final video
        assemble_video(script, videos, audio)

        logging.info("=== Video Generation Complete ===")
    except Exception as e:
        logging.exception("Fatal error")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
