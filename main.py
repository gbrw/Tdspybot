# -*- coding: utf-8 -*-
import os, time, json, random, tempfile, threading, requests
from datetime import datetime

# =================== الإعدادات من المتغيرات ===================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # ضع القيمة في Variables على Railway
if not TELEGRAM_TOKEN:
    raise SystemExit("❌ لم يتم العثور على TELEGRAM_TOKEN في المتغيرات.")

# مدير واحد ثابت كما طلبت (يمكن أيضًا تمريره من البيئة لو تحب لاحقًا)
ADMIN_IDS = {238547634}

# الفترة بين الفحوصات (ثواني) – قابلة للتغيير بأمر /setinterval من المدير
POLL_MIN_SEC = int(os.environ.get("POLL_MIN_SEC", "240"))
POLL_MAX_SEC = int(os.environ.get("POLL_MAX_SEC", "360"))

# مسار التخزين (اربط Volume على /data في Railway)
DATA_DIR = os.environ.get("DATA_DIR", "/data")

# بيانات المالك / الحقوق
OWNER_NAME = "غيث الراوي"
OWNER_IG = "https://instagram.com/gb.rw"
OWNER_TG = "https://t.me/gb.rw"

# روابط وأسماء مهمة
TESTFLIGHT_URL = "https://apps.apple.com/us/app/testflight/id899247664"
APP_NAME_AR = "TDS Video"

# =================== مسارات الملفات ===================
os.makedirs(DATA_DIR, exist_ok=True)
PATH_SUBS = os.path.join(DATA_DIR, "subscribers.json")
PATH_LINKS = os.path.join(DATA_DIR, "links.json")   # { url: {status, last_change} }
PATH_EVENTS = os.path.join(DATA_DIR, "events.json") # قائمة أحداث تغيّر الحالة
PATH_LASTUPD = os.path.join(DATA_DIR, "last_update_id.txt")
PATH_KV = os.path.join(DATA_DIR, "kv.json")         # { "started_at": "...", ... }

# =================== جلسة HTTP ===================
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

# =================== أدوات تخزين (JSON) ===================
def _read_json(path, default):
    try:
        if not os.path.exists(path): return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
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
    # links.json: { url: { "status": "...", "last_change": "ISO" } }
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
    started = kv_get("started_at", "—")
    return subs, len(links), len(events), navailable, started, last_event

# =================== تيليجرام: إرسال رسائل ===================
def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        session.post(f"{API_BASE}/sendMessage", data=data, timeout=15)
    except Exception as e:
        print(f"❌ send_message({chat_id}) failed: {e}")

def broadcast(text):
    for cid in list_subscribers():
        send_message(cid, text)

# =================== محتوى الترحيب والأزرار ===================
import json as _json

def make_main_keyboard():
    kb = {
        "inline_keyboard": [
            [{"text": "⬇️ تحميل TestFlight", "url": TESTFLIGHT_URL}],
            [{"text": "📸 Instagram", "url": OWNER_IG},
             {"text": "✈️ Telegram", "url": OWNER_TG}],
        ]
    }
    return _json.dumps(kb, ensure_ascii=False)

def format_user_name(from_obj):
    if not from_obj: return "صديقي"
    fn = (from_obj.get("first_name") or "").strip()
    ln = (from_obj.get("last_name") or "").strip()
    uname = from_obj.get("username")
    full = (fn + " " + ln).strip()
    if full: return full
    if uname: return "@" + uname
    return fn or "صديقي"

def send_welcome(chat_id, from_obj):
    name = format_user_name(from_obj)
    text = (
        f"مرحبًا بك {name} 👋\n\n"
        f"أهلاً بك في بوت التحقق من توفر تطبيق <b>{APP_NAME_AR}</b>.\n"
        "هدف البوت هو التحقق مما إذا كان هناك مكان شاغر في التطبيق عبر TestFlight "
        "لتستطيع تثبيته فور توفر مقاعد جديدة.\n\n"
        "ℹ️ <b>ملاحظة</b>: لا يمكنك تثبيت التطبيق بدون تطبيق TestFlight.\n"
        "اضغط الزر التالي لتحميله ثم ارجع للبوت.\n\n"
        f"👨‍💻 الحقوق: {OWNER_NAME}\n"
        f"📸 Instagram: {OWNER_IG}\n"
        f"✈️ Telegram: {OWNER_TG}"
    )
    send_message(chat_id, text, parse_mode="HTML", reply_markup=make_main_keyboard())

