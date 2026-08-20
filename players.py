from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import (box, separator, warning_bar_player, power_bar,
                     now_shamsi, notify_pishva, log_line, check_status_gate,
                     progress_bar, get_rank_label)
from config import (PISHVA_ID, ST_CLASS_NAME, ST_PLAYER_CLASS_SELECT,
                    ST_PLAYER_NAME, ST_WARNING_REASON, ST_NOTE_TEXT,
                    ST_EDIT_PLAYER_NAME, ST_SEARCH_PLAYER)


# ─── Class Management ─────────────────────────────────────────
async def class_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{box('✅ ثبت کلاس جدید')}\n\n📝 نام کلاس را وارد کنید (مثلاً ۹۰۱):",
        parse_mode="Markdown"
    )
    return ST_CLASS_NAME

async def class_add_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if ctx.user_data.get("editing_class"):
        cid = ctx.user_data.pop("editing_class")
        await db.rename_class(cid, name)
        await update.message.reply_text(f"✅ نام کلاس به *{name}* تغییر یافت.", parse_mode="Markdown",
                                         reply_markup=kb.kb_class_manage())
    else:
        await db.create_class(name)
        await db.log_action(update.effective_user.id, "create_class", f"ثبت کلاس: {name}")
        await update.message.reply_text(f"✅ کلاس *{name}* ثبت شد.", reply_markup=kb.kb_class_manage(), parse_mode="Markdown")
    return ConversationHandler.END

async def class_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    classes = await db.get_all_classes()
    if not classes:
        await query.edit_message_text(f"{box('🏫 کلاس‌ها')}\n\n❗ هیچ کلاسی ثبت نشده.",
                                       reply_markup=kb.kb_class_manage(), parse_mode="Markdown")
        return
    await query.edit_message_text(f"{box('🏫 لیست کلاس‌ها')}\n\n📌 یک کلاس انتخاب کنید:",
                                   reply_markup=kb.kb_class_list(classes), parse_mode="Markdown")

async def class_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    c = await db.get_class(cid)
    players = await db.get_players_by_class(cid)
    active = sum(1 for p in players if p["status"] == "active")
    await query.edit_message_text(
        f"{box('🏫 کلاس ' + c['name'])}\n\n👥 تعداد بازیکنان: `{len(players)}`\n✅ فعال: `{active}`",
        reply_markup=kb.kb_class_actions(cid), parse_mode="Markdown")

