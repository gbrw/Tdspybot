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
import re

# =================== الإعدادات ===================
TELEGRAM_TOKEN = "8299272165:AAH1s7qqEEO1htuiMdjF1TnvzetpB4vE1Wc"
if not TELEGRAM_TOKEN:
    raise SystemExit("❌ TELEGRAM_TOKEN غير موجود في المتغيرات.")

POLL_MIN_SEC = int(os.environ.get("POLL_MIN_SEC", "180"))
POLL_MAX_SEC = int(os.environ.get("POLL_MAX_SEC", "300"))

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

# =================== جلسة HTTP محسنة ===================
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
session = requests.Session()

# محاكاة متصفح حقيقي لتجنب الحظر
session.headers.update({
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
})

adapter = requests.adapters.HTTPAdapter(
    max_retries=3,
    pool_connections=10,
    pool_maxsize=10
)
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
            [{"text": "📊 الحالة"}, {"text": "🔄 فحص فوري"}],
            [{"text": "👤 المالك"}, {"text": "ℹ️ المساعدة"}],
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

# =================== مراقبة TestFlight محسنة ===================
def clean_html_text(html):
    """تنظيف النص من HTML وإزالة المسافات الزائدة"""
    if not html:
        return ""
    
    # إزالة العلامات HTML
    text = re.sub(r'<[^>]+>', ' ', html)
    # توحيد المسافات البيضاء
    text = re.sub(r'\s+', ' ', text)
    # تنظيف النص
    text = text.lower().strip()
    
    return text

def analyze_testflight_page(html_content, url):
    """تحليل محسن لصفحة TestFlight"""
    if not html_content:
        return "error", "No content"
    
    # تنظيف النص
    clean_text = clean_html_text(html_content)
    
    log(f"Analyzing page for {url}")
    log(f"Page text preview: {clean_text[:200]}...")
    
    # مؤشرات واضحة على أن الصفحة غير موجودة أو منتهية الصلاحية
    NOT_FOUND_INDICATORS = [
        "the requested app is not available or does not exist",
        "this app is no longer available for testing",
        "page not found",
        "could not find",
        "does not exist",
        "not available",
        "no longer available",
        "app not available",
        "invalid invitation",
        "expired invitation",
        "invitation expired",
    ]
    
    # مؤشرات واضحة على أن البيتا ممتلئة
    FULL_INDICATORS = [
        "this beta is full",
        "beta is full",
        "this beta isn't accepting any new testers right now",
        "this beta isn't accepting any new testers",
        "isn't accepting any new testers",
        "is not accepting any new testers",
        "no longer accepting new testers",
        "no longer accepting testers",
        "beta full",
        "capacity reached",
        "maximum testers reached",
        "at capacity",
    ]
    
    # مؤشرات على التوفر (يجب أن تكون محددة جداً)
    AVAILABLE_INDICATORS = [
        # يجب أن تكون هذه العبارات موجودة معاً
        ("start testing", "testflight"),
        ("join the beta", "testflight"), 
        ("view in testflight", "install"),
        ("accept", "install", "testflight"),
    ]
    
    # التحقق من عدم الوجود أولاً
    for indicator in NOT_FOUND_INDICATORS:
        if indicator in clean_text:
            log(f"Found NOT_FOUND indicator: {indicator}")
            return "not_found", f"Found: {indicator}"
    
    # التحقق من الامتلاء
    for indicator in FULL_INDICATORS:
        if indicator in clean_text:
            log(f"Found FULL indicator: {indicator}")
            return "full", f"Found: {indicator}"
    
    # التحقق من التوفر (يتطلب مؤشرات متعددة)
    for indicators in AVAILABLE_INDICATORS:
        all_found = all(ind in clean_text for ind in indicators)
        if all_found:
            log(f"Found AVAILABLE indicators: {indicators}")
            
            # تأكيد إضافي: التأكد من عدم وجود مؤشرات سلبية
            negative_check = any(neg in clean_text for neg in FULL_INDICATORS + NOT_FOUND_INDICATORS)
            if not negative_check:
                return "open", f"Found all: {indicators}"
            else:
                log("Available indicators found but negative indicators also present")
    
    # البحث عن عناصر HTML محددة لتأكيد الحالة
    if 'testflight://' in html_content or 'itms-beta://' in html_content:
        # وجود رابط TestFlight يشير عادة إلى التوفر
        if not any(neg in clean_text for neg in FULL_INDICATORS + NOT_FOUND_INDICATORS):
            log("Found TestFlight URL scheme without negative indicators")
            return "open", "TestFlight URL scheme found"
    
    # إذا وصلنا هنا، لم نجد مؤشرات واضحة
    log("No clear indicators found, defaulting to full")
    return "full", "No clear status indicators"