def send_menu(chat_id):
    send_message(chat_id, "اختر من الأزرار التالية:", reply_markup=make_main_keyboard())

def send_about(chat_id):
    text = (
        f"👨‍💻 المطوّر: {OWNER_NAME}\n"
        f"📸 Instagram: {OWNER_IG}\n"
        f"✈️ Telegram: {OWNER_TG}\n\n"
        f"هذا البوت يتحقق من توافر مقاعد لتطبيق <b>{APP_NAME_AR}</b> على TestFlight ويبلغك فور توفره."
    )
    send_message(chat_id, text, parse_mode="HTML")

# =================== منطق فحص TestFlight ===================
FULL_PATTERNS = ["This beta is full", "no longer accepting new testers"]
AVAILABLE_PATTERNS = ["Join the beta", "Start Testing"]
GONE_PATTERNS = ["app you're looking for can't be found", "app you’re looking for can’t be found"]

def classify_html(html: str) -> str:
    h = html.lower()
    if any(p.lower() in h for p in GONE_PATTERNS): return "غير موجود"
    if any(p.lower() in h for p in FULL_PATTERNS): return "ممتلئ"
    if any(p.lower() in h for p in AVAILABLE_PATTERNS): return "متاح"
    return "غير واضح"

def fetch(url: str, retries=3, timeout=15):
    last_err = None
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200: return r.text
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(1.2*(i+1))
    print(f"⚠️ fetch failed {url}: {last_err}")
    return None

def summarize():
    links = get_links()
    groups = {"متاح": [], "ممتلئ": [], "غير موجود": [], "غير واضح": []}
    for url, meta in links.items():
        groups.get(meta.get("status") or "غير واضح", groups["غير واضح"]).append(url)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"📊 حالة الروابط الآن ({now}):", ""]
    if groups["متاح"]: lines.append("✅ متاح:"); lines += [f"- {u}" for u in groups["متاح"]]; lines.append("")
    if groups["ممتلئ"]: lines.append("⚠️ ممتلئ:"); lines += [f"- {u}" for u in groups["ممتلئ"]]; lines.append("")
    if groups["غير موجود"]: lines.append("❌ غير موجود:"); lines += [f"- {u}" for u in groups["غير موجود"]]; lines.append("")
    if groups["غير واضح"]: lines.append("❓ غير واضح:"); lines += [f"- {u}" for u in groups["غير واضح"]]
    return "\n".join(lines).strip()

