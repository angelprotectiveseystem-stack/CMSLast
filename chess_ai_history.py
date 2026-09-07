"""
chess_ai_history.py — پنل مدیر ارشد: مرورِ سوابقِ چتِ مدیران با حریفِ
هوش‌مصنوعی در «شطرنج زنده» (بازی با هوش مصنوعی).

این با ai_history.py (سوابق چتِ دستیارِ مدیریتی) کاملاً جداست — دو
جدولِ متفاوت (ai_chat_sessions/ai_chat_messages در برابرِ chess_games/
chess_chat)، دو UI جدا. عمداً فایلِ جدا نگه داشته شده تا هرکدام روی
دامنه‌ی خودش تمرکز داشته باشد.

جریان: منوی شطرنج زنده → انتخابِ مدیر → انتخابِ بازه‌ی زمانی → کلِ
تاریخچه‌ی پیام‌های میانِ همان مدیر و هوش‌مصنوعی (روی همه‌ی بازی‌های
AI‌اش در آن بازه)، به‌صورتِ یک تراسکریپتِ پیوسته و زمانی.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from helpers import safe_edit_message_text, box
from config import PISHVA_ID, ROLE_TOURNAMENT_MANAGER
from chess_ai import AI_ID, AI_LEVELS
from ai_history import PERIOD_LABELS, _fmt_dt

TRANSCRIPT_MAX_LEN = 3800


def _level_label(level: str) -> str:
    info = AI_LEVELS.get(level or "medium", AI_LEVELS["medium"])
    return info["label"]


async def chess_ai_admlog_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    admins = await db.get_all_admins()
    if not admins:
        await safe_edit_message_text(query, f"{box('🗂️ سوابق چت با هوش مصنوعی')}\n\n❗ هیچ مدیری ثبت نشده.",
                                       reply_markup=InlineKeyboardMarkup(
                                           [[InlineKeyboardButton("🔙 بازگشت", callback_data="chess_menu")]]))
        return
    rows = []
    for a in admins:
        role_icon = "🏆" if a["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️"
        name = a["display_name"] or a["full_name"]
        rows.append([InlineKeyboardButton(f"{role_icon} {name}", callback_data=f"chess_ai_admlog_pick_{a['telegram_id']}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="chess_menu")])
    await safe_edit_message_text(query,
        f"{box('🗂️ سوابق چت با هوش مصنوعی')}\n\n📌 یک مدیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )


async def chess_ai_admlog_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    admin = await db.get_admin(tid)
    name = (admin["display_name"] or admin["full_name"]) if admin else str(tid)
    rows = [
        [InlineKeyboardButton(PERIOD_LABELS["today"], callback_data=f"chess_ai_admlog_range_{tid}_today"),
         InlineKeyboardButton(PERIOD_LABELS["week"], callback_data=f"chess_ai_admlog_range_{tid}_week")],
        [InlineKeyboardButton(PERIOD_LABELS["month"], callback_data=f"chess_ai_admlog_range_{tid}_month"),
         InlineKeyboardButton(PERIOD_LABELS["all"], callback_data=f"chess_ai_admlog_range_{tid}_all")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="chess_ai_admlog_menu")],
    ]
    await safe_edit_message_text(query,
        f"{box('🗂️ سوابق چت با هوش مصنوعی — ' + name)}\n\n📌 بازه‌ی زمانی را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )


async def chess_ai_admlog_range(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    parts = query.data.split("_")
    tid = int(parts[-2])
    period = parts[-1]
    admin = await db.get_admin(tid)
    name = (admin["display_name"] or admin["full_name"]) if admin else str(tid)

    games = await db.get_chess_ai_games_for_user(tid, period=period, limit=100)
    back_row = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"chess_ai_admlog_pick_{tid}")]]
    if not games:
        await safe_edit_message_text(query,
            f"{box('🗂️ سوابق چت با هوش مصنوعی — ' + name)}\n\n❗ در این بازه هیچ بازی‌ای با هوش مصنوعی پیدا نشد.",
            reply_markup=InlineKeyboardMarkup(back_row), parse_mode="Markdown")
        return

    lines = [f"{box('🗂️ چتِ ' + name + ' با هوش مصنوعی')}", f"🎮 تعداد بازی: `{len(games)}`", ""]
    for g in games:
        ai_is_white = g["white_id"] == AI_ID
        human_color = "سیاه" if ai_is_white else "سفید"
        lines.append(
            f"— بازی {_fmt_dt(g['created_at'])} · {_level_label(g['ai_level'])} · "
            f"مدیر با {human_color} —"
        )
        msgs = await db.get_chess_chat_messages(g["token"], 0)
        relevant = [m for m in msgs if m["sender_id"] in (tid, AI_ID)]
        if not relevant:
            lines.append("_(چتی رد و بدل نشده)_")
        for m in relevant:
            who = "🤖 هوش مصنوعی" if m["sender_id"] == AI_ID else f"👤 {name}"
            lines.append(f"{who}: {m['text']}")
        lines.append("")

    text = "\n".join(lines).strip()
    if len(text) > TRANSCRIPT_MAX_LEN:
        text = text[:TRANSCRIPT_MAX_LEN] + "\n\n… (متن کامل طولانی‌تر بود و کوتاه شد)"

    await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(back_row), parse_mode="Markdown")
