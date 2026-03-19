"""
🤖 بوت الكورسات المجانية - تيليجرام (نسخة محدّثة)
يجيب وصف الكورس + تاريخ انتهاء الكوبون + عدد الكوبونات المتاحة
"""

import requests
from bs4 import BeautifulSoup
import time
import schedule
import json
import os
import re
from datetime import datetime

# ========================================
# ⚙️ الإعدادات - عدّلها بياناتك
# ========================================
TELEGRAM_BOT_TOKEN = "8354441818:AAFW43mmwXDTNod8yA-Xufu2tyOg-44qu3s"
TELEGRAM_CHANNEL_ID = "@Courses for free | الكورسات المدفوعة مجانا"
SHRINKME_API_KEY = "3c748776ec2005ff6824e30a050bb817a5d8f6df"
POSTED_FILE = "posted_courses.json"
POST_INTERVAL_HOURS = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# ========================================
# 📚 سكرابر القائمة من real.discount
# ========================================
def scrape_course_list(max_courses=15):
    courses = []
    try:
        url = "https://real.discount/udemy-free-courses/"
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select(".card")
        for card in cards:
            try:
                title_el = card.select_one(".card-title") or card.select_one("h5")
                link_el  = card.select_one("a")
                cat_el   = card.select_one(".badge") or card.select_one(".category")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                if not href.startswith("http"):
                    href = "https://real.discount" + href
                courses.append({
                    "title":    title_el.get_text(strip=True),
                    "page_url": href,
                    "category": cat_el.get_text(strip=True) if cat_el else "تطوير",
                    "source":   "Udemy",
                })
                if len(courses) >= max_courses:
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"❌ خطأ في السكرابر: {e}")
    return courses


# ========================================
# 🔍 جلب تفاصيل الكورس من صفحته
# ========================================
def get_course_details(page_url):
    details = {
        "description":    "",
        "coupon_count":   "غير محدد",
        "expiry":         "غير محدد",
        "udemy_url":      page_url,
        "original_price": "",
    }
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()

        # ── الوصف ──────────────────────────────────────────────
        desc_el = (
            soup.select_one(".course-description") or
            soup.select_one("[class*='description']") or
            soup.select_one(".card-text") or
            soup.select_one("p.lead") or
            soup.select_one("meta[name='description']")
        )
        if desc_el:
            if desc_el.name == "meta":
                details["description"] = desc_el.get("content", "").strip()
            else:
                details["description"] = desc_el.get_text(separator=" ", strip=True)
        if len(details["description"]) > 300:
            details["description"] = details["description"][:297] + "..."

        # ── عدد الكوبونات ──────────────────────────────────────
        coupon_patterns = [
            r"(\d+)\s*(?:coupon|coupons|كوبون)\s*(?:left|remaining|متاح|متبقي)",
            r"(?:left|remaining|متاح|متبقي)[:\s]*(\d+)",
            r"(\d+)\s*/\s*\d+\s*(?:used|remaining|coupon)",
        ]
        for pat in coupon_patterns:
            m = re.search(pat, page_text, re.IGNORECASE)
            if m:
                details["coupon_count"] = m.group(1)
                break
        if details["coupon_count"] == "غير محدد":
            for el in soup.select("[class*='coupon'],[class*='left'],[id*='coupon']"):
                txt = el.get_text(strip=True)
                m = re.search(r"(\d+)", txt)
                if m and any(k in txt.lower() for k in ["left","remaining","coupon","متاح","متبقي"]):
                    details["coupon_count"] = m.group(1)
                    break

        # ── تاريخ الانتهاء ─────────────────────────────────────
        expiry_patterns = [
            r"(?:expire[sd]?|valid until|expiry|انتهاء|صالح حتى)[:\s]*([A-Za-z]+ \d{1,2},? \d{4})",
            r"(?:expire[sd]?|valid until|expiry|انتهاء|صالح حتى)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* \d{4})",
        ]
        for pat in expiry_patterns:
            m = re.search(pat, page_text, re.IGNORECASE)
            if m:
                details["expiry"] = m.group(1).strip()
                break

        # ── السعر الأصلي ───────────────────────────────────────
        price_el = soup.select_one("[class*='price'],[class*='original-price']")
        if price_el:
            m = re.search(r"\$[\d.]+", price_el.get_text())
            if m:
                details["original_price"] = m.group(0)

        # ── رابط Udemy ─────────────────────────────────────────
        udemy_el = soup.select_one("a[href*='udemy.com/course']")
        if udemy_el:
            details["udemy_url"] = udemy_el.get("href", page_url)

    except Exception as e:
        print(f"⚠️ تعذّر جلب تفاصيل: {e}")
    return details