# =================== استقبال أوامر تيليجرام ===================
def updates_worker():
    print("🛰️ Telegram long polling started")
    # آخر تحديث مقروء
    last_upd = None
    if os.path.exists(PATH_LASTUPD):
        try:
            with open(PATH_LASTUPD, "r", encoding="utf-8") as f:
                v = f.read().strip()
                last_upd = int(v) if v else None
        except Exception:
            last_upd = None

    while True:
        try:
            params = {"timeout": 50}
            if last_upd is not None:
                params["offset"] = last_upd + 1
            resp = session.get(f"{API_BASE}/getUpdates", params=params, timeout=60)
            data = resp.json()
            if not data.get("ok"):
                time.sleep(2); continue

            for upd in data.get("result", []):
                last_upd = upd["update_id"]
                with open(PATH_LASTUPD, "w", encoding="utf-8") as f:
                    f.write(str(last_upd))

                msg = upd.get("message") or upd.get("edited_message")
                if not msg or "chat" not in msg: continue
                chat_id = msg["chat"]["id"]
                text = (msg.get("text") or "").strip()
                from_obj = msg.get("from")

                is_admin = chat_id in ADMIN_IDS

                # أوامر عامة
                lower = text.lower()
                if lower.startswith("/start"):
                    add_subscriber(chat_id)
                    send_welcome(chat_id, from_obj)
                    continue
                if lower.startswith("/stop"):
                    remove_subscriber(chat_id)
                    send_message(chat_id, "🛑 تم إلغاء الاشتراك.")
                    continue
                if lower.startswith("/status"):
                    send_message(chat_id, summarize() or "لا توجد حالة بعد.")
                    continue
                if lower.startswith("/menu"):
                    send_menu(chat_id); continue
                if lower.startswith("/about"):
                    send_about(chat_id); continue

                # أوامر المدير
                if not is_admin:
                    continue

                if text.startswith("/admin"):
                    subs, nlinks, nevents, navail, started, last_event = stats_snapshot()
                    send_message(chat_id,
                        "🛠 لوحة المدير:\n"
                        f"- مشتركين: {subs}\n"
                        f"- عدد الروابط: {nlinks}\n"
                        f"- عدد التغيّرات: {nevents} (متاح: {navail})\n"
                        f"- بدأ التشغيل: {started}\n"
                        f"- آخر حدث: {last_event}\n\n"
                        "أوامر:\n"
                        "/links — عرض الروابط\n"
                        "/addlink <url>\n"
                        "/removelink <url>\n"
                        "/subs — عدد المشتركين\n"
                        "/broadcast <نص>\n"
                        "/setinterval <min> <max>\n"
                        "/status — ملخص الحالة"
                    )
                    continue

                if text.startswith("/links"):
                    links = get_links()
                    if not links:
                        send_message(chat_id, "لا توجد روابط.")
                        continue
                    lines = ["🔗 الروابط:"]
                    for u, meta in links.items():
                        lines.append(f"- {u}  ({meta.get('status') or '—'})  {meta.get('last_change') or ''}")
                    send_message(chat_id, "\n".join(lines))
                    continue

                if text.startswith("/addlink"):
                    parts = text.split(maxsplit=1)
                    if len(parts) == 2 and parts[1].startswith("http"):
                        add_link(parts[1])
                        send_message(chat_id, "✅ تمت الإضافة.")
                    else:
                        send_message(chat_id, "صيغة خاطئة. مثال:\n/addlink https://testflight.apple.com/join/xxxx")
                    continue

                if text.startswith("/removelink"):
                    parts = text.split(maxsplit=1)
                    if len(parts) == 2:
                        remove_link(parts[1])
                        send_message(chat_id, "🗑️ تم الحذف (إن وُجد).")
                    else:
                        send_message(chat_id, "صيغة خاطئة. مثال:\n/removelink https://...")
                    continue

                if text.startswith("/subs"):
                    send_message(chat_id, f"👥 المشتركين: {len(list_subscribers())}")
                    continue

                if text.startswith("/broadcast"):
                    parts = text.split(maxsplit=1)
                    if len(parts) == 2:
                        broadcast("📢 بث من المدير:\n" + parts[1])
                        send_message(chat_id, "تم الإرسال ✅")
                    else:
                        send_message(chat_id, "اكتب الرسالة بعد الأمر.\nمثال:\n/broadcast مرحبًا")
                    continue

                if text.startswith("/setinterval"):
                    parts = text.split()
                    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                        global POLL_MIN_SEC, POLL_MAX_SEC
                        POLL_MIN_SEC = int(parts[1]); POLL_MAX_SEC = int(parts[2])
                        send_message(chat_id, f"⏱️ تم التحديث: {POLL_MIN_SEC}-{POLL_MAX_SEC} ثانية.")
                    else:
                        send_message(chat_id, "مثال:\n/setinterval 240 360")
                    continue

        except Exception as e:
            print(f"⚠️ updates_worker error: {e}")
            time.sleep(3)

# =================== فحص الروابط الدوري ===================
FULL_PATTERNS = ["This beta is full", "no longer accepting new testers"]
AVAILABLE_PATTERNS = ["Join the beta", "Start Testing"]
GONE_PATTERNS = ["app you're looking for can't be found", "app you’re looking for can’t be found"]

def checker_worker():
    print("🔎 checker started")
    while True:
        try:
            links = get_links()
            if not links:
                time.sleep(10); continue

            changed_any = False
            newly_available = []

            for url, meta in links.items():
                html = fetch(url)
                if html is None:
                    continue
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
                    broadcast(f"🚨 رابط متاح الآن:\n{u}")
                broadcast(summarize())

            time.sleep(random.randint(POLL_MIN_SEC, POLL_MAX_SEC))
        except Exception as e:
            print(f"⚠️ checker_worker error: {e}")
            time.sleep(5)

def seed_initial_links():
    # ابدأ بدون روابط، أضف عبر /addlink من حساب المدير
    pass

def main():
    if not os.path.exists(PATH_LINKS):
        seed_initial_links()
        save_links(get_links())
    kv_set("started_at", datetime.utcnow().isoformat())
    t1 = threading.Thread(target=updates_worker, daemon=True)
    t2 = threading.Thread(target=checker_worker, daemon=True)
    t1.start(); t2.start()
    print("🚀 bot is running. أوامر: /start /status /menu /about /stop (وللمدير /admin)")
    while True:
        time.sleep(300)

if __name__ == "__main__":
    main()
