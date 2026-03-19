"""
🤖 بوت الكورسات - حفظ دائم على GitHub
"""

import requests
from bs4 import BeautifulSoup
import time
import schedule
import json
import os
import re
import base64
from datetime import datetime

# ========================================
# ⚙️ الإعدادات
# ========================================
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
SHRINKME_API_KEY    = os.environ.get("SHRINKME_API_KEY", "")
GITHUB_TOKEN        = os.environ.get("GITHUB_TOKEN", "")       # Personal Access Token
GITHUB_REPO         = os.environ.get("GITHUB_REPO", "")        # مثلاً: mabrouk/courses-bot
GITHUB_FILE         = "posted_courses.json"                     # اسم الملف في الـ repo
POSTS_PER_RUN       = int(os.environ.get("POSTS_PER_RUN", "5"))
POST_INTERVAL_HOURS = int(os.environ.get("POST_INTERVAL_HOURS", "3"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

GITHUB_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


# ========================================
# ☁️ حفظ وجلب من GitHub
# ========================================
def load_posted():
    """يجيب الملف من GitHub"""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        r   = requests.get(url, headers=GITHUB_HEADERS, timeout=10)

        if r.status_code == 404:
            # الملف مش موجود لسه — هيتعمل أول نشر
            print("  📄 أول مرة: الملف مش موجود على GitHub")
            return {"titles": [], "urls": [], "sha": None}

        data    = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        posted  = json.loads(content)
        posted["sha"] = data["sha"]  # محتاجينه للـ update
        print(f"  ☁️ محمّل من GitHub: {len(posted.get('titles', []))} كورس منشور")
        return posted

    except Exception as e:
        print(f"  ⚠️ load_posted: {e}")
        return {"titles": [], "urls": [], "sha": None}


def save_posted(data):
    """يحفظ الملف على GitHub"""
    try:
        sha = data.pop("sha", None)

        # احتفظ بآخر 2000 فقط
        data["titles"] = data.get("titles", [])[-2000:]
        data["urls"]   = data.get("urls", [])[-2000:]

        content_bytes   = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        content_base64  = base64.b64encode(content_bytes).decode("utf-8")

        url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        payload = {
            "message": f"update posted courses {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": content_base64,
        }
        if sha:
            payload["sha"] = sha  # لازم للـ update

        r = requests.put(url, headers=GITHUB_HEADERS, json=payload, timeout=15)

        if r.status_code in [200, 201]:
            new_sha       = r.json()["content"]["sha"]
            data["sha"]   = new_sha
            print(f"  ☁️ محفوظ على GitHub ✅")
        else:
            print(f"  ❌ GitHub save error: {r.status_code} {r.text[:100]}")

        data["sha"] = sha  # رجّع الـ sha للـ dict

    except Exception as e:
        print(f"  ⚠️ save_posted: {e}")


def clean_key(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())[:50]

def is_posted(data, title, url):
    return clean_key(title) in data.get("titles", []) or url in data.get("urls", [])

def mark_posted(data, title, url):
    key = clean_key(title)
    if key not in data["titles"]: data["titles"].append(key)
    if url not in data["urls"]:   data["urls"].append(url)


# ========================================
# 📚 مصدر 1: discudemy.com
# ========================================
def scrape_discudemy(max_courses=20):
    courses = []
    try:
        for page in [1, 2]:
            r    = requests.get(f"https://www.discudemy.com/all/{page}", headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select(".card, article"):
                try:
                    a = (card.select_one("h3 a") or card.select_one("h2 a") or card.select_one("a"))
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
            r    = requests.get(f"https://udemyfreebies.com/free-udemy-courses/{page}", headers=HEADERS, timeout=15)
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
        r    = requests.get("https://www.tutorialbar.com/all-courses/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("article,.post"):
            try:
                a = card.select_one("h2 a,h3 a,.entry-title a")
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
# 📚 جمع + إزالة التكرار
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
        try: all_courses.extend(fn())
        except Exception as e: print(f"  ❌ {name}: {e}")
        time.sleep(1)

    seen, unique = set(), []
    for c in all_courses:
        key = clean_key(c["title"])
        if key not in seen and len(key) > 5:
            seen.add(key)
            unique.append(c)
    print(f"📦 {len(unique)} كورس فريد")
    return unique


# ========================================
# 🎯 رابط Udemy المباشر
# ========================================
def get_udemy_direct_link(page_url):
    try:
        r    = requests.get(page_url, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a[href*='udemy.com/course']"):
            return a["href"]
        for a in soup.select("a.btn,a.button,a[class*='enroll'],a[class*='coupon']"):
            href = a.get("href","")
            if "udemy.com" in href: return href
        for script in soup.find_all("script"):
            t = script.string or ""
            m = re.search(r'https://(?:www\.)?udemy\.com/course/[^"\'\\?\s]+', t)
            if m: return m.group(0)
    except Exception as e:
        print(f"  ⚠️ udemy_link: {e}")
    return None


# ========================================
# 🔍 تفاصيل الكورس
# ========================================
def get_course_details(page_url):
    details = {"description":"","coupon_count":"غير محدد",
               "expiry":"غير محدد","udemy_url":page_url,"original_price":""}
    try:
        r    = requests.get(page_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        for sel in ["meta[name='description']",".course-description","[class*='description']","p.lead"]:
            el = soup.select_one(sel)
            if el:
                desc = el.get("content","") if el.name=="meta" else el.get_text(" ",strip=True)
                if len(desc) > 30:
                    details["description"] = desc[:297]+"..." if len(desc)>300 else desc
                    break

        for pat in [r"(\d+)\s*(?:coupon|coupons)\s*(?:left|remaining)",
                    r"(?:left|remaining)[:\s]*(\d+)\s*coupon"]:
            m = re.search(pat, text, re.IGNORECASE)
            if m: details["coupon_count"] = m.group(1); break

        for pat in [r"(?:expire[sd]?|valid until)[:\s]*([A-Za-z]+ \d{1,2},? \d{4})",
                    r"(?:expire[sd]?|valid until)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"]:
            m = re.search(pat, text, re.IGNORECASE)
            if m: details["expiry"] = m.group(1).strip(); break

        price_el = soup.select_one("[class*='price'],[class*='original']")
        if price_el:
            m = re.search(r"\$[\d.]+", price_el.get_text())
            if m: details["original_price"] = m.group(0)

        udemy = get_udemy_direct_link(page_url)
        if udemy:
            details["udemy_url"] = udemy
            print(f"  🎯 Udemy مباشر ✅")
        else:
            fb = soup.select_one("a[href*='udemy.com']")
            if fb: details["udemy_url"] = fb["href"]

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
    direct = "✅ رابط Udemy مباشر" if "udemy.com" in details.get("udemy_url","") else ""

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
            save_posted(posted)
            new_count += 1
            time.sleep(8)

    print(f"\n{'🎉 نُشر ' + str(new_count) + ' كورس جديد' if new_count else 'ℹ️ كل الكورسات اتنشرت من قبل'}")


# ========================================
# ⏱️ الجدولة
# ========================================
if __name__ == "__main__":
    print("🤖 بوت الكورسات — حفظ دائم على GitHub ☁️")
    print(f"📡 القناة: {TELEGRAM_CHANNEL_ID}")
    print(f"⏰ كل {POST_INTERVAL_HOURS} ساعات | {POSTS_PER_RUN} كورسات/دورة")

    run_bot()
    schedule.every(POST_INTERVAL_HOURS).hours.do(run_bot)

    print("\n⏳ في انتظار الجدولة...")
    while True:
        schedule.run_pending()
        time.sleep(60)
