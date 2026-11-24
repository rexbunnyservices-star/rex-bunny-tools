"""
Auto-post shareable audit scorecards to X (Twitter).

Posts at most 3 times/day, only for real (non-test) leads, using the
saved X session from the scraper. The share URL comes from the audit
lead's KV record (key share:<token>) — we find it via the public scorecard
stored in PocketBase's leads collection.

Usage:
  python post_x_viral.py --dry-run   # show planned tweets, no posting
  python post_x_viral.py             # post (max 3/day)

A daily cap and an explicit opt-in flag keep the account safe:
  Create an empty file ENABLE_X_POST to allow real posting.
"""
import argparse
import asyncio
import json
import os
import re
import random
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ENABLE = os.path.join(HERE, 'ENABLE_X_POST')
STATE = os.path.join(HERE, 'x_post_state.json')
LOG = os.path.join(HERE, 'x_post.log')
X_STATE = r'D:\MY Company\scraper\data\sessions\x_state.json'
MAX_PER_DAY = 3

COOKIES = []


def log(msg):
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE, encoding='utf-8'))
        except Exception:
            pass
    return {'posted': [], 'daily': {}}


def save_state(s):
    json.dump(s, open(STATE, 'w', encoding='utf-8'), indent=2)


def test_email(e):
    e = (e or '').lower()
    return e.endswith('@example.com') or e.endswith('@test.com') or 'rexbunnyservices' in e


def load_x_session():
    """Load saved X cookies into a format Playwright can add."""
    if not os.path.exists(X_STATE):
        return None
    data = json.load(open(X_STATE, encoding='utf-8'))
    cookies = data.get('cookies', data) if isinstance(data, dict) else data
    return cookies if isinstance(cookies, list) else None


async def post_to_x(text):
    from playwright.async_api import async_playwright
    cookies = load_x_session()
    if not cookies:
        raise RuntimeError('no X session cookies')
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        try:
            await ctx.add_cookies(cookies)
        except Exception:
            pass
        page = await ctx.new_page()
        await page.goto('https://x.com/compose/post', timeout=60000)
        await page.wait_for_timeout(3000)
        if 'login' in page.url.lower():
            raise RuntimeError('X session expired — run python main.py --login x')
        box = page.locator('[data-testid="tweetTextarea_0"]')
        await box.wait_for(timeout=20000)
        await box.fill(text)
        await page.wait_for_timeout(500)
        btn = page.locator('[data-testid="tweetButton"]')
        await btn.wait_for(timeout=10000)
        await btn.click()
        await page.wait_for_timeout(3000)
        await browser.close()
    return True


def get_share_leads():
    """Reuse audit_nurture's PocketBase fetch, filtering to recent real leads with score."""
    import sys
    sys.path.insert(0, HERE)
    from audit_nurture import pb_audit_leads
    out = []
    for lead in pb_audit_leads():
        email = lead.get('email', '')
        if test_email(email):
            continue
        score = lead.get('auditScore') or lead.get('score')
        site = lead.get('website') or lead.get('url') or ''
        if not score or not site:
            continue
        out.append((email, score, site, lead.get('created', '')))
    return out


def compose(score, site):
    try:
        host = site.split('//')[-1].split('/')[0].replace('www.', '')
    except Exception:
        host = site
    return random.choice([
        f"Just ran the free AI Visibility Audit on {host}. Score: {score}/100. Can you beat it? -> rexbunnyservices.online/rex/",
        f"AI Visibility Score for {host}: {score}/100. Four quick fixes flagged. Try it on your own site -> rexbunnyservices.online/rex/",
        f"{score}/100 for {host} in the AI Visibility Audit. The gaps are usually the same 4. Check yours -> rexbunnyservices.online/rex/",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    state = load_state()
    today = datetime.now(timezone.utc).date().isoformat()
    count = state['daily'].get(today, 0)
    if count >= MAX_PER_DAY and not args.dry_run:
        log(f'daily cap reached ({MAX_PER_DAY})')
        return

    leads = get_share_leads()
    log(f'found {len(leads)} real audit leads')
    candidates = [l for l in leads if l[0] not in state['posted']]
    random.shuffle(candidates)

    for email, score, site, created in candidates[:MAX_PER_DAY - count]:
        text = compose(score, site)
        if args.dry_run:
            log(f'DRY-RUN tweet: {text}')
            continue
        if not os.path.exists(ENABLE):
            log('ENABLE_X_POST missing — refusing to post publicly')
            return
        try:
            asyncio.get_event_loop().run_until_complete(post_to_x(text))
            state['posted'].append(email)
            state['daily'][today] = state['daily'].get(today, 0) + 1
            log(f'posted for {email}')
        except Exception as e:
            log(f'FAILED for {email}: {str(e)[:100]}')
            break
    if not args.dry_run:
        save_state(state)


if __name__ == '__main__':
    main()
