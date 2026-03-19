"""
🤖 بوت الكورسات - ينشر أكتر + يجيب رابط Udemy مباشرة
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
POSTED_FILE         = "posted_courses.json"
POST_INTERVAL_HOURS = int(os.environ.get("POST_INTERVAL_HOURS", "3"))
POSTS_PER_RUN       = int(os.environ.get("POSTS_PER_RUN", "5"))  # كام كورس كل دورة

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


# ========================================
# 🎯 جلب رابط Udemy المباشر من الصفحة
# ========================================
def extract_udemy_direct_link(page_url):
    """
    يدخل على صفحة الكورس في الموقع الوسيط
    ويجيب رابط Udemy الحقيقي مع الكوبون مباشرة
    """
    try:
        r    = requests.get(page_url, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")

        # ── طريقة 1: رابط مباشر في الصفحة ─────────────────────
        for a in soup.select("a[href*='udemy.com/course']"):
            href = a.get("href", "")
            if "udemy.com/course" in href:
                return href

        # ── طريقة 2: زر Go to Course / Enroll ─────────────────
        for a in soup.select("a.btn, a.button, a[class*='btn'], a[class*='enroll'], a[class*='coupon']"):
            href = a.get("href", "")
            if "udemy.com" in href:
                return href

        # ── طريقة 3: redirect link ─────────────────────────────
        for a in soup.select("a[href*='go.udemy'], a[href*='click'], a[href*='redirect']"):
            href = a.get("href", "")
            if href:
                # تتبع الـ redirect
                try:
                    r2 = requests.get(href, headers=HEADERS, timeout=10, allow_redirects=True)
                    if "udemy.com/course" in r2.url:
                        return r2.url
                except Exception:
                    pass

        # ── طريقة 4: بحث في الـ JavaScript ───────────────────
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or ""
            m = re.search(r'https://www\.udemy\.com/course/[^"\'\\]+', text)
            if m:
                return m.group(0)

        # ── طريقة 5: meta redirect ─────────────────────────────
        meta = soup.select_one("meta[http-equiv='refresh']")
        if meta:
            content = meta.get("content", "")
            m = re.search(r'url=(.+)', content, re.IGNORECASE)
            if m and "udemy.com" in m.group(1):
                return m.group(1).strip()

    except Exception as e:
        print(f"  ⚠️ extract_udemy: {e}")

    return None  # مرجعش رابط Udemy


# ========================================
# 📚 مصدر 1: discudemy.com (بيحط رابط Udemy مباشرة)
# ========================================
def scrape_discudemy(max_courses=20):
    courses = []
    try:
        for page in range(1, 3):  # صفحتين
            url = f"https://www.discudemy.com/all/{page}"
            r   = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            # discudemy بيستخدم cards
            for card in soup.select(".card, .course-card, article"):
                try:
                    title_el = (card.select_one("h3 a") or card.select_one("h2 a") or
                                card.select_one(".title a") or card.select_one("a"))
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    href  = title_el.get("href", "")
                    if not href.startswith("http"):
                        href = "https://www.discudemy.com" + href
                    cat_el = card.select_one(".badge, .category, .tag")
                    if len(title) > 5:
                        courses.append({
                            "title":    title,
                            "page_url": href,
                            "category": cat_el.get_text(strip=True) if cat_el else "Development",
                            "source":   "Udemy",
                        })
                except Exception:
                    continue
            time.sleep(1)

        print(f"   discudemy: {len(courses)} كورس")
    except Exception as e:
        print(f"   ❌ discudemy: {e}")
    return courses[:max_courses]


# ========================================
# 📚 مصدر 2: udemyfreebies.com
# ========================================
def scrape_udemyfreebies(max_courses=20):
    courses = []
    try:
        for page in range(1, 3):
            url  = f"https://udemyfreebies.com/free-udemy-courses/{page}"
            r    = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            for card in soup.select(".coupon-card, .course-card, .col-md-4, article"):
                try:
                    title_el = (card.select_one("h4 a") or card.select_one("h3 a") or
                                card.select_one("h4") or card.select_one("h3"))
                    link_el  = card.select_one("a[href]")
                    cat_el   = card.select_one(".badge, .category")
                    if not title_el or not link_el:
                        continue
                    title = title_el.get_text(strip=True)
                    href  = link_el["href"]
                    if not href.startswith("http"):
                        href = "https://udemyfreebies.com" + href
                    if len(title) > 5:
                        courses.append({
                            "title":    title,
                            "page_url": href,
                            "category": cat_el.get_text(strip=True) if cat_el else "Development",
                            "source":   "Udemy",
                        })
                except Exception:
                    continue
            time.sleep(1)

        print(f"   udemyfreebies: {len(courses)} كورس")
    except Exception as e:
        print(f"   ❌ udemyfreebies: {e}")
    return courses[:max_courses]


# ========================================
# 📚 مصدر 3: Tutorial Bar (API)
# ========================================
def scrape_tutorialbar(max_courses=20):
    courses = []
    try:
        url = "https://www.tutorialbar.com/all-courses/"
        r   = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        for card in soup.select("article, .post, .course-item"):
            try:
                title_el = card.select_one("h2 a, h3 a, .entry-title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = title_el.get("href", "")
                cat_el = card.select_one(".cat-links a, .category a")
                if len(title) > 5 and href.startswith("http"):
                    courses.append({
                        "title":    title,
                        "page_url": href,
                        "category": cat_el.get_text(strip=True) if cat_el else "Development",
                        "source":   "Udemy",
                    })
            except Exception:
                continue

        print(f"   tutorialbar: {len(courses)} كورس")
    except Exception as e:
        print(f"   ❌ tutorialbar: {e}")
    return courses[:max_courses]


# ========================================
# 📚 جمع الكورسات من كل المصادر
# ========================================
def get_all_courses(max_total=30):
    print("📚 جاري جلب الكورسات...")
    all_courses = []

    for name, fn in [
        ("discudemy",     lambda: scrape_discudemy(20)),
        ("udemyfreebies", lambda: scrape_udemyfreebies(20)),
        ("tutorialbar",   lambda: scrape_tutorialbar(20)),
    ]:
        print(f"  🔍 {name}...")
        try:
            results = fn()
            all_courses.extend(results)
        except Exception as e:
            print(f"  ❌ {name}: {e}")
        time.sleep(1)

    # إزالة التكرار
    seen, unique = set(), []
    for c in all_courses:
        key = c["title"].lower().strip()[:60]
        if key not in seen and len(key) > 5:
            seen.add(key)
            unique.append(c)

    print(f"📦 إجمالي: {len(unique)} كورس فريد")
    return unique[:max_total]


# ========================================
# 🔍 جلب تفاصيل + رابط Udemy مباشر
# ========================================
def get_course_details(page_url):
    details = {
        "description":    "",
        "coupon_count":   "غير محدد",
        "expiry":         "غير محدد",
        "udemy_url":      None,  # هيتملى من extract_udemy_direct_link
        "original_price": "",
    }
    try:
        r    = requests.get(page_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        # ── الوصف ──────────────────────────────────────────────
        for sel in ["meta[name='description']", ".course-description",
                    "[class*='description']", ".entry-content p", "p.lead"]:
            el = soup.select_one(sel)
            if el:
                desc = (el.get("content","") if el.name=="meta"
                        else el.get_text(" ", strip=True))
                if len(desc) > 30:
                    details["description"] = desc[:297]+"..." if len(desc)>300 else desc
                    break

        # ── عدد الكوبونات ──────────────────────────────────────
        for pat in [
            r"(\d+)\s*(?:coupon|coupons)\s*(?:left|remaining)",
            r"(?:left|remaining)[:\s]*(\d+)\s*coupon",
            r"(\d+)\s*of\s*\d+\s*(?:left|remaining)",
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                details["coupon_count"] = m.group(1)
                break

        # ── تاريخ الانتهاء ─────────────────────────────────────
        for pat in [
            r"(?:expire[sd]?|valid until|expiry)[:\s]*([A-Za-z]+ \d{1,2},? \d{4})",
            r"(?:expire[sd]?|valid until)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                details["expiry"] = m.group(1).strip()
                break

        # ── السعر ──────────────────────────────────────────────
        price_el = soup.select_one("[class*='price'],[class*='original']")
        if price_el:
            m = re.search(r"\$[\d.]+", price_el.get_text())
            if m:
                details["original_price"] = m.group(0)

        # ── رابط Udemy المباشر ─────────────────────────────────
        udemy_url = extract_udemy_direct_link(page_url)
        if udemy_url:
            details["udemy_url"] = udemy_url
            print(f"  🎯 رابط Udemy مباشر: {udemy_url[:60]}...")
        else:
            # fallback: أي رابط udemy في الصفحة
            udemy_el = soup.select_one("a[href*='udemy.com']")
            if udemy_el:
                details["udemy_url"] = udemy_el.get("href")
                print(f"  🔗 رابط Udemy fallback")
            else:
                details["udemy_url"] = page_url
                print(f"  ⚠️ مفيش رابط Udemy، هستخدم صفحة الموقع")

    except Exception as e:
        print(f"  ⚠️ تفاصيل: {e}")
        details["udemy_url"] = page_url

    return details


# ========================================
# 🔗 اختصار الروابط
# ========================================
def shorten_url(long_url):
    try:
        r = requests.get(
            f"https://shrinkme.io/api?api={SHRINKME_API_KEY}&url={long_url}",
            timeout=10
        ).json()
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
    emoji = next((v for k,v in emojis.items()
                  if k.lower() in course["category"].lower()), "🎓")

    price  = (f"~~{details['original_price']}~~ → *مجاناً* 🎉"
              if details["original_price"] else "~~مدفوع~~ → *مجاناً* 🎉")
    desc   = (f"\n📖 *عن الكورس:*\n_{details['description']}_\n"
              if details["description"] else "")
    coupon = (f"🎟️ الكوبونات المتاحة: *{details['coupon_count']} فقط!*"
              if details["coupon_count"] != "غير محدد"
              else "🎟️ الكوبونات: محدودة ⚠️")
    expiry = (f"⏳ صالح حتى: *{details['expiry']}*"
              if details["expiry"] != "غير محدد"
              else "⏳ الصلاحية: محدودة — اشترك الآن!")

    # هل الرابط مباشر على Udemy؟
    direct_badge = "✅ *رابط Udemy مباشر*" if details["udemy_url"] and "udemy.com" in details["udemy_url"] else ""

    return f"""🔥 كورس مجاني - {course["source"]}

