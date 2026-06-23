#!/usr/bin/env python3
"""
Daily Reel poster: reads reels.csv, picks the next unposted product,
generates a silent slideshow-style vertical video with ffmpeg, hosts it
via this repo's raw.githubusercontent.com URL, and posts it as a Reel
to Instagram and Facebook via Buffer's GraphQL API.

Kept as a separate script from post_product.py on purpose - if this one
breaks, the working image-post system keeps running untouched.

Required GitHub repo secrets (same ones used by post_product.py):
  BUFFER_ACCESS_TOKEN
  BUFFER_CHANNEL_IDS   - only facebook/instagram channels make sense here;
                         Pinterest does not support video Reels the same way.

Required CSV columns in reels.csv:
  name, price, link, angle, image_url, posted
"""

import csv
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import requests

from post_product import (
    BUFFER_API_URL,
    NETWORK_METADATA,
    fetch_channel_services,
    load_products,
    save_products,
)

REELS_CSV_PATH = "reels.csv"
REELS_OUTPUT_DIR = "reels"

CREATE_VIDEO_POST_MUTATION = """
mutation CreateScheduledVideoPost(
  $text: String!,
  $channelId: ChannelId!,
  $dueAt: DateTime!,
  $videoUrl: String!,
  $metadata: PostInputMetaData
) {
  createPost(input: {
    text: $text,
    channelId: $channelId,
    schedulingType: automatic,
    mode: customScheduled,
    dueAt: $dueAt,
    assets: [
      { video: { url: $videoUrl } }
    ],
    metadata: $metadata
  }) {
    ... on PostActionSuccess {
      post { id text dueAt }
    }
    ... on MutationError {
      message
    }
  }
}
"""

# Only these services get a video Reel right now. Pinterest "video pins"
# use a different shape we haven't validated - skip it for now rather
# than guess and risk an unnecessary failure.
REEL_SUPPORTED_SERVICES = {"facebook", "instagram"}


def escape_for_drawtext(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")


def download_image(url, dest_path):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(response.content)


def generate_reel(product_image_path, product_name, price, angle, output_path):
    name = escape_for_drawtext(product_name)
    cta = escape_for_drawtext(angle[:60])

    filter_complex = (
        "[0:v]scale=1000:1000:force_original_aspect_ratio=decrease[img];"
        "[1:v][img]overlay=(W-w)/2:300[bg];"
        f"[bg]drawtext=text='{name}':fontcolor=0x1f1d1a:fontsize=58:"
        "x=(w-text_w)/2:y=1420:font=DejaVu-Sans-Bold[t1];"
        f"[t1]drawtext=text='Rs {price}':fontcolor=0xb5502f:fontsize=50:"
        "x=(w-text_w)/2:y=1500[t2];"
        f"[t2]drawtext=text='{cta}':fontcolor=0x7a756c:fontsize=34:"
        "x=(w-text_w)/2:y=1580[t3];"
        "[t3]drawtext=text='Link in bio / comments':fontcolor=0x7a756c:fontsize=32:"
        "x=(w-text_w)/2:y=1680[vout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", product_image_path,
        "-f", "lavfi", "-i", "color=c=0xfaf7f2:s=1080x1920:d=8",
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-t", "8", "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-1500:]}")


def commit_and_get_video_url(local_path, repo_relative_path):
    os.makedirs(os.path.dirname(repo_relative_path) or ".", exist_ok=True)
    subprocess.run(["cp", local_path, repo_relative_path], check=True)
    subprocess.run(["git", "add", repo_relative_path], check=True)
    commit_result = subprocess.run(
        ["git", "commit", "-m", f"Add generated reel: {repo_relative_path}"],
        capture_output=True, text=True,
    )
    if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stdout:
        raise RuntimeError(f"git commit failed: {commit_result.stderr}")
    subprocess.run(["git", "push"], check=True)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY env var not set - can't build raw URL.")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{repo_relative_path}"


