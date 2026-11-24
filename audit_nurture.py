"""
Audit → Sales nurture sequence.

Reads leads captured by /api/audit from PocketBase and sends a timed
4-email sequence through the proven n8n audit-email webhook (Maileroo).

Schedule (days after audit):
  +0  Email 1 — report (already sent by /api/audit; see note below)
  +3  Email 2 — proof / before-after
  +7  Email 3 — direct $197 SEO Audit offer
  +14 Email 4 — last call / higher-tier nudge

State lives in nurture_state.json so the script is idempotent.
Suppress any lead whose status is 'sold' or who replied (manual flag).

Usage:
  python audit_nurture.py --dry-run     # show what would send, no email
  python audit_nurture.py               # send due emails
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'nurture_state.json')
WEBHOOK = 'https://n8n.rexbunnyservices.online/webhook/audit-email'
PB_URL = 'https://pb.rexbunnyservices.online'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'

STEP_DAYS = {2: 3, 3: 7, 4: 14}  # email number -> days after audit

# Never nurture internal/test addresses.
SUPPRESS_EMAILS = {
    'anassaifiboy74@gmail.com', 'help@rexbunnyservices.com',
    'help@rexbunnyservices.online', 'probe@example.com',
    'audit-test@example.com', 'viralcheck@example.com',
    'finalviral@example.com', 'browsershare@example.com',
    'finalcheck@example.com', 'ratelimit-test@example.com',
    'rl@example.com', 'test@example.com',
}

def is_test_email(email: str) -> bool:
    e = email.lower().strip()
    return (e in SUPPRESS_EMAILS or e.endswith('@example.com')
            or e.endswith('@test.com') or e.endswith('@localhost'))

EMAILS = {
    2: {
        'subject': 'We moved our own site 78 → 85 in AI visibility (here is how)',
        'body': '''<p>Hi,</p>
<p>When we ran our own audit a few months ago, the score was <strong>78/100</strong>. The four fixes were the usual suspects: missing entity schema, thin llms.txt, no FAQ schema, and a vague title tag.</p>
<p>After fixing them: <strong>85/100</strong>, and LCP dropped from <strong>4.8s to 3.2s</strong>. Those are our own measured numbers — not a client case study.</p>
<p>Your audit flagged the same kinds of issues. The fastest way to clear them is our <strong>AI Visibility Audit — now $197</strong> (one-time): a technical fix pass, schema you can verify, and a written action plan.</p>
<p><a href="https://rexbunnyservices.online/pricing">See exactly what is included →</a></p>
<p>— Anas, RexBunny Services</p>''',
    },
    3: {
        'subject': 'Your competitors are being quoted by ChatGPT. You can be too.',
        'body': '''<p>Hi,</p>
<p>AI search does not rank pages the way Google does. It <em>quotes</em> entities it can verify — and if your structured data and llms.txt are thin, it quietly picks someone else.</p>
<p>That is the whole game right now, and it is still early.</p>
<p>We do one thing about it: the <strong>$197 AI Visibility Audit</strong>. No retainer, no long contract. We find the gaps, fix the critical ones, and hand you a plan you keep either way.</p>
<p><a href="https://rexbunnyservices.online/pricing">Book the $197 audit →</a></p>
<p>Reply to this email if you want me to look at your site first.</p>
<p>— Anas, RexBunny Services</p>''',
    },
    4: {
        'subject': 'Last note: from score to site (and a freelancer price)',
        'body': '''<p>Hi,</p>
<p>Last note from me on this.</p>
<p>If you would rather we just build it, a <strong>Starter Site is now $1,997</strong> — 3–5 pages, schema-clean, edge-deployed, Lighthouse-targeted, and ready for AI search from day one. No agency markup.</p>
<p>If you want to keep it simple, the <strong>$197 audit</strong> is still there and is the natural first step.</p>
<p><a href="https://rexbunnyservices.online/pricing">See the freelancer pricing →</a></p>
<p>Either way, the scorecard from your free audit is yours to keep and share.</p>
<p>— Anas, RexBunny Services</p>''',
    },
}


def log(msg):
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with open(os.path.join(HERE, 'nurture.log'), 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE, encoding='utf-8'))
        except Exception:
            pass
    return {'sent': {}, 'suppressed': []}


def save_state(s):
    json.dump(s, open(STATE, 'w', encoding='utf-8'), indent=2)


def pb_audit_leads():
    """Fetch audit leads from PocketBase via the local instance."""
    urls = ['http://127.0.0.1:8090', PB_URL]
    for base in urls:
        try:
            auth = urllib.request.Request(
                base + '/api/collections/_superusers/auth-with-password',
                data=json.dumps({'identity': 'admin@rexbunnyservices.com',
                                 'password': os.environ.get('PB_PASSWORD', 'Admin12345!')}).encode(),
                headers={'Content-Type': 'application/json', 'User-Agent': UA}, method='POST')
            token = json.loads(urllib.request.urlopen(auth, timeout=20).read())['token']
            req = urllib.request.Request(
                base + "/api/collections/leads/records?perPage=200&filter=" +
                urllib.parse.quote('source="audit-tool"'),
                headers={'Authorization': 'Bearer ' + token, 'User-Agent': UA})
            return json.loads(urllib.request.urlopen(req, timeout=20).read()).get('items', [])
        except Exception as e:
            log(f'PB fetch failed ({base}): {str(e)[:80]}')
    return []


def send(to, subject, html):
    payload = json.dumps({'to': to, 'subject': subject, 'html': html}).encode()
    req = urllib.request.Request(WEBHOOK, data=payload,
                                 headers={'Content-Type': 'application/json', 'User-Agent': UA},
                                 method='POST')
    resp = urllib.request.urlopen(req, timeout=30)
    return resp.status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    state = load_state()
    leads = pb_audit_leads()
    log(f'checked {len(leads)} audit leads')
    now = datetime.now(timezone.utc)
    sent = 0

    for lead in leads:
        email = lead.get('email', '')
        if not email or '@' not in email or is_test_email(email):
            continue
        if lead.get('status') == 'sold' or email in state.get('suppressed', []):
            continue
        created = lead.get('created') or lead.get('createdAt') or ''
        try:
            t = datetime.fromisoformat(created.replace('Z', '+00:00'))
        except Exception:
            continue
        for step, delay in STEP_DAYS.items():
            key = f'{email}:{step}'
            if key in state['sent']:
                continue
            if now - t < timedelta(days=delay):
                continue
            cfg = EMAILS[step]
            if args.dry_run:
                log(f'DRY-RUN would send #{step} to {email}')
            else:
                try:
                    send(email, cfg['subject'], cfg['body'])
                    state['sent'][key] = now.isoformat()
                    sent += 1
                    log(f'sent #{step} to {email}')
                except Exception as e:
                    log(f'FAILED #{step} to {email}: {str(e)[:80]}')
    if not args.dry_run:
        save_state(state)
    log(f'done — {sent} email(s) sent')


if __name__ == '__main__':
    main()
