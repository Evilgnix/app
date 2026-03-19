"""
🤖 بوت الكورسات المجانية - نسخة مصلّحة
يستخدم Udemy Coupon API + fallback scrapers
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
# ⚙️ الإعدادات من Environment Variables
# ========================================
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@your_channel")
SHRINKME_API_KEY    = os.environ.get("SHRINKME_API_KEY", "YOUR_KEY")
POSTED_FILE         = "posted_courses.json"
POST_INTERVAL_HOURS = int(os.environ.get("POST_INTERVAL_HOURS", "3"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ========================================
# 📚 مصدر 1: discudemy.com
# ========================================
def scrape_discudemy(max_courses=10):
    courses = []
    try:
        url = "https://www.discudemy.com/all"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # كل كورس في card أو section
        items = soup.select("div.card, article, .section-inner")
        print(f"   discudemy: لقى {len(items)} عنصر")

        for item in items:
            try:
                title_el = (item.select_one("h3") or item.select_one("h2") or
                            item.select_one(".title") or item.select_one("a"))
                link_el  = item.select_one("a[href]")
                if not title_el or not link_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = link_el["href"]
                if not href.startswith("http"):
                    href = "https://www.discudemy.com" + href
                if len(title) < 5:
                    continue
                courses.append({
                    "title": title, "page_url": href,
                    "category": "تطوير", "source": "Udemy"
                })
                if len(courses) >= max_courses:
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"   ❌ discudemy error: {e}")
    return courses


# ========================================
# 📚 مصدر 2: udemyfreebies.com
# ========================================
def scrape_udemyfreebies(max_courses=10):
    courses = []
    try:
        url = "https://udemyfreebies.com/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select(".coupon-card, .course-card, article, .col-md-4")
        print(f"   udemyfreebies: لقى {len(items)} عنصر")

        for item in items:
            try:
                title_el = (item.select_one("h4") or item.select_one("h3") or
                            item.select_one(".title"))
                link_el  = item.select_one("a[href]")
                cat_el   = item.select_one(".badge, .category, .tag")
                if not title_el or not link_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = link_el["href"]
                if not href.startswith("http"):
                    href = "https://udemyfreebies.com" + href
                if len(title) < 5:
                    continue
                courses.append({
                    "title":    title,
                    "page_url": href,
                    "category": cat_el.get_text(strip=True) if cat_el else "تطوير",
                    "source":   "Udemy",
                })
                if len(courses) >= max_courses:
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"   ❌ udemyfreebies error: {e}")
    return courses


# ========================================
# 📚 مصدر 3: coursevania.com (API)
# ========================================
def scrape_coursevania(max_courses=10):
    courses = []
    try:
        url = "https://coursevania.com/wp-json/wp/v2/posts?per_page=10&_fields=title,link,categories"
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        print(f"   coursevania: لقى {len(data)} كورس")
        for item in data:
            try:
                title = item.get("title", {}).get("rendered", "")
                link  = item.get("link", "")
                if title and link:
                    # إزالة HTML tags من العنوان
                    title = re.sub(r"<[^>]+>", "", title).strip()
                    courses.append({
                        "title": title, "page_url": link,
                        "category": "تطوير", "source": "Udemy"
                    })
            except Exception:
                continue
            if len(courses) >= max_courses:
                break
    except Exception as e:
        print(f"   ❌ coursevania error: {e}")
    return courses


# ========================================
# 📚 الدالة الرئيسية لجلب الكورسات
# ========================================
def get_all_courses(max_total=10):
    print("📚 جاري جلب الكورسات من عدة مصادر...")
    all_courses = []

    for scraper_name, scraper_fn in [
        ("discudemy",     lambda: scrape_discudemy(max_total)),
        ("udemyfreebies", lambda: scrape_udemyfreebies(max_total)),
        ("coursevania",   lambda: scrape_coursevania(max_total)),
    ]:
        print(f"  🔍 جاري {scraper_name}...")
        try:
            results = scraper_fn()
            print(f"  ✅ {scraper_name}: {len(results)} كورس")
            all_courses.extend(results)
        except Exception as e:
            print(f"  ❌ {scraper_name} فشل: {e}")
        time.sleep(1)

    # إزالة التكرار بناءً على العنوان
    seen_titles = set()
    unique = []
    for c in all_courses:
        t = c["title"].lower().strip()
        if t not in seen_titles and len(t) > 5:
            seen_titles.add(t)
            unique.append(c)

    print(f"\n📦 إجمالي كورسات فريدة: {len(unique)}")
    return unique[:max_total]


# ========================================
# 🔍 جلب تفاصيل الكورس
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
        r    = requests.get(page_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        # ── الوصف ──────────────────────────────────────────────
        for sel in ["meta[name='description']", ".course-description",
                    "[class*='description']", ".card-text", "p.lead"]:
            el = soup.select_one(sel)
            if el:
                desc = el.get("content", "") if el.name == "meta" else el.get_text(" ", strip=True)
                if len(desc) > 30:
                    details["description"] = desc[:297] + "..." if len(desc) > 300 else desc
                    break

        # ── عدد الكوبونات ──────────────────────────────────────
        for pat in [
            r"(\d+)\s*(?:coupon|coupons)\s*(?:left|remaining)",
            r"(?:left|remaining)[:\s]*(\d+)",
            r"(\d+)\s*/\s*\d+\s*(?:used|remaining)",
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
        print(f"  ⚠️ تفاصيل: {e}")
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
        "تطوير":"💻","تصميم":"🎨","بيزنس":"💼",
    }
    emoji = next((v for k, v in emojis.items()
                  if k.lower() in course["category"].lower()), "🎓")

    price  = (f"~~{details['original_price']}~~ → *مجاناً* 🎉"
              if details["original_price"] else "~~مدفوع~~ → *مجاناً* 🎉")
    desc   = f"\n📖 *عن الكورس:*\n_{details['description']}_\n" if details["description"] else ""
    coupon = (f"🎟️ الكوبونات المتاحة: *{details['coupon_count']} فقط!*"
              if details["coupon_count"] != "غير محدد" else "🎟️ الكوبونات: محدودة ⚠️")
    expiry = (f"⏳ صالح حتى: *{details['expiry']}*"
              if details["expiry"] != "غير محدد" else "⏳ الصلاحية: محدودة — اشترك الآن!")

    return f"""🔥 كورس مجاني - {course["source"]}

