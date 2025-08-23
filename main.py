# -*- coding: utf-8 -*-
import os
import time
import json
import random
import threading
import requests
from datetime import datetime

# =================== الإعدادات ===================
TELEGRAM_TOKEN = os.environ.get("8299272165:AAH1s7qqEEO1htuiMdjF1TnvzetpB4vE1Wc")
if not TELEGRAM_TOKEN:
    raise SystemExit("❌ TELEGRAM_TOKEN غير موجود في المتغيرات.")

ADMIN_IDS = {238547634}  # ضع معرف المدير هنا

POLL_MIN_SEC = int(os.environ.get("POLL_MIN_SEC", "30"))
POLL_MAX_SEC = int(os.environ.get("POLL_MAX_SEC", "90"))

DATA_DIR = os.environ.get("DATA_DIR", "/data")

OWNER_NAME = "غيث الراوي"
OWNER_IG = "https://instagram.com/gb.rw"
OWNER_TG = "https://t.me/gb_rw"
TESTFLIGHT_URL = "https://apps.apple.com/us/app/testflight/id899247664"
APP_NAME_AR = "TDS Video"

# روابط ثابتة
FIXED_LINKS = [
    "https://testflight.apple.com/join/kYbkecxa",
    "https://testflight.apple.com/join/uk4993r5",
    "https://testflight.apple.com/join/6drWGVde",
    "https://testflight.apple.com/join/1Z9HQgNw",
]

# =================== مسارات الملفات ===================
os.makedirs(DATA_DIR, exist_ok=True)
PATH_SUBS = os.path.join(DATA_DIR, "subscribers.json")
PATH_LINKS = os.path.join(DATA_DIR, "links.json")
PATH_EVENTS = os.path.join(DATA_DIR, "events.json")
PATH_LASTUPD = os.path.join(DATA_DIR, "last_update_id.txt")
PATH_KV = os.path.join(DATA_DIR, "kv.json")

PENDING_ACTIONS = {}

# =================== جلسة HTTP ===================
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.8",
})

# =================== أدوات مساعدة ===================

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        print(f"[{now_iso()}] read_json error {path}:", e)
        return default

def write_json(path, obj):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[{now_iso()}] write_json error {path}:", e)

