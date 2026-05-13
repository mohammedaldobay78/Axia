import os
import asyncio
import feedparser
# استيراد المكتبة الجديدة
from google import genai
from flask import Flask, request
from pymongo import MongoClient
from telegram import Update, Bot

# --- الإعدادات ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "@Axia_Tech"
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI = os.getenv("MONGO_URI") 

app = Flask(__name__)

# --- إعداد MongoDB ---
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['AxiaTechDB']
collection = db['posted_news']

# --- إعداد Gemini بالمكتبة الجديدة ---
# يتم تمرير مفتاح الواجهة البرمجية (API Key) مباشرة للعميل (Client)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3-flash-preview"

def is_posted(link):
    try:
        return collection.find_one({"link": link}) is not None
    except Exception as e:
        print(f"MongoDB Lookup Error: {e}")
        return True

def save_link(link):
    try:
        collection.insert_one({"link": link})
    except Exception as e:
        print(f"MongoDB Insert Error: {e}")

async def process_news_with_gemini(title, summary):
    clean_summary = summary.replace('<p>', '').replace('</p>', '').strip()
    
    prompt = f"""
    قم بترجمة وتلخيص الخبر التالي للغة العربية بأسلوب تقني شيق وقوي:
    العنوان: {title}
    التفاصيل: {clean_summary}
    
    المطلوب:
    1. صياغة الخبر بأسلوب مناسب لقنوات تليجرام (استخدم الإيموجي).
    2. وضع هاشتاجات ذكية داخل النص (مثال: #جوجل، #AI).
    3. في النهاية، أضف هاشتاجات التصنيف: #تقنية #أخبار_التقنية #Axia_Tech.
    """
    
    # استدعاء Gemini باستخدام الطريقة الجديدة
    response = gemini_client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return response.text

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
        for entry in feed.entries[:3]:
            if not is_posted(entry.link):
                try:
                    formatted_news = await process_news_with_gemini(entry.title, entry.summary)
                    final_text = f"{formatted_news}\n\n🔗 المصدر: {entry.link}"
                    
                    await bot.send_message(chat_id=CHANNEL_ID, text=final_text)
                    save_link(entry.link)
                    print(f"Success: {entry.title}")
                    await asyncio.sleep(2) 
                except Exception as e:
                    print(f"Error in processing entry: {e}")

@app.route('/')
def home():
    return "Axia Tech Bot is Online!"

@app.route('/fetch')
def manual_fetch():
    try:
        asyncio.run(fetch_and_post_news())
        return "Fetch cycle completed successfully!"
    except Exception as e:
        print(f"Critical Error in manual_fetch: {e}")
        return f"Error: {e}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)