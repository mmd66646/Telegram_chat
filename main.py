import os
import threading
import time
import requests
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# متغیرهای محیطی
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable is required")

print(f"✅ Bot Token: {'*' * 20}{BOT_TOKEN[-10:] if len(BOT_TOKEN) > 10 else '*****'}")
print(f"✅ Admin ID: {ADMIN_ID}")

# پایگاه داده کاربران در حافظه
user_database = {}
start_time = datetime.now()
message_count = 0

# Flask app برای health check
app = Flask(__name__)

@app.route('/')
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
        "platform": "Railway/Render Hosting"
    }

@app.route('/health')
def health():
    return {
        "status": "healthy", 
        "bot": "online", 
        "users": len(user_database),
        "messages": message_count,
        "timestamp": datetime.now().isoformat()
    }

@app.route('/stats')
def stats():
    return {
        "bot_statistics": {
            "active_users": len(user_database),
            "total_messages_processed": message_count,
            "uptime_seconds": int((datetime.now() - start_time).total_seconds()),
            "start_time": start_time.isoformat()
        },
        "user_list": [
            {
                "id": user_id,
                "name": info["full_name"],
                "username": info["username"],
                "last_seen": info["last_seen"]
            }
            for user_id, info in user_database.items()
        ]
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
        user_database[user_id] = {
            "username": username,
            "full_name": full_name,
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chat_id": user_id
        }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دستور /start و ثبت اطلاعات کاربر"""
    if update.message is None:
        return
    
    user = update.effective_user
    user_id, username, full_name = get_user_info(user)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # به‌روزرسانی پایگاه داده کاربران
    update_user_database(user)
    
    # ارسال اطلاعات کاربر به ادمین
    start_info = (
        f"🆕 کاربر جدید دستور /start زد:\n\n"
        f"👤 نام کامل: {full_name}\n"
        f"🆔 آیدی: {user_id}\n"
        f"📝 نام کاربری: {username}\n"
        f"⏰ زمان: {current_time}\n\n"
        f"💬 برای پاسخ: /reply {user_id} پیام شما"
    )
    
    try:
        await context.bot.send_message(chat_id=int(ADMIN_ID), text=start_info)
        print(f"✅ New user notification sent to admin for user {user_id}")
    except Exception as e:
        print(f"❌ Error sending to admin: {e}")
    
    # پاسخ به کاربر
    await update.message.reply_text("سلام! ربات فعال شد. پیام‌های شما ارسال خواهد شد ✅")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت و فوروارد تمام پیام‌ها همراه با اطلاعات کاربر"""
    global message_count
    
    if update.message is None:
        return
    
    message_count += 1
    user = update.effective_user
    user_id, username, full_name = get_user_info(user)
    
    # به‌روزرسانی پایگاه داده کاربران
    update_user_database(user)
    
    # اطلاعات کاربر برای همه پیام‌ها
    user_info = f"👤 {full_name} ({username} / {user_id})"
    reply_instruction = f"\n\n💬 برای پاسخ: /reply {user_id} پیام شما"
    
    try:
        if update.message.text:
            # پیام متنی
            msg_text = update.message.text
            full_message = f"{user_info}:\n\n📝 {msg_text}{reply_instruction}"
            await context.bot.send_message(chat_id=int(ADMIN_ID), text=full_message)
            
        elif update.message.photo:
            # عکس
            photo = update.message.photo[-1]  # بهترین کیفیت
            caption = update.message.caption or ""
            photo_caption = f"{user_info}:\n\n📸 عکس"
            if caption:
                photo_caption += f"\nکپشن: {caption}"
            photo_caption += reply_instruction
            await context.bot.send_photo(
                chat_id=int(ADMIN_ID), 
                photo=photo.file_id, 
                caption=photo_caption
            )
            
        elif update.message.voice:
            # پیام صوتی
            voice = update.message.voice
            voice_caption = f"{user_info}:\n\n🎤 پیام صوتی{reply_instruction}"
            await context.bot.send_voice(
                chat_id=int(ADMIN_ID), 
                voice=voice.file_id, 
                caption=voice_caption
            )
            
        elif update.message.document:
            # فایل
            document = update.message.document
            caption = update.message.caption or ""
            file_name = document.file_name or "فایل بدون نام"
            doc_caption = f"{user_info}:\n\n📄 فایل: {file_name}"
            if caption:
                doc_caption += f"\nکپشن: {caption}"
            doc_caption += reply_instruction
            await context.bot.send_document(
                chat_id=int(ADMIN_ID), 
                document=document.file_id, 
                caption=doc_caption
            )
            
        else:
            # سایر انواع پیام
            other_message = f"{user_info}:\n\n❓ نوع پیام پشتیبانی نشده{reply_instruction}"
            await context.bot.send_message(
                chat_id=int(ADMIN_ID), 
                text=other_message
            )

        # تأیید دریافت به کاربر
        await update.message.reply_text("✅ پیام شما ارسال شد")
        print(f"📨 Message #{message_count} forwarded from user {user_id}")
        
    except Exception as e:
        print(f"❌ Error handling message: {e}")
        try:
            await update.message.reply_text("❌ خطا در ارسال پیام")
        except:
            pass

async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ دادن به کاربر خاص توسط ادمین"""
    if update.message is None or str(update.effective_user.id) != str(ADMIN_ID):
        return
    
    # بررسی فرمت دستور
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ فرمت نادرست!\n"
            "استفاده: /reply <user_id> <message>\n"
            "مثال: /reply 123456789 سلام چطوری؟"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        reply_message = " ".join(context.args[1:])
        
        # بررسی وجود کاربر در پایگاه داده
        if target_user_id not in user_database:
            await update.message.reply_text(f"❌ کاربر با آیدی {target_user_id} یافت نشد!")
            return
        
        # ارسال پیام به کاربر
        await context.bot.send_message(
            chat_id=target_user_id,
            text=reply_message
        )
        # تأیید برای ادمین
        user_info = user_database[target_user_id]
        await update.message.reply_text(
            f"✅ پیام به {user_info['full_name']} ({user_info['username']}) ارسال شد!"
        )
        print(f"💬 Admin replied to user {target_user_id}")
        
    except ValueError:
        await update.message.reply_text("❌ آیدی کاربر باید عدد باشد!")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال پیام: {str(e)}")
        print(f"❌ Reply error: {e}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست کاربران فعال"""
    if update.message is None or str(update.effective_user.id) != str(ADMIN_ID):
        return
    
    if not user_database:
        await update.message.reply_text("📭 هیچ کاربری یافت نشد!")
        return
    
    users_list = f"👥 لیست کاربران فعال ({len(user_database)} کاربر):\n\n"
    for user_id, user_info in user_database.items():
        users_list += (
            f"👤 {user_info['full_name']}\n"
            f"🆔 آیدی: {user_id}\n"
            f"📝 {user_info['username']}\n"
            f"⏰ {user_info['last_seen']}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
        )
    
    await update.message.reply_text(users_list)

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پیام به همه کاربران"""
    if update.message is None or str(update.effective_user.id) != str(ADMIN_ID):
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ فرمت نادرست!\n"
            "استفاده: /broadcast <message>\n"
            "مثال: /broadcast سلام به همه!"
        )
        return
    
    broadcast_text = " ".join(context.args)
    sent_count = 0
    failed_count = 0
    
    for user_id in user_database.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 پیام عمومی:\n\n{broadcast_text}"
            )
            sent_count += 1
        except Exception:
            failed_count += 1
    
    await update.message.reply_text(
        f"📊 نتیجه ارسال پیام عمومی:\n"
        f"✅ ارسال شده: {sent_count}\n"
        f"❌ ناموفق: {failed_count}\n"
        f"👥 کل کاربران: {len(user_database)}"
    )

def run_flask():
    """اجرای Flask server"""
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Starting Flask server on port {port}...")
    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception as e:
        print(f"❌ Flask server error: {e}")

def run_bot():
    """اجرای Telegram bot"""
    print("🤖 Starting Telegram bot...")
    
    try:
        telegram_app = Application.builder().token(BOT_TOKEN).build()
        
        # اضافه کردن هندلرها
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("reply", reply_to_user))
        telegram_app.add_handler(CommandHandler("users", list_users))
        telegram_app.add_handler(CommandHandler("broadcast", broadcast_message))
        telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
        
        print("✅ Bot handlers registered successfully")
        
        # شروع polling
        print("🚀 Starting bot polling...")
        telegram_app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        raise

def main():
    print("🚀 Starting Telegram Bot with Flask Health Check...")
    print(f"⏰ Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # شروع Flask server در thread جداگانه
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Flask thread started")
    
    # کمی انتظار تا سرور آماده شود
    time.sleep(3)
    
    # شروع Telegram bot در main thread
    print("🎯 Starting main bot process...")
    run_bot()

if __name__ == "__main__":

    main()

