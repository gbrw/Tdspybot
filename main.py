# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import random
import threading
import requests
from datetime import datetime

# =================== الإعدادات ===================
TELEGRAM_TOKEN = "8299272165:AAH1s7qqEEO1htuiMdjF1TnvzetpB4vE1Wc"
if not TELEGRAM_TOKEN:
    raise SystemExit("❌ TELEGRAM_TOKEN غير موجود في المتغيرات.")

# ممكن لاحقًا تستخدمه داخليًا، حاليًا لا نعرض أوامر مدير
ADMIN_IDS = {238547634}

POLL_MIN_SEC = int(os.environ.get("POLL_MIN_SEC", "240"))
POLL_MAX_SEC = int(os.environ.get("POLL_MAX_SEC", "360"))

DATA_DIR = os.environ.get("DATA_DIR", "/data")

OWNER_NAME = "غيث الراوي"
OWNER_IG = "https://instagram.com/gb.rw"
OWNER_TG = "https://t.me/gb_rw"
TESTFLIGHT_URL = "https://apps.apple.com/us/app/testflight/id899247664"
APP_NAME_AR = "TDS Video"

# روابط ثابتة (تُدمج مع الروابط الديناميكية إن وُجدت)
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

# لا نستخدم إجراءات معلقة الآن (لا أوامر إدارة)، لكن نُبقيه لو احتجته لاحقًا
PENDING_ACTIONS = {}

# =================== جلسة HTTP ===================
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.8",
})
adapter = requests.adapters.HTTPAdapter(max_retries=2)
session.mount("http://", adapter)
session.mount("https://", adapter)

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
    except Exception as e:
        log("read_json error", path, ":", e)
        return default

def write_json(path, obj):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        log("write_json error", path, ":", e)

