#!/usr/bin/env python3
"""
Daily auto-poster: reads products.csv, picks the next unposted product,
generates a caption, and schedules it to Buffer's connected channels.

Required GitHub repo secrets (Settings -> Secrets and variables -> Actions):
  BUFFER_ACCESS_TOKEN   - your Buffer API personal access token
  BUFFER_PROFILE_IDS    - comma-separated Buffer profile IDs to post to

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
BUFFER_API_URL = "https://api.bufferapp.com/1/updates/create.json"

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


def post_to_buffer(caption, link, access_token, profile_ids):
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "text": f"{caption}\n{link}",
        "profile_ids[]": profile_ids,
        "scheduled_at": scheduled_time.isoformat(),
    }
    response = requests.post(
        BUFFER_API_URL,
        data=payload,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def main():
    access_token = os.environ.get("BUFFER_ACCESS_TOKEN")
    profile_ids_raw = os.environ.get("BUFFER_PROFILE_IDS", "")
    profile_ids = [p.strip() for p in profile_ids_raw.split(",") if p.strip()]

    if not access_token or not profile_ids:
        print("Missing BUFFER_ACCESS_TOKEN or BUFFER_PROFILE_IDS secrets.")
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

    try:
        result = post_to_buffer(caption, next_row["link"], access_token, profile_ids)
        print("Buffer response:", result)
    except requests.HTTPError as e:
        print("Buffer API call failed:", e, e.response.text if e.response else "")
        sys.exit(1)

    next_row["posted"] = "yes"
    save_products(CSV_PATH, rows, fieldnames)
    print(f"Marked '{next_row['name']}' as posted.")


if __name__ == "__main__":
    main()
