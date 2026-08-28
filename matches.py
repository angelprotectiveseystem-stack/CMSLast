import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import (safe_edit_message_text, box, separator, now_shamsi, today_gregorian, today_shamsi,
    notify_pishva, check_status_gate, smart_lottery, progress_bar, check_perm)
from config import (PISHVA_ID, ST_MATCH_WHITE, ST_MATCH_BLACK, ST_MATCH_DATE,
    ST_MATCH_DRAW_REASON, ST_MATCH_CANCEL_REASON, ST_SEARCH_MATCH, ST_ADV_LOTTERY_SCOPE,
    ST_ADV_LOTTERY_CLASS_A, ST_ADV_LOTTERY_CLASS_B, ST_ADV_LOTTERY_COUNT)

PLAYER_PAGE_SIZE = 8
PENDING_PAGE_SIZE = 10

def _page_hint(players, page, page_size=PLAYER_PAGE_SIZE):
    total = len(players)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return (f"📄 صفحه {page+1} از {total_pages} ({total} نفر)\n"
            f"🔍 برای جستجوی سریع، بخشی از اسم رو تایپ کنید (یا «همه» برای پاک کردن فیلتر)")

# ─── Add Match ────────────────────────────────────────────────
async def match_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    match_on = await db.get_setting("match_registration_enabled", "1")
    if match_on != "1":
        await query.answer("♟️ ثبت مسابقه غیرفعال است.", show_alert=True)
        return ConversationHandler.END
    if await check_status_gate(query, "match_registration"):
        return ConversationHandler.END
    if await check_perm(query, "match_management"):
        return ConversationHandler.END
    await query.answer()
    players = await db.get_continuing_players()
    if len(players) < 2:
        await safe_edit_message_text(query, 
            f"❌ *خطا — کد ۰۰۱*\n\nحداقل دو بازیکن ادامه‌دهنده برای شروع مسابقه وجود ندارد.",
            reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
        return ConversationHandler.END
    ctx.user_data["match_players_pool"] = [dict(p) for p in players]
    ctx.user_data["mw_view"] = ctx.user_data["match_players_pool"]
    ctx.user_data["mw_page"] = 0
    ctx.user_data.pop("match_white", None)
    ctx.user_data.pop("match_black", None)
    await safe_edit_message_text(query, 
        f"{box('➕ ثبت مسابقه جدید')}\n\n⬜ مرحله ۱: بازیکن *سفید* را انتخاب کنید:\n\n"
        f"{_page_hint(players, 0)}",
        reply_markup=kb.kb_player_select(players, "mwhite", "matches", page=0, nav_prefix="mw"),
        parse_mode="Markdown")
    return ST_MATCH_WHITE

async def match_white_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    ctx.user_data["mw_page"] = page
    view = ctx.user_data.get("mw_view", ctx.user_data.get("match_players_pool", []))
    await safe_edit_message_text(query, 
        f"{box('➕ ثبت مسابقه جدید')}\n\n⬜ مرحله ۱: بازیکن *سفید* را انتخاب کنید:\n\n"
        f"{_page_hint(view, page)}",
        reply_markup=kb.kb_player_select(view, "mwhite", "matches", page=page, nav_prefix="mw"),
        parse_mode="Markdown")
    return ST_MATCH_WHITE

async def match_white_search_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    full_pool = ctx.user_data.get("match_players_pool", [])
    if text in ("همه", "reset", "all"):
        view = full_pool
    else:
        view = [p for p in full_pool if text in p["full_name"]]
    ctx.user_data["mw_view"] = view
    ctx.user_data["mw_page"] = 0
    if not view:
        await update.message.reply_text(
            "❌ کسی با این اسم پیدا نشد. دوباره تایپ کنید یا «همه» را بفرستید.")
        return ST_MATCH_WHITE
    await update.message.reply_text(
        f"{box('➕ ثبت مسابقه جدید')}\n\n⬜ مرحله ۱: بازیکن *سفید* را انتخاب کنید:\n\n"
        f"{_page_hint(view, 0)}",
        reply_markup=kb.kb_player_select(view, "mwhite", "matches", page=0, nav_prefix="mw"),
        parse_mode="Markdown")
    return ST_MATCH_WHITE

async def match_white_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    white_id = int(query.data.split("_")[-1])
    ctx.user_data["match_white"] = white_id
    wp = await db.get_player(white_id)
    pool = [p for p in ctx.user_data.get("match_players_pool", []) if p["id"] != white_id]
    ctx.user_data["match_black_pool"] = pool
    ctx.user_data["mb_view"] = pool
    ctx.user_data["mb_page"] = 0
    await safe_edit_message_text(query, 
        f"{box('➕ ثبت مسابقه جدید')}\n\n"
        f"⬜ سفید: *{wp['full_name']}*\n\n"
        f"⬛ مرحله ۲: بازیکن *سیاه* را انتخاب کنید:\n\n"
        f"{_page_hint(pool, 0)}",
        reply_markup=kb.kb_player_select(pool, "mblack", "matches", page=0, nav_prefix="mb"),
        parse_mode="Markdown")
    return ST_MATCH_BLACK

async def match_black_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    ctx.user_data["mb_page"] = page
    view = ctx.user_data.get("mb_view", ctx.user_data.get("match_black_pool", []))
    wp = await db.get_player(ctx.user_data.get("match_white"))
    wname = wp["full_name"] if wp else ""
    await safe_edit_message_text(query, 
        f"{box('➕ ثبت مسابقه جدید')}\n\n"
        f"⬜ سفید: *{wname}*\n\n"
        f"⬛ مرحله ۲: بازیکن *سیاه* را انتخاب کنید:\n\n"
        f"{_page_hint(view, page)}",
        reply_markup=kb.kb_player_select(view, "mblack", "matches", page=page, nav_prefix="mb"),
        parse_mode="Markdown")
    return ST_MATCH_BLACK

async def match_black_search_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    full_pool = ctx.user_data.get("match_black_pool", [])
    if text in ("همه", "reset", "all"):
        view = full_pool
    else:
        view = [p for p in full_pool if text in p["full_name"]]
    ctx.user_data["mb_view"] = view
    ctx.user_data["mb_page"] = 0
    if not view:
        await update.message.reply_text(
            "❌ کسی با این اسم پیدا نشد. دوباره تایپ کنید یا «همه» را بفرستید.")
        return ST_MATCH_BLACK
    wp = await db.get_player(ctx.user_data.get("match_white"))
    wname = wp["full_name"] if wp else ""
    await update.message.reply_text(
        f"{box('➕ ثبت مسابقه جدید')}\n\n"
        f"⬜ سفید: *{wname}*\n\n"
        f"⬛ مرحله ۲: بازیکن *سیاه* را انتخاب کنید:\n\n"
        f"{_page_hint(view, 0)}",
        reply_markup=kb.kb_player_select(view, "mblack", "matches", page=0, nav_prefix="mb"),
        parse_mode="Markdown")
    return ST_MATCH_BLACK

async def match_black_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    black_id = int(query.data.split("_")[-1])
    ctx.user_data["match_black"] = black_id
    wp = await db.get_player(ctx.user_data["match_white"])
    bp = await db.get_player(black_id)
    today_g = today_gregorian()
    today_s = today_shamsi()
    await safe_edit_message_text(query, 
        f"{box('➕ ثبت مسابقه جدید')}\n\n"
        f"⬜ سفید: *{wp['full_name']}*\n"
        f"⬛ سیاه: *{bp['full_name']}*\n\n"
        f"📅 تاریخ مسابقه را وارد کنید:\n_(فرمت: {today_g})_",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📅 امروز ({today_s})", callback_data="mdate_today")]
        ]),
        parse_mode="Markdown")
    return ST_MATCH_DATE

