import requests
import time
import json

# إعدادات تيليجرام (مباشرة في الكود)
TELEGRAM_TOKEN = "8432204706:AAGMbjgIzIMxIfgv7zAjfGNQXFgAMSzcj2k"
CHAT_ID = "238547634"

print("🚀 بدء التشغيل - باستخدام التوكن والـ Chat ID مباشرة")

# روابط TestFlight
links_status = {
    "https://testflight.apple.com/join/1Z9HQgNw": None,
    "https://testflight.apple.com/join/6drWGVde": None,
    "https://testflight.apple.com/join/uk4993r5": None,
    "https://testflight.apple.com/join/kYbkecxa": None
}

STATUS_FILE = "status.json"

# تحميل الحالة السابقة إذا كانت موجودة
if STATUS_FILE:
    try:
        with open(STATUS_FILE, "r") as f:
            links_status.update(json.load(f))
    except:
        pass

# إرسال إشعار إلى تيليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        resp = requests.post(url, data=payload)
        print(f"📤 إرسال تيليجرام: {message} | استجابة: {resp.text}")
    except Exception as e:
        print(f"❌ خطأ في إرسال الرسالة: {e}")

# إرسال رسالة اختبار عند بدء التشغيل
send_telegram("🚀 البوت بدأ العمل بنجاح على Railway!")

# التحقق من الروابط
def check_links():
    global links_status
    changed = False
    for link in links_status:
        try:
            r = requests.get(link, timeout=10)
            status = "متاح" if "This beta is full" not in r.text else "ممتلئ"
            print(f"🔍 تحقق من {link} → الحالة: {status}")
            if links_status[link] != status:
                links_status[link] = status
                changed = True
                send_telegram(f"{'✅ المقاعد متاحة الآن' if status=='متاح' else '⚠️ المقاعد امتلأت'}: {link}")
        except Exception as e:
            print(f"❌ خطأ في الرابط {link}: {e}")
    
    # حفظ الحالة
    if changed:
        with open(STATUS_FILE, "w") as f:
            json.dump(links_status, f)

# حلقة التشغيل
while True:
    check_links()
    time.sleep(300)  # كل 5 دقائق
