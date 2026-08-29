"""
منوی ثابت پایین چت (Reply Keyboard) — نسخه‌ی مینیمال
────────────────────────────────────────────────────
این ماژول همون کادر کوچیکی که کنار جعبه‌ی تایپ پیام تلگرام می‌شینه رو
مدیریت می‌کنه (چیزی متفاوت از دکمه‌های شیشه‌ای زیر پیام‌ها که بقیه‌ی
پروژه ازش استفاده می‌کنه).

قانون‌ها:
  • توی «بخش اول» (خودِ پنل اصلی) این کیبورد اصلاً نباید دیده بشه.
  • به محض این‌که کاربر وارد هر بخش دیگه‌ای بشه (هر پنل/زیرمنویی غیر
    از خودِ پنل اصلی — چه با زدن یه دکمه‌ی شیشه‌ای، چه با فرستادن
    مستقیم یه کلمه‌ی کلیدی)، همین کیبورد باید ظاهر بشه — و همیشه و
    همیشه فقط و فقط یک دکمه داشته باشه: 🔙 بازگشت.
  • دکمه‌ی بازگشت باید همیشه کار کنه، فارغ از این‌که کاربر وسط چه
    حالتی باشه (دستیار هوشمند، فرم نیمه‌کاره‌ی یه ConversationHandler
    و ...) — همیشه کاربر رو به پنل اصلی برمی‌گردونه.

تلگرام راهی برای عوض کردن کیبورد ثابت بدون فرستادن یه پیام جدید نداره؛
برای همین از یه ترفند ساده استفاده می‌کنیم: یه پیام کوتاه با کیبورد
جدید می‌فرستیم و بلافاصله پاکش می‌کنیم. حذف پیام، کیبورد رو برنمی‌گردونه
— یعنی کاربر هیچ دکمه‌ی اضافه‌ای توی خودِ این بخش نمی‌بینه، فقط همون
مربع کوچیک کنار بخش نوشتن عوض می‌شه.

وضعیت فعلی («root» یا «section») توی ctx.user_data ذخیره می‌شه تا این
پیام مخفی فقط وقتی واقعاً وضعیت عوض شده فرستاده بشه، نه هر بار.
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes

import database as db
from config import PISHVA_ID

BTN_BACK = "🔙 بازگشت"

_KB_STATE_KEY = "_kb_state"  # "root" یا "section"


def back_only_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_BACK)]],
        resize_keyboard=True,
        is_persistent=True,
    )


async def _is_allowed(update: Update) -> bool:
    """فقط برای مدیر ارشد/ادمین فعال این کیبورد رو مدیریت کن."""
    uid = update.effective_user.id if update.effective_user else None
    if not uid:
        return False
    if uid == PISHVA_ID:
        return True
    admin = await db.get_admin(uid)
    return bool(admin and admin["is_active"])


async def _flash_keyboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE, markup, text: str):
    """
    یه پیام کوتاه فقط برای تغییر کیبورد پایین چت می‌فرسته.
    توجه: این پیام دیگه پاک نمی‌شه — چون تلگرام (حداقل روی بعضی
    کلاینت‌ها) با پاک شدن پیامی که کیبورد رو ست کرده، خودِ کیبورد رو
    هم برمی‌گردونه/مخفی می‌کنه. برای همین پیام باقی می‌مونه، ولی چون
    فقط سرِ تغییر وضعیت (نه هر بار) فرستاده می‌شه، اسپم نمی‌شه.
    """
    chat = update.effective_chat
    if not chat:
        return
    try:
        await ctx.bot.send_message(chat_id=chat.id, text=text, reply_markup=markup)
    except Exception:
        pass


async def sync_section_keyboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE, entering_section: bool):
    """
    وضعیت کیبورد پایین چت رو با این‌که کاربر توی پنل اصلیه یا توی یه
    بخش دیگه، هماهنگ می‌کنه. فقط وقتی وضعیت واقعاً عوض شده کاری می‌کنه.
    """
    if not await _is_allowed(update):
        return
    target = "section" if entering_section else "root"
    if ctx.user_data.get(_KB_STATE_KEY) == target:
        return
    ctx.user_data[_KB_STATE_KEY] = target
    if entering_section:
        await _flash_keyboard(update, ctx, back_only_keyboard(), "🔙 برای بازگشت، از دکمه‌ی پایین استفاده کن.")
    else:
        await _flash_keyboard(update, ctx, ReplyKeyboardRemove(), "🏠 برگشتی به پنل اصلی.")


async def reset_to_root_keyboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """برای صدازدن بعد از ورود موفق (/start) — همیشه مطمئن می‌شه کیبورد مخفیه."""
    ctx.user_data.pop(_KB_STATE_KEY, None)
    await sync_section_keyboard(update, ctx, entering_section=False)


async def sync_reply_keyboard_on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Observer عمومی روی همه‌ی دکمه‌های شیشه‌ای (باید در یه group جدا و
    بعد از بقیه‌ی هندلرها ثبت بشه، بدون این‌که خودش query.answer بزنه
    یا پردازش رو متوقف کنه).
    """
    query = update.callback_query
    if not query or query.data is None:
        return
    entering_section = (query.data != "back_main")
    await sync_section_keyboard(update, ctx, entering_section)


async def handle_reply_menu_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    MessageHandler برای تنها دکمه‌ی این منو (🔙 بازگشت). باید در گروهی
    قبل از ConversationHandlerها و قبل از handle_keyword_command ثبت
    بشه تا همیشه، فارغ از هر حالتی، جلوی بقیه‌ی پردازش رو بگیره و
    کاربر رو به پنل اصلی برگردونه.
    """
    if not update.message or not update.message.text:
        return
    if update.message.text.strip() != BTN_BACK:
        return  # این پیام مال منوی ما نیست؛ بذار بقیه‌ی هندلرها پردازشش کنن

    if not await _is_allowed(update):
        return

    # فارغ از این‌که کاربر وسط چه حالتی بود (دستیار هوشمند و ...) پاکش کن
    ctx.user_data.pop("ai_mode", None)
    ctx.user_data.pop("ai_history", None)
    ctx.user_data.pop("ai_session_id", None)

    from keyword_commands import handle_keyword_command
    update.message.text = "پنل"
    try:
        await handle_keyword_command(update, ctx)
    finally:
        await sync_section_keyboard(update, ctx, entering_section=False)