def load_last_update_id():
    try:
        with open(PATH_LASTUPD, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None

def save_last_update_id(i):
    try:
        with open(PATH_LASTUPD, "w", encoding="utf-8") as f:
            f.write(str(i if i is not None else ""))
    except Exception as e:
        print(f"[{now_iso()}] save_last_update_id error:", e)

def ensure_file_defaults():
    if not os.path.exists(PATH_SUBS):
        write_json(PATH_SUBS, [])
    if not os.path.exists(PATH_LINKS):
        write_json(PATH_LINKS, [])
    if not os.path.exists(PATH_EVENTS):
        write_json(PATH_EVENTS, [])
    if not os.path.exists(PATH_KV):
        write_json(PATH_KV, {"link_states": {}})

ensure_file_defaults()

# =================== واجهة تيليغرام ===================

def tg_delete_webhook():
    try:
        r = session.get(f"{API_BASE}/deleteWebhook", timeout=10)
        r.raise_for_status()
        print(f"[{now_iso()}] deleteWebhook:", r.json())
    except Exception as e:
        print(f"[{now_iso()}] deleteWebhook error:", e)

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
    payload.update(kwargs)
    try:
        r = session.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
        if r.status_code == 429:
            ra = int(r.headers.get("Retry-After", "2"))
            time.sleep(max(ra, 2))
            r = session.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
        r.raise_for_status()
        j = r.json()
        if not j.get("ok"):
            print(f"[{now_iso()}] sendMessage not ok:", j)
        return j
    except Exception as e:
        print(f"[{now_iso()}] sendMessage error:", e)

# =================== إدارة مشتركين/روابط ===================

def load_subscribers():
    data = read_json(PATH_SUBS, [])
    clean = []
    for x in data:
        try:
            clean.append(int(x))
        except Exception:
            continue
    return list(sorted(set(clean)))

def save_subscribers(subs):
    write_json(PATH_SUBS, list(sorted(set(int(x) for x in subs))))

def load_dynamic_links():
    return read_json(PATH_LINKS, [])

def save_dynamic_links(links):
    cleaned = []
    for u in links:
        u = str(u).strip()
        if not u:
            continue
        if u not in cleaned:
            cleaned.append(u)
    write_json(PATH_LINKS, cleaned)

def all_links():
    return list(dict.fromkeys(FIXED_LINKS + load_dynamic_links()))

# =================== مراقبة TestFlight ===================

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = (s.replace("’", "'")
           .replace("“", '"')
           .replace("”", '"')
           .replace("–", "-")
           .replace("—", "-")
           .replace("\u00a0", " "))
    s = s.replace("'", "")
    s = " ".join(s.split())
    return s

TF_AVAILABLE_MARKERS = [
    "join the beta",
    "continue",
    "accept",
    "open in testflight",
]

TF_FULL_MARKERS = [
    "this beta is full",
    "beta is full",
    "no longer accepting new testers",
    "this beta isnt accepting any new testers right now",
    "isnt accepting any new testers",
    "is not accepting any new testers",
    "no longer available for testing",
    "no longer accepting testers",
    "the requested app is not available or does not exist",
]

TF_UNAVAILABLE_HINTS = [
    "not available",
    "no longer available",
    "app not available",
    "page not found",
]

def fetch_link_status(url, timeout=15):
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
        return "unknown"
    except Exception as e:
        print(f"[{now_iso()}] fetch_link_status error for {url}:", e)
        return "error"

def load_kv():
    return read_json(PATH_KV, {"link_states": {}})

def save_kv(kv):
    write_json(PATH_KV, kv)

def broadcast(text):
    subs = load_subscribers()
    if not subs:
        return
    for uid in subs:
        tg_send_message(uid, text)
        time.sleep(0.05)

def format_state_msg(url, state):
    if state == "open":
        return f"✅ صار <b>متاح</b>:\n{url}"
    if state == "full":
        return f"⛔️ صار <b>ممتلئ</b>:\n{url}"
    if state == "not_found":
        return f"❓ الرابط غير متاح:\n{url}"
    if state == "unknown":
        return f"ℹ️ حالة غير واضحة:\n{url}"
    return f"⚠️ خطأ أثناء الفحص:\n{url}"

def watch_links_and_notify():
    kv = load_kv()
    last = kv.get("link_states", {})
    while True:
        try:
            changed_msgs = []
            curr = {}
            links = all_links()
            random.shuffle(links)
            for url in links:
                state = fetch_link_status(url)
                curr[url] = {"state": state, "ts": int(time.time())}
                prev_state = (last.get(url) or {}).get("state")
                if state != prev_state:
                    changed_msgs.append(format_state_msg(url, state))
            if changed_msgs:
                broadcast("\n\n".join(changed_msgs))
            last = curr
            kv["link_states"] = last
            save_kv(kv)
            time.sleep(random.randint(POLL_MIN_SEC, POLL_MAX_SEC))
        except Exception as e:
            print(f"[{now_iso()}] watch error:", e)
            time.sleep(10)

# =================== أوامر ===================

HELP_TEXT = f"""\
<b>مرحبًا 👋</b>
بوت مراقبة روابط TestFlight لـ <b>{APP_NAME_AR}</b>.

<b>الأوامر:</b>
/start - بدء
/help - مساعدة
/subscribe - الاشتراك
/unsubscribe - إلغاء الاشتراك
/status - الحالة الحالية
/links - قائمة الروابط
/owners - عن المالك
/ping - اختبار

<b>للمدير:</b>
/addlink
/removelink
"""

def is_admin(user_id):
    return int(user_id) in ADMIN_IDS

def cmd_start(chat_id, from_user):
    name = (from_user.get("first_name") or "").strip()
    tg_send_message(chat_id, f"أهلًا {name or 'بك'} ✅\n"
                             f"استخدم /subscribe للاشتراك.\n\n{HELP_TEXT}")

def cmd_help(chat_id):
    tg_send_message(chat_id, HELP_TEXT)

def cmd_subscribe(chat_id):
    subs = load_subscribers()
    if chat_id in subs:
        tg_send_message(chat_id, "أنت مشترك بالفعل 🔔")
        return
    subs.append(chat_id)
    save_subscribers(subs)
    tg_send_message(chat_id, "تم الاشتراك ✅")

def cmd_unsubscribe(chat_id):
    subs = load_subscribers()
    if chat_id not in subs:
        tg_send_message(chat_id, "أنت غير مشترك 🙂")
        return
    subs = [x for x in subs if x != chat_id]
    save_subscribers(subs)
    tg_send_message(chat_id, "تم إلغاء الاشتراك ✅")

def cmd_status(chat_id):
    kv = load_kv()
    states = kv.get("link_states", {})
    if not states:
        tg_send_message(chat_id, "لا توجد حالات محفوظة بعد.")
        return
    lines = ["<b>الحالة الحالية:</b>"]
    for url in all_links():
        s = states.get(url, {})
        st = s.get("state", "unknown")
        badge = "✅" if st == "open" else ("⛔️" if st == "full" else "ℹ️")
        lines.append(f"{badge} {st} — {url}")
    tg_send_message(chat_id, "\n".join(lines))

def cmd_links(chat_id):
    links = all_links()
    if not links:
        tg_send_message(chat_id, "لا روابط حالياً.")
        return
    body = "\n".join(f"• {u}" for u in links)
    tg_send_message(chat_id, f"<b>الروابط:</b>\n{body}")

def cmd_owners(chat_id):
    tg_send_message(chat_id,
                    f"<b>المالك:</b> {OWNER_NAME}\n"
                    f"IG: {OWNER_IG}\nTG: {OWNER_TG}\nTestFlight: {TESTFLIGHT_URL}")

def cmd_ping(chat_id):
    tg_send_message(chat_id, "pong ✅")

def cmd_addlink(chat_id, user_id):
    if not is_admin(user_id):
        tg_send_message(chat_id, "للمدير فقط.")
        return
    PENDING_ACTIONS[chat_id] = {"action": "add"}
    tg_send_message(chat_id, "أرسل الرابط لإضافته.")

def cmd_removelink(chat_id, user_id):
    if not is_admin(user_id):
        tg_send_message(chat_id, "للمدير فقط.")
        return
    PENDING_ACTIONS[chat_id] = {"action": "remove"}
    tg_send_message(chat_id, "أرسل الرابط لحذفه.")

def handle_text_message(chat_id, user_id, text, from_user):
    pending = PENDING_ACTIONS.get(chat_id)
    if pending:
        action = pending.get("action")
        url = text.strip()
        links = load_dynamic_links()
        if action == "add":
            if url in FIXED_LINKS or url in links:
                tg_send_message(chat_id, "موجود مسبقاً.")
            else:
                links.append(url)
                save_dynamic_links(links)
                tg_send_message(chat_id, "تمت الإضافة ✅")
        elif action == "remove":
            if url in links:
                links = [u for u in links if u != url]
                save_dynamic_links(links)
                tg_send_message(chat_id, "تم الحذف ✅")
            else:
                tg_send_message(chat_id, "لم أجد الرابط.")
        PENDING_ACTIONS.pop(chat_id, None)
        return

    t = (text or "").strip()
    if t.startswith("/start"):
        cmd_start(chat_id, from_user)
    elif t.startswith("/help"):
        cmd_help(chat_id)
    elif t.startswith("/subscribe"):
        cmd_subscribe(chat_id)
    elif t.startswith("/unsubscribe"):
        cmd_unsubscribe(chat_id)
    elif t.startswith("/status"):
        cmd_status(chat_id)
    elif t.startswith("/links"):
        cmd_links(chat_id)
    elif t.startswith("/owners"):
        cmd_owners(chat_id)
    elif t.startswith("/ping"):
        cmd_ping(chat_id)
    elif t.startswith("/addlink"):
        cmd_addlink(chat_id, user_id)
    elif t.startswith("/removelink"):
        cmd_removelink(chat_id, user_id)
    else:
        tg_send_message(chat_id, "أمر غير مفهوم. /help")

def handle_update(u):
    if "message" in u:
        msg = u["message"]
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {}) or {}
        user_id = from_user.get("id")
        text = msg.get("text", "")
        if text:
            handle_text_message(chat_id, user_id, text, from_user)

