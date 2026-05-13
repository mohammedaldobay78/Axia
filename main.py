import logging
import feedparser
import sqlite3
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

# --- الإعدادات ---
TELEGRAM_TOKEN = os.getenv("YOUR_TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("YOUR_GEMINI_API_KEY")
CHANNEL_ID = "@Axia_Tech"  # معرف قناتك
ADMIN_ID = os.getenv("Admin")  # أيدي حسابك الشخصي فقط
WEBHOOK_URL = "https://your-domain.com/webhook"

# إعداد Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# إعداد قاعدة البيانات لمنع التكرار
def init_db():
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS posted_news (link TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

def is_posted(link):
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute("SELECT * FROM posted_news WHERE link=?", (link,))
    result = c.fetchone()
    conn.close()
    return result is not None

def save_link(link):
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute("INSERT INTO posted_news VALUES (?)", (link,))
    conn.commit()
    conn.close()

# معالجة الخبر باستخدام Gemini
async def process_news_with_gemini(title, summary):
    prompt = f"""
    قم بترجمة وتلخيص الخبر التالي للغة العربية بأسلوب تقني شيق:
    العنوان: {title}
    التفاصيل: {summary}
    
    المطلوب:
    1. صياغة الخبر بأسلوب مناسب لقنوات تليجرام.
    2. وضع هاشتاجات مناسبة داخل النص (مثل #جوجل، #مايكروسوفت).
    3. في نهاية المنشور، أضف هاشتاجات تصنيف عامة مثل #تقنية #ذكاء_اصطناعي.
    """
    response = model.generate_content(prompt)
    return response.text

# جلب الأخبار ونشرها
async def fetch_and_post_news(context: ContextTypes.DEFAULT_TYPE):
    feeds = [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://openai.com/news/rss.xml",
        "https://www.engadget.com/rss.xml",
        "https://www.reuters.com/technology/",
        ""
    ]
    
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]: # فحص آخر 3 أخبار من كل مصدر
            if not is_posted(entry.link):
                try:
                    formatted_news = await process_news_with_gemini(entry.title, entry.summary)
                    final_text = f"{formatted_news}\n\n🔗 المصدر: {entry.link}"
                    
                    await context.bot.send_message(chat_id=CHANNEL_ID, text=final_text)
                    save_link(entry.link)
                except Exception as e:
                    print(f"Error processing news: {e}")

# تقييد الوصول (الأمان)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return # تجاهل أي شخص غيرك
    await update.message.reply_text("البوت يعمل بنجاح ومخصص لهذه القناة فقط.")

def main():
    init_db()
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # إضافة الأوامر
    application.add_handler(CommandHandler("start", start))

    # جدولة جلب الأخبار كل 30 دقيقة
    job_queue = application.job_queue
    job_queue.run_repeating(fetch_and_post_news, interval=1800, first=10)

    # تشغيل Webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", "8443")),
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    )

if __name__ == '__main__':
    main()