async def match_date_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["match_date"] = today_gregorian()
    return await _finalize_match(update, ctx, via_query=True)

async def match_date_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["match_date"] = update.message.text.strip()
    return await _finalize_match(update, ctx, via_query=False)

async def _finalize_match(update, ctx, via_query: bool):
    white_id = ctx.user_data.get("match_white")
    black_id = ctx.user_data.get("match_black")
    date = ctx.user_data.get("match_date", today_gregorian())
    uid = update.effective_user.id
    if not white_id or not black_id:
        msg = "❌ خطا. دوباره از ابتدا شروع کنید."
        if via_query:
            await update.callback_safe_edit_message_text(query, msg)
        else:
            await update.message.reply_text(msg)
        return ConversationHandler.END
    default_t = await db.get_default_tournament()
    tid = default_t["id"] if default_t else None
    mid = await db.create_match(white_id, black_id, date, tid, uid)
    wp = await db.get_player(white_id)
    bp = await db.get_player(black_id)
    await db.log_action(uid, "create_match", f"{wp['full_name']} vs {bp['full_name']}", mid)
    text = (
        f"✅ *مسابقه ثبت شد!*\n\n"
        f"╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼\n"
        f"⬜ سفید: *{wp['full_name']}*\n"
        f"⬛ سیاه: *{bp['full_name']}*\n"
        f"📅 تاریخ: `{date}`\n"
        f"🆔 شناسه: `{mid}`\n"
        f"⏱️ `{now_shamsi()}`\n"
        f"╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 ثبت نتیجه", callback_data="match_result"),
        InlineKeyboardButton("✅ بازگشت", callback_data="back_matches")],
    ])
    if via_query:
        await update.callback_safe_edit_message_text(query, text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return ConversationHandler.END

# ─── Match Result ─────────────────────────────────────────────
def _render_pending_page(pending, page):
    total = len(pending)
    total_pages = max(1, (total + PENDING_PAGE_SIZE - 1) // PENDING_PAGE_SIZE)
    start = page * PENDING_PAGE_SIZE
    page_items = pending[start:start + PENDING_PAGE_SIZE]
    rows = []
    for m in page_items:
        label = f"⬜{m['white_name']} ⚔️ {m['black_name']}⬛"
        if m["claimed_by_name"]:
            label += f" — 🔒{m['claimed_by_name']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"result_select_{m['id']}")])
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"mrpage_{page-1}"))
    if start + PENDING_PAGE_SIZE < total:
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"mrpage_{page+1}"))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches")])
    text = (f"{box('🏆 ثبت نتیجه')}\n\n📌 مسابقه را انتخاب کنید:\n\n"
            f"📄 صفحه {page+1} از {total_pages} ({total} مسابقه بدون نتیجه)\n"
            f"🔒 = یه ادمین دیگه داره روش کار می‌کنه")
    return text, InlineKeyboardMarkup(rows)

