"""
🤖 بوت الكورسات - نسخة مصلّحة
إصلاح: تكرار الكورسات + حفظ دائم على Railway
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
# ⚙️ الإعدادات
# ========================================
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@your_channel")
SHRINKME_API_KEY    = os.environ.get("SHRINKME_API_KEY", "YOUR_KEY")
POSTS_PER_RUN       = int(os.environ.get("POSTS_PER_RUN", "5"))
POST_INTERVAL_HOURS = int(os.environ.get("POST_INTERVAL_HOURS", "3"))

# ✅ مسار ثابت على Railway مش بيتمسحش
POSTED_FILE = "/app/posted_courses.json"
# لو مش Railway استخدم مجلد الكود
if not os.path.exists("/app"):
    POSTED_FILE = "posted_courses.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


# ========================================
# 💾 تتبع المنشور بالعنوان مش الـ URL
# ========================================
def load_posted():
    """يرجع dict فيه titles و urls"""
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # دعم النسخ القديمة (list)
                if isinstance(data, list):
                    return {"titles": [], "urls": data}
                return data
    except Exception:
        pass
    return {"titles": [], "urls": []}

def save_posted(data):
    try:
        os.makedirs(os.path.dirname(POSTED_FILE), exist_ok=True) if os.path.dirname(POSTED_FILE) else None
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️ save_posted: {e}")

def is_posted(posted_data, title, url):
    """يتحقق لو الكورس اتنشر قبل كده بالعنوان أو الـ URL"""
    clean_title = clean_key(title)
    return (clean_title in posted_data["titles"] or
            url in posted_data["urls"])

def mark_posted(posted_data, title, url):
    posted_data["titles"].append(clean_key(title))
    posted_data["urls"].append(url)
    # احتفظ بآخر 500 فقط
    posted_data["titles"] = posted_data["titles"][-500:]
    posted_data["urls"]   = posted_data["urls"][-500:]
    save_posted(posted_data)

def clean_key(text):
    """ينظف العنوان عشان يكون مفتاح موحّد"""
    return re.sub(r'[^a-z0-9]', '', text.lower())[:50]


# ========================================
# 📚 مصدر 1: discudemy.com
# ========================================
def scrape_discudemy(max_courses=20):
    courses = []
    try:
        for page in [1, 2]:
            url  = f"https://www.discudemy.com/all/{page}"
            r    = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select(".card, article"):
                try:
                    a = (card.select_one("h3 a") or card.select_one("h2 a") or
                         card.select_one("a.title") or card.select_one("a"))
                    if not a: continue
                    title = a.get_text(strip=True)
                    href  = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://www.discudemy.com" + href
                    cat = card.select_one(".badge,.category")
                    if len(title) > 8:
                        courses.append({"title":title,"page_url":href,
                            "category": cat.get_text(strip=True) if cat else "Development",
                            "source":"Udemy"})
                except Exception: continue
            time.sleep(1)
        print(f"   discudemy: {len(courses)}")
    except Exception as e:
        print(f"   ❌ discudemy: {e}")
    return courses[:max_courses]


# ========================================
# 📚 مصدر 2: udemyfreebies.com
# ========================================
def scrape_udemyfreebies(max_courses=20):
    courses = []
    try:
        for page in [1, 2]:
            url  = f"https://udemyfreebies.com/free-udemy-courses/{page}"
            r    = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select(".coupon-card,.course-card,.col-md-4,article"):
                try:
                    title_el = (card.select_one("h4 a") or card.select_one("h3 a") or
                                card.select_one("h4") or card.select_one("h3"))
                    link_el  = card.select_one("a[href]")
                    if not title_el or not link_el: continue
                    title = title_el.get_text(strip=True)
                    href  = link_el["href"]
                    if not href.startswith("http"):
                        href = "https://udemyfreebies.com" + href
                    cat = card.select_one(".badge,.category")
                    if len(title) > 8:
                        courses.append({"title":title,"page_url":href,
                            "category": cat.get_text(strip=True) if cat else "Development",
                            "source":"Udemy"})
                except Exception: continue
            time.sleep(1)
        print(f"   udemyfreebies: {len(courses)}")
    except Exception as e:
        print(f"   ❌ udemyfreebies: {e}")
    return courses[:max_courses]


# ========================================
# 📚 مصدر 3: tutorialbar.com
# ========================================
def scrape_tutorialbar(max_courses=20):
    courses = []
    try:
        url  = "https://www.tutorialbar.com/all-courses/"
        r    = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("article,.post"):
            try:
                a = card.select_one("h2 a, h3 a, .entry-title a")
                if not a: continue
                title = a.get_text(strip=True)
                href  = a.get("href","")
                cat   = card.select_one(".cat-links a")
                if len(title) > 8 and href.startswith("http"):
                    courses.append({"title":title,"page_url":href,
                        "category": cat.get_text(strip=True) if cat else "Development",
                        "source":"Udemy"})
            except Exception: continue
        print(f"   tutorialbar: {len(courses)}")
    except Exception as e:
        print(f"   ❌ tutorialbar: {e}")
    return courses[:max_courses]


# ========================================
# 📚 جمع + إزالة التكرار بالعنوان
# ========================================
def get_all_courses():
    print("📚 جاري جلب الكورسات...")
    all_courses = []

    for name, fn in [
        ("discudemy",     lambda: scrape_discudemy(20)),
        ("udemyfreebies", lambda: scrape_udemyfreebies(20)),
        ("tutorialbar",   lambda: scrape_tutorialbar(20)),
    ]:
        print(f"  🔍 {name}...")
        try:
            all_courses.extend(fn())
        except Exception as e:
            print(f"  ❌ {name}: {e}")
        time.sleep(1)

    # ✅ إزالة التكرار بالعنوان (مش الـ URL)
    seen, unique = set(), []
    for c in all_courses:
        key = clean_key(c["title"])
        if key not in seen and len(key) > 5:
            seen.add(key)
            unique.append(c)

    print(f"📦 {len(unique)} كورس فريد")
    return unique


# ========================================
# 🎯 جلب رابط Udemy المباشر
# ========================================
def get_udemy_direct_link(page_url):
    """يجيب رابط Udemy الحقيقي مع الكوبون"""
    try:
        r    = requests.get(page_url, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")

        # طريقة 1: رابط مباشر في الصفحة
        for a in soup.select("a[href*='udemy.com/course']"):
            return a["href"]

        # طريقة 2: أزرار التسجيل
        for a in soup.select("a.btn,a.button,a[class*='enroll'],a[class*='coupon'],a[class*='get']"):
            href = a.get("href","")
            if "udemy.com" in href:
                return href

        # طريقة 3: في الـ JavaScript
        for script in soup.find_all("script"):
            t = script.string or ""
            m = re.search(r'https://(?:www\.)?udemy\.com/course/[^"\'\\?\s]+\?couponCode=[^"\'\\?\s]+', t)
            if m: return m.group(0)
            m = re.search(r'https://(?:www\.)?udemy\.com/course/[^"\'\\?\s]+', t)
            if m: return m.group(0)

        # طريقة 4: تتبع redirect
        for a in soup.select("a[href*='redirect'],a[href*='go'],a[href*='click']"):
            href = a.get("href","")
            if href and "udemy" not in href:
                try:
                    r2 = requests.get(href, headers=HEADERS, timeout=8, allow_redirects=True)
                    if "udemy.com/course" in r2.url:
                        return r2.url
                except Exception: pass

    except Exception as e:
        print(f"  ⚠️ udemy_link: {e}")
    return None


# ========================================
# 🔍 تفاصيل الكورس
# ========================================
def get_course_details(page_url):
    details = {
        "description": "", "coupon_count": "غير محدد",
        "expiry": "غير محدد", "udemy_url": page_url, "original_price": "",
    }
    try:
        r    = requests.get(page_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        # الوصف
        for sel in ["meta[name='description']",".course-description","[class*='description']","p.lead"]:
            el = soup.select_one(sel)
            if el:
                desc = el.get("content","") if el.name=="meta" else el.get_text(" ",strip=True)
                if len(desc) > 30:
                    details["description"] = desc[:297]+"..." if len(desc)>300 else desc
                    break

        # الكوبونات
        for pat in [r"(\d+)\s*(?:coupon|coupons)\s*(?:left|remaining)",
                    r"(?:left|remaining)[:\s]*(\d+)\s*coupon"]:
            m = re.search(pat, text, re.IGNORECASE)
            if m: details["coupon_count"] = m.group(1); break

        # الانتهاء
        for pat in [r"(?:expire[sd]?|valid until)[:\s]*([A-Za-z]+ \d{1,2},? \d{4})",
                    r"(?:expire[sd]?|valid until)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"]:
            m = re.search(pat, text, re.IGNORECASE)
            if m: details["expiry"] = m.group(1).strip(); break

        # السعر
        price_el = soup.select_one("[class*='price'],[class*='original']")
        if price_el:
            m = re.search(r"\$[\d.]+", price_el.get_text())
            if m: details["original_price"] = m.group(0)

        # رابط Udemy المباشر
        udemy = get_udemy_direct_link(page_url)
        if udemy:
            details["udemy_url"] = udemy
            print(f"  🎯 Udemy مباشر ✅")
        else:
            fallback = soup.select_one("a[href*='udemy.com']")
            if fallback:
                details["udemy_url"] = fallback["href"]
                print(f"  🔗 Udemy fallback")
            else:
                print(f"  ⚠️ مفيش رابط Udemy")

    except Exception as e:
        print(f"  ⚠️ details: {e}")
    return details


# ========================================
# 🔗 اختصار الروابط
# ========================================
def shorten_url(long_url):
    try:
        r = requests.get(
            f"https://shrinkme.io/api?api={SHRINKME_API_KEY}&url={long_url}",
            timeout=10).json()
        if r.get("status") == "success":
            return r["shortenedUrl"]
    except Exception as e:
        print(f"  ❌ اختصار: {e}")
    return long_url


# ========================================
# 📝 تنسيق الرسالة
# ========================================
def format_message(course, details, short_url):
    emojis = {
        "programming":"💻","development":"💻","design":"🎨","business":"💼",
        "marketing":"📢","data":"📊","finance":"💰","it":"🖥️","security":"🔐",
        "photography":"📷","music":"🎵","health":"💪","teaching":"📚",
    }
    emoji  = next((v for k,v in emojis.items() if k.lower() in course["category"].lower()), "🎓")
    price  = f"~~{details['original_price']}~~ → *مجاناً* 🎉" if details["original_price"] else "~~مدفوع~~ → *مجاناً* 🎉"
    desc   = f"\n📖 *عن الكورس:*\n_{details['description']}_\n" if details["description"] else ""
    coupon = f"🎟️ متاح: *{details['coupon_count']} كوبون فقط!*" if details["coupon_count"] != "غير محدد" else "🎟️ الكوبونات: محدودة ⚠️"
    expiry = f"⏳ صالح حتى: *{details['expiry']}*" if details["expiry"] != "غير محدد" else "⏳ الصلاحية محدودة — اشترك الآن!"
    direct = "✅ رابط Udemy مباشر" if details["udemy_url"] and "udemy.com" in details["udemy_url"] else ""

    return f"""🔥 كورس مجاني - {course["source"]}

