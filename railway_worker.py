#!/usr/bin/env python3
"""PTE Vocab Worker — runs on Railway, sends ntfy notifications on schedule."""

import json
import os
import random
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

# ── Config from Railway environment variables ─────────────────────────────────
NTFY_TOPIC       = os.environ.get("NTFY_TOPIC", "pte-vocab")
NTFY_SERVER      = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
INTERVAL_MINUTES = int(os.environ.get("INTERVAL_MINUTES", "30"))
WORDS_PER_ALERT  = int(os.environ.get("WORDS_PER_ALERT", "3"))
START_HOUR       = int(os.environ.get("START_HOUR", "10"))
END_HOUR         = int(os.environ.get("END_HOUR", "23"))
TIMEZONE         = os.environ.get("TIMEZONE", "Australia/Melbourne")

# CATEGORIES: comma-separated list, empty = all categories
# e.g. "บุคลิกลักษณะ,การสื่อสาร,สติปัญญา/การตัดสิน"
_cats_env = os.environ.get("CATEGORIES", "").strip()
CATEGORIES: list[str] = [c.strip() for c in _cats_env.split(",") if c.strip()]

# ── Word state (in-memory; resets on redeploy) ────────────────────────────────
shown_words: set[str] = set()
total_sent = 0

# ── ntfy sender ───────────────────────────────────────────────────────────────
def send_ntfy(title: str, body: str) -> None:
    payload = json.dumps({
        "topic":   NTFY_TOPIC,
        "title":   title,
        "message": body,
        "tags":    ["books"],
        "priority": 3,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            NTFY_SERVER,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[ntfy error] {e}")

# ── Word picker ────────────────────────────────────────────────────────────────
def pick_words(n: int) -> list[dict]:
    global shown_words
    from vocab_data import PTE_VOCABULARY
    from vocab_meta import VOCAB_META

    # attach meta to all words first
    pool = []
    for w in PTE_VOCABULARY:
        meta = VOCAB_META.get(w["word"], {})
        w["pron"] = meta.get("pron", "")
        w["pos"]  = meta.get("pos", "")
        w["cat"]  = meta.get("cat", "")
        pool.append(w)

    # filter by category if specified
    if CATEGORIES:
        pool = [w for w in pool if w["cat"] in CATEGORIES]
        if not pool:
            print("[warn] No words match CATEGORIES filter — using all words")
            pool = list(PTE_VOCABULARY)

    unseen = [w for w in pool if w["word"] not in shown_words]
    if len(unseen) < n:
        shown_words = set()
        unseen = list(pool)
        print("[info] Cycle complete — starting new cycle.")

    chosen = random.sample(unseen, min(n, len(unseen)))
    shown_words.update(w["word"] for w in chosen)
    return chosen

# ── Alert sender ──────────────────────────────────────────────────────────────
def send_alert() -> None:
    global total_sent
    tz  = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)

    if not (START_HOUR <= now.hour < END_HOUR):
        print(f"[{now:%H:%M}] Outside hours ({START_HOUR:02d}:00–{END_HOUR:02d}:00) — skip")
        return

    words = pick_words(WORDS_PER_ALERT)
    total_sent += 1

    for i, word in enumerate(words):
        title = f"PTE • {word['word']}  [{word.get('pos','')}]"
        body  = (
            f"/{word.get('pron','')}/"
            f"   #{word.get('cat','')}\n"
            f"{word.get('thai','')}\n"
            f"{word['meaning']}\n"
            f"{word.get('thai_example','')}"
        )
        send_ntfy(title, body)
        if i < len(words) - 1:
            time.sleep(0.8)

    words_str = ", ".join(w["word"] for w in words)
    print(f"[{now:%H:%M}] Sent #{total_sent}: {words_str}")

# ── Main loop ─────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 50)
    print("PTE Vocab Worker starting on Railway")
    print(f"  Topic      : {NTFY_TOPIC}")
    print(f"  Interval   : every {INTERVAL_MINUTES} min")
    print(f"  Hours      : {START_HOUR:02d}:00 – {END_HOUR:02d}:00 ({TIMEZONE})")
    print(f"  Words      : {WORDS_PER_ALERT} per alert")
    print(f"  Categories : {', '.join(CATEGORIES) if CATEGORIES else 'ทั้งหมด (all)'}")
    print("=" * 50)

    # Send one alert immediately on startup (so you know it works)
    send_alert()

    while True:
        time.sleep(INTERVAL_MINUTES * 60)
        send_alert()

if __name__ == "__main__":
    main()
