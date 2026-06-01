#!/usr/bin/env python3
"""PTE Vocabulary Alert App — macOS + iPhone (ntfy) notifications on a schedule."""

import json
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
HISTORY_FILE = BASE_DIR / "history.json"


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"shown": [], "total_sessions": 0, "start_date": datetime.now().isoformat()}


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)


# ── Notification senders ─────────────────────────────────────────────────────

def notify_mac(title, body, sound=True):
    sound_str = "default" if sound else "none"
    script = f'display notification "{body}" with title "{title}" sound name "{sound_str}"'
    subprocess.run(["osascript", "-e", script], check=False)


def notify_ntfy(title, body, cfg, sound=True):
    """Send a push notification to iPhone via ntfy.sh."""
    topic = cfg.get("ntfy_topic", "").strip()
    server = cfg.get("ntfy_server", "https://ntfy.sh").rstrip("/")
    if not topic:
        return

    url = f"{server}/{topic}"

    # ntfy headers must be ASCII — encode non-ASCII with RFC 5987
    def encode_header(s):
        try:
            s.encode("ascii")
            return s
        except UnicodeEncodeError:
            encoded = urllib.parse.quote(s.encode("utf-8"))
            return f"=?utf-8?Q?{s.encode('utf-8').hex()}?="

    # Simple safe approach: send as JSON payload instead
    import json as _json
    payload = _json.dumps({
        "topic": topic,
        "title": title,
        "message": body,
        "tags": ["books"],
        "priority": 3,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{server}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"ntfy error: {e}")


def send_notification(title, body, cfg, sound=True):
    if cfg.get("notify_mac", True):
        notify_mac(title, body, sound)
    if cfg.get("notify_iphone", False) and cfg.get("ntfy_topic"):
        notify_ntfy(title, body, cfg, sound)


# ── Core logic ───────────────────────────────────────────────────────────────

def pick_words(n, history):
    from vocab_data import PTE_VOCABULARY
    from vocab_meta import VOCAB_META
    shown_words = set(history.get("shown", []))
    unseen = [w for w in PTE_VOCABULARY if w["word"] not in shown_words]
    if len(unseen) < n:
        history["shown"] = []
        unseen = list(PTE_VOCABULARY)
    chosen = random.sample(unseen, min(n, len(unseen)))
    history["shown"].extend(w["word"] for w in chosen)
    # merge pronunciation / pos / category
    for w in chosen:
        meta = VOCAB_META.get(w["word"], {})
        w["pron"] = meta.get("pron", "")
        w["pos"]  = meta.get("pos", "")
        w["cat"]  = meta.get("cat", "")
    return chosen


def send_vocab_alert():
    cfg = load_config()
    if not cfg.get("enabled", True):
        return

    now = datetime.now()
    if not (cfg.get("start_hour", 8) <= now.hour < cfg.get("end_hour", 22)):
        return

    history = load_history()
    n = cfg.get("words_per_alert", 3)
    words = pick_words(n, history)
    history["total_sessions"] = history.get("total_sessions", 0) + 1
    save_history(history)

    sound = cfg.get("sound", True)

    for i, word in enumerate(words):
        pos  = word.get("pos", "")
        pron = word.get("pron", "")
        cat  = word.get("cat", "")
        title = f"PTE • {word['word']}  [{pos}]"
        body = (
            f"/{pron}/   #{cat}\n"
            f"{word.get('thai','')}\n"
            f"{word['meaning']}\n"
            f"{word.get('thai_example','')}"
        )
        send_notification(title, body, cfg, sound=(i == 0 and sound))
        if i < len(words) - 1:
            time.sleep(0.6)


def run_daemon():
    print("PTE Vocab Daemon started. Press Ctrl+C to stop.")
    while True:
        cfg = load_config()
        if not cfg.get("enabled", True):
            print(f"[{datetime.now():%H:%M}] Disabled — sleeping 60s")
            time.sleep(60)
            continue
        send_vocab_alert()
        interval = cfg.get("interval_minutes", 30) * 60
        next_time = datetime.fromtimestamp(time.time() + interval).strftime("%H:%M")
        print(f"[{datetime.now():%H:%M}] Alert sent. Next at {next_time}")
        time.sleep(interval)


# ── CLI ──────────────────────────────────────────────────────────────────────

HELP = """
PTE Vocabulary Alert App

Commands:
  python pte_vocab.py run              Start the background scheduler
  python pte_vocab.py now              Send an alert immediately (test)
  python pte_vocab.py config           Show current settings
  python pte_vocab.py set <key> <val>  Change a setting:
      interval_minutes  20
      words_per_alert   5
      start_hour        7
      end_hour          23
      enabled           true/false
      sound             true/false
      notify_mac        true/false
      notify_iphone     true/false
      ntfy_topic        pte-vocab
      ntfy_server       https://ntfy.sh
  python pte_vocab.py stats            Show learning progress
  python pte_vocab.py reset            Reset word history
  python pte_vocab.py help             Show this help
"""


def cmd_config():
    cfg = load_config()
    topic = cfg.get("ntfy_topic", "not set")
    status = "เปิดอยู่" if cfg.get("notify_iphone") else "ปิดอยู่"
    print("\nCurrent settings:")
    print(f"  interval_minutes  : {cfg['interval_minutes']} นาที")
    print(f"  words_per_alert   : {cfg['words_per_alert']} คำ")
    print(f"  start_hour        : {cfg['start_hour']:02d}:00")
    print(f"  end_hour          : {cfg['end_hour']:02d}:00")
    print(f"  enabled           : {cfg['enabled']}")
    print(f"  notify_mac        : {cfg.get('notify_mac', True)}")
    print(f"  notify_iphone     : {cfg.get('notify_iphone', False)}  ({status})")
    print(f"  ntfy_topic        : {topic}")
    print(f"  ntfy_server       : {cfg.get('ntfy_server', 'https://ntfy.sh')}\n")


def cmd_set(key, value):
    cfg = load_config()
    int_keys = {"interval_minutes", "words_per_alert", "start_hour", "end_hour"}
    bool_keys = {"enabled", "sound", "notify_mac", "notify_iphone"}
    str_keys = {"ntfy_topic", "ntfy_server"}
    if key in int_keys:
        cfg[key] = int(value)
    elif key in bool_keys:
        cfg[key] = value.lower() in ("true", "1", "yes")
    elif key in str_keys:
        cfg[key] = value
    else:
        print(f"ไม่รู้จัก key '{key}'")
        return
    save_config(cfg)
    print(f"อัพเดทแล้ว: {key} = {cfg[key]}")


def cmd_stats():
    from vocab_data import PTE_VOCABULARY
    history = load_history()
    total = len(PTE_VOCABULARY)
    seen = len(set(history.get("shown", [])))
    sessions = history.get("total_sessions", 0)
    start = history.get("start_date", "unknown")[:10]
    pct = seen / total * 100 if total else 0
    bar_len = 30
    filled = int(bar_len * seen / total) if total else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\nสถิติการเรียน:")
    print(f"  เริ่มเรียนวันที่   : {start}")
    print(f"  ส่งแจ้งเตือนแล้ว  : {sessions} ครั้ง")
    print(f"  คำศัพท์ทั้งหมด   : {total} คำ")
    print(f"  เรียนไปแล้ว      : {seen} / {total} คำ")
    print(f"  ความคืบหน้า      : [{bar}] {pct:.1f}%\n")


def cmd_reset():
    history = load_history()
    history["shown"] = []
    save_history(history)
    print("รีเซ็ตแล้ว จะเริ่มต้นใหม่จากคำแรก")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "help":
        print(HELP)
    elif args[0] == "run":
        run_daemon()
    elif args[0] == "now":
        send_vocab_alert()
        print("ส่งแจ้งเตือนแล้ว")
    elif args[0] == "config":
        cmd_config()
    elif args[0] == "set" and len(args) == 3:
        cmd_set(args[1], args[2])
    elif args[0] == "stats":
        cmd_stats()
    elif args[0] == "reset":
        cmd_reset()
    else:
        print("ไม่รู้จักคำสั่งนี้ ลองพิมพ์: python3 pte_vocab.py help")


if __name__ == "__main__":
    main()
