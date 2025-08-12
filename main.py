# -*- coding: utf-8 -*-
import os, time, json, random, tempfile, threading, requests
from datetime import datetime

# =================== الإعدادات ===================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("❌ TELEGRAM_TOKEN غير موجود في المتغيرات.")

# معرف المدير (ثابت)
ADMIN_IDS = {238547634}

# الفاصل الزمني بين الفحوصات (ثواني)
POLL_MIN_SEC = int(os.environ.get("POLL_MIN_SEC", "60"))
POLL_MAX_SEC = int(os.environ.get("POLL_MAX_SEC", "60"))

# مسار التخزين
DATA_DIR = os.environ.get("DATA_DIR", "/data")

# بيانات المالك
OWNER_NAME = "غيث الراوي"
OWNER_IG = "https://instagram.com/gb.rw"
OWNER_TG = "https://t.me/gb.rw"

# روابط مهمة
TESTFLIGHT_URL = "https://apps.apple.com/us/app/testflight/id899247664"
APP_NAME_AR = "TDS Video"

# =================== مسارات الملفات ===================
os.makedirs(DATA_DIR, exist_ok=True)
PATH_SUBS = os.path.join(DATA_DIR, "subscribers.json")
PATH_LINKS = os.path.join(DATA_DIR, "links.json")
PATH_EVENTS = os.path.join(DATA_DIR, "events.json")
PATH_LASTUPD = os.path.join(DATA_DIR, "last_update_id.txt")
PATH_KV = os.path.join(DATA_DIR, "kv.json")

# =================== جلسة HTTP ===================
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.8",
})

# =================== أدوات تخزين ===================
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

def kv_get(key, default=None):
    kv = _read_json(PATH_KV, {})
    return kv.get(key, default)

def kv_set(key, value):
    kv = _read_json(PATH_KV, {})
    kv[key] = value
    _write_json_atomic(PATH_KV, kv)

# =================== المشتركين ===================
def add_subscriber(chat_id):
    subs = set(_read_json(PATH_SUBS, []))
    subs.add(chat_id)
    _write_json_atomic(PATH_SUBS, list(subs))

def remove_subscriber(chat_id):
    subs = set(_read_json(PATH_SUBS, []))
    if chat_id in subs:
        subs.remove(chat_id)
        _write_json_atomic(PATH_SUBS, list(subs))

def list_subscribers():
    return _read_json(PATH_SUBS, [])

# =================== الروابط ===================
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

# =================== الأحداث ===================
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
    started = kv_get("started_at", "—")
    return subs, len(links), len(events), navailable, started, last_event

# =================== رسائل وأزرار ===================
def make_control_keyboard():
    kb = {
        "keyboard": [
            ["📊 الحالة الآن", "📜 القائمة"],
            ["ℹ️ معلومات", "🛑 إلغاء الاشتراك"]
        ],
        "resize_keyboard": True
    }
    return json.dumps(kb, ensure_ascii=False)

def make_admin_keyboard():
    kb = {
        "keyboard": [
            ["📊 الحالة الآن", "📜 القائمة"],
            ["ℹ️ معلومات", "🛑 إلغاء الاشتراك"],
            ["🛠 روابط", "➕ إضافة رابط", "➖ حذف رابط"],
            ["👥 المشتركين", "📢 بث", "⏱ تغيير الفاصل"]
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

def format_user_name(from_obj):
    if not from_obj: return "صديقي"
    fn = (from_obj.get("first_name") or "").strip()
    ln = (from_obj.get("last_name") or "").strip()
    uname = from_obj.get("username")
    full = (fn + " " + ln).strip()
    if full: return full
    if uname: return "@" + uname
    return fn or "صديقي"

def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        session.post(f"{API_BASE}/sendMessage", data=data, timeout=15)
    except Exception as e:
        print(f"❌ send_message failed: {e}")

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
        f"👨‍💻 المطور: {OWNER_NAME}\n"
        f"📸 Instagram: {OWNER_IG}\n"
        f"✈️ Telegram: {OWNER_TG}"
    )
    send_message(chat_id, text, parse_mode="HTML", reply_markup=make_main_inline())

# =================== فحص TestFlight ===================
FULL_PATTERNS = ["This beta is full", "no longer accepting new testers"]
AVAILABLE_PATTERNS = ["Join the beta", "Start Testing"]
GONE_PATTERNS = ["app you're looking for can't be found", "app you’re looking for can’t be found"]

def classify_html(html):
    h = html.lower()
    if any(p.lower() in h for p in GONE_PATTERNS): return "غير موجود"
    if any(p.lower() in h for p in FULL_PATTERNS): return "ممتلئ"
    if any(p.lower() in h for p in AVAILABLE_PATTERNS): return "متاح"
    return "غير واضح"

def fetch(url, retries=3, timeout=15):
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except:
            pass
        time.sleep(1)
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

                # أزرار المستخدم
                if text.lower().startswith("/start"):
                    add_subscriber(chat_id)
                    send_welcome(chat_id, from_obj, is_admin)
                    continue
                if text in ["📊 الحالة الآن", "/status"]:
                    send_message(chat_id, summarize() or "لا توجد حالة بعد.")
                    continue
                if text in ["📜 القائمة", "/menu"]:
                    send_message(chat_id, "اختر من الأزرار:", reply_markup=make_main_inline())
                    continue
                if text in ["ℹ️ معلومات", "/about"]:
                    send_message(chat_id, f"👨‍💻 {OWNER_NAME}\n📸 {OWNER_IG}\n✈️ {OWNER_TG}")
                    continue
                if text in ["🛑 إلغاء الاشتراك", "/stop"]:
                    remove_subscriber(chat_id)
                    send_message(chat_id, "🛑 تم إلغاء الاشتراك.")
                    continue

                # أزرار المدير
                if is_admin:
                    if text in ["🛠 روابط", "/links"]:
                        links = get_links()
                        if not links:
                            send_message(chat_id, "لا توجد روابط.")
                        else:
                            send_message(chat_id, "\n".join([f"- {u}: {meta['status']}" for u, meta in links.items()]))
                        continue
                    if text.startswith("➕") or text.startswith("/addlink"):
                        send_message(chat_id, "أرسل الرابط بصيغة:\n/addlink <url>")
                        continue
                    if text.startswith("➖") or text.startswith("/removelink"):
                        send_message(chat_id, "أرسل الرابط بصيغة:\n/removelink <url>")
                        continue
                    if text in ["👥 المشتركين", "/subs"]:
                        send_message(chat_id, f"👥 المشتركين: {len(list_subscribers())}")
                        continue
                    if text in ["📢 بث", "/broadcast"]:
                        send_message(chat_id, "أرسل الرسالة:\n/broadcast <نص>")
                        continue
                    if text in ["⏱ تغيير الفاصل", "/setinterval"]:
                        send_message(chat_id, "أرسل:\n/setinterval <min> <max>")
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
                    broadcast(f"🚨 متاح الآن:\n{u}")
                broadcast(summarize())
            time.sleep(random.randint(POLL_MIN_SEC, POLL_MAX_SEC))
        except Exception as e:
            print("⚠️ checker_worker error:", e)
            time.sleep(5)

# =================== تشغيل ===================
def main():
    if not os.path.exists(PATH_LINKS):
        save_links({})
    kv_set("started_at", datetime.utcnow().isoformat())
    threading.Thread(target=updates_worker, daemon=True).start()
    threading.Thread(target=checker_worker, daemon=True).start()
    print("🚀 Bot is running")
    while True:
        time.sleep(300)

if __name__ == "__main__":
    main()