def post_video_to_buffer(caption, link, video_url, channel_id, service, access_token):
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
    variables = {
        "text": f"{caption}\n{link}",
        "channelId": channel_id,
        "dueAt": scheduled_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "videoUrl": video_url,
        "metadata": NETWORK_METADATA.get(service),
    }
    response = requests.post(
        BUFFER_API_URL,
        json={"query": CREATE_VIDEO_POST_MUTATION, "variables": variables},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code} from Buffer: {response.text[:1000]}")
    body = response.json()
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    result = body.get("data", {}).get("createPost", {})
    if "message" in result:
        raise RuntimeError(f"Buffer rejected post: {result['message']}")
    return body


def build_reel_caption(product):
    return (
        f"{product['name']} - Rs {product['price']}\n\n"
        f"{product['angle']}.\n\n"
        f"Link in bio/comments.\n"
        f"#AmazonFinds #ReelOfTheDay #SmartBuy #DealOfTheDay"
    )


def main():
    access_token = os.environ.get("BUFFER_ACCESS_TOKEN")
    channel_ids_raw = os.environ.get("BUFFER_CHANNEL_IDS", "")
    channel_ids = [c.strip() for c in channel_ids_raw.split(",") if c.strip()]

    if not access_token or not channel_ids:
        print("Missing BUFFER_ACCESS_TOKEN or BUFFER_CHANNEL_IDS secrets.")
        sys.exit(1)

    if not os.path.exists(REELS_CSV_PATH):
        print(f"{REELS_CSV_PATH} not found - nothing to post. Create it with the same "
              f"columns as products.csv (name,price,link,angle,image_url,posted).")
        return

    rows = load_products(REELS_CSV_PATH)
    if not rows:
        print(f"{REELS_CSV_PATH} is empty. Nothing to post.")
        return

    fieldnames = rows[0].keys()
    next_row = next((r for r in rows if r.get("posted", "no").lower() == "no"), None)
    if next_row is None:
        print("All reel products already posted. Add more rows to reels.csv.")
        return

    image_url = next_row.get("image_url", "").strip()
    if not image_url:
        print(f"No image_url set for '{next_row['name']}' - skipping.")
        sys.exit(1)

    os.makedirs("tmp_reel_build", exist_ok=True)
    local_image_path = "tmp_reel_build/product.jpg"
    local_video_path = "tmp_reel_build/reel.mp4"

    try:
        print("Downloading product image...")
        download_image(image_url, local_image_path)

        print("Generating reel video with ffmpeg...")
        generate_reel(
            local_image_path,
            next_row["name"],
            next_row["price"],
            next_row["angle"],
            local_video_path,
        )

        safe_name = "".join(c if c.isalnum() else "_" for c in next_row["name"])[:40]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        repo_relative_path = f"{REELS_OUTPUT_DIR}/{timestamp}_{safe_name}.mp4"

        print("Committing video to repo and building public URL...")
        video_url = commit_and_get_video_url(local_video_path, repo_relative_path)
        print("Video URL:", video_url)

    except (requests.RequestException, RuntimeError, subprocess.CalledProcessError) as e:
        print("Failed to build/host the reel:", e)
        sys.exit(1)

    try:
        channel_services = fetch_channel_services(access_token)
    except RuntimeError as e:
        print("Could not fetch channel info from Buffer:", e)
        sys.exit(1)

    caption = build_reel_caption(next_row)
    print("Generated caption:\n", caption)

    any_failure = False
    posted_to_any = False
    for channel_id in channel_ids:
        service = channel_services.get(channel_id, "")
        if service not in REEL_SUPPORTED_SERVICES:
            print(f"Skipping channel {channel_id} (service={service or 'unknown'}) - "
                  f"reels only supported for {REEL_SUPPORTED_SERVICES} right now.")
            continue
        try:
            result = post_video_to_buffer(
                caption, next_row["link"], video_url, channel_id, service, access_token
            )
            print(f"Posted reel to {service} channel {channel_id}:", result)
            posted_to_any = True
        except (requests.HTTPError, RuntimeError) as e:
            print(f"Failed to post reel to {service} channel {channel_id}:", e)
            any_failure = True

    if not posted_to_any or any_failure:
        print("Not marking as posted - will retry tomorrow.")
        sys.exit(1)

    next_row["posted"] = "yes"
    save_products(REELS_CSV_PATH, rows, fieldnames)
    print(f"Marked '{next_row['name']}' reel as posted.")


if __name__ == "__main__":
    main()