{emoji} *{course["title"]}*

📂 التصنيف: {course["category"]}
💰 السعر: {price}{desc}
━━━━━━━━━━━━━━━━
{coupon}
{expiry}
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
            print("  ✅ نُشر بنجاح!")
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
    print(f"\n{'='*50}")
    print(f"⏰ [{datetime.now().strftime('%H:%M:%S')}] دورة جديدة")
    print(f"{'='*50}")

    posted_urls = load_posted()
    courses     = get_all_courses(max_total=15)

    if not courses:
        print("⚠️ مفيش كورسات من أي مصدر — هحاول تاني بعد كده")
        return

    new_count = 0
    for course in courses:
        if course["page_url"] in posted_urls:
            continue

        print(f"\n📌 {course['title'][:55]}...")
        details   = get_course_details(course["page_url"])
        time.sleep(2)

        short_url = shorten_url(details["udemy_url"])
        time.sleep(1)

        message   = format_message(course, details, short_url)

        if send_to_telegram(message):
            posted_urls.append(course["page_url"])
            save_posted(posted_urls)
            new_count += 1
            time.sleep(5)
        break  # كورس واحد كل دورة

    print(f"\n{'🎉 نُشر ' + str(new_count) + ' كورس' if new_count else 'ℹ️ كل الكورسات اتنشرت من قبل'}")


# ========================================
# ⏱️ الجدولة
# ========================================
if __name__ == "__main__":
    print("🤖 بوت الكورسات — النسخة المصلّحة")
    print(f"📡 القناة: {TELEGRAM_CHANNEL_ID}")
    print(f"⏰ كل {POST_INTERVAL_HOURS} ساعات")

    run_bot()
    schedule.every(POST_INTERVAL_HOURS).hours.do(run_bot)

    print("\n⏳ في انتظار الجدولة...")
    while True:
        schedule.run_pending()
        time.sleep(60)
