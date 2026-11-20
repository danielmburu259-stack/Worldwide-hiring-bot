import os, requests
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
print(f"TOKEN len={len(BOT_TOKEN)} starts={BOT_TOKEN[:6]}")
print(f"CHANNEL_ID={CHANNEL_ID}")
r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHANNEL_ID, "text": "✅ TEST - If you see this in channel, Token + Channel + Admin are all CORRECT. Delete this message."}, timeout=20)
print(f"TELEGRAM TEST: {r.status_code} - {r.text[:500]}")
