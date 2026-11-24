# REX Bunny Tools

Small, useful scripts from [REX Bunny Services](https://rexbunnyservices.online) — a one-person agency building websites, stores, social and AI-search growth systems.

Nothing here is a secret: these are the real helpers we use, shared so you can audit your own setup or borrow the pattern.

## Scripts

### `audit_nurture.py`
A tiny, idempotent email nurture scheduler for free-tool signups. Reads leads from PocketBase, sends a timed 4-email sequence through an n8n webhook, suppresses test/sold addresses, and keeps state in a local JSON file. No third-party SaaS required.

```bash
python audit_nurture.py --dry-run   # see what would send
python audit_nurture.py             # send due emails
```

### `post_x_viral.py`
Posts shareable audit scorecards to X using a saved browser session, with a 3-per-day cap and an explicit enable flag (`ENABLE_X_POST`) so it can never post by accident.

```bash
python post_x_viral.py --dry-run    # preview tweets
```

### `pipeline-count.ts`
A Cloudflare Pages Function that returns a public, privacy-safe pipeline count without exposing any PocketBase records (the collection is admin-only). Returns both the current record count and an all-time processed total.

## Why we publish these

We build **AI Visibility Audit** — a free 18-point check of how ChatGPT, Perplexity and Gemini see your site. If you want to know whether AI search can find your business, run it at [rexbunnyservices.online](https://rexbunnyservices.online/rex/).

Licensed MIT. Questions? Open an issue.
