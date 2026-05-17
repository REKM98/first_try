import json
from datetime import timedelta, datetime
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import config

DATA_FILE = "data.json"


# -------------------- دستور استارت --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 سلام! من ربات ضداسپم هستم و می‌توانم گروه شما را مدیریت کنم.\n\n"
        "📌 دستورات موجود:\n"
        "/start - نمایش این پیام\n"
        "/addword <کلمه> - افزودن کلمه ممنوعه\n"
        "/removeword <کلمه> - حذف کلمه از لیست\n"
        "/listwords - نمایش لیست کلمات ممنوعه\n"
        "/warn @username - دادن اخطار دستی به کاربر\n"
        "/warns @username - نمایش تعداد اخطارهای کاربر\n"
        "/resetwarn @username - پاک کردن اخطارهای کاربر\n"
        "/settings - باز کردن پنل تنظیمات ربات\n"
        "\n⚠️ توجه: تمام دستورات مدیریتی فقط برای ادمین‌ها قابل اجراست."
    )
    await update.message.reply_text(help_text)


# -------------------- مدیریت داده --------------------
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "banned_words": [],
            "spam_control": True,
            "flood_limit": 5,
            "antilink": True,
            "antiforward": True,
            "antimedia": True,
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


data = load_data()
user_messages = {}


# -------------------- ابزارها --------------------
async def is_admin(update: Update, user_id: int):
    admins = await update.effective_chat.get_administrators()
    return user_id in [a.user.id for a in admins]


# -------------------- مدیریت کلمات --------------------
async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        return await update.message.reply_text("❌ فقط ادمین‌ها می‌توانند.")

    if not context.args:
        return await update.message.reply_text("⚠️ /addword کلمه")

    word = context.args[0].lower()
    if word not in data["banned_words"]:
        data["banned_words"].append(word)
        save_data(data)
        await update.message.reply_text(f"✅ '{word}' اضافه شد.")
    else:
        await update.message.reply_text("⚠️ این کلمه از قبل در لیست هست.")


async def remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        return await update.message.reply_text("❌ فقط ادمین‌ها می‌توانند.")

    if not context.args:
        return await update.message.reply_text("⚠️ /removeword کلمه")

    word = context.args[0].lower()
    if word in data["banned_words"]:
        data["banned_words"].remove(word)
        save_data(data)
        await update.message.reply_text(f"✅ '{word}' حذف شد.")
    else:
        await update.message.reply_text("⚠️ این کلمه در لیست نبود.")


async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = data["banned_words"]
    if not words:
        await update.message.reply_text("📭 لیست کلمات ممنوعه خالی است.")
    else:
        await update.message.reply_text("🚫 کلمات ممنوعه:\n" + ", ".join(words))


# -------------------- فیلتر پیام‌ها --------------------
async def filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.lower() if update.message.text else ""

    # فیلتر کلمات
    for word in data["banned_words"]:
        if word in text:
            await update.message.delete()
            return

    # ضد لینک
    if data["antilink"] and (
        "http://" in text or "https://" in text or "t.me/" in text
    ):
        await update.message.delete()
        return

    # ضد فوروارد
    if data["antiforward"] and update.message.forward_from:
        await update.message.delete()
        return

    # ضد رسانه
    if data["antimedia"]:
        if (
            update.message.photo
            or update.message.video
            or update.message.sticker
            or update.message.animation
        ):
            await update.message.delete()
            return

    # کنترل اسپم (flood)
    if data["spam_control"]:
        now = datetime.now()
        if user_id not in user_messages:
            user_messages[user_id] = []
        user_messages[user_id] = [
            t for t in user_messages[user_id] if (now - t).seconds < 10
        ]
        user_messages[user_id].append(now)

        if len(user_messages[user_id]) > data["flood_limit"]:
            await update.message.chat.restrict_member(
                user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=now + timedelta(minutes=1),
            )
            await update.message.reply_text(
                f"⚠️ {update.message.from_user.first_name} به دلیل اسپم ۱ دقیقه میوت شد."
            )
            user_messages[user_id] = []


# -------------------- مدیریت کاربران --------------------
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        return
    if not context.args:
        return await update.message.reply_text("⚠️ /ban @username")

    user = context.args[0]
    member = await update.effective_chat.get_member(user)
    await update.effective_chat.ban_member(member.user.id)
    await update.message.reply_text(f"🚫 {user} بن شد.")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        return
    if not context.args:
        return await update.message.reply_text("⚠️ /unban @username")

    user = context.args[0]
    member = await update.effective_chat.get_member(user)
    await update.effective_chat.unban_member(member.user.id)
    await update.message.reply_text(f"✅ {user} آزاد شد.")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        return
    if len(context.args) < 2:
        return await update.message.reply_text("⚠️ /mute @username 1h")

    username, duration = context.args[0], context.args[1]
    member = await update.effective_chat.get_member(username)

    if duration.endswith("h"):
        until = timedelta(hours=int(duration[:-1]))
    elif duration.endswith("m"):
        until = timedelta(minutes=int(duration[:-1]))
    elif duration.endswith("d"):
        until = timedelta(days=int(duration[:-1]))
    else:
        return await update.message.reply_text("⚠️ فرمت نامعتبر. (مثال: 1h, 30m, 1d)")

    await update.effective_chat.restrict_member(
        member.user.id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=datetime.now() + until,
    )
    await update.message.reply_text(f"🔇 {username} برای {duration} میوت شد.")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        return
    if not context.args:
        return await update.message.reply_text("⚠️ /unmute @username")

    username = context.args[0]
    member = await update.effective_chat.get_member(username)
    await update.effective_chat.restrict_member(
        member.user.id, permissions=ChatPermissions(can_send_messages=True)
    )
    await update.message.reply_text(f"✅ {username} آزاد شد.")


# -------------------- پنل تنظیمات --------------------
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        return
    keyboard = [
        [
            InlineKeyboardButton(
                f"🔗 ضد لینک: {'✅' if data['antilink'] else '❌'}",
                callback_data="toggle_antilink",
            )
        ],
        [
            InlineKeyboardButton(
                f"📨 ضد فوروارد: {'✅' if data['antiforward'] else '❌'}",
                callback_data="toggle_antiforward",
            )
        ],
        [
            InlineKeyboardButton(
                f"🖼️ ضد رسانه: {'✅' if data['antimedia'] else '❌'}",
                callback_data="toggle_antimedia",
            )
        ],
        [
            InlineKeyboardButton(
                f"💬 کنترل اسپم: {'✅' if data['spam_control'] else '❌'}",
                callback_data="toggle_spam",
            )
        ],
    ]
    await update.message.reply_text(
        "⚙️ تنظیمات:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("toggle_"):
        key = query.data.replace("toggle_", "")
        data[key] = not data[key]
        save_data(data)
        await settings(update, context)


# -------------------- اجرا --------------------
def main():
    app = Application.builder().token(config.TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    # مدیریت کلمات
    app.add_handler(CommandHandler("addword", add_word))
    app.add_handler(CommandHandler("removeword", remove_word))
    app.add_handler(CommandHandler("listwords", list_words))

    # مدیریت کاربران
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))

    # تنظیمات
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CallbackQueryHandler(button_handler))

    # فیلتر پیام‌ها
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, filter_messages))

    app.run_polling()


if __name__ == "__main__":
    main()
