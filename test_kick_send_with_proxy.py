#!/usr/bin/env python3
"""
test_kick_send_with_proxy.py – версия с поддержкой прокси
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

print(f"SESSION_RAW: {SESSION_RAW}")
print(f"XSRF_TOKEN: {XSRF_TOKEN}")
print(f"SESSION_DECODED: {SESSION_DECODED}")

# ── настройка прокси ───────────────────────────────────────────────────────
proxy_url = "socks5://8mf7a:v49nk0v1@217.177.33.19:5432"  # прокси из БД
print(f"Using proxy: {proxy_url}")

# ── фиксированные значения для тестирования ─────────────────────────────────
slug = "xqc"  # популярный канал для тестирования
msg  = "тест сообщения"  # тестовое сообщение

print(f"Testing with channel: {slug}")
print(f"Testing with message: {msg}")

# ── discover chatroom_id ───────────────────────────────────────────────────
S = cloudscraper.create_scraper()

# Настраиваем прокси
if proxy_url.startswith('socks5://'):
    print("Configuring SOCKS5 proxy...")
    # Устанавливаем переменные окружения для SOCKS5
    import os
    os.environ['HTTP_PROXY'] = proxy_url
    os.environ['HTTPS_PROXY'] = proxy_url
elif proxy_url.startswith(('http://', 'https://')):
    print("Configuring HTTP/HTTPS proxy...")
    S.proxies = {'http': proxy_url, 'https': proxy_url}

S.headers.update({"cookie": COOKIE, "user-agent": "Mozilla/5.0"})

try:
    print(f"Getting channel info for: {slug}")
    response = S.get(f"https://kick.com/api/v2/channels/{slug}", timeout=10)
    print(f"Response status: {response.status_code}")
    print(f"Response text: {response.text[:400]}")
    
    if response.status_code != 200:
        print(f"❌ Failed to get channel info: {response.status_code}")
        sys.exit(1)
    
    chat_id = response.json()["chatroom"]["id"]
    print(f"✓ Got chatroom_id: {chat_id}")
    
except Exception as e:
    print(f"❌ Could not fetch channel info: {e}")
    sys.exit(1)

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

print(f"Sending POST to: {url}")
print(f"Headers: {headers}")
print(f"Payload: {payload}")

r = S.post(url, headers=headers, json=payload, timeout=10)

print(f"Response status: {r.status_code}")
print(f"Response text: {r.text[:400]}")

if r.status_code == 201:
    print("✓ sent:", msg)
else:
    print("❌ failed:", r.status_code)
    print(r.text[:400]) 