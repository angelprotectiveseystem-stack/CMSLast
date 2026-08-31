"""
chess_challenge.py
جریان «درخواست بازی شطرنج» بین مدیران و مدیر ارشد (پیشوا):
مدیر درخواست می‌فرستد ← طرف مقابل قبول/رد می‌کند ← در صورت قبول،
یک بازی ساخته و دکمه‌ی ورود به مینی‌اپ برای هر دو طرف ارسال می‌شود.
"""

import logging
import random

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
    rows.append([InlineKeyboardButton("🏆 جدول Elo شطرنج زنده", callback_data="chess_elo_board")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")])

    await safe_edit_message_text(
        query,
        f"{box('♟️ شطرنج زنده')}\n\n"
        "با یکی از مدیران محترم یا مدیر ارشد وارد یک بازی شطرنج زنده شوید.\n"
        "حریف خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )


async def chess_elo_board(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from elo import ensure_chess_elo_table, get_chess_elo_leaderboard, get_elo_title

    await ensure_chess_elo_table()
    rows = await get_chess_elo_leaderboard(15)
    if not rows:
        text = f"{box('🏆 جدول Elo شطرنج زنده')}\n\nهنوز هیچ بازی‌ای ثبت نشده است."
    else:
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, r in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{medal} {r['display_name']} — `{int(r['rating'])}` ({get_elo_title(r['rating'])})")
        text = f"{box('🏆 جدول Elo شطرنج زنده')}\n\n" + "\n".join(lines)

    await safe_edit_message_text(
        query, text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="chess_menu")]]),
        parse_mode=ParseMode.MARKDOWN,
    )


TIME_CONTROLS = [
    (180, "۳ دقیقه"),
    (300, "۵ دقیقه"),
    (600, "۱۰ دقیقه"),
    (900, "۱۵ دقیقه"),
    (1800, "۳۰ دقیقه"),
]
COLOR_LABELS = {"w": "⚪ سفید", "b": "⚫ سیاه", "r": "🎲 تصادفی"}


async def chess_pick_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """قدم اول بعد از انتخاب حریف: میزبان زمان بازی را انتخاب می‌کند."""
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

    await query.answer()
    rows = [
        [InlineKeyboardButton(label, callback_data=f"chess_time_{target_id}_{secs}")]
        for secs, label in TIME_CONTROLS
    ]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="chess_menu")])
    await safe_edit_message_text(
        query,
        f"{box('♟️ شطرنج زنده')}\n\n⏱ زمان فکر هر طرف را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )


async def chess_pick_color(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """قدم دوم: میزبان رنگ مهره‌های خودش را انتخاب می‌کند."""
    query = update.callback_query
    await query.answer()
    _, _, target_id, secs = query.data.split("_")
    rows = [
        [InlineKeyboardButton(COLOR_LABELS[c], callback_data=f"chess_go_{target_id}_{secs}_{c}")]
        for c in ("w", "b", "r")
    ]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="chess_menu")])
    await safe_edit_message_text(
        query,
        f"{box('♟️ شطرنج زنده')}\n\nبا کدام رنگ بازی می‌کنید؟",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )


async def chess_send_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    _, _, target_id, secs, color = query.data.split("_")
    target_id = int(target_id)
    time_control = int(secs)

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
    req_id = await db.create_chess_request(uid, target_id, time_control, color)
    requester_name = await _display_name(uid)
    time_label = next((lbl for s, lbl in TIME_CONTROLS if s == time_control), f"{time_control // 60} دقیقه")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ قبول", callback_data=f"chess_acc_{req_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"chess_dec_{req_id}"),
    ]])
    try:
        await ctx.bot.send_message(
            chat_id=target_id,
            text=f"{box('♟️ درخواست بازی شطرنج')}\n\n"
                 f"{requester_name} از شما درخواست یک بازی شطرنج زنده دارد.\n"
                 f"⏱ زمان: {time_label}\n"
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
    time_control = req["time_control"] or 300
    req_color = req["requester_color"] or "random"
    if req_color == "random":
        req_color = random.choice(["w", "b"])
    if req_color == "w":
        white_id, black_id = requester_id, uid
        white_name, black_name = requester_name, accepter_name
    else:
        white_id, black_id = uid, requester_id
        white_name, black_name = accepter_name, requester_name

    token = new_game_token()
    await db.create_chess_game(token, white_id, black_id, white_name, black_name, START_FEN, time_control)

    requester_is_white = white_id == requester_id
    await safe_edit_message_text(
        query,
        f"{box('♟️ بازی پذیرفته شد!')}\n\nبازی بین شما و {requester_name} آغاز شد. "
        f"شما با مهره‌های {'سیاه' if requester_is_white else 'سفید'} بازی می‌کنید.",
        reply_markup=_kb_play(token),
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        await ctx.bot.send_message(
            chat_id=requester_id,
            text=f"{box('♟️ درخواست شما پذیرفته شد!')}\n\n"
                 f"{accepter_name} درخواست بازی شما را قبول کرد. "
                 f"شما با مهره‌های {'سفید' if requester_is_white else 'سیاه'} بازی می‌کنید"
                 f"{'، نوبت شماست.' if requester_is_white else '.'}",
            reply_markup=_kb_play(token),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        logger.exception("Failed to notify requester %s", requester_id)

    await _announce_game_to_others(ctx, requester_id, uid, white_name, black_name, token)


async def _announce_game_to_others(ctx, player1_id, player2_id, white_name, black_name, token):
    """به بقیه‌ی مدیران (و پیشوا، در صورتی که خودش بازیکن نباشد) خبر می‌دهد که
    یک بازی شطرنج زنده در جریان است و امکان تماشا و ارسال پیام را می‌دهد."""
    notify_ids = set()
    if player1_id != PISHVA_ID and player2_id != PISHVA_ID:
        notify_ids.add(PISHVA_ID)
    admins = await db.get_active_admins()
    for a in admins:
        tid = a["telegram_id"]
        if tid not in (player1_id, player2_id):
            notify_ids.add(tid)

    if not notify_ids:
        return
    text = (
        f"{box('♟️ یک بازی شطرنج زنده در جریان است')}\n\n"
        f"⚪ {white_name}  در مقابل  ⚫ {black_name}\n\n"
        "می‌توانید بازی را زنده تماشا کنید و حتی در گفتگوی آن پیام بدهید."
    )
    for tid in notify_ids:
        try:
            await ctx.bot.send_message(
                chat_id=tid, text=text, reply_markup=_kb_spectate(token), parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            logger.exception("Failed to notify %s about ongoing chess game", tid)


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


def _kb_spectate(token: str) -> InlineKeyboardMarkup:
    if not WEBAPP_URL:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
    url = f"{WEBAPP_URL}/webapp/?token={token}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁 تماشای بازی", web_app=WebAppInfo(url=url))],
    ])


def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]])