async def match_result_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending = await db.get_pending_matches()
    if not pending:
        await safe_edit_message_text(query, 
            f"{box('🏆 ثبت نتیجه')}\n\n✅ همه مسابقات نتیجه دارند.",
            reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
        return
    ctx.user_data["mr_pending"] = pending
    text, markup = _render_pending_page(pending, 0)
    await safe_edit_message_text(query, text, reply_markup=markup, parse_mode="Markdown")

async def match_result_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    pending = await db.get_pending_matches()  # تازه می‌خونیم تا وضعیت claim به‌روز باشه
    ctx.user_data["mr_pending"] = pending
    if not pending:
        await safe_edit_message_text(query, 
            f"{box('🏆 ثبت نتیجه')}\n\n✅ همه مسابقات نتیجه دارند.",
            reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
        return
    text, markup = _render_pending_page(pending, page)
    await safe_edit_message_text(query, text, reply_markup=markup, parse_mode="Markdown")

async def match_result_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    m = await db.get_match(mid)
    await db.claim_match(mid, query.from_user.id)  # فقط برای نمایش به بقیه ادمین‌ها
    await safe_edit_message_text(query, 
        f"{box('🏆 ثبت نتیجه')}\n\n"
        f"⬜ سفید: *{m['white_name']}*\n"
        f"⬛ سیاه: *{m['black_name']}*\n\n"
        f"📌 نتیجه را انتخاب کنید:",
        reply_markup=kb.kb_match_result_options(mid, m["white_name"], m["black_name"]),
        parse_mode="Markdown")

async def result_white(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    m = await db.get_match(mid)
    try:
        recorded = await db.record_match_result(mid, "white", "", query.from_user.id)
    except Exception:
        await safe_edit_message_text(query, 
            "⚠️ خطایی هنگام ثبت نتیجه پیش اومد. این مسابقه ممکنه دیتای ناقص "
            "داشته باشه — به مدیر ارشد اطلاع داده شد، لطفاً دستی چک کنید.")
        await notify_pishva(query.get_bot(),
            f"🚨 ثبت نتیجه مسابقه {mid} (برد سفید) با خطا مواجه شد. لطفاً دستی بررسی کنید.")
        return
    if not recorded:
        await query.answer("این مسابقه قبلاً نتیجه‌اش ثبت شده.", show_alert=True)
        return
    await db.log_action(query.from_user.id, "match_result", f"برد سفید — مسابقه {mid}", mid)
    chg_w = chg_b = 0
    try:
        from elo import update_elo_after_match, ensure_elo_table
        await ensure_elo_table()
        _, _, chg_w, chg_b = await update_elo_after_match(
            m["white_player_id"], m["black_player_id"], "white", mid)
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"Elo update failed: {e}")
    try:
        from features import announce_match_result
        await announce_match_result(query.get_bot(), mid, "white",
            m["white_name"], m["black_name"], chg_w, chg_b)
    except Exception:
        pass
    loser = await db.get_player(m["black_player_id"])
    warn = ""
    if loser["is_elite"] or loser["is_special"]:
        icon = "🌟" if loser["is_elite"] else "⚡"
        warn = f"\n\n⚠️ *توجه:* {loser['full_name']} {icon} است!"
    w_sign = "+" if chg_w >= 0 else ""
    b_sign = "+" if chg_b >= 0 else ""
    elo_txt = f"\n📊 Elo: ⬜`{w_sign}{chg_w}` | ⬛`{b_sign}{chg_b}`" if chg_w or chg_b else ""
    await safe_edit_message_text(query, 
        f"🥇 برد *{m['white_name']}* ثبت شد.{elo_txt}{warn}\n\n"
        f"آیا می‌خواهید *{m['black_name']}* حذف شود؟",
        reply_markup=kb.kb_eliminate_ask(m["black_player_id"], m["black_name"]),
        parse_mode="Markdown")

async def result_black(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    m = await db.get_match(mid)
    try:
        recorded = await db.record_match_result(mid, "black", "", query.from_user.id)
    except Exception:
        await safe_edit_message_text(query, 
            "⚠️ خطایی هنگام ثبت نتیجه پیش اومد. این مسابقه ممکنه دیتای ناقص "
            "داشته باشه — به مدیر ارشد اطلاع داده شد، لطفاً دستی چک کنید.")
        await notify_pishva(query.get_bot(),
            f"🚨 ثبت نتیجه مسابقه {mid} (برد سیاه) با خطا مواجه شد. لطفاً دستی بررسی کنید.")
        return
    if not recorded:
        await query.answer("این مسابقه قبلاً نتیجه‌اش ثبت شده.", show_alert=True)
        return
    await db.log_action(query.from_user.id, "match_result", f"برد سیاه — مسابقه {mid}", mid)
    chg_w = chg_b = 0
    try:
        from elo import update_elo_after_match, ensure_elo_table
        await ensure_elo_table()
        _, _, chg_w, chg_b = await update_elo_after_match(
            m["white_player_id"], m["black_player_id"], "black", mid)
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"Elo update failed: {e}")
    try:
        from features import announce_match_result
        await announce_match_result(query.get_bot(), mid, "black",
            m["white_name"], m["black_name"], chg_w, chg_b)
    except Exception:
        pass
    loser = await db.get_player(m["white_player_id"])
    warn = ""
    if loser["is_elite"] or loser["is_special"]:
        icon = "🌟" if loser["is_elite"] else "⚡"
        warn = f"\n\n⚠️ *توجه:* {loser['full_name']} {icon} است!"
    w_sign = "+" if chg_w >= 0 else ""
    b_sign = "+" if chg_b >= 0 else ""
    elo_txt = f"\n📊 Elo: ⬜`{w_sign}{chg_w}` | ⬛`{b_sign}{chg_b}`" if chg_w or chg_b else ""
    await safe_edit_message_text(query, 
        f"🥇 برد *{m['black_name']}* ثبت شد.{elo_txt}{warn}\n\n"
        f"آیا می‌خواهید *{m['white_name']}* حذف شود؟",
        reply_markup=kb.kb_eliminate_ask(m["white_player_id"], m["white_name"]),
        parse_mode="Markdown")

async def result_draw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    await safe_edit_message_text(query, 
        "🤝 علت تساوی را انتخاب کنید:",
        reply_markup=kb.kb_draw_reasons(mid))

async def draw_reason(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    reason_key = parts[1]
    mid = int(parts[-1])
    reason_map = {"pat": "پات", "time": "اتمام زمان", "moves": "حرکات بسیار", "repeat": "سه تکرار"}
    if reason_key == "other":
        ctx.user_data["draw_match"] = mid
        await safe_edit_message_text(query, "📝 دلیل تساوی را بنویسید:")
        return ST_MATCH_DRAW_REASON
    reason = reason_map.get(reason_key, reason_key)
    m = await db.get_match(mid)
    try:
        recorded = await db.record_match_result(mid, "draw", reason, query.from_user.id)
    except Exception:
        await safe_edit_message_text(query, 
            "⚠️ خطایی هنگام ثبت نتیجه پیش اومد. این مسابقه ممکنه دیتای ناقص "
            "داشته باشه — به مدیر ارشد اطلاع داده شد، لطفاً دستی چک کنید.")
        await notify_pishva(query.get_bot(),
            f"🚨 ثبت نتیجه مسابقه {mid} (تساوی) با خطا مواجه شد. لطفاً دستی بررسی کنید.")
        return
    if not recorded:
        await query.answer("این مسابقه قبلاً نتیجه‌اش ثبت شده.", show_alert=True)
        return
    await db.log_action(query.from_user.id, "match_result", f"تساوی ({reason}) — {mid}", mid)
    chg_w = chg_b = 0
    try:
        from elo import update_elo_after_match, ensure_elo_table
        await ensure_elo_table()
        _, _, chg_w, chg_b = await update_elo_after_match(
            m["white_player_id"], m["black_player_id"], "draw", mid)
    except Exception:
        pass
    try:
        from features import announce_match_result
        await announce_match_result(query.get_bot(), mid, "draw",
            m["white_name"], m["black_name"], chg_w, chg_b)
    except Exception:
        pass
    w_sign = "+" if chg_w >= 0 else ""
    b_sign = "+" if chg_b >= 0 else ""
    elo_txt = f"\n📊 Elo: ⬜`{w_sign}{chg_w}` | ⬛`{b_sign}{chg_b}`" if chg_w or chg_b else ""
    await safe_edit_message_text(query, 
        f"🤝 تساوی ثبت شد.\n📋 علت: *{reason}*{elo_txt}",
        reply_markup=kb.kb_back("matches"), parse_mode="Markdown")

async def draw_reason_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    mid = ctx.user_data.get("draw_match")
    if mid:
        try:
            recorded = await db.record_match_result(mid, "draw", reason, update.effective_user.id)
        except Exception:
            await update.message.reply_text(
                "⚠️ خطایی هنگام ثبت نتیجه پیش اومد. این مسابقه ممکنه دیتای ناقص "
                "داشته باشه — به مدیر ارشد اطلاع داده شد، لطفاً دستی چک کنید.")
            await notify_pishva(ctx.bot,
                f"🚨 ثبت نتیجه مسابقه {mid} (تساوی) با خطا مواجه شد. لطفاً دستی بررسی کنید.")
            return ConversationHandler.END
        if not recorded:
            await update.message.reply_text("این مسابقه قبلاً نتیجه‌اش ثبت شده.")
            return ConversationHandler.END
        await db.log_action(update.effective_user.id, "match_result", f"تساوی ({reason}) — {mid}", mid)
        await update.message.reply_text(
            f"🤝 تساوی ثبت شد.\n📋 علت: *{reason}*",
            reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
    return ConversationHandler.END

async def result_cancel_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    ctx.user_data["cancel_match"] = mid
    await safe_edit_message_text(query, "📝 دلیل لغو مسابقه را بنویسید:")
    return ST_MATCH_CANCEL_REASON

async def match_cancel_reason_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    mid = ctx.user_data.pop("cancel_match", None)
    if mid:
        m = await db.get_match(mid)
        await db.set_match_result(mid, "cancelled", reason, update.effective_user.id)
        await db.log_action(update.effective_user.id, "match_result",
            f"لغو مسابقه ({reason}) — {mid}", mid)
        await update.message.reply_text(
            f"❌ مسابقه *{m['white_name']}* ⚔️ *{m['black_name']}* لغو شد.\n📋 دلیل: {reason}",
            reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
    return ConversationHandler.END

async def eliminate_yes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = await db.get_player(pid)
    await db.update_player(pid, status="eliminated")
    await db.log_action(query.from_user.id, "eliminate_player", f"حذف: {p['full_name']}", pid)
    await safe_edit_message_text(query, 
        f"⛔ *{p['full_name']}* از لیست ادامه‌دهندگان حذف شد.",
        reply_markup=kb.kb_back("matches"), parse_mode="Markdown")

async def eliminate_no(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await safe_edit_message_text(query, 
        "✅ بازیکن در لیست ادامه‌دهندگان باقی ماند.",
        reply_markup=kb.kb_back("matches"))

# ─── History ──────────────────────────────────────────────────
async def match_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await safe_edit_message_text(query, 
        f"{box('🔍 تاریخچه مسابقات')}\n\n📌 فیلتر را انتخاب کنید:",
        reply_markup=kb.kb_match_history_filter(), parse_mode="Markdown")

async def match_hist_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.split("_")[-1]
    matches = await db.get_matches_by_filter(period)
    label = {"today": "امروز", "week": "این هفته", "month": "این ماه", "all": "کل"}.get(period, period)
    if not matches:
        await safe_edit_message_text(query, f"❗ مسابقه‌ای در {label} یافت نشد.",
            reply_markup=kb.kb_match_history_filter())
        return
    await safe_edit_message_text(query, 
        f"{box('📋 مسابقات — ' + label)} ({len(matches)} مسابقه)",
        reply_markup=kb.kb_match_list(matches), parse_mode="Markdown")

async def match_hist_search_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await safe_edit_message_text(query, "🔍 نام بازیکن یا تاریخ را وارد کنید:")
    return ST_SEARCH_MATCH

async def match_hist_search_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    matches = await db.search_matches(q)
    if not matches:
        await update.message.reply_text("❗ نتیجه‌ای یافت نشد.", reply_markup=kb.kb_back("match_history"))
        return ConversationHandler.END
    await update.message.reply_text(f"🔍 نتایج ({len(matches)}):", reply_markup=kb.kb_match_list(matches))
    return ConversationHandler.END

async def match_full_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    matches = await db.get_matches_by_filter("all")
    if not matches:
        await safe_edit_message_text(query, "❗ هیچ مسابقه‌ای ثبت نشده.", reply_markup=kb.kb_back("matches"))
        return
    await safe_edit_message_text(query, 
        f"{box('📋 تاریخچه کامل')} ({len(matches)} مسابقه)",
        reply_markup=kb.kb_match_list(matches), parse_mode="Markdown")

async def match_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    m = await db.get_match(mid)
    if not m:
        await query.answer("مسابقه یافت نشد.", show_alert=True)
        return
    result_map = {
        "white": f"🥇 برد {m['white_name']}",
        "black": f"🥇 برد {m['black_name']}",
        "draw": "🤝 تساوی", "cancelled": "❌ لغو شده", None: "⏳ بدون نتیجه"
    }
    admin_name = "—"
    if m["created_by"]:
        if m["created_by"] == PISHVA_ID:
            admin_name = await db.get_setting("pishva_display_name", "مدیر ارشد")
        else:
            a = await db.get_admin(m["created_by"])
            admin_name = a["display_name"] or a["full_name"] if a else str(m["created_by"])
    reason_label = "📋 دلیل لغو" if m["result"] == "cancelled" else "📋 علت تساوی"
    text = (
        f"{box('♟️ جزئیات مسابقه')}\n\n"
        f"⬜ سفید: *{m['white_name']}*\n"
        f"⬛ سیاه: *{m['black_name']}*\n"
        f"🏆 نتیجه: {result_map.get(m['result'], '—')}\n"
        f"{reason_label}: {m['draw_reason'] or '—'}\n"
        f"📅 تاریخ: `{m['match_date'] or '—'}`\n"
        f"👤 ثبت‌کننده: {admin_name}\n"
        f"⏱️ `{str(m['created_at'] or '')[:16]}`\n"
        f"{'📌 پین‌شده' if m['is_pinned'] else ''}"
    )
    await safe_edit_message_text(query, text, reply_markup=kb.kb_match_item_actions(mid), parse_mode="Markdown")

async def match_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if await check_status_gate(query, "match_delete"):
        return
    if uid != PISHVA_ID:
        perm = await db.get_admin_permission(uid, "edit_delete_match")
        if not perm:
            await query.answer("⛔ شما اجازه حذف مسابقه ندارید.", show_alert=True)
            return
    await query.answer()
    mid = int(query.data.split("_")[-1])
    await db.delete_match(mid)
    await db.log_action(uid, "delete_match", f"حذف مسابقه {mid}", mid)
    await safe_edit_message_text(query, "🗑️ مسابقه حذف شد.", reply_markup=kb.kb_back("match_history"))

async def match_pin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_perm(query, "match_management"):
        return
    await query.answer()
    mid = int(query.data.split("_")[-1])
    m = await db.get_match(mid)
    new_pin = 0 if m["is_pinned"] else 1
    await db.update_match(mid, is_pinned=new_pin)
    label = "📌 پین شد" if new_pin else "پین برداشته شد"
    await safe_edit_message_text(query, label, reply_markup=kb.kb_back("match_history"))

async def match_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    matches = await db.get_matches_by_filter("all")
    players = await db.get_all_players()
    default_t = await db.get_default_tournament()
    top_players = sorted(players, key=lambda p: p["wins"], reverse=True)[:5]
    top_lines = "\n".join(
        [f"  `{i+1}.` {p['full_name']} — ✅{p['wins']} 🤝{p['draws']} ❌{p['losses']}"
         for i, p in enumerate(top_players)]
    ) or "  _هنوز آماری ثبت نشده_"
    total_m = len(matches)
    done_m = sum(1 for m in matches if m["result"])
    pct = int(done_m / total_m * 100) if total_m > 0 else 0
    bar = progress_bar(pct)
    text = (
        f"{box('📊 پنل مدیریت مسابقات')}\n\n"
        f"🏅 تورنمنت فعال: *{default_t['name'] if default_t else 'ندارد'}*\n\n"
        f"{separator('📈 آمار کلی')}\n"
        f"♟️ کل: `{total_m}` | ✅ با نتیجه: `{done_m}` | ⏳ بدون نتیجه: `{total_m - done_m}`\n"
        f"👥 بازیکنان: `{len(players)}`\n"
        f"🏁 پیشرفت: `{bar}`\n\n"
        f"{separator('🌟 برترین بازیکنان')}\n"
        f"{top_lines}"
    )
    await safe_edit_message_text(query, text, reply_markup=kb.kb_back("matches"), parse_mode="Markdown")

# ─── Lottery (ساده) ────────────────────────────────────────────
async def lottery_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await safe_edit_message_text(query, 
        f"{box('🎲 قرعه‌کشی هوشمند')}\n\n📌 محدوده بازیکنان:",
        reply_markup=kb.kb_lottery_scope(), parse_mode="Markdown")

async def lottery_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["lottery_scope"] = "all"
    players = await db.get_continuing_players()
    await _run_lottery(query, ctx, players)

async def lottery_class_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    classes = await db.get_all_classes()
    rows = []
    for i in range(0, len(classes), 2):
        row = [InlineKeyboardButton(f"🏫 {c['name']}", callback_data=f"lclass_{c['id']}") for c in classes[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="lottery_start")])
    await safe_edit_message_text(query, "🏫 کلاس را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(rows))

async def lottery_class_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    ctx.user_data["lottery_scope"] = "class"
    ctx.user_data["lottery_class"] = cid
    players = await db.get_continuing_players()
    players = [p for p in players if p["class_id"] == cid]
    await _run_lottery(query, ctx, players)

async def _run_lottery(query, ctx, players):
    if len(players) < 2:
        await safe_edit_message_text(query, "❌ تعداد بازیکنان کمتر از ۲ نفر است.",
            reply_markup=kb.kb_back("matches"))
        return
    p1, p2, all_played = await smart_lottery(players)
    ctx.user_data["lottery_p1"] = p1["id"]
    ctx.user_data["lottery_p2"] = p2["id"]
    warn = "\n\n⚠️ همه بازیکنان قبلاً با هم بازی کرده‌اند. قرعه‌کشی تصادفی انجام شد." if all_played else ""
    text = (
        f"╼╼╼╼╼╼ 🎲 نتیجه قرعه‌کشی ╾╾╾╾╾╾\n\n"
        f"⬜ سفید: *{p1['full_name']}* [{p1['class_name'] if p1['class_name'] else ''}]\n"
        f"⬛ سیاه: *{p2['full_name']}* [{p2['class_name'] if p2['class_name'] else ''}]\n\n"
        f"📅 تاریخ پیشنهادی: `{today_shamsi()}`"
        f"{warn}\n╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼"
    )
    await safe_edit_message_text(query, 
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تأیید و ثبت", callback_data=f"lottery_confirm_{p1['id']}_{p2['id']}")],
            [InlineKeyboardButton("🔄 قرعه‌کشی مجدد", callback_data="lottery_redo"),
            InlineKeyboardButton("✏️ ویرایش دستی", callback_data="lottery_manual")],
        ]),
        parse_mode="Markdown")

async def lottery_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    p1_id = int(parts[-2])
    p2_id = int(parts[-1])
    ctx.user_data["match_white"] = p1_id
    ctx.user_data["match_black"] = p2_id
    ctx.user_data["match_players_pool"] = []
    today_s = today_shamsi()
    await safe_edit_message_text(query, 
        f"📅 تاریخ مسابقه را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📅 امروز ({today_s})", callback_data="mdate_today")]
        ]))
    return ST_MATCH_DATE