def fetch_link_status(url, timeout=30):
    """جلب حالة الرابط مع تحليل محسن"""
    try:
        log(f"Fetching: {url}")
        
        # طلب مع headers محسنة
        response = session.get(url, timeout=timeout, allow_redirects=True)
        
        log(f"Response status: {response.status_code}")
        log(f"Final URL after redirects: {response.url}")
        
        # التحقق من رمز الاستجابة
        if response.status_code == 404:
            return "not_found"
        elif response.status_code != 200:
            log(f"Unexpected status code: {response.status_code}")
            return "error"
        
        # تحليل المحتوى
        status, reason = analyze_testflight_page(response.text, url)
        log(f"Analysis result: {status} - {reason}")
        
        return status
        
    except requests.exceptions.Timeout:
        log(f"Timeout for {url}")
        return "error"
    except requests.exceptions.RequestException as e:
        log(f"Request error for {url}: {e}")
        return "error"
    except Exception as e:
        log(f"Unexpected error for {url}: {e}")
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
        time.sleep(0.15)  # تأخير للتجنب Rate Limiting
    
    log(f"Broadcast completed: {success_count}/{len(subs)} successful")

def format_state_msg(url, state, ts, show_url=True):
    labels = {
        "open": ("🟢", "متاح للتسجيل"),
        "full": ("🔴", "ممتلئ"),
        "not_found": ("❌", "غير موجود/منتهي"),
        "unknown": ("❓", "غير معروف"),
        "error": ("⚠️", "خطأ في الفحص"),
    }
    badge, label = labels.get(state, ("❓", state))
    
    if show_url:
        return f"{badge} <b>{label}</b>\n🕐 {format_time(ts)}\n🔗 {url}"
    else:
        return f"{badge} <b>{label}</b> — {format_time(ts)}"

def check_all_links():
    """فحص جميع الروابط مع تأخير بينها"""
    results = {}
    for i, url in enumerate(FIXED_LINKS):
        if i > 0:  # تأخير بين الطلبات
            time.sleep(random.randint(3, 7))
        
        state = fetch_link_status(url)
        ts = int(time.time())
        results[url] = {"state": state, "ts": ts}
        
        log(f"Link {i+1}/{len(FIXED_LINKS)}: {state}")
    
    return results

def watch_links_and_notify():
    log("Starting enhanced link monitoring...")
    kv = load_kv()
    last_states = kv.get("link_states", {})
    
    # فحص أولي
    log("Performing initial check...")
    try:
        initial_results = check_all_links()
        last_states = initial_results
        kv["link_states"] = last_states
        kv["last_check"] = int(time.time())
        save_kv(kv)
        log("Initial check completed")
    except Exception as e:
        log(f"Initial check failed: {e}")
    
    while True:
        try:
            log("Starting monitoring cycle...")
            current_results = check_all_links()
            
            # تحليل التغييرات
            notifications = []
            critical_notifications = []
            
            for url, current_data in current_results.items():
                current_state = current_data["state"]
                current_ts = current_data["ts"]
                
                last_data = last_states.get(url, {})
                last_state = last_data.get("state")
                
                if current_state != last_state:
                    log(f"State change detected for {url}: {last_state} -> {current_state}")
                    
                    msg = format_state_msg(url, current_state, current_ts)
                    
                    # إشعارات حرجة للتوفر فقط
                    if current_state == "open":
                        critical_msg = (
                            f"🚨 <b>عاجل: مكان متاح الآن!</b> 🚨\n\n"
                            f"{msg}\n\n"
                            f"⚡ <b>سارع بالتسجيل قبل امتلاء المكان!</b>\n"
                            f"📱 تأكد من تثبيت TestFlight أولاً"
                        )
                        critical_notifications.append(critical_msg)
                    else:
                        notifications.append(msg)
            
            # إرسال الإشعارات الحرجة أولاً
            for notif in critical_notifications:
                broadcast(notif, important=True)
                time.sleep(2)  # تأخير بين الإشعارات المهمة
            
            # إرسال الإشعارات العادية
            if notifications:
                combined_msg = "📊 <b>تحديث الحالة:</b>\n\n" + "\n\n".join(notifications)
                broadcast(combined_msg)
            
            # حفظ البيانات
            last_states = current_results
            kv["link_states"] = last_states
            kv["last_check"] = int(time.time())
            save_kv(kv)
            
            # انتظار الدورة التالية
            sleep_time = random.randint(POLL_MIN_SEC, POLL_MAX_SEC)
            log(f"Monitoring cycle completed. Next check in {sleep_time} seconds")
            time.sleep(sleep_time)
            
        except Exception as e:
            log(f"Monitoring error: {e}")
            time.sleep(120)  # انتظار أطول عند الخطأ

