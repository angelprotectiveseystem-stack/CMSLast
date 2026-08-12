from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import (box, separator, now_shamsi, today_gregorian, today_shamsi,
                     notify_pishva, check_status_gate, smart_lottery, progress_bar)
from config import (PISHVA_ID, ST_MATCH_WHITE, ST_MATCH_BLACK, ST_MATCH_DATE,
                    ST_MATCH_DRAW_REASON, ST_SEARCH_MATCH)


# ─── Add Match ────────────────────────────────────────────────
async def match_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    match_on = await db.get_setting("match_registration_enabled", "1")
    if match_on != "1":
        await query.answer("♟️ ثبت مسابقه غیرفعال است.", show_alert=True)
        return ConversationHandler.END
    if await check_status_gate(query, "match_registration"):
        return ConversationHandler.END
    await query.answer()
    players = await db.get_continuing_players()
    if len(players) < 2:
        await query.edit_message_text(
            f"❌ *خطا — کد ۰۰۱*\n\nحداقل دو بازیکن ادامه‌دهنده برای شروع مسابقه وجود ندارد.",
            reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
        return ConversationHandler.END
    ctx.user_data["match_players_pool"] = [dict(p) for p in players]
    ctx.user_data.pop("match_white", None)
    ctx.user_data.pop("match_black", None)
    await query.edit_message_text(
        f"{box('➕ ثبت مسابقه جدید')}\n\n⬜ مرحله ۱: بازیکن *سفید* را انتخاب کنید:",
        reply_markup=kb.kb_player_select(players, "mwhite", "matches"),
        parse_mode="Markdown")
    return ST_MATCH_WHITE


async def match_white_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    white_id = int(query.data.split("_")[-1])
    ctx.user_data["match_white"] = white_id
    wp = await db.get_player(white_id)
    pool = [p for p in ctx.user_data.get("match_players_pool", []) if p["id"] != white_id]
    await query.edit_message_text(
        f"{box('➕ ثبت مسابقه جدید')}\n\n"
        f"⬜ سفید: *{wp['full_name']}*\n\n"
        f"⬛ مرحله ۲: بازیکن *سیاه* را انتخاب کنید:",
        reply_markup=kb.kb_player_select(pool, "mblack", "matches"),
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
    await query.edit_message_text(
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
            await update.callback_query.edit_message_text(msg)
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
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return ConversationHandler.END


# ─── Match Result ─────────────────────────────────────────────
async def match_result_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending = await db.get_pending_matches()
    if not pending:
        await query.edit_message_text(
            f"{box('🏆 ثبت نتیجه')}\n\n✅ همه مسابقات نتیجه دارند.",
            reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
        return
    rows = []
    for m in pending[:15]:
        rows.append([InlineKeyboardButton(
            f"⬜{m['white_name']} ⚔️ {m['black_name']}⬛",
            callback_data=f"result_select_{m['id']}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches")])
    await query.edit_message_text(
        f"{box('🏆 ثبت نتیجه')}\n\n📌 مسابقه را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")


async def match_result_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    m = await db.get_match(mid)
    await query.edit_message_text(
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
    await db.set_match_result(mid, "white", "", query.from_user.id)
    await db.update_player_stats(m["white_player_id"], "win")
    await db.update_player_stats(m["black_player_id"], "loss")
    await db.log_action(query.from_user.id, "match_result", f"برد سفید — مسابقه {mid}", mid)
    loser = await db.get_player(m["black_player_id"])
    warn = ""
    if loser["is_elite"] or loser["is_special"]:
        icon = "🌟" if loser["is_elite"] else "⚡"
        warn = f"\n\n⚠️ *توجه:* {loser['full_name']} {icon} است!"
    await query.edit_message_text(
        f"🥇 برد *{m['white_name']}* ثبت شد.{warn}\n\n"
        f"آیا می‌خواهید *{m['black_name']}* حذف شود؟",
        reply_markup=kb.kb_eliminate_ask(m["black_player_id"], m["black_name"]),
        parse_mode="Markdown")


async def result_black(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    m = await db.get_match(mid)
    await db.set_match_result(mid, "black", "", query.from_user.id)
    await db.update_player_stats(m["black_player_id"], "win")
    await db.update_player_stats(m["white_player_id"], "loss")
    await db.log_action(query.from_user.id, "match_result", f"برد سیاه — مسابقه {mid}", mid)
    loser = await db.get_player(m["white_player_id"])
    warn = ""
    if loser["is_elite"] or loser["is_special"]:
        icon = "🌟" if loser["is_elite"] else "⚡"
        warn = f"\n\n⚠️ *توجه:* {loser['full_name']} {icon} است!"
    await query.edit_message_text(
        f"🥇 برد *{m['black_name']}* ثبت شد.{warn}\n\n"
        f"آیا می‌خواهید *{m['white_name']}* حذف شود؟",
        reply_markup=kb.kb_eliminate_ask(m["white_player_id"], m["white_name"]),
        parse_mode="Markdown")


async def result_draw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    await query.edit_message_text(
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
        await query.edit_message_text("📝 دلیل تساوی را بنویسید:")
        return ST_MATCH_DRAW_REASON
    reason = reason_map.get(reason_key, reason_key)
    m = await db.get_match(mid)
    await db.set_match_result(mid, "draw", reason, query.from_user.id)
    await db.update_player_stats(m["white_player_id"], "draw")
    await db.update_player_stats(m["black_player_id"], "draw")
    await db.log_action(query.from_user.id, "match_result", f"تساوی ({reason}) — {mid}", mid)
    await query.edit_message_text(
        f"🤝 تساوی ثبت شد.\n📋 علت: *{reason}*",
        reply_markup=kb.kb_back("matches"), parse_mode="Markdown")


async def draw_reason_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    mid = ctx.user_data.get("draw_match")
    if mid:
        m = await db.get_match(mid)
        await db.set_match_result(mid, "draw", reason, update.effective_user.id)
        await db.update_player_stats(m["white_player_id"], "draw")
        await db.update_player_stats(m["black_player_id"], "draw")
        await update.message.reply_text(
            f"🤝 تساوی ثبت شد.\n📋 علت: *{reason}*",
            reply_markup=kb.kb_back("matches"), parse_mode="Markdown")
    return ConversationHandler.END


async def eliminate_yes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = await db.get_player(pid)
    await db.update_player(pid, status="eliminated")
    await db.log_action(query.from_user.id, "eliminate_player", f"حذف: {p['full_name']}", pid)
    await query.edit_message_text(
        f"⛔ *{p['full_name']}* از لیست ادامه‌دهندگان حذف شد.",
        reply_markup=kb.kb_back("matches"), parse_mode="Markdown")


async def eliminate_no(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✅ بازیکن در لیست ادامه‌دهندگان باقی ماند.",
        reply_markup=kb.kb_back("matches"))


# ─── History ──────────────────────────────────────────────────
async def match_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{box('🔍 تاریخچه مسابقات')}\n\n📌 فیلتر را انتخاب کنید:",
        reply_markup=kb.kb_match_history_filter(), parse_mode="Markdown")


async def match_hist_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.split("_")[-1]
    matches = await db.get_matches_by_filter(period)
    label = {"today": "امروز", "week": "این هفته", "month": "این ماه", "all": "کل"}.get(period, period)
    if not matches:
        await query.edit_message_text(f"❗ مسابقه‌ای در {label} یافت نشد.",
                                       reply_markup=kb.kb_match_history_filter())
        return
    await query.edit_message_text(
        f"{box('📋 مسابقات — ' + label)} ({len(matches)} مسابقه)",
        reply_markup=kb.kb_match_list(matches), parse_mode="Markdown")


async def match_hist_search_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔍 نام بازیکن یا تاریخ را وارد کنید:")
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
        await query.edit_message_text("❗ هیچ مسابقه‌ای ثبت نشده.", reply_markup=kb.kb_back("matches"))
        return
    await query.edit_message_text(
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
        "draw": "🤝 تساوی", None: "⏳ بدون نتیجه"
    }
    admin_name = "—"
    if m["created_by"]:
        if m["created_by"] == PISHVA_ID:
            admin_name = await db.get_setting("pishva_display_name", "پیشوا")
        else:
            a = await db.get_admin(m["created_by"])
            admin_name = a["display_name"] or a["full_name"] if a else str(m["created_by"])
    text = (
        f"{box('♟️ جزئیات مسابقه')}\n\n"
        f"⬜ سفید: *{m['white_name']}*\n"
        f"⬛ سیاه: *{m['black_name']}*\n"
        f"🏆 نتیجه: {result_map.get(m['result'], '—')}\n"
        f"📋 علت تساوی: {m['draw_reason'] or '—'}\n"
        f"📅 تاریخ: `{m['match_date'] or '—'}`\n"
        f"👤 ثبت‌کننده: {admin_name}\n"
        f"⏱️ `{str(m['created_at'] or '')[:16]}`\n"
        f"{'📌 پین‌شده' if m['is_pinned'] else ''}"
    )
    await query.edit_message_text(text, reply_markup=kb.kb_match_item_actions(mid), parse_mode="Markdown")


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
    await query.edit_message_text("🗑️ مسابقه حذف شد.", reply_markup=kb.kb_back("match_history"))


async def match_pin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[-1])
    m = await db.get_match(mid)
    new_pin = 0 if m["is_pinned"] else 1
    await db.update_match(mid, is_pinned=new_pin)
    label = "📌 پین شد" if new_pin else "پین برداشته شد"
    await query.edit_message_text(label, reply_markup=kb.kb_back("match_history"))


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
    await query.edit_message_text(text, reply_markup=kb.kb_back("matches"), parse_mode="Markdown")


# ─── Lottery ─────────────────────────────────────────────────
async def lottery_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
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
    await query.edit_message_text("🏫 کلاس را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(rows))


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
        await query.edit_message_text("❌ تعداد بازیکنان کمتر از ۲ نفر است.",
                                       reply_markup=kb.kb_back("matches"))
        return
    p1, p2, all_played = await smart_lottery(players)
    ctx.user_data["lottery_p1"] = p1["id"]
    ctx.user_data["lottery_p2"] = p2["id"]
    warn = "\n\n⚠️ همه بازیکنان قبلاً با هم بازی کرده‌اند. قرعه‌کشی تصادفی انجام شد." if all_played else ""
    text = (
        f"╼╼╼╼╼╼ 🎲 نتیجه قرعه‌کشی ╾╾╾╾╾╾\n\n"
        f"⬜ سفید: *{p1['full_name']}* [{p1.get('class_name', '')}]\n"
        f"⬛ سیاه: *{p2['full_name']}* [{p2.get('class_name', '')}]\n\n"
        f"📅 تاریخ پیشنهادی: `{today_shamsi()}`"
        f"{warn}\n╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼"
    )
    await query.edit_message_text(
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
    await query.edit_message_text(
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
    await query.edit_message_text(
        f"{box('✏️ انتخاب دستی')}\n\n⬜ بازیکن سفید را انتخاب کنید:",
        reply_markup=kb.kb_player_select(players, "mwhite", "matches"),
        parse_mode="Markdown")
    return ST_MATCH_WHITE
