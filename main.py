import os
import asyncio
import feedparser
import google.generativeai as genai
from flask import Flask, request
from pymongo import MongoClient
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# --- الإعدادات ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "@Axia_Tech"
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI = os.getenv("MONGO_URI") 

app = Flask(__name__)

# --- إعداد MongoDB مع إضافة معايير استقرار الاتصال ---
# أضفنا serverSelectionTimeoutMS لتجنب تعليق الكود لفترة طويلة إذا فشل الاتصال
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['AxiaTechDB']
collection = db['posted_news']

# إعداد Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def is_posted(link):
    try:
        return collection.find_one({"link": link}) is not None
    except Exception as e:
        print(f"MongoDB Lookup Error: {e}")
        return True # نرجع True في حال الخطأ لتجنب تكرار النشر العشوائي

def save_link(link):
    try:
        collection.insert_one({"link": link})
    except Exception as e:
        print(f"MongoDB Insert Error: {e}")

async def process_news_with_gemini(title, summary):
    # تنظيف النص من أي وسوم HTML قد تعطل Gemini أو Telegram
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
    response = model.generate_content(prompt)
    return response.text

async def fetch_and_post_news():
    feeds = [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://openai.com/news/rss.xml",
        "https://www.engadget.com/rss.xml"
    ]
    
    # استخدام session واحدة لتسريع عملية الإرسال
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
                    # تأخير بسيط لتجنب الـ Spam Detection من تليجرام
                    await asyncio.sleep(2) 
                except Exception as e:
                    print(f"Error in processing entry: {e}")

@app.route('/')
def home():
    return "Axia Tech Bot is Online!"

@app.route('/fetch')
def manual_fetch():
    try:
        # استخدام الطريقة الصحيحة لتشغيل asyncio داخل Flask
        asyncio.run(fetch_and_post_news())
        return "Fetch cycle completed successfully!"
    except Exception as e:
        print(f"Critical Error in manual_fetch: {e}")
        return f"Error: {e}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)