async def lottery_redo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    scope = ctx.user_data.get("lottery_scope", "all")
    if scope == "class":
        cid = ctx.user_data.get("lottery_class")
        players = await db.get_continuing_players()
        players = [p for p in players if p["class_id"] == cid]
    else:
        players = await db.get_continuing_players()
    await _run_lottery(query, ctx, players)

async def lottery_manual(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    players = await db.get_continuing_players()
    ctx.user_data["match_players_pool"] = [dict(p) for p in players]
    ctx.user_data["mw_view"] = ctx.user_data["match_players_pool"]
    ctx.user_data["mw_page"] = 0
    await safe_edit_message_text(query, 
        f"{box('✏️ انتخاب دستی')}\n\n⬜ بازیکن سفید را انتخاب کنید:\n\n"
        f"{_page_hint(players, 0)}",
        reply_markup=kb.kb_player_select(players, "mwhite", "matches", page=0, nav_prefix="mw"),
        parse_mode="Markdown")
    return ST_MATCH_WHITE

# ─── Advanced Lottery (پیشرفته — چند مسابقه با هم) ──────────────
async def adv_lottery_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.pop("adv_pairs", None)
    ctx.user_data.pop("adv_count", None)
    await safe_edit_message_text(query, 
        f"{box('🎯 قرعه‌کشی پیشرفته')}\n\nمحدوده انتخاب بازیکنان چطور باشد؟",
        reply_markup=kb.kb_adv_lottery_scope(), parse_mode="Markdown")
    return ST_ADV_LOTTERY_SCOPE

async def adv_lottery_scope_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    scope = query.data.replace("adv_scope_", "")  # same / diff / open
    ctx.user_data["adv_scope"] = scope
    if scope == "open":
        ctx.user_data["adv_class_a"] = None
        ctx.user_data["adv_class_b"] = None
        await safe_edit_message_text(query, 
            f"{box('🎯 قرعه‌کشی پیشرفته')}\n\n"
            f"چند نفر می‌خواهید به‌صورت شانسی مقابل هم قرار بگیرند؟\n"
            f"(یک عدد زوج بفرستید — مثلاً ۲۰ نفر یعنی ۱۰ مسابقه)",
            parse_mode="Markdown")
        return ST_ADV_LOTTERY_COUNT
    classes = await db.get_all_classes()
    if not classes:
        await safe_edit_message_text(query, "❗ هیچ کلاسی ثبت نشده.", reply_markup=kb.kb_back("matches"))
        return ConversationHandler.END
    rows = []
    prefix = "adv_class_same_" if scope == "same" else "adv_classA_"
    for i in range(0, len(classes), 2):
        row = [InlineKeyboardButton(f"🏫 {c['name']}", callback_data=f"{prefix}{c['id']}") for c in classes[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="adv_lottery_start")])
    label = "🏫 کلاس مشترک هر دو طرف را انتخاب کنید:" if scope == "same" else "🏫 کلاس طرف اول (سفید) را انتخاب کنید:"
    await safe_edit_message_text(query, label, reply_markup=InlineKeyboardMarkup(rows))
    return ST_ADV_LOTTERY_CLASS_A

