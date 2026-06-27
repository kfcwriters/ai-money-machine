#!/usr/bin/env python3
"""
Standalone Pinterest poster - completely separate from post_product.py
and post_reel.py on purpose. If this breaks or needs more debugging,
the working Facebook/Instagram systems are never touched.

Reads pinterest_products.csv, picks the next unposted product, and
schedules a Pin via Buffer's GraphQL API using the full (un-shortened)
Amazon link, since Pinterest blocks shortened links outright.

Required GitHub repo secret:
  BUFFER_ACCESS_TOKEN     - same token used by the other scripts
  PINTEREST_CHANNEL_ID    - just the one Pinterest channel ID (not a list)

Required CSV columns in pinterest_products.csv:
  name, price, link_full, angle, image_url, posted
(link_full must be the real, full Amazon URL - no amzn.to / link.amazon)
"""

import csv
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

CSV_PATH = "pinterest_products.csv"
BUFFER_API_URL = "https://api.buffer.com"

CREATE_POST_MUTATION = """
mutation CreatePinterestPost(
  $text: String!,
  $channelId: ChannelId!,
  $dueAt: DateTime!,
  $imageUrl: String!
) {
  createPost(input: {
    text: $text,
    channelId: $channelId,
    schedulingType: automatic,
    mode: customScheduled,
    dueAt: $dueAt,
    assets: [
      { image: { url: $imageUrl } }
    ]
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


def load_products(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_products(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_pinterest_caption(product):
    """
    Pinterest caps posts at 500 characters and performs better with
    short, plain descriptions rather than hashtag-heavy captions.
    """
    name = product["name"]
    if len(name) > 80:
        name = name[:77] + "..."
    angle = product["angle"]
    if len(angle) > 100:
        angle = angle[:97] + "..."
    return f"{name} - Rs {product['price']}. {angle}."


def post_to_buffer(caption, link, image_url, channel_id, access_token):
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
    variables = {
        "text": f"{caption}\n{link}",
        "channelId": channel_id,
        "dueAt": scheduled_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "imageUrl": image_url,
    }
    response = requests.post(
        BUFFER_API_URL,
        json={"query": CREATE_POST_MUTATION, "variables": variables},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=20,
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


def main():
    access_token = os.environ.get("BUFFER_ACCESS_TOKEN")
    channel_id = os.environ.get("PINTEREST_CHANNEL_ID", "").strip()

    if not access_token or not channel_id:
        print("Missing BUFFER_ACCESS_TOKEN or PINTEREST_CHANNEL_ID secrets.")
        sys.exit(1)

    if not os.path.exists(CSV_PATH):
        print(f"{CSV_PATH} not found - create it with columns: "
              f"name,price,link_full,angle,image_url,posted")
        return

    rows = load_products(CSV_PATH)
    if not rows:
        print(f"{CSV_PATH} is empty. Nothing to post.")
        return

    fieldnames = rows[0].keys()
    next_row = next((r for r in rows if r.get("posted", "no").lower() == "no"), None)
    if next_row is None:
        print("All Pinterest products already posted. Add more rows to pinterest_products.csv.")
        return

    link_full = next_row.get("link_full", "").strip()
    if not link_full:
        print(f"No link_full set for '{next_row['name']}' - skipping. "
              f"Pinterest requires the full, un-shortened Amazon link.")
        sys.exit(1)

    image_url = next_row.get("image_url", "").strip()
    if not image_url:
        print(f"No image_url set for '{next_row['name']}' - skipping.")
        sys.exit(1)

    caption = build_pinterest_caption(next_row)
    print("Generated caption:\n", caption)
    print("Caption + link length:", len(caption) + len(link_full) + 1, "/ 500 max")

    try:
        result = post_to_buffer(caption, link_full, image_url, channel_id, access_token)
        print(f"Posted to pinterest channel {channel_id}:", result)
    except (requests.HTTPError, RuntimeError) as e:
        print(f"Failed to post to pinterest channel {channel_id}:", e)
        sys.exit(1)

    next_row["posted"] = "yes"
    save_products(CSV_PATH, rows, fieldnames)
    print(f"Marked '{next_row['name']}' as posted on Pinterest.")


if __name__ == "__main__":
    main()