{emoji} *{course["title"]}*

📂 التصنيف: {course["category"]}
💰 السعر: {price}{desc}
━━━━━━━━━━━━━━━━
{coupon}
{expiry}
{direct_badge}
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
            timeout=10
        ).json()
        if res.get("ok"):
            print("  ✅ نُشر!")
            return True
        print(f"  ❌ فشل: {res.get('description')}")
    except Exception as e:
        print(f"  ❌ تيليجرام: {e}")
    return False


# ========================================
# 💾 تتبع المنشور
# ========================================
def load_posted():
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_posted(urls):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(urls, f)


# ========================================
# 🚀 الوظيفة الرئيسية
# ========================================
def run_bot():
    print(f"\n{'='*55}")
    print(f"⏰ [{datetime.now().strftime('%H:%M:%S')}] دورة جديدة — هينشر {POSTS_PER_RUN} كورسات")
    print(f"{'='*55}")

    posted_urls = load_posted()
    courses     = get_all_courses(max_total=50)

    if not courses:
        print("⚠️ مفيش كورسات من أي مصدر")
        return

    new_count = 0
    for course in courses:
        if new_count >= POSTS_PER_RUN:
            break
        if course["page_url"] in posted_urls:
            continue

        print(f"\n📌 [{new_count+1}/{POSTS_PER_RUN}] {course['title'][:55]}...")

        details   = get_course_details(course["page_url"])
        time.sleep(2)

        short_url = shorten_url(details["udemy_url"])
        time.sleep(1)

        message = format_message(course, details, short_url)

        if send_to_telegram(message):
            posted_urls.append(course["page_url"])
            save_posted(posted_urls)
            new_count += 1
            time.sleep(8)  # استنى 8 ثواني بين كل نشر

    print(f"\n{'🎉 نُشر ' + str(new_count) + ' كورس' if new_count else 'ℹ️ كل الكورسات اتنشرت'}")


# ========================================
# ⏱️ الجدولة
# ========================================
if __name__ == "__main__":
    print("🤖 بوت الكورسات — ينشر أكتر + رابط Udemy مباشر")
    print(f"📡 القناة: {TELEGRAM_CHANNEL_ID}")
    print(f"⏰ كل {POST_INTERVAL_HOURS} ساعات | {POSTS_PER_RUN} كورسات كل مرة")

    run_bot()
    schedule.every(POST_INTERVAL_HOURS).hours.do(run_bot)

    print("\n⏳ في انتظار الجدولة...")
    while True:
        schedule.run_pending()
        time.sleep(60)