async def adv_lottery_classA_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    scope = ctx.user_data.get("adv_scope")
    if scope == "same":
        ctx.user_data["adv_class_a"] = cid
        ctx.user_data["adv_class_b"] = cid
        await safe_edit_message_text(query, 
            f"{box('🎯 قرعه‌کشی پیشرفته')}\n\n"
            f"چند نفر می‌خواهید به‌صورت شانسی مقابل هم قرار بگیرند؟\n"
            f"(یک عدد زوج بفرستید — مثلاً ۲۰ نفر یعنی ۱۰ مسابقه)",
            parse_mode="Markdown")
        return ST_ADV_LOTTERY_COUNT
    ctx.user_data["adv_class_a"] = cid
    classes = await db.get_all_classes()
    rows = []
    for i in range(0, len(classes), 2):
        row = [InlineKeyboardButton(f"🏫 {c['name']}", callback_data=f"adv_classB_{c['id']}") for c in classes[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="adv_lottery_start")])
    await safe_edit_message_text(query, "🏫 کلاس طرف دوم (سیاه) را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(rows))
    return ST_ADV_LOTTERY_CLASS_B

async def adv_lottery_classB_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    ctx.user_data["adv_class_b"] = cid
    await safe_edit_message_text(query, 
        f"{box('🎯 قرعه‌کشی پیشرفته')}\n\n"
        f"چند نفر می‌خواهید به‌صورت شانسی مقابل هم قرار بگیرند؟\n"
        f"(یک عدد زوج بفرستید — مثلاً ۲۰ نفر یعنی ۱۰ مسابقه)",
        parse_mode="Markdown")
    return ST_ADV_LOTTERY_COUNT

async def _generate_adv_pairs(scope, class_a, class_b, count):
    all_players = await db.get_continuing_players()
    if scope == "open":
        pool_a = pool_b = list(all_players)
    elif scope == "same":
        pool_a = pool_b = [p for p in all_players if p["class_id"] == class_a]
    else:
        pool_a = [p for p in all_players if p["class_id"] == class_a]
        pool_b = [p for p in all_players if p["class_id"] == class_b]

    if scope == "diff":
        side_needed = count // 2
        if len(pool_a) < side_needed or len(pool_b) < side_needed:
            return None, (
                f"⚠️ تعداد بازیکنان کافی نیست!\n"
                f"کلاس اول: `{len(pool_a)}` نفر موجود (نیاز: `{side_needed}`)\n"
                f"کلاس دوم: `{len(pool_b)}` نفر موجود (نیاز: `{side_needed}`)"
            )
        pool_a = list(pool_a)
        pool_b = list(pool_b)
        random.shuffle(pool_a)
        random.shuffle(pool_b)
        chosen_a = pool_a[:side_needed]
        chosen_b = pool_b[:side_needed]
        pairs = list(zip(chosen_a, chosen_b))
    else:
        pool = list(pool_a)
        if len(pool) < count:
            return None, (
                f"⚠️ تعداد بازیکنان کافی نیست!\n"
                f"موجود: `{len(pool)}` نفر | نیاز: `{count}` نفر"
            )
        random.shuffle(pool)
        chosen = pool[:count]
        pairs = [(chosen[i], chosen[i + 1]) for i in range(0, count, 2)]
    return pairs, None

def _render_adv_preview(pairs):
    lines = [box(f"🎯 پیش‌نمایش {len(pairs)} مسابقه")]
    for i, (p1, p2) in enumerate(pairs, start=1):
        lines.append(f"{i}. ⬜{p1['full_name']} ⚔️ {p2['full_name']}⬛")
    lines.append("")
    lines.append("✅ همه را ثبت کنم یا 🔄 دوباره قرعه‌کشی کنم؟")
    return "\n".join(lines)

def _adv_preview_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ثبت همه", callback_data="adv_lottery_confirm")],
        [InlineKeyboardButton("🔄 دوباره", callback_data="adv_lottery_redo"),
        InlineKeyboardButton("❌ لغو", callback_data="adv_lottery_cancel")],
    ])

