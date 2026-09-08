"""
chess_games_history.py
لیستِ تاریخچه‌ی بازی‌های *تمام‌شده*‌ی «شطرنج زنده» — برای همه‌ی نقش‌هایی
که به منوی شطرنج (chess_menu در chess_challenge.py) دسترسی دارند: پیشوا،
مدیر مسابقات، مدیر امنیتی. از داخلِ همان منو با دکمه‌ی «📜 لیست بازی‌ها»
باز می‌شود.

امکانات:
- فیلترِ بازه‌ی زمانی (امروز/این هفته/این ماه/کل تاریخ) + دکمه‌ی مجزای
  «📚 همه بازی‌ها» (بدونِ هیچ فیلتری، هم بازه هم مدیر).
- فیلترِ «فقط بازی‌های یک مدیر/پیشوایِ مشخص» (چه سفید بوده چه سیاه).
- صفحه‌بندی، چون ممکن است هزاران بازی ثبت شده باشد.
- با زدنِ هر بازی، همان بازی از اول در مینی‌اپ باز می‌شود — تخته‌ی کامل،
  و همان مودالِ پایانِ بازیِ ازقبل‌موجود که دکمه‌های «بستن» (خروج) و
  «🔍 تحلیل مسابقه» را دارد. محتوای چتِ داخلِ آن بازی برای همه مخفی است،
  به‌جز پیشوا (نگاه کنید به پارامترِ chat= در URL و SHOW_CHAT در app.js).

همه‌ی فیلترها/صفحه به‌طورِ کامل داخلِ خودِ callback_data کد می‌شوند (نه در
ctx.user_data)، پس این بخش کاملاً stateless و در برابرِ ری‌استارت/تداخلِ
هم‌زمانِ چند کاربر امن است.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

import database as db
import keyboards as kb
from config import PISHVA_ID, WEBAPP_URL
from helpers import safe_edit_message_text, box, pishva_display, escape_md_legacy
from chess_challenge import _resolve_bot_username

logger = logging.getLogger(__name__)

PAGE_SIZE = 8

PERIOD_LABEL = {"today": "امروز", "week": "این هفته", "month": "این ماه", "all": "کل تاریخ"}


# ─── کمکی‌های نمایشی ────────────────────────────────────────────
def _trim(s, n=11):
    s = str(s or "؟")
    return s if len(s) <= n else s[: n - 1] + "…"


def _winner_name(g):
    if g["winner_id"] == g["white_id"]:
        return g["white_name"] or "؟"
    if g["winner_id"] == g["black_id"]:
        return g["black_name"] or "؟"
    return "؟"


def _result_label(g):
    if g["status"] in ("draw", "draw_agreement"):
        return "🤝 مساوی"
    if g["winner_id"]:
        return f"برد {_trim(_winner_name(g), 10)}"
    if g["status"] == "resigned":
        return "🏳️ تسلیم"
    if g["status"] == "timeout":
        return "⏱ اتمام وقت"
    return "—"


def _game_button_label(g):
    white = _trim(g["white_name"])
    black = _trim(g["black_name"])
    t = str(g["finished_at"] or g["created_at"] or "")[:10]
    return f"⚪{white}×⚫{black} — {_result_label(g)} | {t}"


async def _admin_label(admin_filter: str) -> str:
    if admin_filter == "all":
        return "همه"
    try:
        admin_id = int(admin_filter)
    except (TypeError, ValueError):
        return "همه"
    if admin_id == PISHVA_ID:
        return await pishva_display()
    a = await db.get_admin(admin_id)
    return (a["display_name"] or a["full_name"]) if a else str(admin_id)


async def _admin_choices():
    """پیشوا + همه‌ی مدیران (فعال یا غیرفعال — تاریخچه باید همه را نشان بدهد)."""
    pname = await pishva_display()
    admins = await db.get_all_admins()
    choices = [(PISHVA_ID, pname)]
    for a in admins:
        choices.append((a["telegram_id"], a["display_name"] or a["full_name"]))
    return choices


# ─── دکمه‌های بازپخش (وب‌اپ/دیپ‌لینک) ────────────────────────────
def _replay_button(label: str, token: str, show_chat: bool, is_group: bool, bot_username: str = None):
    """مثلِ _watch_button در chess_challenge.py، ولی به‌جای بازیِ زنده،
    به یک بازیِ *تمام‌شده* برای بازپخش/تحلیل لینک می‌دهد، و پرچمِ chat را
    هم به مینی‌اپ منتقل می‌کند (فقط پیشوا چتِ داخلِ بازی را می‌بیند)."""
    chat_flag = "1" if show_chat else "0"
    if is_group:
        if not bot_username:
            return None
        return InlineKeyboardButton(
            label, url=f"https://t.me/{bot_username}?start=chess_replay_{chat_flag}_{token}"
        )
    if not WEBAPP_URL:
        return None
    url = f"{WEBAPP_URL}/webapp/?token={token}&chat={chat_flag}"
    return InlineKeyboardButton(label, web_app=WebAppInfo(url=url))


def kb_replay(token: str, show_chat: bool) -> InlineKeyboardMarkup:
    """کیبورد تک‌دکمه‌ای «مشاهده‌ی بازی» — برای دیپ‌لینکِ گروه→پیوی
    (پیامِ جدیدی که auth.py بعد از /start?=chess_replay_... می‌فرستد)."""
    if not WEBAPP_URL:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="chess_menu")]])
    chat_flag = "1" if show_chat else "0"
    url = f"{WEBAPP_URL}/webapp/?token={token}&chat={chat_flag}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♟️ مشاهده‌ی بازی", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="chess_menu")],
    ])


# ─── هندلرها ────────────────────────────────────────────────────
async def chess_history_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ورودی: دکمه‌ی «📜 لیست بازی‌ها» داخلِ منوی شطرنج (chess_menu)."""
    query = update.callback_query
    await query.answer()
    await safe_edit_message_text(
        query,
        f"{box('📜 لیست بازی‌ها')}\n\n"
        "📌 یک بازه‌ی زمانی انتخاب کنید، یا برای دیدنِ همه‌ی بازی‌ها روی «📚 همه بازی‌ها» بزنید:\n"
        "می‌توانید فیلترِ مدیر را هم جداگانه اضافه کنید.",
        reply_markup=kb.kb_chess_history_filter(),
        parse_mode="Markdown",
    )


