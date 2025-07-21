#!/usr/bin/env python3
"""
kickchatsend.py – send ONE chat line to a live Kick channel.

COOKIE.txt must be a single line that contains:
   session_token=USERID|TOKEN
   XSRF-TOKEN=<url-encoded string>
"""

import json, os, pathlib, re, sys, time, cloudscraper, urllib.parse

# ── load cookie ────────────────────────────────────────────────────────────
os.chdir(pathlib.Path(__file__).resolve().parent)
COOKIE = pathlib.Path("COOKIE.txt").read_text().strip()

def cval(key):
    m = re.search(fr"{key}=([^;]+)", COOKIE)
    return m.group(1) if m else None     # keep URL-encoded!

SESSION_RAW = cval("session_token")      # still URL-encoded (%7C)
XSRF_TOKEN  = cval("XSRF-TOKEN")
if not (SESSION_RAW and XSRF_TOKEN):
    sys.exit("COOKIE.txt must contain session_token and XSRF-TOKEN.")

# Bearer expects decoded token (with the literal | pipe)
SESSION_DECODED = urllib.parse.unquote(SESSION_RAW)

# ── ask for slug + message ─────────────────────────────────────────────────
slug = input("Kick channel slug: ").strip().lower()
msg  = input("Message to send : ").strip()
if not slug or not msg:
    sys.exit("Need both slug and message.")

# ── discover chatroom_id ───────────────────────────────────────────────────
S = cloudscraper.create_scraper()
S.headers.update({"cookie": COOKIE, "user-agent": "Mozilla/5.0"})

try:
    chat_id = S.get(f"https://kick.com/api/v2/channels/{slug}",
                    timeout=10).json()["chatroom"]["id"]
except Exception as e:
    sys.exit(f"Could not fetch channel info: {e}")

# ── build request ──────────────────────────────────────────────────────────
url = f"https://kick.com/api/v2/messages/send/{chat_id}"

headers = {
    "Authorization": f"Bearer {SESSION_DECODED}",
    "X-XSRF-TOKEN": XSRF_TOKEN,           # still URL-encoded!
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": f"https://kick.com/{slug}",
    "cluster": "v2",                      # Kick's front-end sends this
}

payload = {
    "content": msg,
    "type": "message",
    "message_ref": str(int(time.time() * 1000))  # ms epoch
}

r = S.post(url, headers=headers, json=payload, timeout=10)

if r.status_code == 201:
    print("✓ sent:", msg)
else:
    print("❌ failed:", r.status_code)
    print(r.text[:400]) 