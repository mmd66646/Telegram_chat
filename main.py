
import os
import threading
import time
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

# متغیرهای محیطی
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_ENV = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not ADMIN_ID_ENV:
    raise ValueError("ADMIN_ID must be provided")

try:
    ADMIN_ID = int(ADMIN_ID_ENV)
except Exception:
    raise ValueError("ADMIN_ID must be a numeric Telegram user id")

print(f"✅ Bot Token: {'*' * 10}{BOT_TOKEN[-8:] if len(BOT_TOKEN) > 8 else '*****'}")
print(f"✅ Admin ID: {ADMIN_ID}")

# پایگاه داده کاربران در حافظه
user_database = {}  # keys: int user_id
start_time = datetime.now()
message_count = 0

# نگهداری کاربری که ادمین قصد پاسخ دادن به او را دارد
pending_replies = {}  # key: ADMIN_ID -> value: target_user_id (int)

# Flask app برای health check
app = Flask(__name__)


@app.route("/")
def home():
    current_time = datetime.now()
    uptime = current_time - start_time
    return {
        "status": "🤖 Telegram Bot is Running!",
        "message": "Bot is online and ready to receive messages",
        "uptime_days": uptime.days,
        "uptime_hours": uptime.seconds // 3600,
        "uptime_minutes": (uptime.seconds % 3600) // 60,
        "active_users": len(user_database),
        "total_messages": message_count,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.route("/health")
def health():
    return {
        "status": "healthy",
        "bot": "online",
        "users": len(user_database),
        "messages": message_count,
        "timestamp": datetime.now().isoformat(),
    }


def get_user_info(user):
    """استخراج اطلاعات کاربر"""
    user_id = user.id if user else "Unknown"
    username = f"@{user.username}" if user and user.username else "No username"
    full_name = user.full_name if user else "Unknown"
    return user_id, username, full_name


def update_user_database(user):
    """به‌روزرسانی پایگاه داده کاربران"""
    if user:
        user_id, username, full_name = get_user_info(user)
        user_database[int(user_id)] = {
            "username": username,
            "full_name": full_name,
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chat_id": int(user_id),
        }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دستور /start و ثبت اطلاعات کاربر"""
    if update.message is None:
        return

    user = update.effective_user
    user_id, username, full_name = get_user_info(user)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    update_user_database(user)

    start_info = (
        f"🆕 کاربر جدید دستور /start زد:\n\n"
        f"👤 نام کامل: {full_name}\n"
        f"🆔 آیدی: {user_id}\n"
        f"📝 نام کاربری: {username}\n"
        f"⏰ زمان: {current_time}"
    )

    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=start_info)
    except Exception as e:
        print(f"❌ Error sending new-user notify to admin: {e}")

    await update.message.reply_text("سلام! ربات فعال شد. پیام‌های شما ارسال خواهد شد ✅")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فوروارد پیام کاربر به ادمین و افزودن دکمه‌ها"""
    global message_count
    if update.message is None:
        return

    user = update.effective_user
    user_id = int(user.id)

    # جلوگیری از فوروارد پیام ادمین به خودش
    if user_id == ADMIN_ID:
        return

    update_user_database(user)
    message_count += 1

    reply_instruction = "\n\n💬 برای پاسخ کلیک کنید یا از دکمه‌ها استفاده کنید."

    try:
        # دکمه‌ها
        keyboard = [
            [
                InlineKeyboardButton(f"Reply to {user_id}", callback_data=f"reply_{user_id}"),
                InlineKeyboardButton("Open Chat", url=f"tg://openmessage?user_id={user_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        full_name = user.full_name if user else "Unknown"
        username = f"@{user.username}" if user and user.username else "No username"

        # متن پیام
        if update.message.text:
            msg_text = update.message.text
            full_message = f"👤 {full_name} ({username} / {user_id}):\n\n📝 {msg_text}{reply_instruction}"
            await context.bot.send_message(chat_id=ADMIN_ID, text=full_message, reply_markup=reply_markup)

        # عکس
        elif update.message.photo:
            photo = update.message.photo[-1]
            caption = update.message.caption or ""
            photo_caption = f"👤 {full_name} ({username} / {user_id}):\n\n📸 عکس\n\n{caption}"
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo.file_id, caption=photo_caption, reply_markup=reply_markup)

        # صوت
        elif update.message.voice:
            voice = update.message.voice
            voice_caption = f"👤 {full_name} ({username} / {user_id}):\n\n🎤 پیام صوتی"
            await context.bot.send_voice(chat_id=ADMIN_ID, voice=voice.file_id, caption=voice_caption, reply_markup=reply_markup)

        # سند/فایل
        elif update.message.document:
            document = update.message.document
            caption = update.message.caption or ""
            doc_caption = f"👤 {full_name} ({username} / {user_id}):\n\n📄 فایل: {document.file_name or 'فایل'}\n\n{caption}"
            await context.bot.send_document(chat_id=ADMIN_ID, document=document.file_id, caption=doc_caption, reply_markup=reply_markup)

        else:
            other_message = f"👤 {full_name} ({username} / {user_id}):\n\n❓ نوع پیام پشتیبانی نشده"
            await context.bot.send_message(chat_id=ADMIN_ID, text=other_message, reply_markup=reply_markup)

        # تأیید برای کاربر
        try:
            await update.message.reply_text("✅ پیام شما ارسال شد")
        except Exception:
            pass

        print(f"📨 Message #{message_count} forwarded from user {user_id}")

    except Exception as e:
        print(f"❌ Error handling message: {e}")
        try:
            await update.message.reply_text("❌ خطا در ارسال پیام")
        except:
            pass


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    if query.data and query.data.startswith("reply_"):
        try:
            target_user_id = int(query.data.split("_")[1])
            pending_replies[ADMIN_ID] = target_user_id  # استفاده از ADMIN_ID ثابت
            await query.message.reply_text(
                f"✍️ حالا متنت رو بنویس، من می‌فرستم برای {target_user_id}"
            )
        except Exception as e:
            await query.message.reply_text("❌ خطا در پردازش دکمه ریپلای")
            print("Callback handling error:", e)


async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پیام ادمین به کاربر هدف"""
    if update.message is None:
        return

    if update.effective_user.id != ADMIN_ID:
        return  # فقط ادمین

    if ADMIN_ID not in pending_replies:
        await update.message.reply_text("❌ ابتدا روی دکمه Reply کلیک کنید")
        return

    target_user_id = pending_replies[ADMIN_ID]

    try:
        await context.bot.send_message(chat_id=target_user_id, text=update.message.text)
        await update.message.reply_text(f"✅ پیام برای {target_user_id} ارسال شد")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال پیام: {e}")
        print("Error sending admin message:", e)

    # حذف pending بعد از ارسال
    del pending_replies[ADMIN_ID]


async def reply_to_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /reply برای ادمین"""
    if update.message is None or update.effective_user.id != ADMIN_ID:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ فرمت نادرست!\nاستفاده: /reply <user_id> <message>\nمثال: /reply 123456789 سلام"
        )
        return

    try:
        target_user_id = int(context.args[0])
        reply_message = " ".join(context.args[1:])
        if target_user_id not in user_database:
            await update.message.reply_text(f"❌ کاربر با آیدی {target_user_id} یافت نشد!")
            return
        await context.bot.send_message(chat_id=target_user_id, text=reply_message)
        await update.message.reply_text("✅ پیام ارسال شد")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال پیام: {e}")
        print("reply cmd error:", e)


def run_flask():
    """اجرای Flask server"""
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Starting Flask server on port {port}...")
    try:
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
    except Exception as e:
        print(f"❌ Flask server error: {e}")


def run_bot():
    """اجرای Telegram bot"""
    print("🤖 Starting Telegram bot...")
    try:
        telegram_app = Application.builder().token(BOT_TOKEN).build()

        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("reply", reply_to_user_cmd))
        telegram_app.add_handler(CallbackQueryHandler(button_callback))
        telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message))

        print("✅ Bot handlers registered successfully")
        print("🚀 Starting bot polling...")
        telegram_app.run_polling(drop_pending_updates=True)

    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        raise


def main():
    print("🚀 Starting Telegram Bot with Flask Health Check...")
    print(f"⏰ Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Flask thread started")

    time.sleep(3)

    print("🎯 Starting main bot process...")
    run_bot()


if __name__ == "__main__":
    main()
