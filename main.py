import os
import asyncio
import feedparser
from google import genai
from flask import Flask, request
from pymongo import MongoClient
from telegram import Update, Bot

# --- الإعدادات ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "@Axia_Tech"
MONGO_URI = os.getenv("MONGO_URI") 

app = Flask(__name__)

# --- إعداد MongoDB ---
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['AxiaTechDB']
collection = db['posted_news']

# --- إعداد Gemini ---
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3-flash-preview"

def is_posted(link):
    try:
        return collection.find_one({"link": link}) is not None
    except Exception as e:
        print(f"MongoDB Lookup Error: {e}")
        return True

def save_link(link, title):
    try:
        # نحفظ العنوان أيضاً للمقارنة لاحقاً من قبل Gemini
        collection.insert_one({"link": link, "title": title})
    except Exception as e:
        print(f"MongoDB Insert Error: {e}")

def get_recent_titles():
    """جلب آخر 10 عناوين نُشرت للمقارنة بها ومنع التكرار المحتوي"""
    try:
        titles = list(collection.find({}, {"title": 1}).sort("_id", -1).limit(10))
        return [t.get('title', '') for t in titles if t.get('title')]
    except:
        return []

async def process_news_with_gemini(title, summary):
    clean_summary = summary.replace('<p>', '').replace('</p>', '').strip()
    recent_titles = get_recent_titles()
    titles_context = "\n".join([f"- {t}" for t in recent_titles])

    prompt = f"""
    أنت محرر تقني ذكي. مهمتك هي معالجة الخبر التالي لقناة تليجرام @Axia_Tech.
    
    عناوين الأخبار التي نُشرت مؤخراً (ممنوع تكرار محتواها):
    {titles_context}

    الخبر الجديد المراد معالجته:
    العنوان: {title}
    التفاصيل: {clean_summary}

    المطلوب (شروط صارمة):
    1. إذا كان هذا الخبر يتحدث عن نفس موضوع أو حدث مذكور في "العناوين المنشورة مؤخراً" أعلاه، رد بكلمة "SKIP" فقط.
    2. إذا كان الخبر جديداً، صغه بالعربية بأسلوب شيق وقوي.
    3. ابدأ بالخبر مباشرة ولا تضع أي مقدمات مثل "إليك التلخيص".
    4. ممنوع استخدام النجوم (**) نهائياً في النص.
    5. استخدم الإيموجي والهاشتاجات الذكية (مثل #ذكاء_اصطناعي، #آيفون).
    6. في النهاية، أضف الهاشتاجات: #تقنية #أخبار_التقنية #Axia_Tech.
    """
    
    response = gemini_client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    
    text = response.text.strip()
    
    # تنظيف إضافي لإزالة النجوم والمقدمات
    text = text.replace('**', '')
    prefixes = ["إليك صياغة", "إليك الخبر", "صياغة الخبر", "إليك التلخيص", "إليك المخلص"]
    for prefix in prefixes:
        if text.startswith(prefix):
            lines = text.split('\n')
            text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else text
            
    return text

async def fetch_and_post_news():
    feeds = [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://openai.com/news/rss.xml",
        "https://www.engadget.com/rss.xml"
    ]
    
    bot = Bot(token=TELEGRAM_TOKEN)
    
    for url in feeds:
        print(f"Checking feed: {url}")
        feed = feedparser.parse(url)
        
        # جلب خبر واحد فقط من كل مصدر لضمان التنوع وعدم الإزعاج
        for entry in feed.entries[:1]: 
            if not is_posted(entry.link):
                try:
                    formatted_news = await process_news_with_gemini(entry.title, entry.summary)
                    
                    # إذا قرر Gemini أن الخبر مكرر محتوياً
                    if "SKIP" in formatted_news.upper():
                        print(f"Skipping duplicate content: {entry.title}")
                        save_link(entry.link, entry.title) # نحفظ الرابط لكي لا يمر عليه مجدداً
                        continue
                    
                    final_text = f"{formatted_news}\n\n🔗 المصدر: {entry.link}"
                    
                    await bot.send_message(chat_id=CHANNEL_ID, text=final_text)
                    save_link(entry.link, entry.title)
                    print(f"Success post: {entry.title}")
                    
                    await asyncio.sleep(2) # تأخير بسيط بين الرسائل
                except Exception as e:
                    print(f"Error in processing entry: {e}")

@app.route('/')
def home():
    return "Axia Tech Bot is Online and Smart!"

@app.route('/fetch')
def manual_fetch():
    try:
        asyncio.run(fetch_and_post_news())
        return "Fetch cycle completed! Duplicates filtered."
    except Exception as e:
        print(f"Critical Error: {e}")
        return f"Error: {e}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)