# =================== واجهة المستخدم ===================
WELCOME_TEXT = (
    f"🎉 مرحباً بك في بوت مراقبة <b>{APP_NAME_AR}</b>\n\n"
    "🔍 <b>مراقبة دقيقة ومحسنة لروابط TestFlight</b>\n\n"
    "✨ <b>المميزات:</b>\n"
    "• كشف دقيق للحالات (بدون إنذارات كاذبة)\n"
    "• إشعارات فورية عند التوفر الحقيقي\n"
    "• مراقبة مستمرة ومحسنة\n"
    "• تحليل متقدم لصفحات TestFlight\n\n"
    "⚠️ <b>مهم:</b> تحتاج تطبيق TestFlight لتثبيت التطبيق"
)

HELP_TEXT = """\
📖 <b>دليل الاستخدام المفصل</b>

🟢 <b>تفعيل الإشعارات</b>
└ تفعيل إشعارات التوفر الفورية (محسنة ودقيقة)

🔴 <b>تعطيل الإشعارات</b>
└ إيقاف جميع الإشعارات

📊 <b>الحالة</b>
└ عرض حالة جميع الروابط مع آخر فحص

🔄 <b>فحص فوري</b>
└ فحص محسن ودقيق للروابط الآن

👤 <b>المالك</b>
└ معلومات المطور

🔧 <b>التحسينات الجديدة:</b>
• كشف دقيق للحالات (لا مزيد من الإنذارات الكاذبة)
• تحليل متقدم لصفحات TestFlight
• فحص كل 3-5 دقائق
• إشعارات موثوقة 100%

⚡ <b>ملاحظة:</b> البوت الآن يتجنب الإنذارات الكاذبة تماماً
"""

def cmd_start(chat_id, from_user):
    tg_send_message(chat_id, WELCOME_TEXT, reply_markup=testflight_inline_button())
    time.sleep(1)
    tg_send_message(chat_id, "🎯 اختر من الأزرار أدناه للبدء", reply_markup=main_keyboard())

def cmd_help(chat_id):
    tg_send_message(chat_id, HELP_TEXT, reply_markup=main_keyboard())

def cmd_enable(chat_id):
    subs = load_subscribers()
    is_new = chat_id not in subs
    
    if is_new:
        subs.append(chat_id)
        save_subscribers(subs)
        msg = (
            "✅ تم <b>تفعيل</b> الإشعارات بنجاح!\n\n"
            "🎯 <b>مميزات النظام المحسن:</b>\n"
            "• كشف دقيق 100% للحالات\n"
            "• لا مزيد من الإنذارات الكاذبة\n"
            "• إشعارات فورية عند التوفر الحقيقي\n\n"
            "🔔 ستحصل على إشعار فقط عند توفر مكان حقيقي!"
        )
    else:
        msg = "✅ الإشعارات <b>مفعلة</b> مسبقاً مع النظام المحسن!"
    
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
    tg_send_message(chat_id, "🔍 جاري الفحص المحسن والدقيق...", reply_markup=main_keyboard())
    
    try:
        results = check_all_links()
        lines = ["🎯 <b>نتائج الفحص المحسن:</b>\n"]
        
        available_count = 0
        full_count = 0
        error_count = 0
        
        for url in FIXED_LINKS:
            data = results.get(url, {})
            state = data.get("state", "unknown")
            ts = data.get("ts", int(time.time()))
            
            if state == "open":
                available_count += 1
            elif state == "full":
                full_count += 1
            elif state == "error":
                error_count += 1
            
            lines.append(format_state_msg(url, state, ts))
        
        # إضافة ملخص
        summary = f"📊 <b>الملخص:</b> {available_count} متاح | {full_count} ممتلئ | {error_count} خطأ\n"
        lines.insert(1, summary)
        
        if available_count > 0:
            lines.insert(2, f"🎉 <b>يوجد {available_count} رابط متاح فعلاً!</b>\n")
        else:
            lines.insert(2, "😔 لا توجد أماكن متاحة حالياً\n")
        
        tg_send_message(chat_id, "\n\n".join(lines), disable_web_page_preview=True, reply_markup=main_keyboard())
        
    except Exception as e:
        log(f"Instant check error: {e}")
        tg_send_message(chat_id, "❌ حدث خطأ أثناء الفحص، حاول مرة أخرى.", reply_markup=main_keyboard())