async def class_players(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    c = await db.get_class(cid)
    players = await db.get_players_by_class(cid)
    if not players:
        await query.edit_message_text(f"👥 کلاس *{c['name']}*\n\n❗ بازیکنی ثبت نشده.",
                                       reply_markup=kb.kb_back("class_list"), parse_mode="Markdown")
        return
    lines = []
    for p in players:
        icon = "🟢" if p["status"] == "active" else "⛔" if p["status"] == "eliminated" else "🔴"
        lines.append(f"{icon} {p['full_name']} — W:{p['wins']} D:{p['draws']} L:{p['losses']}")
    await query.edit_message_text(f"👥 بازیکنان کلاس *{c['name']}*:\n\n" + "\n".join(lines),
                                   reply_markup=kb.kb_back("class_list"), parse_mode="Markdown")

async def class_edit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    ctx.user_data["editing_class"] = cid
    c = await db.get_class(cid)
    await query.edit_message_text(f"✏️ نام جدید برای کلاس *{c['name']}*:", parse_mode="Markdown")
    return ST_CLASS_NAME

async def class_perf(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    c = await db.get_class(cid)
    players = await db.get_players_by_class(cid)
    total_w = sum(p["wins"] for p in players)
    total_d = sum(p["draws"] for p in players)
    total_l = sum(p["losses"] for p in players)
    bar = power_bar(total_w, total_l, total_d)
    await query.edit_message_text(
        f"{box('📈 عملکرد کلاس ' + c['name'])}\n\n"
        f"✅ برد: `{total_w}` | 🤝 مساوی: `{total_d}` | ❌ باخت: `{total_l}`\n\n"
        f"⚡ سطح قدرت:\n`{bar}`",
        reply_markup=kb.kb_back(f"class_select_{cid}"), parse_mode="Markdown")

# ─── Player Registration ──────────────────────────────────────
async def player_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    classes = await db.get_all_classes()
    if not classes:
        await query.edit_message_text("❗ ابتدا باید حداقل یک کلاس ثبت کنید.",
                                       reply_markup=kb.kb_class_manage(), parse_mode="Markdown")
        return ConversationHandler.END
    rows = []
    for i in range(0, len(classes), 2):
        row = [InlineKeyboardButton(f"🏫 {c['name']}", callback_data=f"pclass_{c['id']}") for c in classes[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_players")])
    await query.edit_message_text(
        f"{box('➕ ثبت‌نام بازیکن')}\n\n📌 مرحله ۱/۲: کلاس بازیکن را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
    return ST_PLAYER_CLASS_SELECT

async def player_class_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split("_")[-1])
    ctx.user_data["player_class"] = cid
    c = await db.get_class(cid)
    await query.edit_message_text(
        f"{box('➕ ثبت‌نام بازیکن')}\n\n🏫 کلاس: *{c['name']}*\n\n📌 مرحله ۲/۲: نام و نام‌خانوادگی:",
        parse_mode="Markdown")
    return ST_PLAYER_NAME

async def player_add_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    cid = ctx.user_data.get("player_class")
    if not cid or not full_name:
        await update.message.reply_text("❌ خطا. دوباره از ابتدا شروع کنید.")
        return ConversationHandler.END
    pid = await db.create_player(full_name, cid)
    await db.log_action(update.effective_user.id, "create_player", f"ثبت بازیکن: {full_name}", pid)
    c = await db.get_class(cid)
    team_mode = await db.get_setting("team_mode_enabled", "0")
    team_reg = await db.get_setting("team_registration_enabled", "1")
    if team_mode == "1" and team_reg == "1":
        teams = await db.get_all_teams()
        if teams:
            ctx.user_data["new_player_id"] = pid
            rows = []
            for i in range(0, len(teams), 2):
                row = [InlineKeyboardButton(f"🏆 {t['name']}", callback_data=f"player_jointeam_{pid}_{t['id']}") for t in teams[i:i+2]]
                rows.append(row)
            rows.append([InlineKeyboardButton("⏭️ رد کردن", callback_data=f"player_noteam_{pid}")])
            await update.message.reply_text(
                f"✅ بازیکن *{full_name}* (کلاس {c['name']}) ثبت شد.\n\nآیا به تیمی ملحق شود؟",
                reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
            return ConversationHandler.END
    await update.message.reply_text(
        f"✅ بازیکن *{full_name}* در کلاس *{c['name']}* ثبت شد.\n🆔 شناسه: `{pid}`",
        reply_markup=kb.kb_players_menu("pishva"), parse_mode="Markdown")
    return ConversationHandler.END

async def player_join_team(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    pid = int(parts[-2])
    tid = int(parts[-1])
    await db.add_team_member(tid, pid)
    p = await db.get_player(pid)
    t = await db.get_team(tid)
    await query.edit_message_text(f"✅ *{p['full_name']}* به تیم *{t['name']}* اضافه شد.",
                                   reply_markup=kb.kb_players_menu("pishva"), parse_mode="Markdown")

async def player_no_team(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ بازیکن بدون تیم ثبت شد.", reply_markup=kb.kb_players_menu("pishva"))

# ─── Player List ──────────────────────────────────────────────
async def player_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    players = await db.get_all_players()
    if not players:
        await query.edit_message_text(f"{box('👤 لیست بازیکنان')}\n\n❗ هیچ بازیکنی ثبت نشده.",
                                       reply_markup=kb.kb_back("players"), parse_mode="Markdown")
        return
    await query.edit_message_text(
        f"{box('👤 لیست بازیکنان')}\n\n👥 تعداد کل: `{len(players)}`\n\n📌 یک بازیکن انتخاب کنید:",
        reply_markup=kb.kb_player_list(players), parse_mode="Markdown")

async def player_list_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    players = await db.get_all_players()
    await query.edit_message_text(
        f"{box('👤 لیست بازیکنان')}\n\n👥 تعداد کل: `{len(players)}`",
        reply_markup=kb.kb_player_list(players, page), parse_mode="Markdown")

async def player_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = await db.get_player(pid)
    if not p:
        await query.answer("بازیکن یافت نشد.", show_alert=True)
        return

    role = "pishva" if query.from_user.id == PISHVA_ID else "admin"
    total = p["wins"] + p["losses"] + p["draws"]
    warn_bar = warning_bar_player(p["warnings"])
    pw = power_bar(p["wins"], p["losses"], p["draws"])
    rank = get_rank_label(p["wins"], total)
    win_pct = int(p["wins"] / total * 100) if total > 0 else 0
    win_bar = progress_bar(win_pct)

    status_map = {
        "active": "🟢 فعال", "suspended": "⏸️ تعلیق",
        "kicked": "❌ اخراج", "eliminated": "⛔ حذف در مسابقه"
    }

    # Best opponent
    history = await db.get_player_match_history(pid)
    opponent_wins = {}
    for m in history:
        if m["result"] == "white" and m["white_player_id"] == pid:
            opp = m["black_name"]
        elif m["result"] == "black" and m["black_player_id"] == pid:
            opp = m["white_name"]
        else:
            continue
        opponent_wins[opp] = opponent_wins.get(opp, 0) + 1
    best_opp = max(opponent_wins, key=opponent_wins.get) if opponent_wins else "—"
    hardest_opp_wins = {}
    for m in history:
        if m["result"] == "black" and m["white_player_id"] == pid:
            opp = m["black_name"]
        elif m["result"] == "white" and m["black_player_id"] == pid:
            opp = m["white_name"]
        else:
            continue
        hardest_opp_wins[opp] = hardest_opp_wins.get(opp, 0) + 1
    hardest = max(hardest_opp_wins, key=hardest_opp_wins.get) if hardest_opp_wins else "—"

    elite_tag = "  🌟 بازیکن برتر" if p["is_elite"] else ""
    special_tag = "  ⚡ نیروی ویژه" if p["is_special"] else ""

    text = (
        f"{box('👤 ' + p['full_name'])}\n\n"
        f"🏫 کلاس: *{(p['class_name'] or '—')}*\n"
        f"📊 وضعیت: {status_map.get(p['status'], p['status'])}\n"
        f"🏆 رتبه: {rank}{elite_tag}{special_tag}\n\n"
        f"{separator('📊 آمار عملکرد')}\n"
        f"✅ برد: `{p['wins']}` | 🤝 مساوی: `{p['draws']}` | ❌ باخت: `{p['losses']}`\n"
        f"📈 مجموع: `{total}` بازی\n"
        f"🎯 درصد برد:\n`{win_bar}`\n"
        f"⚡ سطح قدرت:\n`{pw}`\n\n"
        f"{separator('⚔️ اطلاعات رقابتی')}\n"
        f"🏅 بهترین حریف (بیشترین برد مقابل): {best_opp}\n"
        f"💀 سخت‌ترین حریف (بیشترین باخت مقابل): {hardest}\n\n"
        f"{separator('⚠️ اخطار')}\n"
        f"{warn_bar}\n"
        f"{'📂 یادداشت: _' + p['notes'] + '_' if p['notes'] else ''}"
    )
    await query.edit_message_text(text, reply_markup=kb.kb_player_actions(pid, role), parse_mode="Markdown")

# ─── Player Actions ───────────────────────────────────────────
async def player_warn_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_status_gate(query, "warning"):
        return
    await query.answer()
    pid = int(query.data.split("_")[-1])
    ctx.user_data["warning_player"] = pid
    p = await db.get_player(pid)
    await query.edit_message_text(f"⚠️ دلیل اخطار برای *{p['full_name']}*:", parse_mode="Markdown")
    return ST_WARNING_REASON

async def player_warn_reason(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    pid = ctx.user_data.get("warning_player")
    uid = update.effective_user.id
    if not pid:
        return ConversationHandler.END
    p = await db.get_player(pid)
    await db.add_player_warning(pid, reason, uid)
    p_updated = await db.get_player(pid)
    warn_bar = warning_bar_player(p_updated["warnings"])
    await update.message.reply_text(
        f"⚠️ اخطار برای *{p['full_name']}* ثبت شد.\n📋 دلیل: {reason}\n\n{warn_bar}",
        reply_markup=kb.kb_back("player_list"), parse_mode="Markdown")
    await db.log_action(uid, "player_warning", f"اخطار به {p['full_name']}: {reason}", pid)
    if p_updated["warnings"] >= 3:
        await notify_pishva(update.get_bot(),
            f"🔴 بازیکن *{p['full_name']}* به ۳ اخطار رسید!\n📋 دلیل: {reason}\n⏱️ `{now_shamsi()}`")
    return ConversationHandler.END

async def player_kick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_status_gate(query, "ban_player"):
        return
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = await db.get_player(pid)
    if p["is_elite"] or p["is_special"]:
        icon = "🌟" if p["is_elite"] else "⚡"
        await query.answer(f"⚠️ این بازیکن {icon} است! برای تأیید دوباره بزنید.", show_alert=True)
    await db.update_player(pid, status="kicked")
    await db.log_action(query.from_user.id, "kick_player", f"اخراج: {p['full_name']}", pid)
    await query.edit_message_text(f"🚫 *{p['full_name']}* اخراج شد.",
                                   reply_markup=kb.kb_back("player_list"), parse_mode="Markdown")

async def player_suspend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = await db.get_player(pid)
    await db.update_player(pid, status="suspended")
    await db.log_action(query.from_user.id, "suspend_player", f"تعلیق: {p['full_name']}", pid)
    await query.edit_message_text(f"⏸️ *{p['full_name']}* تعلیق شد.",
                                   reply_markup=kb.kb_back("player_list"), parse_mode="Markdown")

async def player_revive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = await db.get_player(pid)
    await db.update_player(pid, status="active", warnings=0)
    await db.log_action(query.from_user.id, "revive_player", f"احیا: {p['full_name']}", pid)
    await query.edit_message_text(f"🔄 *{p['full_name']}* احیا شد و به لیست فعال بازگشت.",
                                   reply_markup=kb.kb_back("player_list"), parse_mode="Markdown")

async def player_note_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    ctx.user_data["note_player"] = pid
    p = await db.get_player(pid)
    await query.edit_message_text(f"📝 یادداشت برای *{p['full_name']}*:", parse_mode="Markdown")
    return ST_NOTE_TEXT

async def player_note_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    pid = ctx.user_data.get("note_player")
    if pid:
        await db.update_player(pid, notes=note)
        await update.message.reply_text("📝 یادداشت ذخیره شد.", reply_markup=kb.kb_back("player_list"))
    return ConversationHandler.END

async def player_elite_set(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = await db.get_player(pid)
    new_val = 0 if p["is_elite"] else 1
    await db.update_player(pid, is_elite=new_val)
    label = "🌟 به برترین‌ها اضافه شد" if new_val else "از برترین‌ها حذف شد"
    await query.edit_message_text(f"✅ {p['full_name']} — {label}",
                                   reply_markup=kb.kb_back("player_list"), parse_mode="Markdown")

async def player_special_set(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط پیشوا می‌تواند نیروی ویژه تعیین کند.", show_alert=True)
        return
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = await db.get_player(pid)
    new_val = 0 if p["is_special"] else 1
    await db.update_player(pid, is_special=new_val)
    label = "⚡ نیروی ویژه شد" if new_val else "از نیروهای ویژه حذف شد"
    await query.edit_message_text(f"✅ {p['full_name']} — {label}",
                                   reply_markup=kb.kb_back("player_list"), parse_mode="Markdown")

async def player_editname_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    ctx.user_data["edit_player"] = pid
    p = await db.get_player(pid)
    await query.edit_message_text(f"✏️ نام جدید برای *{p['full_name']}*:", parse_mode="Markdown")
    return ST_EDIT_PLAYER_NAME

async def player_editname_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    pid = ctx.user_data.get("edit_player")
    if pid and new_name:
        await db.update_player(pid, full_name=new_name)
        await update.message.reply_text(f"✅ نام به *{new_name}* تغییر یافت.", parse_mode="Markdown")
    return ConversationHandler.END

async def player_editclass_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    ctx.user_data["editclass_player"] = pid
    classes = await db.get_all_classes()
    rows = []
    for i in range(0, len(classes), 2):
        row = [InlineKeyboardButton(f"🏫 {c['name']}", callback_data=f"setclass_{pid}_{c['id']}") for c in classes[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"player_view_{pid}")])
    await query.edit_message_text("🏫 کلاس جدید را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(rows))

async def player_setclass(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    pid = int(parts[-2])
    cid = int(parts[-1])
    await db.update_player(pid, class_id=cid)
    c = await db.get_class(cid)
    p = await db.get_player(pid)
    await query.edit_message_text(f"✅ کلاس *{p['full_name']}* به *{c['name']}* تغییر یافت.",
                                   reply_markup=kb.kb_back("player_list"), parse_mode="Markdown")

async def player_search_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"{box('🔍 جستجو بازیکن')}\n\nنام، نام‌خانوادگی یا کلاس را وارد کنید:",
                                   parse_mode="Markdown")
    return ST_SEARCH_PLAYER

async def player_search_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    results = await db.search_players(q)
    if not results:
        await update.message.reply_text("❗ نتیجه‌ای یافت نشد.", reply_markup=kb.kb_back("players"))
        return ConversationHandler.END
    await update.message.reply_text(f"🔍 نتایج جستجو برای «{q}»:",
                                     reply_markup=kb.kb_player_list(results), parse_mode="Markdown")
    return ConversationHandler.END

async def player_continuing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    players = await db.get_continuing_players()
    if not players:
        await query.edit_message_text(f"{box('✅ بازیکنان ادامه‌دهنده')}\n\n❗ هیچ بازیکن ادامه‌دهنده‌ای وجود ندارد.",
                                       reply_markup=kb.kb_back("players"), parse_mode="Markdown")
        return
    await query.edit_message_text(
        f"{box('✅ بازیکنان ادامه‌دهنده')}\n\n👥 تعداد: `{len(players)}`",
        reply_markup=kb.kb_player_list(players), parse_mode="Markdown")

async def player_eliminated(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    players = await db.get_all_players()
    kicked = [p for p in players if p["status"] == "kicked"]
    eliminated = [p for p in players if p["status"] == "eliminated"]
    rows = [
        [InlineKeyboardButton(f"❌ اخراجی‌ها ({len(kicked)})", callback_data="player_list_kicked"),
         InlineKeyboardButton(f"⛔ شکست‌خورده‌ها ({len(eliminated)})", callback_data="player_list_elim")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_players")],
    ]
    await query.edit_message_text(f"{box('❌ بازیکنان حذف‌شده')}\n\n📌 نوع را انتخاب کنید:",
                                   reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")

async def player_list_kicked(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    players = await db.get_all_players()
    kicked = [p for p in players if p["status"] == "kicked"]
    if not kicked:
        await query.edit_message_text("❗ هیچ بازیکن اخراجی وجود ندارد.", reply_markup=kb.kb_back("player_eliminated"))
        return
    await query.edit_message_text(f"❌ اخراجی‌ها ({len(kicked)}):", reply_markup=kb.kb_player_list(kicked))

async def player_list_elim(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    players = await db.get_all_players()
    elim = [p for p in players if p["status"] == "eliminated"]
    if not elim:
        await query.edit_message_text("❗ هیچ بازیکن شکست‌خورده‌ای وجود ندارد.", reply_markup=kb.kb_back("player_eliminated"))
        return
    await query.edit_message_text(f"⛔ شکست‌خورده‌ها ({len(elim)}):", reply_markup=kb.kb_player_list(elim))

async def player_elite_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    players = await db.get_all_players()
    elite = [p for p in players if p["is_elite"]]
    if not elite:
        await query.edit_message_text("🌟 هیچ بازیکن برتری تعیین نشده.", reply_markup=kb.kb_back("players"))
        return
    await query.edit_message_text(f"🌟 بازیکنان برتر ({len(elite)}):", reply_markup=kb.kb_player_list(elite))

async def player_special_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    players = await db.get_all_players()
    special = [p for p in players if p["is_special"]]
    if not special:
        await query.edit_message_text("⚡ هیچ نیروی ویژه‌ای تعیین نشده.", reply_markup=kb.kb_back("players"))
        return
    await query.edit_message_text(f"⚡ نیروهای ویژه ({len(special)}):", reply_markup=kb.kb_player_list(special))
