# Reels Add-On (Instagram + Facebook video Reels)

This is a second, independent system alongside the working image-post
system. If something breaks here, your original image posts keep running
untouched - that was a deliberate design choice.

## How it works

1. `reels.csv` holds products the same way `products.csv` does.
2. Daily, GitHub Actions:
   - Downloads the product image
   - Uses ffmpeg (free, preinstalled on GitHub's runners) to build an
     8-second silent vertical video: product photo + title + price +
     short hook text + "link in bio"
   - Commits that video into the repo's `reels/` folder so it has a real,
     stable public URL (`raw.githubusercontent.com/...`)
   - Posts that video as a Reel to Instagram and Facebook via Buffer

## Setup (uses the same secrets you already added)

No new secrets needed - it reuses `BUFFER_ACCESS_TOKEN` and
`BUFFER_CHANNEL_IDS` from the image-post setup.

1. Upload `reels.csv`, the updated `scripts/post_reel.py`, and
   `.github/workflows/daily-reel.yml` into your repo, keeping the same
   folder structure.
2. Test manually: Actions tab -> "Daily Amazon Affiliate Reel" -> Run workflow.
3. Check the log the same way as before (Run reel poster script step).

## Honest limitations of this version

- **Silent, no music yet.** Adding royalty-free music is a real next step,
  kept out of this version on purpose to get one thing working first.
- **Pinterest is skipped for Reels** - Buffer's video-pin format wasn't
  validated yet, so the script intentionally only posts reels to Facebook
  and Instagram channels, while your image posts still go to all three.
- **Same caption-judgment caveat as before** - check a few reels after
  they go live to confirm the text overlay looks right and isn't cut off
  on your specific products' image shapes.
- **The repo will grow over time** as each day's video gets committed.
  Not a problem for a long while, but worth knowing - if it ever becomes
  an issue, old videos in `reels/` can be deleted since Buffer only needs
  the URL at the moment it fetches the video to schedule the post.