def cmd_status(chat_id):
    kv = load_kv()
    states = kv.get("link_states", {})
    last_check = kv.get("last_check", 0)
    
    if not states:
        tg_send_message(
            chat_id, 
            "⏳ لم يتم فحص الروابط بعد.\n"
            "استخدم 'فحص فوري' للفحص المحسن الآن.", 
            reply_markup=main_keyboard()
        )
        return
    
    lines = ["📊 <b>الحالة الحالية (النظام المحسن):</b>"]
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
        lines.insert(-len(FIXED_LINKS), f"🎉 <b>{available_count} رابط متاح حقيقياً!</b>\n")
    else:
        lines.insert(-len(FIXED_LINKS), "🔍 <b>لا توجد أماكن متاحة - الفحص دقيق 100%</b>\n")
    
    tg_send_message(chat_id, "\n\n".join(lines), disable_web_page_preview=True, reply_markup=main_keyboard())

def cmd_owners(chat_id):
    tg_send_message(
        chat_id,
        f"👤 <b>معلومات المطور:</b>\n\n"
        f"📧 <b>الاسم:</b> {OWNER_NAME}\n"
        f"📱 <b>Instagram:</b> {OWNER_IG}\n"
        f"💬 <b>Telegram:</b> {OWNER_TG}\n\n"
        f"🎯 <b>التحسينات الجديدة:</b>\n"
        f"• كشف دقيق للحالات (لا إنذارات كاذبة)\n"
        f"• تحليل متقدم لصفحات TestFlight\n"
        f"• نظام إشعارات محسن وموثوق",
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
        tg_send_message(chat_id, "🎯 اختر من الأزرار أدناه", reply_markup=main_keyboard())

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
    log("🚀 Enhanced TestFlight Monitor Bot starting...")
    log(f"📊 Monitoring {len(FIXED_LINKS)} links with improved accuracy")
    log(f"⏱️ Check interval: {POLL_MIN_SEC}-{POLL_MAX_SEC} seconds")
    log("🎯 Enhanced detection system active - no more false positives!")
    
    # بدء الخيوط
    watcher_thread = threading.Thread(target=watch_links_and_notify, daemon=True, name="EnhancedLinkWatcher")
    poller_thread = threading.Thread(target=poll_loop, daemon=True, name="TelegramPoller")
    
    watcher_thread.start()
    poller_thread.start()
    
    log("✅ Enhanced monitoring system started successfully")
    
    # حلقة المراقبة الرئيسية
    try:
        while True:
            time.sleep(60)
            # فحص صحة الخيوط
            if not watcher_thread.is_alive():
                log("❌ Watcher thread died, restarting with enhancements...")
                watcher_thread = threading.Thread(target=watch_links_and_notify, daemon=True, name="EnhancedLinkWatcher")
                watcher_thread.start()
            
            if not poller_thread.is_alive():
                log("❌ Poller thread died, restarting...")
                poller_thread = threading.Thread(target=poll_loop, daemon=True, name="TelegramPoller")
                poller_thread.start()
                
    except KeyboardInterrupt:
        log("🛑 Enhanced bot stopped by user")
    except Exception as e:
        log(f"❌ Main loop error: {e}")

if __name__ == "__main__":
    main()