{emoji} *{course["title"]}*

📂 التصنيف: {course["category"]}
💰 السعر: {price}{desc}
━━━━━━━━━━━━━━━━
{coupon}
{expiry}
{direct}
📅 {datetime.now().strftime("%d/%m/%Y")}
━━━━━━━━━━━━━━━━

🔗 رابط التسجيل المجاني:
👇👇👇
{short_url}

⚡ لا تفوّت الفرصة!

🤖 {TELEGRAM_CHANNEL_ID}
"""


# ========================================
# 📤 إرسال على تيليجرام
# ========================================
def send_to_telegram(message):
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL_ID, "text": message,
                  "parse_mode": "Markdown", "disable_web_page_preview": False},
            timeout=10).json()
        if res.get("ok"):
            print("  ✅ نُشر!")
            return True
        print(f"  ❌ فشل: {res.get('description')}")
    except Exception as e:
        print(f"  ❌ تيليجرام: {e}")
    return False


# ========================================
# 🚀 الوظيفة الرئيسية
# ========================================
def run_bot():
    print(f"\n{'='*55}")
    print(f"⏰ [{datetime.now().strftime('%H:%M:%S')}] دورة جديدة — هينشر {POSTS_PER_RUN} كورسات")
    print(f"{'='*55}")

    posted    = load_posted()
    courses   = get_all_courses()
    new_count = 0

    if not courses:
        print("⚠️ مفيش كورسات")
        return

    for course in courses:
        if new_count >= POSTS_PER_RUN:
            break

        # ✅ تحقق بالعنوان والـ URL معًا
        if is_posted(posted, course["title"], course["page_url"]):
            continue

        print(f"\n📌 [{new_count+1}/{POSTS_PER_RUN}] {course['title'][:55]}...")

        details   = get_course_details(course["page_url"])
        time.sleep(2)
        short_url = shorten_url(details["udemy_url"])
        time.sleep(1)
        message   = format_message(course, details, short_url)

        if send_to_telegram(message):
            mark_posted(posted, course["title"], course["page_url"])
            new_count += 1
            time.sleep(8)

    print(f"\n{'🎉 نُشر ' + str(new_count) + ' كورس جديد' if new_count else 'ℹ️ كل الكورسات اتنشرت من قبل'}")


# ========================================
# ⏱️ الجدولة
# ========================================
if __name__ == "__main__":
    print("🤖 بوت الكورسات — نسخة مصلّحة")
    print(f"📡 القناة: {TELEGRAM_CHANNEL_ID}")
    print(f"⏰ كل {POST_INTERVAL_HOURS} ساعات | {POSTS_PER_RUN} كورسات/دورة")

    run_bot()
    schedule.every(POST_INTERVAL_HOURS).hours.do(run_bot)

    print("\n⏳ في انتظار الجدولة...")
    while True:
        schedule.run_pending()
        time.sleep(60)
