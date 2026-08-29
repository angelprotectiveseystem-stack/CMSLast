"""
منوی ثابت پایین چت (Reply Keyboard)
────────────────────────────────────
این ماژول همون کادر دکمه‌داری که زیر جعبه‌ی تایپ پیام تلگرام می‌شینه رو
می‌سازه — چیزی متفاوت از دکمه‌های شیشه‌ای زیر پیام‌ها (Inline Keyboard)
که بقیه‌ی پروژه ازش استفاده می‌کنه.

هر دکمه‌ی این منو دقیقاً معادل یکی از «کلمات کلیدی» موجود در
keyword_commands.py است. به‌جای بازنویسی منطق هر پنل، پیام دکمه رو به
همون کلمه‌ی کلیدی ترجمه می‌کنیم و به‌طور مستقیم به handle_keyword_command
تحویل می‌دیم — یعنی:
  • رفتار در گروه (سوال «همینجا یا پیوی؟») دقیقاً یکسانه
  • چک مجوزها/نقش‌ها هیچ تفاوتی با بقیه‌ی مسیرها نداره
  • برای اضافه کردن دکمه‌ی جدید فقط کافیه به BUTTON_TO_KEYWORD
    یک ورودی اضافه کنی که به یکی از کلیدهای SIMPLE_KEYWORDS اشاره کنه
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ApplicationHandlerStop

import database as db
from config import PISHVA_ID

# ─── برچسب دکمه‌ها ─────────────────────────────────────────────
BTN_PANEL = "🏠 پنل اصلی"
BTN_DASHBOARD = "📊 داشبورد"
BTN_MATCHES = "♟️ مسابقات"
BTN_PLAYERS = "👤 بازیکنان"
BTN_TASKS = "📋 وظایف"
BTN_COMMS = "📡 مخابرات"
BTN_TEAMS = "🏆 تیم‌ها"
BTN_LOTTERY = "🎲 قرعه‌کشی"
BTN_ELO = "📈 جدول Elo"
BTN_SECURITY = "🛡️ امنیت"
BTN_HELP = "❓ راهنما"
BTN_AI = "🤖 دستیار هوشمند"

# دکمه‌هایی که فقط برای مدیر ارشد نشون داده می‌شن
PISHVA_ONLY_BUTTONS = {BTN_SECURITY}

# نگاشت برچسب دکمه → متن دقیق کلمه‌ی کلیدی (از SIMPLE_KEYWORDS در keyword_commands.py)
BUTTON_TO_KEYWORD = {
    BTN_PANEL: "پنل",
    BTN_DASHBOARD: "داشبورد",
    BTN_MATCHES: "مسابقه",
    BTN_PLAYERS: "بازیکن",
    BTN_TASKS: "وظیفه",
    BTN_COMMS: "مخابره",
    BTN_TEAMS: "تیم",
    BTN_LOTTERY: "قرعه",
    BTN_ELO: "جدول",
    BTN_SECURITY: "امنیت",
    BTN_HELP: "راهنما",
}


def _rows_for(is_pishva: bool):
    rows = [
        [KeyboardButton(BTN_PANEL), KeyboardButton(BTN_DASHBOARD)],
        [KeyboardButton(BTN_MATCHES), KeyboardButton(BTN_PLAYERS)],
        [KeyboardButton(BTN_TASKS), KeyboardButton(BTN_COMMS)],
        [KeyboardButton(BTN_TEAMS), KeyboardButton(BTN_LOTTERY)],
        [KeyboardButton(BTN_ELO), KeyboardButton(BTN_AI)],
    ]
    if is_pishva:
        rows.append([KeyboardButton(BTN_SECURITY), KeyboardButton(BTN_HELP)])
    else:
        rows.append([KeyboardButton(BTN_HELP)])
    return rows


def main_reply_keyboard(is_pishva: bool) -> ReplyKeyboardMarkup:
    """کیبورد ثابت متناسب با نقش کاربر (هم برای پیوی هم گروه)."""
    return ReplyKeyboardMarkup(
        _rows_for(is_pishva),
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="یک گزینه رو انتخاب کن یا پیام بنویس…",
    )


async def send_main_reply_keyboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    منوی ثابت پایین چت رو برای کاربر فعال می‌کنه، بدون اینکه محتوای
    پیام قبلی (خوش‌آمدگویی و ...) رو تغییر بده. بعد از /start و بعد از
    ورود موفق ادمین/مدیر ارشد صدا زده می‌شه.
    """
    uid = update.effective_user.id if update.effective_user else None
    if not uid or not update.message:
        return
    is_pishva = (uid == PISHVA_ID)
    if not is_pishva:
        admin = await db.get_admin(uid)
        if not admin or not admin["is_active"]:
            return  # کاربر ناشناس → منو نشون نده
    await update.message.reply_text(
        "⌨️ منوی سریع فعال شد — از پایین صفحه در دسترسه.",
        reply_markup=main_reply_keyboard(is_pishva),
    )


async def handle_reply_menu_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    MessageHandler برای دکمه‌های منوی ثابت. باید در group=-2 (قبل از
    ConversationHandlerها) و قبل از handle_keyword_command ثبت بشه.
    """
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()

    if text == BTN_AI:
        await _open_ai_assistant(update, ctx)
        raise ApplicationHandlerStop()

    keyword = BUTTON_TO_KEYWORD.get(text)
    if keyword is None:
        return  # این پیام مال منوی ما نیست؛ بذار بقیه‌ی هندلرها پردازشش کنن

    uid = update.effective_user.id if update.effective_user else None
    if not uid:
        return
    is_pishva = (uid == PISHVA_ID)

    if text in PISHVA_ONLY_BUTTONS and not is_pishva:
        await update.message.reply_text("⛔ این بخش فقط برای مدیر ارشد است.")
        raise ApplicationHandlerStop()

    # ─── تحویل به همون مسیر «کلمات کلیدی» — رفتار صددرصد یکسان ───
    from keyword_commands import handle_keyword_command
    update.message.text = keyword
    await handle_keyword_command(update, ctx)


async def _open_ai_assistant(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """باز کردن دستیار هوشمند از طریق دکمه‌ی منوی ثابت (این اکشن کلمه‌ی کلیدی ندارد)."""
    from ai_assistant import _is_ai_online, _can_use_ai, kb_ai_reply, AI_OFFLINE_MESSAGE
    from helpers import get_user_role

    uid = update.effective_user.id
    is_pishva = (uid == PISHVA_ID)
    if not is_pishva:
        admin = await db.get_admin(uid)
        if not admin or not admin["is_active"]:
            return

    role = await get_user_role(uid)
    if not await _is_ai_online():
        await update.message.reply_text(AI_OFFLINE_MESSAGE)
        return
    if role and not await _can_use_ai(uid, role):
        await update.message.reply_text("⛔ دسترسی شما به دستیار هوشمند مسدود است.")
        return

    ctx.user_data["ai_mode"] = True
    ctx.user_data["ai_history"] = []
    ctx.user_data["ai_session_id"] = await db.ai_create_session(uid, role or "")
    await update.message.reply_text(
        "🤖 دستیار هوشمند فعال شد. هرچی بخوای بگو — می‌تونم کارهات رو انجام بدم، "
        "گزارش بدم یا فقط باهات حرف بزنم.",
        reply_markup=kb_ai_reply(),
    )