def poll_loop():
    tg_delete_webhook()
    last_id = load_last_update_id()
    while True:
        try:
            data = tg_get_updates(last_id, timeout=50)
            updates = data.get("result", [])
            for u in updates:
                last_id = max(last_id or 0, u["update_id"])
                handle_update(u)
            save_last_update_id(last_id)
        except Exception as e:
            print(f"[{now_iso()}] poll error:", e)
            time.sleep(5)

# =================== main ===================

def main():
    threading.Thread(target=watch_links_and_notify, daemon=True).start()
    threading.Thread(target=poll_loop, daemon=True).start()
    print(f"[{now_iso()}] Bot is running…")
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()})

# =================== أدوات التخزين ===================
def _read_json(path, default):
    try:
        if not os.path.exists(path): return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def _write_json_atomic(path, data):
    fd, tmp = tempfile.mkstemp(prefix="tmp_", suffix=".json", dir=DATA_DIR)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# =================== مشتركين وروابط ===================
def add_subscriber(chat_id):
    subs = set(_read_json(PATH_SUBS, []))
    subs.add(chat_id)
    _write_json_atomic(PATH_SUBS, list(subs))

def list_subscribers():
    return _read_json(PATH_SUBS, [])

def get_links():
    return _read_json(PATH_LINKS, {})