async def chess_history_period_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """callback_data = chesshist_periodmenu_<admin_filter>"""
    query = update.callback_query
    await query.answer()
    admin_filter = query.data.split("_")[-1]
    admin_label = await _admin_label(admin_filter)
    await safe_edit_message_text(
        query,
        f"{box('📜 لیست بازی‌ها')}\n\n👤 مدیر: {escape_md_legacy(admin_label)}\n📌 بازه‌ی زمانی را انتخاب کنید:",
        reply_markup=kb.kb_chess_history_period_menu(admin_filter),
        parse_mode="Markdown",
    )


async def chess_history_admin_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """callback_data = chesshist_admsel_<period>"""
    query = update.callback_query
    await query.answer()
    period = query.data.split("_")[-1]
    choices = await _admin_choices()
    await safe_edit_message_text(
        query,
        f"{box('📜 لیست بازی‌ها')}\n\n👤 یک مدیر یا پیشوا را برای فیلتر انتخاب کنید:",
        reply_markup=kb.kb_chess_history_admin_select(period, choices),
        parse_mode="Markdown",
    )


async def chess_history_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """callback_data = chesshist_list_<period>_<admin>_<page>"""
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # ["chesshist", "list", period, admin, page]
    period, admin_filter, page_s = parts[2], parts[3], parts[4]
    try:
        page = max(0, int(page_s))
    except (TypeError, ValueError):
        page = 0
    try:
        admin_id = None if admin_filter == "all" else int(admin_filter)
    except (TypeError, ValueError):
        admin_id = None
        admin_filter = "all"

    games, total = await db.get_chess_games_log_paginated(period, admin_id, page, PAGE_SIZE)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if page >= total_pages and total_pages:
        # صفحه‌ی درخواستی دیگر معتبر نیست (مثلاً فیلتر عوض شده و بازی‌ها کم شده)
        page = total_pages - 1
        games, total = await db.get_chess_games_log_paginated(period, admin_id, page, PAGE_SIZE)

    admin_label = await _admin_label(admin_filter)
    period_label = PERIOD_LABEL.get(period, period)
    header = (
        f"{box('📜 لیست بازی‌ها')}\n\n"
        f"⏱ بازه: {period_label}   |   👤 مدیر: {escape_md_legacy(admin_label)}\n"
        f"🔢 {total} بازی"
    )

    if not games:
        text = header + "\n\n❗ هیچ بازی‌ای با این فیلتر یافت نشد."
        rows = kb.kb_chess_history_change_rows(period, admin_filter)
        await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
        return

    header += f" — صفحه {page + 1} از {total_pages}"

    is_group = bool(query.message and query.message.chat.type in ("group", "supergroup"))
    bot_username = await _resolve_bot_username(ctx.bot) if is_group else None
    # فقط پیشوا محتوای چتِ داخلِ بازی را در بازپخش می‌بیند.
    show_chat = query.from_user.id == PISHVA_ID

    rows = []
    for g in games:
        btn = _replay_button(_game_button_label(g), g["token"], show_chat, is_group, bot_username)
        if btn:
            rows.append([btn])

    if not rows:
        # نه WEBAPP_URL تنظیم شده، نه (در حالتِ گروه) یوزرنیمِ ربات در دسترس بود
        text = header + "\n\n⚠️ در حال حاضر امکانِ باز کردنِ بازی‌ها از این‌جا فراهم نیست."
        rows = kb.kb_chess_history_change_rows(period, admin_filter)
        await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
        return

    rows.extend(kb.kb_chess_history_nav_row(period, admin_filter, page, total_pages))
    rows.extend(kb.kb_chess_history_change_rows(period, admin_filter))
    await safe_edit_message_text(query, header, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
