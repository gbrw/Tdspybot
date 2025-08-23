# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import random
import threading
import requests
import pytz
from datetime import datetime

# =================== الإعدادات ===================
TELEGRAM_TOKEN = "8299272165:AAH1s7qqEEO1htuiMdjF1TnvzetpB4vE1Wc"
if not TELEGRAM_TOKEN:
    raise SystemExit("❌ TELEGRAM_TOKEN غير موجود في المتغيرات.")

POLL_MIN_SEC = int(os.environ.get("POLL_MIN_SEC", "240"))
POLL_MAX_SEC = int(os.environ.get("POLL_MAX_SEC", "360"))

DATA_DIR = os.environ.get("DATA_DIR", "/data")

OWNER_NAME = "غيث الراوي"
OWNER_IG = "https://instagram.com/gb.rw"
OWNER_TG = "https://t.me/gb_rw"
TESTFLIGHT_URL = "https://apps.apple.com/us/app/testflight/id899247664"
APP_NAME_AR = "TDS Video"

# روابط ثابتة (المراقبة)
FIXED_LINKS = [
    "https://testflight.apple.com/join/kYbkecxa",
    "https://testflight.apple.com/join/uk4993r5",
    "https://testflight.apple.com/join/6drWGVde",
    "https://testflight.apple.com/join/1Z9HQgNw",
]

# =================== مسارات الملفات ===================
os.makedirs(DATA_DIR, exist_ok=True)
PATH_SUBS = os.path.join(DATA_DIR, "subscribers.json")
PATH_KV = os.path.join(DATA_DIR, "kv.json")
PATH_LASTUPD = os.path.join(DATA_DIR, "last_update_id.txt")

# =================== جلسة HTTP ===================
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})
adapter = requests.adapters.HTTPAdapter(max_retries=2)
session.mount("http://", adapter)
session.mount("https://", adapter)

# =================== وقت بغداد ===================
DEFAULT_TZ = pytz.timezone("Asia/Baghdad")

def format_time(ts: int) -> str:
    try:
        dt_utc = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc)
        dt_local = dt_utc.astimezone(DEFAULT_TZ)
        return dt_local.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception:
        return "—"

