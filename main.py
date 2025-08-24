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

POLL_MIN_SEC = int(os.environ.get("POLL_MIN_SEC", "120"))  # قللت الوقت للمراقبة الأسرع
POLL_MAX_SEC = int(os.environ.get("POLL_MAX_SEC", "180"))

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
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})
adapter = requests.adapters.HTTPAdapter(max_retries=3)
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
    except Exception as e:
        log(f"Error reading {path}: {e}")
        return default

def write_json(path, obj):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        log(f"Error writing {path}: {e}")

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
        log(f"Error saving update ID: {e}")

# =================== تيليغرام API ===================
def tg_delete_webhook():
    try:
        session.get(f"{API_BASE}/deleteWebhook", timeout=10)
        log("Webhook deleted")
    except Exception as e:
        log(f"Delete webhook error: {e}")

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
        r.raise_for_status()
        log(f"Message sent to {chat_id}")
        return True
    except Exception as e:
        log(f"sendMessage error to {chat_id}: {e}")
        return False

# =============== لوحات الأزرار ===============
def main_keyboard():
    return {
        "keyboard": [
            [{"text": "🟢 تفعيل الإشعارات"}, {"text": "🔴 تعطيل الإشعارات"}],
            [{"text": "📊 الحالة"}, {"text": "👤 المالك"}],
            [{"text": "ℹ️ المساعدة"}, {"text": "🔄 فحص فوري"}],
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
    s = (s.replace("'", "'")
           .replace("'", "'")
           .replace(""", '"')
           .replace(""", '"')
           .replace("–", "-")
           .replace("—", "-")
           .replace("\u00a0", " "))
    s = s.replace("isn't", "isn't").replace("is not", "isn't")
    s = s.replace("'", "")
    s = " ".join(s.split())
    return s

# محسن لكشف الحالات بدقة أكبر
TF_AVAILABLE_MARKERS = [
    "join the beta",
    "start testing",
    "accept",
    "install",
    "view in testflight",
]

TF_FULL_MARKERS = [
    "this beta is full",
    "beta is full",
    "this beta isn't accepting any new testers right now",
    "this beta isn't accepting any new testers",
    "isn't accepting any new testers",
    "is not accepting any new testers",
    "no longer accepting new testers",
    "no longer accepting testers",
    "beta full",
    "full beta",
]

TF_UNAVAILABLE_HINTS = [
    "not available",
    "no longer available",
    "app not available",
    "page not found",
    "the requested app is not available or does not exist",
    "could not find",
    "does not exist",
]

def fetch_link_status(url, timeout=25):
    try:
        log(f"Checking {url}")
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        code = resp.status_code
        html_norm = normalize_text(resp.text)
        
        log(f"Response code for {url}: {code}")
        
        if code == 404:
            return "not_found"
        
        # التحقق من عدم التوفر أولاً
        for marker in TF_UNAVAILABLE_HINTS:
            if marker in html_norm:
                log(f"Found unavailable marker: {marker}")
                return "not_found"
        
        # التحقق من الامتلاء
        for marker in TF_FULL_MARKERS:
            if marker in html_norm:
                log(f"Found full marker: {marker}")
                return "full"
        
        # التحقق من التوفر
        for marker in TF_AVAILABLE_MARKERS:
            if marker in html_norm:
                log(f"Found available marker: {marker}")
                return "open"
        
        # إذا لم نجد أي علامة واضحة، نعتبره ممتلئ
        log(f"No clear markers found for {url}, assuming full")
        return "full"
        
    except requests.exceptions.Timeout:
        log(f"Timeout for {url}")
        return "error"
    except Exception as e:
        log(f"fetch_link_status error for {url}: {e}")
        return "error"

def load_kv():
    return read_json(PATH_KV, {"link_states": {}, "last_check": 0})

def save_kv(kv):
    write_json(PATH_KV, kv)

def broadcast(text, important=False):
    subs = load_subscribers()
    success_count = 0
    
    if not subs:
        log("No subscribers to broadcast to")
        return
    
    log(f"Broadcasting to {len(subs)} subscribers")
    
    for uid in subs:
        if tg_send_message(uid, text, reply_markup=main_keyboard()):
            success_count += 1
        time.sleep(0.1)  # زيادة التأخير قليلاً لتجنب Rate Limiting
    
    log(f"Broadcast completed: {success_count}/{len(subs)} successful")

def format_state_msg(url, state, ts, show_url=True):
    labels = {
        "open": ("🟢", "متاح للتسجيل"),
        "full": ("🔴", "ممتلئ"),
        "not_found": ("❓", "غير موجود"),
        "unknown": ("ℹ️", "غير معروف"),
        "error": ("⚠️", "خطأ في الفحص"),
    }
    badge, label = labels.get(state, ("❓", state))
    
    if show_url:
        return f"{badge} <b>{label}</b>\n🕐 {format_time(ts)}\n🔗 {url}"
    else:
        return f"{badge} <b>{label}</b> — {format_time(ts)}"

def check_all_links():
    """فحص جميع الروابط وإرجاع النتائج"""
    results = {}
    for url in FIXED_LINKS:
        state = fetch_link_status(url)
        ts = int(time.time())
        results[url] = {"state": state, "ts": ts}
        time.sleep(2)  # تأخير بين الطلبات
    return results

def watch_links_and_notify():
    log("Starting link monitoring...")
    kv = load_kv()
    last_states = kv.get("link_states", {})
    
    while True:
        try:
            log("Checking all links...")
            current_results = check_all_links()
            
            # التحقق من التغييرات وإرسال الإشعارات
            notifications = []
            important_notifications = []
            
            for url, current_data in current_results.items():
                current_state = current_data["state"]
                current_ts = current_data["ts"]
                
                last_data = last_states.get(url, {})
                last_state = last_data.get("state")
                
                # إذا تغيرت الحالة
                if current_state != last_state:
                    log(f"State changed for {url}: {last_state} -> {current_state}")
                    
                    msg = format_state_msg(url, current_state, current_ts)
                    
                    # إذا أصبح متاحاً، هذا مهم جداً!
                    if current_state == "open":
                        important_msg = f"🚨 <b>عاجل: مكان متاح الآن!</b> 🚨\n\n{msg}\n\n⚡ سارع بالتسجيل قبل امتلاء المكان!"
                        important_notifications.append(important_msg)
                    else:
                        notifications.append(msg)
            
            # إرسال الإشعارات المهمة أولاً
            for notif in important_notifications:
                broadcast(notif, important=True)
                time.sleep(1)
            
            # ثم الإشعارات العادية
            if notifications:
                combined_msg = "\n\n" + "="*30 + "\n\n".join(notifications)
                broadcast(combined_msg)
            
            # حفظ الحالات الجديدة
            last_states = current_results
            kv["link_states"] = last_states
            kv["last_check"] = int(time.time())
            save_kv(kv)
            
            # انتظار قبل الفحص التالي
            sleep_time = random.randint(POLL_MIN_SEC, POLL_MAX_SEC)
            log(f"Next check in {sleep_time} seconds")
            time.sleep(sleep_time)
            
        except Exception as e:
            log(f"Watch error: {e}")
            time.sleep(60)  # انتظار أطول عند حدوث خطأ

# =================== رسائل الواجهة ===================
WELCOME_TEXT = (
    f"🎉 مرحباً بك في بوت مراقبة <b>{APP_NAME_AR}</b>\n\n"
    "📱 هذا البوت يراقب توفر أماكن TestFlight ويرسل إشعارات فورية عند التوفر\n\n"
    "✅ المميزات:\n"
    "• مراقبة مستمرة 24/7\n"
    "• إشعارات فورية عند التوفر\n"
    "• متابعة عدة روابط\n\n"
    "⚠️ تحتاج تطبيق TestFlight لتثبيت التطبيق"
)

HELP_TEXT = """\
📋 <b>دليل الاستخدام</b>

🟢 <b>تفعيل الإشعارات</b>
└ تفعيل إشعارات التوفر الفورية

🔴 <b>تعطيل الإشعارات</b>
└ إيقاف جميع الإشعارات

📊 <b>الحالة</b>
└ عرض حالة جميع الروابط الحالية

🔄 <b>فحص فوري</b>
└ فحص الروابط الآن دون انتظار

👤 <b>المالك</b>
└ معلومات المطور

ℹ️ <b>ملاحظات مهمة:</b>
• الفحص يتم كل 2-3 دقائق
• ستحصل على إشعار فوري عند التوفر
• تأكد من تفعيل الإشعارات
"""

def cmd_start(chat_id, from_user):
    tg_send_message(chat_id, WELCOME_TEXT, reply_markup=testflight_inline_button())
    time.sleep(1)
    tg_send_message(chat_id, "اختر من الأزرار أدناه 👇", reply_markup=main_keyboard())

def cmd_help(chat_id):
    tg_send_message(chat_id, HELP_TEXT, reply_markup=main_keyboard())

def cmd_enable(chat_id):
    subs = load_subscribers()
    is_new = chat_id not in subs
    
    if is_new:
        subs.append(chat_id)
        save_subscribers(subs)
        msg = "✅ تم <b>تفعيل</b> الإشعارات بنجاح!\n\nستحصل على إشعار فوري عند توفر أي مكان."
    else:
        msg = "✅ الإشعارات <b>مفعلة</b> مسبقاً!"
    
    tg_send_message(chat_id, msg, reply_markup=main_keyboard())

def cmd_disable(chat_id):
    subs = load_subscribers()
    if chat_id in subs:
        subs = [x for x in subs if x != chat_id]
        save_subscribers(subs)
        msg = "🔴 تم <b>تعطيل</b> الإشعارات."
    else:
        msg = "🔴 الإشعارات <b>معطلة</b> مسبقاً."
    
    tg_send_message(chat_id, msg, reply_markup=main_keyboard())

def cmd_instant_check(chat_id):
    tg_send_message(chat_id, "🔄 جاري الفحص الفوري...", reply_markup=main_keyboard())
    
    try:
        results = check_all_links()
        lines = ["📊 <b>نتائج الفحص الفوري:</b>\n"]
        
        available_count = 0
        for url in FIXED_LINKS:
            data = results.get(url, {})
            state = data.get("state", "unknown")
            ts = data.get("ts", int(time.time()))
            
            if state == "open":
                available_count += 1
            
            lines.append(format_state_msg(url, state, ts))
        
        if available_count > 0:
            lines.insert(1, f"🎉 <b>{available_count} رابط متاح حالياً!</b>\n")
        else:
            lines.insert(1, "😔 لا توجد أماكن متاحة حالياً\n")
        
        tg_send_message(chat_id, "\n\n".join(lines), disable_web_page_preview=True, reply_markup=main_keyboard())
        
    except Exception as e:
        log(f"Instant check error: {e}")
        tg_send_message(chat_id, "❌ حدث خطأ أثناء الفحص، حاول مرة أخرى.", reply_markup=main_keyboard())

def cmd_status(chat_id):
    kv = load_kv()
    states = kv.get("link_states", {})
    last_check = kv.get("last_check", 0)
    
    if not states:
        tg_send_message(chat_id, "⏳ لم يتم فحص الروابط بعد.\nاستخدم 'فحص فوري' للفحص الآن.", reply_markup=main_keyboard())
        return
    
    lines = ["📊 <b>الحالة الحالية:</b>"]
    if last_check:
        lines.append(f"🕐 آخر فحص: {format_time(last_check)}\n")
    
    available_count = 0
    for url in FIXED_LINKS:
        data = states.get(url, {})
        state = data.get("state", "unknown")
        ts = data.get("ts", 0)
        
        if state == "open":
            available_count += 1
        
        lines.append(format_state_msg(url, state, ts))
    
    if available_count > 0:
        lines.insert(-len(FIXED_LINKS), f"🎉 <b>{available_count} رابط متاح!</b>\n")
    
    tg_send_message(chat_id, "\n\n".join(lines), disable_web_page_preview=True, reply_markup=main_keyboard())

def cmd_owners(chat_id):
    tg_send_message(
        chat_id,
        f"👤 <b>معلومات المطور:</b>\n\n"
        f"📧 <b>الاسم:</b> {OWNER_NAME}\n"
        f"📱 <b>Instagram:</b> {OWNER_IG}\n"
        f"💬 <b>Telegram:</b> {OWNER_TG}\n\n"
        f"💡 <b>نصائح:</b>\n"
        f"• فعّل الإشعارات للحصول على التحديثات\n"
        f"• استخدم الفحص الفوري للتحقق السريع",
        disable_web_page_preview=True,
        reply_markup=main_keyboard()
    )

def handle_text_message(chat_id, text, from_user):
    t = (text or "").strip()
    
    log(f"Received message from {chat_id}: {t}")
    
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
    elif t in ("/check", "🔄 فحص فوري"):
        cmd_instant_check(chat_id)
    elif t in ("/owners", "👤 المالك"):
        cmd_owners(chat_id)
    else:
        tg_send_message(chat_id, "❓ اختر من الأزرار أدناه 👇", reply_markup=main_keyboard())

def handle_update(u):
    try:
        if "message" in u:
            msg = u["message"]
            chat_id = msg["chat"]["id"]
            from_user = msg.get("from", {}) or {}
            text = msg.get("text", "")
            if text:
                handle_text_message(chat_id, text, from_user)
    except Exception as e:
        log(f"Error handling update: {e}")

def poll_loop():
    log("Starting Telegram polling...")
    while True:
        try:
            tg_delete_webhook()
            last_id = load_last_update_id()
            log(f"Starting polling from update_id: {last_id}")
            
            while True:
                try:
                    data = tg_get_updates(last_id, timeout=50)
                    updates = data.get("result", [])
                    
                    for u in updates:
                        last_id = max(last_id or 0, u["update_id"])
                        handle_update(u)
                    
                    if updates:
                        save_last_update_id(last_id)
                        
                except requests.exceptions.Timeout:
                    log("Polling timeout, continuing...")
                    continue
                except Exception as e:
                    log(f"Polling error: {e}")
                    time.sleep(10)
                    break
                    
        except Exception as e:
            log(f"Poll loop error: {e}")
            time.sleep(30)

# =================== main ===================
def main():
    log("🚀 Bot starting...")
    log(f"Monitoring {len(FIXED_LINKS)} links")
    log(f"Check interval: {POLL_MIN_SEC}-{POLL_MAX_SEC} seconds")
    
    # بدء الخيوط
    watcher_thread = threading.Thread(target=watch_links_and_notify, daemon=True, name="LinkWatcher")
    poller_thread = threading.Thread(target=poll_loop, daemon=True, name="TelegramPoller")
    
    watcher_thread.start()
    poller_thread.start()
    
    log("✅ All threads started successfully")
    
    # حلقة رئيسية للحفاظ على البرنامج
    try:
        while True:
            time.sleep(60)
            # التحقق من صحة الخيوط
            if not watcher_thread.is_alive():
                log("❌ Watcher thread died, restarting...")
                watcher_thread = threading.Thread(target=watch_links_and_notify, daemon=True, name="LinkWatcher")
                watcher_thread.start()
            
            if not poller_thread.is_alive():
                log("❌ Poller thread died, restarting...")
                poller_thread = threading.Thread(target=poll_loop, daemon=True, name="TelegramPoller")
                poller_thread.start()
                
    except KeyboardInterrupt:
        log("🛑 Bot stopped by user")
    except Exception as e:
        log(f"❌ Main loop error: {e}")

if __name__ == "__main__":
    main()
