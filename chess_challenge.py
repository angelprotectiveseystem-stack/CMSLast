"""
chess_challenge.py
جریان «درخواست بازی شطرنج» بین مدیران و مدیر ارشد (پیشوا):
مدیر درخواست می‌فرستد ← طرف مقابل قبول/رد می‌کند ← در صورت قبول،
یک بازی ساخته و دکمه‌ی ورود به مینی‌اپ برای هر دو طرف ارسال می‌شود.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import database as db
from config import PISHVA_ID, WEBAPP_URL
from game_server import new_game_token
from helpers import safe_edit_message_text, box, pishva_display

logger = logging.getLogger(__name__)

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


async def _display_name(user_id: int) -> str:
    if user_id == PISHVA_ID:
        return await pishva_display()
    admin = await db.get_admin(user_id)
    if admin:
        return admin["display_name"] or admin["full_name"]
    return "ادمین"


async def _eligible_opponents(requester_id: int):
    """پیشوا + همه‌ی مدیران فعال به‌جز خود درخواست‌دهنده."""
    opponents = []
    if requester_id != PISHVA_ID:
        opponents.append((PISHVA_ID, await pishva_display()))
    admins = await db.get_active_admins()
    for a in admins:
        if a["telegram_id"] != requester_id:
            opponents.append((a["telegram_id"], a["display_name"] or a["full_name"]))
    return opponents


async def chess_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    active_game = await db.get_active_chess_game_for(uid)
    if active_game:
        await safe_edit_message_text(
            query,
            f"{box('♟️ شطرنج زنده')}\n\n"
            f"⏳ شما یک بازی فعال دارید. برای ادامه، روی دکمه‌ی زیر بزنید:",
            reply_markup=_kb_resume(active_game["token"]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    opponents = await _eligible_opponents(uid)
    if not opponents:
        await safe_edit_message_text(
            query,
            f"{box('♟️ شطرنج زنده')}\n\nهیچ مدیر دیگری برای دعوت به بازی پیدا نشد.",
            reply_markup=_kb_back(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    rows = []
    for opp_id, name in opponents:
        label = ("👑 " if opp_id == PISHVA_ID else "🎖️ ") + name
        rows.append([InlineKeyboardButton(label, callback_data=f"chess_req_{opp_id}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")])

    await safe_edit_message_text(
        query,
        f"{box('♟️ شطرنج زنده')}\n\n"
        "با یکی از مدیران محترم یا مدیر ارشد وارد یک بازی شطرنج زنده شوید.\n"
        "حریف خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )


async def chess_send_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    target_id = int(query.data.split("_")[-1])

    if target_id == uid:
        await query.answer("نمی‌توانید به خودتان درخواست بدهید.", show_alert=True)
        return

    if await db.has_pending_chess_request(uid, target_id):
        await query.answer("درخواست قبلی هنوز در انتظار پاسخ است.", show_alert=True)
        return

    active_game = await db.get_active_chess_game_for(uid)
    if active_game:
        await query.answer("شما یک بازی فعال دارید؛ ابتدا آن را تمام کنید.", show_alert=True)
        return

    await query.answer("درخواست ارسال شد ✅")
    req_id = await db.create_chess_request(uid, target_id)
    requester_name = await _display_name(uid)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ قبول", callback_data=f"chess_acc_{req_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"chess_dec_{req_id}"),
    ]])
    try:
        await ctx.bot.send_message(
            chat_id=target_id,
            text=f"{box('♟️ درخواست بازی شطرنج')}\n\n"
                 f"{requester_name} از شما درخواست یک بازی شطرنج زنده دارد.\n"
                 f"آیا قبول می‌کنید؟",
            reply_markup=kb,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        logger.exception("Failed to deliver chess request to %s", target_id)

    await safe_edit_message_text(
        query,
        f"{box('♟️ شطرنج زنده')}\n\n"
        f"⏳ درخواست بازی برای {await _display_name(target_id)} ارسال شد.\n"
        f"به محض پاسخ ایشان به شما اطلاع داده می‌شود.",
        reply_markup=_kb_back(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def chess_accept(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    req_id = int(query.data.split("_")[-1])
    req = await db.get_chess_request(req_id)

    if not req or req["status"] != "pending" or req["target_id"] != uid:
        await query.answer("این درخواست دیگر معتبر نیست.", show_alert=True)
        return

    await query.answer()
    await db.set_chess_request_status(req_id, "accepted")

    requester_id = req["requester_id"]
    requester_name = await _display_name(requester_id)
    accepter_name = await _display_name(uid)

    token = new_game_token()
    await db.create_chess_game(token, requester_id, uid, requester_name, accepter_name, START_FEN)

    await safe_edit_message_text(
        query,
        f"{box('♟️ بازی پذیرفته شد!')}\n\nبازی بین شما و {requester_name} آغاز شد.",
        reply_markup=_kb_play(token),
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        await ctx.bot.send_message(
            chat_id=requester_id,
            text=f"{box('♟️ درخواست شما پذیرفته شد!')}\n\n"
                 f"{accepter_name} درخواست بازی شما را قبول کرد. نوبت شماست (سفید).",
            reply_markup=_kb_play(token),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        logger.exception("Failed to notify requester %s", requester_id)


async def chess_decline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    req_id = int(query.data.split("_")[-1])
    req = await db.get_chess_request(req_id)

    if not req or req["status"] != "pending" or req["target_id"] != uid:
        await query.answer("این درخواست دیگر معتبر نیست.", show_alert=True)
        return

    await query.answer("درخواست رد شد.")
    await db.set_chess_request_status(req_id, "declined")
    await safe_edit_message_text(
        query,
        f"{box('♟️ درخواست رد شد')}\n\nشما این درخواست بازی را رد کردید.",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        await ctx.bot.send_message(
            chat_id=req["requester_id"],
            text=f"{box('♟️ درخواست رد شد')}\n\n{await _display_name(uid)} درخواست بازی شما را رد کرد.",
        )
    except Exception:
        logger.exception("Failed to notify decline to %s", req["requester_id"])


def _kb_play(token: str) -> InlineKeyboardMarkup:
    if not WEBAPP_URL:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
    url = f"{WEBAPP_URL}/webapp/?token={token}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♟️ ورود به بازی", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])


def _kb_resume(token: str) -> InlineKeyboardMarkup:
    return _kb_play(token)


def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
