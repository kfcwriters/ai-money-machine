#!/usr/bin/env python3
"""
Daily auto-poster: reads products.csv, picks the next unposted product,
generates a caption, and schedules it via Buffer's GraphQL API.

Required GitHub repo secrets (Settings -> Secrets and variables -> Actions):
  BUFFER_ACCESS_TOKEN   - your Buffer API personal access token
  BUFFER_CHANNEL_IDS    - comma-separated Buffer channel IDs to post to

Both are kept out of the code on purpose. Never put real keys directly
into this file or commit them - GitHub repos can be public.
"""

import csv
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import requests

CSV_PATH = "products.csv"
BUFFER_API_URL = "https://api.buffer.com"

CREATE_POST_MUTATION = """
mutation CreateScheduledPost(
  $text: String!,
  $channelId: ChannelId!,
  $dueAt: DateTime!,
  $imageUrl: String!,
  $metadata: PostInputMetaData
) {
  createPost(input: {
    text: $text,
    channelId: $channelId,
    schedulingType: automatic,
    mode: customScheduled,
    dueAt: $dueAt,
    assets: [
      { image: { url: $imageUrl } }
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

# Facebook and Instagram require an explicit post "type" (post/story/reel)
# when assets are attached. Pinterest and other networks don't need this.
NETWORK_METADATA = {
    "facebook": {"facebook": {"type": "post"}},
    "instagram": {"instagram": {"type": "post"}},
}

HOOK_TEMPLATES = [
    "Didn't expect to actually use this daily, but here we are.",
    "Saw this mentioned a few times and finally tried it. Worth it.",
    "Cheaper than I thought it'd be for what it actually does.",
    "This fixed an annoying problem I'd just been living with.",
    "Not sponsored, just genuinely useful for the price.",
]

HASHTAG_POOL = [
    "#AmazonFinds", "#AmazonIndia", "#BudgetFinds", "#DealOfTheDay",
    "#SmartBuy", "#DailyEssentials", "#TechFinds", "#WorthIt",
]


def load_products(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_products(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_caption(product):
    hook = random.choice(HOOK_TEMPLATES)
    tags = " ".join(random.sample(HASHTAG_POOL, 4))
    return (
        f"{hook}\n\n"
        f"{product['name']} - ₹{product['price']}\n"
        f"{product['angle']}.\n\n"
        f"Link in bio/comments.\n"
        f"{tags}"
    )


GET_CHANNELS_QUERY = """
query GetChannels {
  account {
    organizations {
      channels {
        id
        service
      }
    }
  }
}
"""


def fetch_channel_services(access_token):
    """Returns a dict mapping channel_id -> service name (e.g. 'facebook')."""
    response = requests.post(
        BUFFER_API_URL,
        json={"query": GET_CHANNELS_QUERY},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(
            f"HTTP {response.status_code} fetching channels: {response.text[:1000]}"
        )
    body = response.json()
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors fetching channels: {body['errors']}")

    mapping = {}
    orgs = body.get("data", {}).get("account", {}).get("organizations", [])
    for org in orgs:
        for channel in org.get("channels", []):
            mapping[channel["id"]] = channel["service"]
    return mapping


def post_to_buffer(caption, link, image_url, channel_id, service, access_token):
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
    variables = {
        "text": f"{caption}\n{link}",
        "channelId": channel_id,
        "dueAt": scheduled_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "imageUrl": image_url,
        "metadata": NETWORK_METADATA.get(service),  # None for networks that don't need it
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
        raise RuntimeError(
            f"HTTP {response.status_code} from Buffer: {response.text[:1000]}"
        )
    body = response.json()
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    result = body.get("data", {}).get("createPost", {})
    if "message" in result:  # MutationError shape
        raise RuntimeError(f"Buffer rejected post: {result['message']}")
    return body


def main():
    access_token = os.environ.get("BUFFER_ACCESS_TOKEN")
    channel_ids_raw = os.environ.get("BUFFER_CHANNEL_IDS", "")
    channel_ids = [c.strip() for c in channel_ids_raw.split(",") if c.strip()]

    if not access_token or not channel_ids:
        print("Missing BUFFER_ACCESS_TOKEN or BUFFER_CHANNEL_IDS secrets.")
        sys.exit(1)

    rows = load_products(CSV_PATH)
    if not rows:
        print("products.csv is empty. Nothing to post.")
        return

    fieldnames = rows[0].keys()
    next_row = next((r for r in rows if r.get("posted", "no").lower() == "no"), None)

    if next_row is None:
        print("All products already posted. Add more rows to products.csv.")
        return

    caption = build_caption(next_row)
    print("Generated caption:\n", caption)

    image_url = next_row.get("image_url", "").strip()
    if not image_url:
        print(f"No image_url set for '{next_row['name']}' - skipping, add one to products.csv.")
        sys.exit(1)

    try:
        channel_services = fetch_channel_services(access_token)
    except RuntimeError as e:
        print("Could not fetch channel info from Buffer:", e)
        sys.exit(1)

    any_failure = False
    for channel_id in channel_ids:
        service = channel_services.get(channel_id, "")
        if not service:
            print(f"Warning: channel {channel_id} not found in your Buffer account - skipping.")
            any_failure = True
            continue
        try:
            result = post_to_buffer(caption, next_row["link"], image_url, channel_id, service, access_token)
            print(f"Posted to {service} channel {channel_id}:", result)
        except (requests.HTTPError, RuntimeError) as e:
            print(f"Failed to post to {service} channel {channel_id}:", e)
            any_failure = True

    if any_failure:
        print("At least one channel failed - not marking as posted, will retry tomorrow.")
        sys.exit(1)

    next_row["posted"] = "yes"
    save_products(CSV_PATH, rows, fieldnames)
    print(f"Marked '{next_row['name']}' as posted.")


if __name__ == "__main__":
    main()
