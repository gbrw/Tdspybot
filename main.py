import requests
import time
import json
import os

TELEGRAM_TOKEN = "8432204706:AAGMbjgIzIMxIfgv7zAjfGNQXFgAMSzcj2k"
CHAT_ID = "238547634"

links_status = {
    "https://testflight.apple.com/join/1Z9HQgNw": None,
    "https://testflight.apple.com/join/6drWGVde": None,
    "https://testflight.apple.com/join/uk4993r5": None,
    "https://testflight.apple.com/join/kYbkecxa": None
}

STATUS_FILE = "status.json"

# تحميل الحالة القديمة
if os.path.exists(STATUS_FILE):
    try:
        with open(STATUS_FILE, "r") as f:
            saved_status = json.load(f)
            links_status.update(saved_status)
    except:
        pass

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ خطأ في الإرسال: {e}")

def check_links():
    global links_status
    changed = False
    new_available_links = []  # الروابط التي أصبحت متاحة الآن
    
    # فحص الروابط
    for link in links_status:
        try:
            r = requests.get(link, timeout=10)
            status = "متاح" if "This beta is full" not in r.text else "ممتلئ"
            
            # إذا تغيرت الحالة
            if links_status[link] != status:
                changed = True
                
                # إذا الرابط أصبح متاح الآن
                if status == "متاح":
                    new_available_links.append(link)
            
            links_status[link] = status
        
        except Exception as e:
            print(f"❌ خطأ في الرابط {link}: {e}")

    # إذا حدث أي تغيير
    if changed:
        # حفظ الحالة الجديدة
        with open(STATUS_FILE, "w") as f:
            json.dump(links_status, f)
        
        # 🚨 إشعارات خاصة للروابط الجديدة المتاحة
        for link in new_available_links:
            send_telegram(f"🚨 رابط متاح الآن:\n{link}")
        
        # 📊 إرسال ملخص كامل
        available = [link for link, status in links_status.items() if status == "متاح"]
        full = [link for link, status in links_status.items() if status == "ممتلئ"]

        message = "📊 حالة الروابط الآن:\n\n"
        if available:
            message += "✅ متاح:\n" + "\n".join(f"- {link}" for link in available) + "\n\n"
        if full:
            message += "⚠️ ممتلئ:\n" + "\n".join(f"- {link}" for link in full)

        send_telegram(message)

print("🚀 البوت يعمل... في انتظار أي تغيير")
while True:
    check_links()
    time.sleep(300)
