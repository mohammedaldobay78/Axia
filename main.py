import os
import asyncio
import feedparser
import google.generativeai as genai
from flask import Flask, request
from pymongo import MongoClient
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# --- الإعدادات (تأكد من إضافتها في Environment Variables على Render) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "@Axia_Tech"
# تحويل ADMIN_ID إلى رقم صحيح (int) لأن الـ ID في تليجرام رقمي
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
# رابط MongoDB من الصورة image_73203a.png
MONGO_URI = os.getenv("MONGO_URI") 

# إعداد Flask (مطلوب لاستقبال طلبات Webhook و Cron-job)
app = Flask(__name__)

# إعداد قاعدة البيانات MongoDB
client = MongoClient(MONGO_URI)
db = client['AxiaTechDB']  # اسم قاعدة البيانات
collection = db['posted_news']  # اسم الجدول/المجموعة

# إعداد Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# دالة التأكد من عدم التكرار (باستخدام MongoDB)
def is_posted(link):
    return collection.find_one({"link": link}) is not None

def save_link(link):
    collection.insert_one({"link": link})

# معالجة الخبر باستخدام Gemini
async def process_news_with_gemini(title, summary):
    prompt = f"""
    قم بترجمة وتلخيص الخبر التالي للغة العربية بأسلوب تقني شيق وقوي:
    العنوان: {title}
    التفاصيل: {summary}
    
    المطلوب:
    1. صياغة الخبر بأسلوب مناسب لقنوات تليجرام (استخدم الإيموجي).
    2. وضع هاشتاجات ذكية داخل النص (مثال: #جوجل، #AI).
    3. في النهاية، أضف هاشتاجات التصنيف: #تقنية #أخبار_التقنية #Axia_Tech.
    """
    response = model.generate_content(prompt)
    return response.text

# الوظيفة الأساسية لجلب الأخبار
async def fetch_and_post_news():
    feeds = [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://openai.com/news/rss.xml",
        "https://www.engadget.com/rss.xml"
    ]
    
    bot = Bot(token=TELEGRAM_TOKEN)
    
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            if not is_posted(entry.link):
                try:
                    formatted_news = await process_news_with_gemini(entry.title, entry.summary)
                    final_text = f"{formatted_news}\n\n🔗 المصدر: {entry.link}"
                    
                    await bot.send_message(chat_id=CHANNEL_ID, text=final_text)
                    save_link(entry.link)
                    print(f"تم نشر خبر جديد: {entry.title}")
                except Exception as e:
                    print(f"Error processing news: {e}")

# مسارات Flask
@app.route('/')
def home():
    return "Bot is alive!"

# هذا الرابط ستستخدمه في Cron-job.org لتشغيل البوت تلقائياً
@app.route('/fetch')
def manual_fetch():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fetch_and_post_news())
    return "Fetch cycle completed!"

if __name__ == '__main__':
    # Render يحدد المنفذ تلقائياً عبر متغير البيئة PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)