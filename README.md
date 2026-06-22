# Amazon Affiliate Auto-Poster

A free, automatic system that posts one product per day to your social
channels via Buffer, using GitHub Actions as the free scheduler/runner.

## How it actually works

1. `products.csv` holds your product list (name, price, link, angle).
2. Every day, a GitHub Action wakes up, picks the next unposted product,
   writes a caption, and schedules it through Buffer's API.
3. Buffer publishes it to your connected channels (Instagram, Facebook,
   etc. - not X/Twitter, which now charges per post with a link).
4. The script marks that product "posted" so it won't repeat.

Your ongoing job: add new rows to `products.csv` every so often. That's it.

## One-time setup (do this once, takes about 15-20 minutes)

### 1. Create a GitHub account and repo
- Go to github.com, sign up free.
- Create a **new repository** (can be private - recommended, since it's
  simpler than managing secrets visibility on a public repo).
- Upload all files from this folder into that repo, keeping the same
  folder structure (`.github/workflows/daily-post.yml`, `scripts/`, etc).

### 2. Create a Buffer account and connect your channels
- Go to buffer.com, sign up free.
- Connect Instagram, Facebook, Pinterest, or whichever channels you have
  (free plan supports 3 channels).

### 3. Create your Buffer Access Token
- Go to publish.buffer.com/settings/api -> Personal Keys tab.
- Click "New Key", name it anything (e.g. "AutoPoster").
- Copy the token shown - this is your `BUFFER_ACCESS_TOKEN`.

### 4. Get your Channel IDs
Buffer's API is GraphQL-based. To find each connected channel's ID:
- Go to the API Explorer linked from your API settings page (or
  developers.buffer.com), paste in your access token, and run:
  ```
  query {
    account {
      organizations {
        channels { id service }
      }
    }
  }
  ```
- This returns one `id` per connected channel (Facebook, Instagram,
  Pinterest) alongside which service it is. Copy all the IDs you want
  to post to.

### 5. Add secrets to your GitHub repo (never put these in the code itself)
In your repo: Settings -> Secrets and variables -> Actions -> New repository secret
- `BUFFER_ACCESS_TOKEN` = the token from step 3
- `BUFFER_CHANNEL_IDS` = comma-separated channel IDs, e.g. `abc123,def456,ghi789`

### 6. Test it manually
- Go to the "Actions" tab in your repo -> "Daily Amazon Affiliate Post" ->
  "Run workflow" button. This runs it immediately so you can check it works
  before waiting for the schedule.

## Adding new products

Open `products.csv` and add a new line in this exact format:

```
"Product Name Here",999,https://your-affiliate-link,"one honest reason to want this",no
```

Always set the last column to `no` for new entries - the script flips it
to `yes` automatically once posted.

## Important honest notes

- **This does not write itself.** You still decide which products go in
  the list - that judgment call was never something that could be removed.
- **Captions are template-based**, not deeply unique each time. Check a
  few after they go live and tell me if the wording feels off so I can
  adjust the templates in `scripts/post_product.py`.
- **X/Twitter is excluded on purpose** - as of Feb 2026 it charges per
  post with a link, so it's no longer free for this use case.
- **This does not guarantee sales.** It guarantees consistent, automatic
  posting. Whether people click and buy still depends on whether the
  products and captions are genuinely good - that's the part worth
  checking in on, not blindly trusting.