def save_links(links_map):
    _write_json_atomic(PATH_LINKS, links_map)

def add_link(url):
    links = get_links()
    links.setdefault(url.strip(), {"status": None, "last_change": None})
    save_links(links)

def remove_link(url):
    links = get_links()
    if url.strip() in links:
        links.pop(url.strip())
        save_links(links)

# =================== الأحداث/الإحصائيات ===================
def append_event(link, old_status, new_status):
    events = _read_json(PATH_EVENTS, [])
    events.append({
        "ts": datetime.utcnow().isoformat(),
        "url": link,
        "old": old_status,
        "new": new_status
    })
    _write_json_atomic(PATH_EVENTS, events)

def stats_snapshot():
    subs = len(list_subscribers())
    links = get_links()
    events = _read_json(PATH_EVENTS, [])
    navailable = sum(1 for e in events if e.get("new") == "متاح")
    last_event = events[-1]["ts"] if events else "—"
    started = _read_json(PATH_KV, {}).get("started_at", "—")
    return subs, len(links), len(events), navailable, started, last_event

# =================== الأزرار ===================
def make_control_keyboard():
    kb = {"keyboard": [["📊 الحالة الآن"], ["ℹ️ معلومات"]], "resize_keyboard": True}
    return json.dumps(kb, ensure_ascii=False)

def make_admin_keyboard():
    kb = {
        "keyboard": [
            ["📊 الحالة الآن"], ["ℹ️ معلومات"],
            ["🛠 إدارة الروابط"],
            ["➕ إضافة رابط", "➖ حذف رابط"],
            ["📢 بث رسالة"]
        ],
        "resize_keyboard": True
    }
    return json.dumps(kb, ensure_ascii=False)

def make_main_inline():
    kb = {
        "inline_keyboard": [
            [{"text": "⬇️ تحميل TestFlight", "url": TESTFLIGHT_URL}],
            [{"text": "📸 Instagram", "url": OWNER_IG},
             {"text": "✈️ Telegram", "url": OWNER_TG}],
        ]
    }
    return json.dumps(kb, ensure_ascii=False)

# =================== رسائل ===================
def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode: data["parse_mode"] = parse_mode
    if reply_markup: data["reply_markup"] = reply_markup
    try:
        session.post(f"{API_BASE}/sendMessage", data=data, timeout=15)
    except Exception as e:
        print(f"❌ send_message failed: {e}")

def format_user_name(from_obj):
    if not from_obj: return "صديقي"
    fn = (from_obj.get("first_name") or "").strip()
    ln = (from_obj.get("last_name") or "").strip()
    uname = from_obj.get("username")
    full = (fn + " " + ln).strip()
    if full: return full
    if uname: return "@" + uname
    return fn or "صديقي"