async def adv_lottery_count_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 2:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر (حداقل ۲) بفرستید:")
        return ST_ADV_LOTTERY_COUNT
    count = int(text)
    if count % 2 != 0:
        await update.message.reply_text(
            f"❌ عدد باید زوج باشد (هر مسابقه ۲ نفر لازم دارد).\n"
            f"مثلاً {count - 1} یا {count + 1} را امتحان کنید:")
        return ST_ADV_LOTTERY_COUNT

    scope = ctx.user_data.get("adv_scope")
    class_a = ctx.user_data.get("adv_class_a")
    class_b = ctx.user_data.get("adv_class_b")
    ctx.user_data["adv_count"] = count

    pairs, err = await _generate_adv_pairs(scope, class_a, class_b, count)
    if err:
        await update.message.reply_text(err + "\n\nعدد کوچک‌تری بفرستید:", parse_mode="Markdown")
        return ST_ADV_LOTTERY_COUNT

    ctx.user_data["adv_pairs"] = [(p1["id"], p2["id"]) for p1, p2 in pairs]
    await update.message.reply_text(
        _render_adv_preview(pairs), reply_markup=_adv_preview_kb(), parse_mode="Markdown")
    return ConversationHandler.END

async def adv_lottery_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pairs = ctx.user_data.get("adv_pairs", [])
    if not pairs:
        await safe_edit_message_text(query, "❌ داده‌ای برای ثبت وجود ندارد.", reply_markup=kb.kb_back("matches"))
        return
    default_t = await db.get_default_tournament()
    tid = default_t["id"] if default_t else None
    uid = query.from_user.id
    date = today_gregorian()
    count = 0
    for white_id, black_id in pairs:
        await db.create_match(white_id, black_id, date, tid, uid)
        count += 1
    await db.log_action(uid, "adv_lottery", f"ثبت گروهی {count} مسابقه با قرعه‌کشی پیشرفته")
    ctx.user_data.pop("adv_pairs", None)
    ctx.user_data.pop("adv_count", None)
    await safe_edit_message_text(query, f"✅ {count} مسابقه با موفقیت ثبت شد.", reply_markup=kb.kb_back("matches"))

async def adv_lottery_redo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    scope = ctx.user_data.get("adv_scope")
    class_a = ctx.user_data.get("adv_class_a")
    class_b = ctx.user_data.get("adv_class_b")
    count = ctx.user_data.get("adv_count")
    if not count:
        await safe_edit_message_text(query, "❌ اطلاعات قبلی یافت نشد. دوباره از ابتدا شروع کنید.",
            reply_markup=kb.kb_back("matches"))
        return
    pairs, err = await _generate_adv_pairs(scope, class_a, class_b, count)
    if err:
        await safe_edit_message_text(query, err, reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
        return
    ctx.user_data["adv_pairs"] = [(p1["id"], p2["id"]) for p1, p2 in pairs]
    await safe_edit_message_text(query, 
        _render_adv_preview(pairs), reply_markup=_adv_preview_kb(), parse_mode="Markdown")

async def adv_lottery_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.pop("adv_pairs", None)
    ctx.user_data.pop("adv_count", None)
    await safe_edit_message_text(query, "❌ قرعه‌کشی پیشرفته لغو شد.", reply_markup=kb.kb_back("matches"))