# ========================================
# 🔗 اختصار الروابط
# ========================================
def shorten_url(long_url):
    try:
        api_url = f"https://shrinkme.io/api?api={SHRINKME_API_KEY}&url={long_url}"
        data = requests.get(api_url, timeout=10).json()
        if data.get("status") == "success":
            return data["shortenedUrl"]
    except Exception as e:
        print(f"❌ خطأ اختصار الرابط: {e}")
    return long_url


# ========================================
# 📝 تنسيق رسالة التيليجرام
# ========================================
def format_message(course, details, shortened_url):
    category_emojis = {
        "programming":"💻","development":"💻","design":"🎨","business":"💼",
        "marketing":"📢","data":"📊","finance":"💰","language":"🗣️",
        "it":"🖥️","security":"🔐","photo":"📷","music":"🎵",
        "تطوير":"💻","تصميم":"🎨","بيزنس":"💼",
    }
    emoji = "🎓"
    for key, val in category_emojis.items():
        if key.lower() in course["category"].lower():
            emoji = val
            break

    now = datetime.now().strftime("%d/%m/%Y")

    price_line = (
        f"💰 السعر الأصلي: ~~{details['original_price']}~~ → *مجاناً* 🎉\n"
        if details["original_price"]
        else "💰 السعر: ~~مدفوع~~ → *مجاناً* 🎉\n"
    )

    desc_section = (
        f"\n📖 *عن الكورس:*\n_{details['description']}_\n"
        if details["description"] else ""
    )

    coupon_line = (
        f"🎟️ الكوبونات المتاحة: *{details['coupon_count']} فقط!*"
        if details["coupon_count"] != "غير محدد"
        else "🎟️ الكوبونات: محدودة ⚠️"
    )

    expiry_line = (
        f"⏳ صالح حتى: *{details['expiry']}*"
        if details["expiry"] != "غير محدد"
        else "⏳ الصلاحية: محدودة - اشترك الآن!"
    )

    return f"""🔥 كورس مجاني - {course["source"]}

{emoji} *{course["title"]}*

📂 التصنيف: {course["category"]}
{price_line}{desc_section}
━━━━━━━━━━━━━━━━
{coupon_line}
{expiry_line}
📅 تم النشر: {now}
━━━━━━━━━━━━━━━━

🔗 رابط التسجيل المجاني:
👇👇👇
{shortened_url}

⚡ لا تفوّت الفرصة - الكوبونات تنتهي بسرعة!

🤖 @{TELEGRAM_CHANNEL_ID.replace("@", "")}
"""


# ========================================
# 📤 إرسال على تيليجرام
# ========================================
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }, timeout=10).json()
        if res.get("ok"):
            print("✅ تم النشر بنجاح!")
            return True
        print(f"❌ فشل النشر: {res.get('description')}")
    except Exception as e:
        print(f"❌ خطأ تيليجرام: {e}")
    return False


# ========================================
# 💾 تتبع المنشور
# ========================================
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_posted(urls):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(urls, f)


# ========================================
# 🚀 الوظيفة الرئيسية
# ========================================
def run_bot():
    print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] بدأ البوت...")
    posted_urls = load_posted()

    print("📚 جاري جلب قائمة الكورسات...")
    courses = scrape_course_list(max_courses=15)
    if not courses:
        print("⚠️ مفيش كورسات")
        return

    print(f"✅ لقى {len(courses)} كورس")
    new_count = 0

    for course in courses:
        if course["page_url"] in posted_urls:
            continue

        print(f"\n🔍 {course['title'][:50]}...")

        details = get_course_details(course["page_url"])
        time.sleep(2)

        print(f"   📖 وصف: {'✅' if details['description'] else '❌'}")
        print(f"   🎟️ كوبونات: {details['coupon_count']}")
        print(f"   ⏳ انتهاء:  {details['expiry']}")

        short_url = shorten_url(details["udemy_url"])
        time.sleep(1)

        message = format_message(course, details, short_url)

        if send_to_telegram(message):
            posted_urls.append(course["page_url"])
            save_posted(posted_urls)
            new_count += 1
            time.sleep(5)

        break  # كورس واحد كل دورة

    print(f"\n{'🎉 تم نشر ' + str(new_count) + ' كورس' if new_count else 'ℹ️ كل الكورسات اتنشرت قبل كده'}")


# ========================================
# ⏱️ الجدولة
# ========================================
if __name__ == "__main__":
    print("🤖 بوت الكورسات - النسخة المتطورة!")
    print(f"📡 القناة: {TELEGRAM_CHANNEL_ID}")
    print(f"⏰ كل {POST_INTERVAL_HOURS} ساعات")
    print("━" * 45)

    run_bot()
    schedule.every(POST_INTERVAL_HOURS).hours.do(run_bot)

    print("\n⏳ في انتظار الجدولة التالية...")
    while True:
        schedule.run_pending()
        time.sleep(60)