def send_welcome(chat_id, from_obj, is_admin=False):
    name = format_user_name(from_obj)
    kb = make_admin_keyboard() if is_admin else make_control_keyboard()
    send_message(chat_id, "مرحبًا بك! اختر من لوحة التحكم:", reply_markup=kb)
    text = (
        f"مرحبًا بك {name} 👋\n\n"
        f"هذا البوت يتحقق من توفر تطبيق <b>{APP_NAME_AR}</b> عبر TestFlight.\n"
        "📌 إذا توفر مكان شاغر سيتم إشعارك فورًا.\n\n"
        "ℹ️ <b>ملاحظة</b>: لا يمكنك تثبيت التطبيق بدون TestFlight.\n"
        "⬇️ حمّله من الزر أدناه.\n\n"
        "صنع بواسطة غيث الراوي"
    )
    send_message(chat_id, text, parse_mode="HTML", reply_markup=make_main_inline())

# =================== فحص الروابط ===================
FULL_PATTERNS = ["This beta is full", "no longer accepting new testers"]
AVAILABLE_PATTERNS = ["Join the beta", "Start Testing"]
GONE_PATTERNS = ["app you're looking for can't be found", "app you’re looking for can’t be found"]

def classify_html(html):
    h = html.lower()
    if any(p.lower() in h for p in GONE_PATTERNS): return "غير موجود"
    if any(p.lower() in h for p in FULL_PATTERNS): return "ممتلئ"
    if any(p.lower() in h for p in AVAILABLE_PATTERNS): return "متاح"
    return "غير واضح"

def fetch(url):
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200: return r.text
    except:
        pass
    return None

def summarize():
    links = get_links()
    groups = {"متاح": [], "ممتلئ": [], "غير موجود": [], "غير واضح": []}
    for url, meta in links.items():
        groups.get(meta.get("status") or "غير واضح", groups["غير واضح"]).append(url)

    # التاريخ فقط + كلمة "الآن"
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"📊 حالة الروابط الآن ({today} - الآن):", ""]

    for st in ["متاح", "ممتلئ", "غير موجود", "غير واضح"]:
        if groups[st]:
            icon = "✅" if st == "متاح" else "⚠️" if st == "ممتلئ" else "❌" if st == "غير موجود" else "❓"
            lines.append(f"{icon} {st}:")
            lines += [f"- {u}" for u in groups[st]]
            lines.append("")
    return "\n".join(lines).strip()

