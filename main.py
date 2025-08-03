import requests
import time

# إعدادات تيليجرام
TELEGRAM_TOKEN = "
          8432204706:AAGMbjgIzIMxIfgv7zAjfGNQXFgAMSzcj2k"
CHAT_ID = "238547634"

# روابط TestFlight
links = {
    "https://testflight.apple.com/join/1Z9HQgNw": None,
    "https://testflight.apple.com/join/6drWGVde": None,
    "https://testflight.apple.com/join/uk4993r5": None,
    "https://testflight.apple.com/join/kYbkecxa": None
}

# دالة إرسال إشعار إلى تيليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ خطأ في إرسال الرسالة: {e}")

# دالة التحقق من توفر المقاعد
def check_links():
    global links
    for link in links:
        try:
            r = requests.get(link, timeout=10)
            status = "متاح" if "This beta is full" not in r.text else "ممتلئ"

            # إذا تغيرت الحالة فقط أرسل إشعار
            if links[link] != status:
                links[link] = status
                if status == "متاح":
                    send_telegram(f"✅ المقاعد متاحة الآن: {link}")
                else:
                    send_telegram(f"⚠️ المقاعد امتلأت: {link}")

        except Exception as e:
            print(f"❌ خطأ في الرابط {link}: {e}")

# تشغيل التحقق كل 5 دقائق
while True:
    check_links()
    time.sleep(300)  # 5 دقائق