def load_last_update_id():
    try:
        with open(PATH_LASTUPD, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None

def save_last_update_id(i):
    try:
        with open(PATH_LASTUPD, "w", encoding="utf-8") as f:
            f.write("" if i is None else str(i))
    except Exception as e:
        log("save_last_update_id error:", e)

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

# =================== تيليغرام API ===================
def tg_delete_webhook():
    try:
        r = session.get(f"{API_BASE}/deleteWebhook", timeout=10)
        r.raise_for_status()
        log("deleteWebhook:", r.json())
    except Exception as e:
        log("deleteWebhook error:", e)

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
    payload.update(kwargs)  # يمكن تمرير reply_markup=dict هنا
    try:
        r = session.post(f"{API_BASE}/sendMessage", json=payload, timeout=20)
        if r.status_code == 429:
            ra = int(r.headers.get("Retry-After", "2"))
            log("sendMessage 429, sleeping", ra, "s")
            time.sleep(max(ra, 2))
            r = session.post(f"{API_BASE}/sendMessage", json=payload, timeout=20)
        r.raise_for_status()
        j = r.json()
        if not j.get("ok"):
            log("sendMessage not ok:", j)
        return j
    except Exception as e:
        log("sendMessage error:", e)

# =============== لوحة الأزرار (Reply Keyboard) ===============
def main_keyboard():
    return {
        "keyboard": [
            [{"text": "🟢 الاشتراك"}, {"text": "🔴 إلغاء الاشتراك"}],
            [{"text": "📊 الحالة"}, {"text": "👤 المالك"}],
            [{"text": "ℹ️ المساعدة"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# =================== إدارة مشتركين/روابط ===================
def load_subscribers():
    data = read_json(PATH_SUBS, [])
    clean = []
    for x in data:
        try:
            clean.append(int(x))
        except Exception:
            pass
    return list(sorted(set(clean)))

def save_subscribers(subs):
    write_json(PATH_SUBS, list(sorted(set(int(x) for x in subs))))

def load_dynamic_links():
    return read_json(PATH_LINKS, [])

def save_dynamic_links(links):
    cleaned = []
    for u in links:
        u = str(u).strip()
        if u and u not in cleaned:
            cleaned.append(u)
    write_json(PATH_LINKS, cleaned)

def all_links():
    # دمج الروابط الثابتة مع أي روابط ديناميكية (حاليًا لا نعرض إدارة)
    return list(dict.fromkeys(FIXED_LINKS + load_dynamic_links()))

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
    # إزالة الأبوستروف لتوحيد isn't / isn’t / isnt
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

def fetch_link_status(url, timeout=20):
    """
    يرجع: open | full | not_found | unknown | error
    """
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        code = resp.status_code
        html_norm = normalize_text(resp.text)

        if code == 404:
            return "not_found"

        # الامتلاء أولاً لمنع الإيجابيات الكاذبة
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
        log("fetch_link_status error for", url, ":", e)
        return "error"

def load_kv():
    return read_json(PATH_KV, {"link_states": {}})

def save_kv(kv):
    write_json(PATH_KV, kv)

def broadcast(text):
    subs = load_subscribers()
    if not subs:
        log("broadcast skipped (no subscribers)")
        return
    for uid in subs:
        tg_send_message(uid, text, reply_markup=main_keyboard())
        time.sleep(0.05)

def format_state_msg(url, state):
    if state == "open":
        return f"✅ صار <b>متاح</b>:\n{url}"
    if state == "full":
        return f"⛔️ صار <b>ممتلئ</b>:\n{url}"
    if state == "not_found":
        return f"❓ الرابط غير متاح/غير موجود:\n{url}"
    if state == "unknown":
        return f"ℹ️ حالة غير واضحة حاليا:\n{url}"
    return f"⚠️ خطأ أثناء الفحص:\n{url}"

def watch_links_and_notify():
    # خيط مراقبة الروابط (محمي ضد الأعطال)
    while True:
        try:
            kv = load_kv()
            last = kv.get("link_states", {})
            log("Watcher started. Links:", len(all_links()))
            while True:
                changed_msgs = []
                curr = {}
                links = all_links()
                if not links:
                    time.sleep(60)
                    continue
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
            log("watch fatal error:", e)
            time.sleep(30)

# =================== واجهة المستخدم (أزرار) ===================
HELP_TEXT = f"""\
ℹ️ <b>المساعدة</b>
🟢 <b>الاشتراك</b>: تفعيل إشعارات تغيّر حالة روابط TestFlight
🔴 <b>إلغاء الاشتراك</b>: إيقاف الإشعارات
📊 <b>الحالة</b>: عرض الحالة الحالية للروابط
👤 <b>المالك</b>: معلومات عن المطوّر
"""

def cmd_start(chat_id, from_user):
    name = (from_user.get("first_name") or "").strip()
    tg_send_message(
        chat_id,
        f"أهلًا {name or 'بك'} ✅\nاختر من الأزرار أدناه 👇",
        reply_markup=main_keyboard()
    )

def cmd_help(chat_id):
    tg_send_message(chat_id, HELP_TEXT, reply_markup=main_keyboard())

def cmd_subscribe(chat_id):
    subs = load_subscribers()
    if chat_id in subs:
        tg_send_message(chat_id, "أنت مشترك بالفعل 🔔", reply_markup=main_keyboard())
        return
    subs.append(chat_id)
    save_subscribers(subs)
    tg_send_message(chat_id, "تم الاشتراك ✅", reply_markup=main_keyboard())

def cmd_unsubscribe(chat_id):
    subs = load_subscribers()
    if chat_id not in subs:
        tg_send_message(chat_id, "أنت غير مشترك 🙂", reply_markup=main_keyboard())
        return
    subs = [x for x in subs if x != chat_id]
    save_subscribers(subs)
    tg_send_message(chat_id, "تم إلغاء الاشتراك ✅", reply_markup=main_keyboard())

def cmd_status(chat_id):
    kv = load_kv()
    states = kv.get("link_states", {})
    if not states:
        tg_send_message(chat_id, "لا توجد حالات محفوظة بعد.", reply_markup=main_keyboard())
        return
    lines = ["<b>الحالة الحالية:</b>"]
    for url in all_links():
        s = states.get(url, {})
        st = s.get("state", "unknown")
        ts = s.get("ts")
        ts_str = datetime.utcfromtimestamp(ts).isoformat(timespec="seconds")+"Z" if ts else "—"
        badge = "✅" if st == "open" else ("⛔️" if st == "full" else ("❓" if st == "not_found" else "ℹ️"))
        lines.append(f"{badge} <code>{st}</code> — <a href='{url}'>الرابط</a> — <i>{ts_str}</i>")
    tg_send_message(chat_id, "\n".join(lines), disable_web_page_preview=False, reply_markup=main_keyboard())

def cmd_owners(chat_id):
    tg_send_message(
        chat_id,
        f"<b>المالك:</b> {OWNER_NAME}\n"
        f"<b>Instagram:</b> {OWNER_IG}\n"
        f"<b>Telegram:</b> {OWNER_TG}\n"
        f"<b>TestFlight:</b> {TESTFLIGHT_URL}",
        disable_web_page_preview=False,
        reply_markup=main_keyboard()
    )

def handle_text_message(chat_id, user_id, text, from_user):
    t = (text or "").strip()

    # ندعم من يكتب الأوامر يدويًا + الأزرار
    if t in ("/start", "ابدأ"):
        cmd_start(chat_id, from_user)
    elif t in ("/help", "ℹ️ المساعدة"):
        cmd_help(chat_id)
    elif t in ("/subscribe", "🟢 الاشتراك"):
        cmd_subscribe(chat_id)
    elif t in ("/unsubscribe", "🔴 إلغاء الاشتراك"):
        cmd_unsubscribe(chat_id)
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
        user_id = from_user.get("id")
        text = msg.get("text", "")
        if text:
            handle_text_message(chat_id, user_id, text, from_user)

def poll_loop():
    # خيط polling محمي ضد الأعطال
    while True:
        try:
            tg_delete_webhook()
            last_id = load_last_update_id()
            log("Polling started. last_update_id=", last_id)
            while True:
                data = tg_get_updates(last_id, timeout=50)
                updates = data.get("result", [])
                for u in updates:
                    last_id = max(last_id or 0, u["update_id"])
                    handle_update(u)
                save_last_update_id(last_id)
        except Exception as e:
            log("poll fatal error:", e)
            time.sleep(30)

# =================== main ===================
def main():
    log("Bot starting…")
    threading.Thread(target=watch_links_and_notify, daemon=True, name="watcher").start()
    threading.Thread(target=poll_loop, daemon=True, name="poller").start()
    # حارس بسيط يضمن بقاء العملية حيّة
    while True:
        names = [t.name for t in threading.enumerate()]
        log("Threads alive:", names)
        time.sleep(300)

if __name__ == "__main__":
    main()
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
    except Exception as e:
        log("read_json error", path, ":", e)
        return default

def write_json(path, obj):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        log("write_json error", path, ":", e)

def load_last_update_id():
    try:
        with open(PATH_LASTUPD, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None

def save_last_update_id(i):
    try:
        with open(PATH_LASTUPD, "w", encoding="utf-8") as f:
            f.write("" if i is None else str(i))
    except Exception as e:
        log("save_last_update_id error:", e)

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

# =================== تيليغرام API ===================

def tg_delete_webhook():
    try:
        r = session.get(f"{API_BASE}/deleteWebhook", timeout=10)
        r.raise_for_status()
        log("deleteWebhook:", r.json())
    except Exception as e:
        log("deleteWebhook error:", e)

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
        r = session.post(f"{API_BASE}/sendMessage", json=payload, timeout=20)
        if r.status_code == 429:
            ra = int(r.headers.get("Retry-After", "2"))
            log("sendMessage 429, sleeping", ra, "s")
            time.sleep(max(ra, 2))
            r = session.post(f"{API_BASE}/sendMessage", json=payload, timeout=20)
        r.raise_for_status()
        j = r.json()
        if not j.get("ok"):
            log("sendMessage not ok:", j)
        return j
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else str(e)
        log("sendMessage HTTPError:", body)
    except Exception as e:
        log("sendMessage error:", e)

# =================== إدارة المشتركين والروابط ===================

def load_subscribers():
    data = read_json(PATH_SUBS, [])
    clean = []
    for x in data:
        try:
            clean.append(int(x))
        except Exception:
            pass
    return list(sorted(set(clean)))

def save_subscribers(subs):
    write_json(PATH_SUBS, list(sorted(set(int(x) for x in subs))))

def load_dynamic_links():
    return read_json(PATH_LINKS, [])

def save_dynamic_links(links):
    cleaned = []
    for u in links:
        u = str(u).strip()
        if u and u not in cleaned:
            cleaned.append(u)
    write_json(PATH_LINKS, cleaned)

def all_links():
    # دمج مع إزالة التكرارات مع الحفاظ على الترتيب
    return list(dict.fromkeys(FIXED_LINKS + load_dynamic_links()))

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
    # إزالة الأبوستروف حتى نتعامل مع isn't / isn’t / isnt
    s = s.replace("'", "")
    # ضغط المسافات
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

def fetch_link_status(url, timeout=20):
    """
    يرجع: open | full | not_found | unknown | error
    """
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        code = resp.status_code
        html_norm = normalize_text(resp.text)

        if code == 404:
            return "not_found"

        # الامتلاء أولاً لمنع إيجابيات كاذبة
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
        log("fetch_link_status error for", url, ":", e)
        return "error"

def load_kv():
    return read_json(PATH_KV, {"link_states": {}})

def save_kv(kv):
    write_json(PATH_KV, kv)

def broadcast(text):
    subs = load_subscribers()
    if not subs:
        log("broadcast skipped (no subscribers)")
        return
    for uid in subs:
        tg_send_message(uid, text)
        time.sleep(0.05)  # تهدئة خفيفة

def format_state_msg(url, state):
    if state == "open":
        return f"✅ صار <b>متاح</b>:\n{url}"
    if state == "full":
        return f"⛔️ صار <b>ممتلئ</b>:\n{url}"
    if state == "not_found":
        return f"❓ الرابط غير متاح/غير موجود:\n{url}"
    if state == "unknown":
        return f"ℹ️ حالة غير واضحة حاليا:\n{url}"
    return f"⚠️ خطأ أثناء الفحص:\n{url}"

def watch_links_and_notify():
    """
    خيط مراقبة الروابط. محمي بـ while True حتى لو وقع استثناء يرجع يشتغل.
    """
    while True:
        try:
            kv = load_kv()
            last = kv.get("link_states", {})
            log("Watcher started. Links:", len(all_links()))
            backoff = 5
            while True:
                changed_msgs = []
                curr = {}
                links = all_links()
                if not links:
                    log("No links to watch; sleeping 60s")
                    time.sleep(60)
                    continue
                random.shuffle(links)
                for url in links:
                    state = fetch_link_status(url)
                    curr[url] = {"state": state, "ts": int(time.time())}
                    prev_state = (last.get(url) or {}).get("state")
                    if state != prev_state:
                        changed_msgs.append(format_state_msg(url, state))

                if changed_msgs:
                    broadcast("\n\n".join(changed_msgs))
                    backoff = 5  # نعيد التهدئة للمستوى الأدنى عند نشاط
                else:
                    # لا تغيّر: نزيد backoff حتى حد أقصى لتقليل الاستهلاك
                    backoff = min(backoff + 5, 60)

                last = curr
                kv["link_states"] = last
                save_kv(kv)

                sleep_s = random.randint(POLL_MIN_SEC, POLL_MAX_SEC)
                log(f"Watcher sleep {sleep_s}s (backoff={backoff})")
                time.sleep(sleep_s)
        except Exception as e:
            log("watch fatal error:", e)
            time.sleep(30)  # انتظر ثم أعد المحاولة من جديد

# =================== أوامر البوت ===================

HELP_TEXT = f"""\
<b>مرحبًا 👋</b>
هذا البوت يراقب روابط TestFlight لـ <b>{APP_NAME_AR}</b> ويبلغك عند تغيّر الحالة.

<b>الأوامر:</b>
/start - بدء
/help - مساعدة
/subscribe - الاشتراك في الإشعارات
/unsubscribe - إلغاء الاشتراك
/status - الحالة الحالية من آخر فحص
/links - قائمة الروابط المُراقَبة
/owners - عن المالك
/ping - اختبار

<b>للمدير فقط:</b>
/addlink - إضافة رابط TestFlight (أرسل الرابط بعد الأمر)
/removelink - حذف رابط TestFlight
"""

def is_admin(user_id):
    try:
        return int(user_id) in ADMIN_IDS
    except Exception:
        return False

def cmd_start(chat_id, from_user):
    name = (from_user.get("first_name") or "").strip()
    tg_send_message(chat_id, f"أهلًا {name or 'بك'} ✅\n"
                             f"استخدم /subscribe للاشتراك بالإشعارات.\n\n{HELP_TEXT}")

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
        tg_send_message(chat_id, "لا توجد حالات محفوظة بعد. انتظر أول دورة فحص…")
        return
    lines = ["<b>الحالة الحالية:</b>"]
    for url in all_links():
        s = states.get(url, {})
        st = s.get("state", "unknown")
        ts = s.get("ts")
        ts_str = datetime.utcfromtimestamp(ts).isoformat(timespec="seconds")+"Z" if ts else "—"
        badge = "✅" if st == "open" else ("⛔️" if st == "full" else ("❓" if st == "not_found" else "ℹ️"))
        lines.append(f"{badge} <code>{st}</code> — <a href='{url}'>الرابط</a> — <i>{ts_str}</i>")
    tg_send_message(chat_id, "\n".join(lines), disable_web_page_preview=False)

def cmd_links(chat_id):
    links = all_links()
    if not links:
        tg_send_message(chat_id, "لا توجد روابط حالياً.")
        return
    body = "\n".join(f"• <a href='{u}'>{u}</a>" for u in links)
    tg_send_message(chat_id, f"<b>الروابط المُراقَبة ({len(links)}):</b>\n{body}",
                    disable_web_page_preview=False)

def cmd_owners(chat_id):
    tg_send_message(chat_id,
                    f"<b>المالك:</b> {OWNER_NAME}\n"
                    f"<b>Instagram:</b> {OWNER_IG}\n"
                    f"<b>Telegram:</b> {OWNER_TG}\n"
                    f"<b>TestFlight:</b> {TESTFLIGHT_URL}",
                    disable_web_page_preview=False)

def cmd_ping(chat_id):
    tg_send_message(chat_id, "pong ✅")

def cmd_addlink(chat_id, user_id):
    if not is_admin(user_id):
        tg_send_message(chat_id, "هذا الأمر للمدير فقط.")
        return
    PENDING_ACTIONS[chat_id] = {"action": "add"}
    tg_send_message(chat_id, "أرسل الآن رابط TestFlight الذي تريد إضافته.")

def cmd_removelink(chat_id, user_id):
    if not is_admin(user_id):
        tg_send_message(chat_id, "هذا الأمر للمدير فقط.")
        return
    PENDING_ACTIONS[chat_id] = {"action": "remove"}
    tg_send_message(chat_id, "أرسل الآن الرابط الذي تريد حذفه (بالضبط).")

def handle_text_message(chat_id, user_id, text, from_user):
    pending = PENDING_ACTIONS.get(chat_id)
    if pending:
        action = pending.get("action")
        url = text.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            tg_send_message(chat_id, "الرجاء إرسال رابط صحيح يبدأ بـ http/https.")
            return
        links = load_dynamic_links()
        if action == "add":
            if url in FIXED_LINKS or url in links:
                tg_send_message(chat_id, "الرابط موجود مسبقًا.")
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
                tg_send_message(chat_id, "لم أجد هذا الرابط ضمن الروابط الديناميكية.")
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
        tg_send_message(chat_id, "لم أفهم الأمر. اكتب /help لعرض الأوامر المتاحة.")

def handle_update(u):
    if "message" in u:
        msg = u["message"]
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {}) or {}
        user_id = from_user.get("id")
        text = msg.get("text", "")
        if text:
            handle_text_message(chat_id, user_id, text, from_user)
    elif "edited_message" in u:
        # تجاهل الرسائل المعدّلة
        pass

def poll_loop():
    """
    خيط polling لتيليغرام. محمي بحيث لا يخرج عند الاستثناءات.
    """
    while True:
        try:
            tg_delete_webhook()
            last_id = load_last_update_id()
            log("Polling started. last_update_id=", last_id)
            backoff = 1
            while True:
                try:
                    data = tg_get_updates(last_id, timeout=50)
                    if not data.get("ok"):
                        log("getUpdates not ok:", data)
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 60)
                        continue
                    updates = data.get("result", [])
                    if updates:
                        backoff = 1
                    for u in updates:
                        last_id = max(last_id or 0, u["update_id"])
                        handle_update(u)
                    save_last_update_id(last_id)
                except Exception as e:
                    log("poll inner error:", e)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
        except Exception as e:
            log("poll fatal error:", e)
            time.sleep(30)

# =================== مراقبة الخيوط وإبقاء العملية حيّة ===================

def main():
    log("Bot starting…")
    # تشغيل الخيوط باسماء ثابتة لسهولة المراقبة
    t_watch = threading.Thread(target=watch_links_and_notify, daemon=True, name="watcher")
    t_poll = threading.Thread(target=poll_loop, daemon=True, name="poller")
    t_watch.start()
    t_poll.start()

    # حلقة حارس: تعيد تشغيل الخيوط لو توقفت لأي سبب
    while True:
        names = [t.name for t in threading.enumerate()]
        log("Threads alive:", names)
        alive_names = set(names)
        if "watcher" not in alive_names:
            log("watcher thread is down. restarting…")
            threading.Thread(target=watch_links_and_notify, daemon=True, name="watcher").start()
        if "poller" not in alive_names:
            log("poller thread is down. restarting…")
            threading.Thread(target=poll_loop, daemon=True, name="poller").start()
        time.sleep(300)  # راقب كل 5 دقائق

if __name__ == "__main__":
    main()