# =================== استقبال الأوامر ===================
def updates_worker():
    print("🛰️ Listening for updates...")
    last_upd = None
    if os.path.exists(PATH_LASTUPD):
        try:
            with open(PATH_LASTUPD, "r") as f:
                last_upd = int(f.read().strip())
        except:
            pass

    while True:
        try:
            params = {"timeout": 50}
            if last_upd is not None:
                params["offset"] = last_upd + 1
            resp = session.get(f"{API_BASE}/getUpdates", params=params, timeout=60).json()
            if not resp.get("ok"):
                time.sleep(2)
                continue
            for upd in resp["result"]:
                last_upd = upd["update_id"]
                with open(PATH_LASTUPD, "w") as f:
                    f.write(str(last_upd))
                msg = upd.get("message")
                if not msg: continue
                chat_id = msg["chat"]["id"]
                text = (msg.get("text") or "").strip()
                from_obj = msg.get("from")
                is_admin = chat_id in ADMIN_IDS

                # أوامر عامة
                if text.lower().startswith("/start"):
                    add_subscriber(chat_id)
                    send_welcome(chat_id, from_obj, is_admin)
                    continue
                if text in ["📊 الحالة الآن", "/status"]:
                    send_message(chat_id, summarize() or "لا توجد حالة بعد.")
                    continue
                if text in ["ℹ️ معلومات", "/about"]:
                    send_message(chat_id, f"👨‍💻 {OWNER_NAME}\n📸 {OWNER_IG}\n✈️ {OWNER_TG}")
                    continue

                # أوامر المدير
                if is_admin:
                    if text in ["🛠 إدارة الروابط", "/links"]:
                        links = get_links()
                        if not links:
                            send_message(chat_id, "لا توجد روابط.")
                        else:
                            lines = ["🔗 الروابط:"]
                            for u, meta in links.items():
                                lines.append(f"- {u}  ({meta.get('status') or '—'})")
                            send_message(chat_id, "\n".join(lines))
                        continue

                    if text == "➕ إضافة رابط":
                        PENDING_ACTIONS[chat_id] = {"action": "add"}
                        send_message(chat_id, "أرسل الرابط الآن:")
                        continue
                    if text == "➖ حذف رابط":
                        PENDING_ACTIONS[chat_id] = {"action": "remove"}
                        send_message(chat_id, "أرسل الرابط الذي تريد حذفه:")
                        continue

                    if text.startswith("/addlink"):
                        parts = text.split(maxsplit=1)
                        if len(parts) == 2 and parts[1].startswith("http"):
                            add_link(parts[1])
                            send_message(chat_id, "✅ تمت الإضافة.")
                        else:
                            send_message(chat_id, "صيغة خاطئة.")
                        continue
                    if text.startswith("/removelink"):
                        parts = text.split(maxsplit=1)
                        if len(parts) == 2:
                            remove_link(parts[1])
                            send_message(chat_id, "🗑️ تم الحذف.")
                        else:
                            send_message(chat_id, "صيغة خاطئة.")
                        continue

                    if text == "📢 بث رسالة":
                        send_message(chat_id, "أرسل نص الرسالة:")
                        PENDING_ACTIONS[chat_id] = {"action": "broadcast"}
                        continue

                # استقبال الروابط أو البث بناءً على الإجراء المعلّق
                if chat_id in PENDING_ACTIONS:
                    act = PENDING_ACTIONS.pop(chat_id)
                    if act["action"] == "add":
                        if text.startswith("http"):
                            add_link(text)
                            send_message(chat_id, "✅ تمت الإضافة.")
                        else:
                            send_message(chat_id, "صيغة غير صحيحة.")
                        continue
                    if act["action"] == "remove":
                        if text.startswith("http"):
                            remove_link(text)
                            send_message(chat_id, "🗑️ تم الحذف.")
                        else:
                            send_message(chat_id, "صيغة غير صحيحة.")
                        continue
                    if act["action"] == "broadcast":
                        for cid in list_subscribers():
                            send_message(cid, text)
                        send_message(chat_id, "✅ تم الإرسال.")
                        continue

        except Exception as e:
            print("⚠️ updates_worker error:", e)
            time.sleep(3)

# =================== فحص الروابط ===================
def checker_worker():
    print("🔎 Checker started")
    while True:
        try:
            links = get_links()
            if not links:
                time.sleep(10)
                continue
            changed_any = False
            newly_available = []
            for url, meta in links.items():
                html = fetch(url)
                if not html: continue
                new_state = classify_html(html)
                old_state = meta.get("status")
                if new_state != old_state:
                    links[url]["status"] = new_state
                    links[url]["last_change"] = datetime.utcnow().isoformat()
                    append_event(url, old_state, new_state)
                    changed_any = True
                    if new_state == "متاح":
                        newly_available.append(url)
            if changed_any:
                save_links(links)
                for u in newly_available:
                    for cid in list_subscribers():
                        send_message(cid, f"🚨 متاح الآن:\n{u}")
                for cid in list_subscribers():
                    send_message(cid, summarize())
            time.sleep(random.randint(POLL_MIN_SEC, POLL_MAX_SEC))
        except Exception as e:
            print("⚠️ checker_worker error:", e)
            time.sleep(5)

# =================== تشغيل ===================
def ensure_fixed_links():
    for url in FIXED_LINKS:
        add_link(url)
        
def main():
    if not os.path.exists(PATH_LINKS):
        save_links({})
        ensure_fixed_links()
    _write_json_atomic(PATH_KV, {"started_at": datetime.utcnow().isoformat()})
    threading.Thread(target=updates_worker, daemon=True).start()
    threading.Thread(target=checker_worker, daemon=True).start()
    print("🚀 Bot is running...")
    while True:
        time.sleep(300)

if __name__ == "__main__":
    main()
