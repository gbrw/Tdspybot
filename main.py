# -*- coding: utf-8 -*-
import os, time, json, random, tempfile, threading, requests
from datetime import datetime

# =================== الإعدادات ===================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("❌ TELEGRAM_TOKEN غير موجود في المتغيرات.")

ADMIN_IDS = {238547634}  # معرف المدير

POLL_MIN_SEC = int(os.environ.get("POLL_MIN_SEC", "60"))   # افتراضي 60 ثانية
POLL_MAX_SEC = int(os.environ.get("POLL_MAX_SEC", "60"))   # افتراضي 60 ثانية

DATA_DIR = os.environ.get("DATA_DIR", "/data")

OWNER_NAME = "غيث الراوي"
OWNER_IG = "https://instagram.com/gb.rw"
OWNER_TG = "https://t.me/gb.rw"
TESTFLIGHT_URL = "https://apps.apple.com/us/app/testflight/id899247664"
APP_NAME_AR = "TDS Video"

# =================== مسارات الملفات ===================
os.makedirs(DATA_DIR, exist_ok=True)
PATH_SUBS = os.path.join(DATA_DIR, "subscribers.json")
PATH_LINKS = os.path.join(DATA_DIR, "links.json")
PATH_EVENTS = os.path.join(DATA_DIR, "events.json")
PATH_LASTUPD = os.path.join(DATA_DIR, "last_update_id.txt")
PATH_KV = os.path.join(DATA_DIR, "kv.json")

# ذاكرة مؤقتة لإدخال الرابط بعد زر الإضافة/الحذف
PENDING_ACTIONS = {}  # { chat_id: {"action": "add"|"remove"} }

# =================== جلسة HTTP ===================
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.8",
})

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
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"📊 حالة الروابط الآن ({now}):", ""]
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
def main():
    if not os.path.exists(PATH_LINKS):
        save_links({})
    _write_json_atomic(PATH_KV, {"started_at": datetime.utcnow().isoformat()})
    threading.Thread(target=updates_worker, daemon=True).start()
    threading.Thread(target=checker_worker, daemon=True).start()
    print("🚀 Bot is running...")
    while True:
        time.sleep(300)

if __name__ == "__main__":
    main()