# =================== أدوات مساعدة ===================
def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def log(*args):
    print(f"[{now_iso()}]", *args, file=sys.stdout, flush=True)

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_last_update_id():
    try:
        with open(PATH_LASTUPD, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None

def save_last_update_id(i):
    with open(PATH_LASTUPD, "w", encoding="utf-8") as f:
        f.write("" if i is None else str(i))

# =================== تيليغرام API ===================
def tg_delete_webhook():
    try:
        session.get(f"{API_BASE}/deleteWebhook", timeout=10)
    except:
        pass

def tg_get_updates(offset=None, timeout=50):
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset + 1
    r = session.get(f"{API_BASE}/getUpdates", params=params, timeout=timeout + 10)
    r.raise_for_status()
    return r.json()

def tg_send_message(chat_id, text, **kwargs):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
        "parse_mode": "HTML",
    }
    payload.update(kwargs)  # reply_markup=...
    try:
        r = session.post(f"{API_BASE}/sendMessage", json=payload, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log("sendMessage error:", e)

# =============== لوحات الأزرار ===============
def main_keyboard():
    return {
        "keyboard": [
            [{"text": "🟢 تفعيل الإشعارات"}, {"text": "🔴 تعطيل الإشعارات"}],
            [{"text": "📊 الحالة"}, {"text": "👤 المالك"}],
            [{"text": "ℹ️ المساعدة"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def testflight_inline_button():
    return {
        "inline_keyboard": [
            [{"text": "⬇️ تحميل TestFlight", "url": TESTFLIGHT_URL}]
        ]
    }

# =================== مشتركين ===================
def load_subscribers():
    return read_json(PATH_SUBS, [])

def save_subscribers(subs):
    write_json(PATH_SUBS, list(sorted(set(int(x) for x in subs))))

# =================== مراقبة TestFlight ===================
def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = (s.replace("’", "'")
           .replace("‘", "'")
           .replace("“", '"')
           .replace("”", '"')
           .replace("–", "-")
           .replace("—", "-")
           .replace("\u00a0", " "))
    s = s.replace("isn’t", "isn't").replace("is not", "isn't")
    s = s.replace("'", "")
    s = " ".join(s.split())
    return s

TF_AVAILABLE_MARKERS = [
    "join the beta",
    "accept",
]

TF_FULL_MARKERS = [
    "this beta is full",
    "beta is full",
    "this beta isnt accepting any new testers right now",
    "this beta isnt accepting any new testers",
    "isnt accepting any new testers",
    "is not accepting any new testers",
    "no longer accepting new testers",
    "no longer accepting testers",
    "no longer available for testing",
]

TF_UNAVAILABLE_HINTS = [
    "not available",
    "no longer available",
    "app not available",
    "page not found",
    "the requested app is not available or does not exist",
]

def fetch_link_status(url, timeout=20):
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        code = resp.status_code
        html_norm = normalize_text(resp.text)

        if code == 404:
            return "not_found"

        for m in TF_FULL_MARKERS:
            if m in html_norm:
                return "full"

        for m in TF_AVAILABLE_MARKERS:
            if m in html_norm:
                return "open"

        for m in TF_UNAVAILABLE_HINTS:
            if m in html_norm:
                return "not_found"

        return "full"  # الافتراضي الآمن
    except Exception as e:
        log("fetch_link_status error for", url, ":", e)
        return "error"

def load_kv():
    return read_json(PATH_KV, {"link_states": {}})

def save_kv(kv):
    write_json(PATH_KV, kv)

def broadcast(text):
    subs = load_subscribers()
    for uid in subs:
        tg_send_message(uid, text, reply_markup=main_keyboard())
        time.sleep(0.05)

def format_state_msg(url, state, ts):
    labels = {
        "open": ("✅", "متاح"),
        "full": ("⛔", "ممتلئ"),
        "not_found": ("❓", "غير موجود"),
        "unknown": ("ℹ️", "غير معروف"),
        "error": ("⚠️", "خطأ"),
    }
    badge, label = labels.get(state, ("❓", state))
    return f"{badge} {label} — {format_time(ts)}\n🔗 {url}"

def watch_links_and_notify():
    while True:
        try:
            kv = load_kv()
            last = kv.get("link_states", {})
            while True:
                changed_msgs = []
                curr = {}
                for url in FIXED_LINKS:
                    state = fetch_link_status(url)
                    ts = int(time.time())
                    curr[url] = {"state": state, "ts": ts}
                    prev_state = (last.get(url) or {}).get("state")
                    if state != prev_state:
                        changed_msgs.append(format_state_msg(url, state, ts))
                if changed_msgs:
                    broadcast("\n\n".join(changed_msgs))
                last = curr
                kv["link_states"] = last
                save_kv(kv)
                time.sleep(random.randint(POLL_MIN_SEC, POLL_MAX_SEC))
        except Exception as e:
            log("watch error:", e)
            time.sleep(30)

# =================== رسائل الواجهة ===================
WELCOME_TEXT = (
    f"هذا البوت يتحقق من توفر تطبيق <b>{APP_NAME_AR}</b> عبر TestFlight.\n"
    "📌 إذا توفر مكان شاغر سيتم إشعارك فورًا.\n\n"
    "ℹ️ ملاحظة: لا يمكنك تثبيت التطبيق بدون TestFlight.\n"
    "⬇️ حمّله من الزر أدناه"
)

HELP_TEXT = """\
ℹ️ <b>المساعدة</b>
🟢 <b>تفعيل الإشعارات</b>: تفعيل إشعارات تغيّر حالة روابط TestFlight
🔴 <b>تعطيل الإشعارات</b>: إيقاف الإشعارات
📊 <b>الحالة</b>: عرض الحالة الحالية
👤 <b>المالك</b>: معلومات عن المطوّر
"""

def cmd_start(chat_id, from_user):
    tg_send_message(chat_id, WELCOME_TEXT, reply_markup=testflight_inline_button())
    tg_send_message(chat_id, "اختر من الأزرار 👇", reply_markup=main_keyboard())

def cmd_help(chat_id):
    tg_send_message(chat_id, HELP_TEXT, reply_markup=main_keyboard())

def cmd_enable(chat_id):
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        save_subscribers(subs)
    tg_send_message(chat_id, "تم <b>تفعيل</b> الإشعارات ✅", reply_markup=main_keyboard())

def cmd_disable(chat_id):
    subs = load_subscribers()
    if chat_id in subs:
        subs = [x for x in subs if x != chat_id]
        save_subscribers(subs)
    tg_send_message(chat_id, "تم <b>تعطيل</b> الإشعارات ⛔", reply_markup=main_keyboard())

def cmd_status(chat_id):
    kv = load_kv()
    states = kv.get("link_states", {})
    if not states:
        tg_send_message(chat_id, "لا توجد حالات محفوظة بعد.", reply_markup=main_keyboard())
        return
    lines = ["<b>الحالة الحالية:</b>"]
    for url in FIXED_LINKS:
        s = states.get(url, {})
        st = s.get("state", "unknown")
        ts = s.get("ts", 0)
        lines.append(format_state_msg(url, st, ts))
    tg_send_message(chat_id, "\n\n".join(lines), disable_web_page_preview=True, reply_markup=main_keyboard())

def cmd_owners(chat_id):
    tg_send_message(
        chat_id,
        f"<b>المالك:</b> {OWNER_NAME}\n"
        f"IG: {OWNER_IG}\n"
        f"TG: {OWNER_TG}",
        disable_web_page_preview=True,
        reply_markup=main_keyboard()
    )

def handle_text_message(chat_id, text, from_user):
    t = (text or "").strip()
    if t in ("/start", "ابدأ"):
        cmd_start(chat_id, from_user)
    elif t in ("/help", "ℹ️ المساعدة"):
        cmd_help(chat_id)
    elif t in ("/subscribe", "🟢 تفعيل الإشعارات"):
        cmd_enable(chat_id)
    elif t in ("/unsubscribe", "🔴 تعطيل الإشعارات"):
        cmd_disable(chat_id)
    elif t in ("/status", "📊 الحالة"):
        cmd_status(chat_id)
    elif t in ("/owners", "👤 المالك"):
        cmd_owners(chat_id)
    else:
        tg_send_message(chat_id, "اختر من الأزرار 👇", reply_markup=main_keyboard())

def handle_update(u):
    if "message" in u:
        msg = u["message"]
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {}) or {}
        text = msg.get("text", "")
        if text:
            handle_text_message(chat_id, text, from_user)

def poll_loop():
    while True:
        try:
            tg_delete_webhook()
            last_id = load_last_update_id()
            while True:
                data = tg_get_updates(last_id, timeout=50)
                updates = data.get("result", [])
                for u in updates:
                    last_id = max(last_id or 0, u["update_id"])
                    handle_update(u)
                save_last_update_id(last_id)
        except Exception as e:
            log("poll error:", e)
            time.sleep(30)

# =================== main ===================
def main():
    log("Bot starting…")
    threading.Thread(target=watch_links_and_notify, daemon=True, name="watcher").start()
    threading.Thread(target=poll_loop, daemon=True, name="poller").start()
    while True:
        time.sleep(300)

if __name__ == "__main__":
    main()
