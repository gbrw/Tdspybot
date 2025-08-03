import requests
import time
import json
import os

# إعدادات تيليجرام
TELEGRAM_TOKEN = "8432204706:AAGMbjgIzIMxIfgv7zAjfGNQXFgAMSzcj2k"
CHAT_ID = "238547634"

# روابط TestFlight مع الحالة
links_status = {
    "https://testflight.apple.com/join/1Z9HQgNw": None,
    "https://testflight.apple.com/join/6drWGVde": None,
    "https://testflight.apple.com/join/uk4993r5": None,
    "https://testflight.apple.com/join/kYbkecxa": None
}

STATUS_FILE = "status.json"

# تحميل الحالة السابقة إذا وجدت
if os.path.exists(STATUS_FILE):
    try:
        with open(STATUS_FILE, "r") as f:
            saved_status = json.load(f)
            links_status.update(saved_status)
        print("✅ تم تحميل الحالة السابقة بنجاح")
    except Exception as e:
        print(f"⚠️ فشل تحميل الحالة السابقة: {e}")

# إرسال رسالة تيليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        resp = requests.post(url, data=payload)
        print(f"📤 إرسال: {message} | استجابة: {resp.text}")
    except Exception as e:
        print(f"❌ خطأ في إرسال الرسالة: {e}")

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
                send_telegram(f"{'✅ المقاعد متاحة' if status == 'متاح' else '⚠️ المقاعد امتلأت'}: {link}")
        except Exception as e:
            print(f"❌ خطأ في الرابط {link}: {e}")
    
    if changed:
        with open(STATUS_FILE, "w") as f:
            json.dump(links_status, f)

# بدء المراقبة
print("🚀 البوت يعمل... في انتظار أي تغيير")
while True:
    check_links()
    time.sleep(300)  # كل 5 دقائقwhile True:
    check_links()
    time.sleep(300)  # كل 5 دقائق
