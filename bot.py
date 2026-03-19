from __future__ import annotations
import logging
import os
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# --- CONFIG ---
BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", "8588796274:AAGmyftrjBgLlB5vZizhx5LM9Di3Wj2oWeQ")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "433236357"))

# --- FILE TO STORE REGISTERED TEACHERS ---
TEACHERS_FILE = "teachers.json"

# --- STATES ---
REG_NAME, REG_PHONE, CLASS, ABSENT_STUDENTS, CONFIRM = range(5)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# TEACHER STORAGE HELPERS
# ─────────────────────────────────────────

def load_teachers() -> dict:
    if os.path.exists(TEACHERS_FILE):
        with open(TEACHERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_teacher(user_id: int, data: dict):
    teachers = load_teachers()
    teachers[str(user_id)] = data
    with open(TEACHERS_FILE, "w", encoding="utf-8") as f:
        json.dump(teachers, f, ensure_ascii=False, indent=2)


def get_teacher(user_id: int) -> dict | None:
    teachers = load_teachers()
    return teachers.get(str(user_id))


# ─────────────────────────────────────────
# /start
# ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    teacher = get_teacher(user_id)

    if teacher:
        context.user_data["teacher"] = teacher
        await update.message.reply_text(
            f"👋 Xush kelibsiz, *{teacher['name']}*!\n\n"
            f"📚 Sinfni kiriting (masalan: *8-V* yoki *10-A*):",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return CLASS

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "Bu botdan foydalanish uchun bir martalik ro'yxatdan o'tish kerak.\n\n"
        "✏️ Iltimos, to'liq ismingizni kiriting:\n_(masalan: Abdullayeva Nodira)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return REG_NAME


# ─────────────────────────────────────────
# REGISTRATION
# ─────────────────────────────────────────

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()

    if len(name) < 3:
        await update.message.reply_text("❗ Iltimos, to'liq ismingizni kiriting.")
        return REG_NAME

    context.user_data["reg_name"] = name

    phone_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        f"✅ Rahmat, *{name}*!\n\n"
        "📱 Endi telefon raqamingizni ulashing.\n"
        "Quyidagi tugmani bosing:",
        parse_mode="Markdown",
        reply_markup=phone_keyboard,
    )
    return REG_PHONE


async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
    elif update.message.text:
        phone = update.message.text.strip()
        if not (phone.startswith("+") and len(phone) >= 9):
            await update.message.reply_text(
                "❗ Iltimos, telefon raqamingizni ulashing yoki qo'lda kiriting (+998XXXXXXXXX)."
            )
            return REG_PHONE
    else:
        await update.message.reply_text("❗ Telefon raqamini ulashing.")
        return REG_PHONE

    user = update.effective_user
    teacher_data = {
        "name": context.user_data["reg_name"],
        "phone": phone,
        "tg_id": user.id,
        "tg_username": f"@{user.username}" if user.username else "yo'q",
        "tg_fullname": user.full_name or "",
        "registered_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

    save_teacher(user.id, teacher_data)
    context.user_data["teacher"] = teacher_data

    await update.message.reply_text(
        f"✅ *Ro'yxatdan o'tdingiz!*\n\n"
        f"👤 Ism: *{teacher_data['name']}*\n"
        f"📱 Telefon: *{phone}*\n\n"
        f"Endi har safar /start bosganda to'g'ridan-to'g'ri sinf kiritishga o'tasiz.\n\n"
        f"📚 Sinfni kiriting (masalan: *8-V* yoki *10-A*):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return CLASS


# ─────────────────────────────────────────
# CLASS INPUT
# ─────────────────────────────────────────

async def get_class(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chosen = update.message.text.strip()

    if len(chosen) < 2:
        await update.message.reply_text("❗ Iltimos, sinf nomini kiriting (masalan: 7-B).")
        return CLASS

    context.user_data["class"] = chosen
    context.user_data["absent_students"] = []

    await update.message.reply_text(
        f"📝 *{chosen}* sinfi — darsga kelmaganlar:\n\n"
        "Ismlarni *vergul* bilan ajratib yozing:\n"
        "_Karimov Jasur, Toshmatov Dilshod, Yusupova Malika_\n\n"
        "Agar hamma kelgan bo'lsa: *Hamma keldi* deb yozing.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ABSENT_STUDENTS


# ─────────────────────────────────────────
# ABSENT STUDENTS INPUT
# ─────────────────────────────────────────

async def get_absent_students(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text.lower() in ["hamma keldi", "hamma kelgan", "hammasi keldi", "yo'q"]:
        context.user_data["absent_students"] = []
        context.user_data["all_present"] = True
    else:
        students = [s.strip() for s in text.split(",") if s.strip()]
        if not students:
            await update.message.reply_text(
                "❗ Iltimos, ismlarni vergul bilan ajratib kiriting.\n"
                "Misol: _Karimov Jasur, Toshmatov Dilshod_",
                parse_mode="Markdown",
            )
            return ABSENT_STUDENTS
        context.user_data["absent_students"] = students
        context.user_data["all_present"] = False

    teacher = context.user_data["teacher"]
    klass = context.user_data["class"]
    students = context.user_data["absent_students"]
    all_present = context.user_data.get("all_present", False)

    if all_present:
        student_text = "✅ Hamma o'quvchi kelgan"
    else:
        student_text = "\n".join(f"  • {s}" for s in students)

    await update.message.reply_text(
        f"📋 *Tasdiqlash*\n\n"
        f"👤 O'qituvchi: *{teacher['name']}*\n"
        f"🏫 Sinf: *{klass}*\n"
        f"❌ Kelmagan: *{'0' if all_present else len(students)} kishi*\n\n"
        f"{student_text}\n\n"
        f"Ma'lumot to'g'rimi?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Tayyor", "✏️ O'zgartirish", "❌ Bekor"]],
            resize_keyboard=True,
        ),
    )
    return CONFIRM


# ─────────────────────────────────────────
# CONFIRM & SEND
# ─────────────────────────────────────────

async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "❌ Bekor":
        return await cancel(update, context)

    if text == "✏️ O'zgartirish":
        klass = context.user_data["class"]
        context.user_data["absent_students"] = []
        context.user_data["all_present"] = False
        await update.message.reply_text(
            f"✏️ *{klass}* sinfi uchun qayta kiriting:\n\n"
            "Ismlarni *vergul* bilan ajratib yozing:\n"
            "_Karimov Jasur, Toshmatov Dilshod_\n\n"
            "Yoki: *Hamma keldi*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ABSENT_STUDENTS

    if text == "✅ Tayyor":
        teacher = context.user_data["teacher"]
        klass = context.user_data["class"]
        students = context.user_data["absent_students"]
        all_present = context.user_data.get("all_present", False)
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        if all_present:
            student_text = "✅ Hamma o'quvchi kelgan"
            count = "0"
        else:
            student_text = "\n".join(f"  • {s}" for s in students)
            count = str(len(students))

        username_line = f"📲 Telegram: {teacher['tg_username']}\n" if teacher['tg_username'] != "yo'q" else ""

        admin_msg = (
            f"🔔 <b>YANGI DAVOMAT HISOBOTI</b>\n"
            f"{'─' * 32}\n"
            f"📅 <b>Sana:</b> {now}\n\n"
            f"👤 <b>O'qituvchi:</b> {teacher['name']}\n"
            f"📱 <b>Telefon:</b> {teacher['phone']}\n"
            f"{username_line}"
            f"🪪 <b>Telegram ID:</b> <code>{teacher['tg_id']}</code>\n\n"
            f"🏫 <b>Sinf:</b> {klass}\n"
            f"❌ <b>Kelmagan:</b> {count} kishi\n\n"
            f"{student_text}\n"
            f"{'─' * 32}"
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_msg,
                parse_mode="HTML",
            )
            await update.message.reply_text(
                "✅ *Yuborildi!* Rahmat.\n\nYana yuborish uchun /start bosing.",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception as e:
            logger.error(f"Admin send error: {e}")
            await update.message.reply_text(
                f"❗ Xatolik: {e}",
                reply_markup=ReplyKeyboardRemove(),
            )

        return ConversationHandler.END

    await update.message.reply_text("❗ Iltimos, tugmalardan birini tanlang.")
    return CONFIRM


# ─────────────────────────────────────────
# CANCEL & UNKNOWN
# ─────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Bekor qilindi. Qayta boshlash uchun /start bosing.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Boshlash uchun /start yuboring.")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_PHONE: [
                MessageHandler(filters.CONTACT, reg_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_phone),
            ],
            CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_class)],
            ABSENT_STUDENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_absent_students)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_submission)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
