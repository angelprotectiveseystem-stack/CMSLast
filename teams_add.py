from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import safe_edit_message_text, box, now_shamsi, today_shamsi, today_gregorian
from config import (PISHVA_ID, ST_TEAM_NAME, ST_TEAM_SLOGAN, ST_TEAM_MEMBERS,
                    ST_TEAM_DATE, ST_TEAM_REQUESTER)


async def teams_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id

    # Check permission
    team_mode = await db.get_setting("team_mode_enabled", "0")
    if team_mode != "1":
        await query.answer("🏆 حالت تیمی غیرفعال است.", show_alert=True)
        return ConversationHandler.END

    mgr_can_create = await db.get_setting("managers_can_create_teams", "0")
    if uid != PISHVA_ID and mgr_can_create != "1":
        await query.answer("⛔ فقط مدیر ارشد می‌تواند تیم بسازد.", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    await safe_edit_message_text(query, 
        f"{box('➕ افزودن تیم')}\n\n📝 مرحله ۱: نام تیم را وارد کنید:",
        parse_mode="Markdown"
    )
    ctx.user_data["new_team"] = {}
    return ST_TEAM_NAME


async def team_name_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ نام خالی است. دوباره وارد کنید:")
        return ST_TEAM_NAME
    ctx.user_data["new_team"]["name"] = name
    await update.message.reply_text(
        f"🎯 مرحله ۲: شعار تیم را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ رد کردن (اسکیپ)", callback_data="team_skip_slogan")]
        ])
    )
    return ST_TEAM_SLOGAN


async def team_skip_slogan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["new_team"]["slogan"] = ""
    return await _ask_members(query, ctx)


async def team_slogan_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_team"]["slogan"] = update.message.text.strip()
    return await _ask_members_msg(update, ctx)


async def _ask_members(query_or_update, ctx):
    players = await db.get_all_players()
    active = [p for p in players if p["status"] == "active"]
    ctx.user_data["new_team"]["selected_members"] = []
    ctx.user_data["new_team"]["all_active_players"] = [dict(p) for p in active]

    markup = _build_member_selector(active, [])
    text = (
        f"{box('➕ افزودن تیم')}\n\n"
        f"👥 مرحله ۳: حداقل سه عضو انتخاب کنید:\n"
        f"_(روی هر بازیکن بزنید تا انتخاب/لغو شود)_"
    )
    if hasattr(query_or_update, "edit_message_text"):
        await safe_edit_message_text(query_or_update, text, reply_markup=markup, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return ST_TEAM_MEMBERS


async def _ask_members_msg(update, ctx):
    players = await db.get_all_players()
    active = [p for p in players if p["status"] == "active"]
    ctx.user_data["new_team"]["selected_members"] = []
    ctx.user_data["new_team"]["all_active_players"] = [dict(p) for p in active]

    markup = _build_member_selector(active, [])
    text = (
        f"{box('➕ افزودن تیم')}\n\n"
        f"👥 مرحله ۳: حداقل سه عضو انتخاب کنید:\n"
        f"_(روی هر بازیکن بزنید تا انتخاب/لغو شود)_"
    )
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return ST_TEAM_MEMBERS


def _build_member_selector(players, selected_ids):
    rows = []
    for i in range(0, len(players), 2):
        row = []
        for p in players[i:i+2]:
            tick = "✅ " if p["id"] in selected_ids else ""
            row.append(InlineKeyboardButton(
                f"{tick}{p['full_name']}",
                callback_data=f"tselect_{p['id']}"
            ))
        rows.append(row)
    rows.append([
        InlineKeyboardButton("⏭️ رد کردن (بعداً عضو اضافه می‌کنم)", callback_data="team_skip_members")
    ])
    if len(selected_ids) >= 3:
        rows.append([InlineKeyboardButton(f"✅ تأیید ({len(selected_ids)} نفر انتخاب‌شده)", callback_data="team_confirm_members")])
    return InlineKeyboardMarkup(rows)


async def team_toggle_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    selected = ctx.user_data.get("new_team", {}).get("selected_members", [])
    if pid in selected:
        selected.remove(pid)
    else:
        selected.append(pid)
    ctx.user_data["new_team"]["selected_members"] = selected
    players = ctx.user_data["new_team"].get("all_active_players", [])
    markup = _build_member_selector(players, selected)
    await query.edit_message_reply_markup(reply_markup=markup)


async def team_skip_members(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["new_team"]["selected_members"] = []
    await safe_edit_message_text(query, 
        f"📅 مرحله ۴: تاریخ ثبت‌نام تیم را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📅 تاریخ امروز ({today_shamsi()})", callback_data="team_date_today")]
        ])
    )
    return ST_TEAM_DATE


async def team_confirm_members(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await safe_edit_message_text(query, 
        f"📅 مرحله ۴: تاریخ ثبت‌نام تیم را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📅 تاریخ امروز ({today_shamsi()})", callback_data="team_date_today")]
        ])
    )
    return ST_TEAM_DATE


async def team_date_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["new_team"]["date"] = today_gregorian()
    await safe_edit_message_text(query, "🙋 مرحله ۵: این تیم توسط چه دانش‌آموزی درخواست ساخت شده؟ (فقط نام):")
    return ST_TEAM_REQUESTER


async def team_date_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_team"]["date"] = update.message.text.strip()
    await update.message.reply_text("🙋 مرحله ۵: این تیم توسط چه دانش‌آموزی درخواست ساخت شده؟ (فقط نام):")
    return ST_TEAM_REQUESTER


async def team_requester_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    requester = update.message.text.strip()
    team_data = ctx.user_data.get("new_team", {})
    uid = update.effective_user.id

    team_id = await db.create_team(
        name=team_data.get("name", "تیم جدید"),
        slogan=team_data.get("slogan", ""),
        requester_name=requester,
        created_by=uid
    )

    # Add selected members
    for pid in team_data.get("selected_members", []):
        await db.add_team_member(team_id, pid)

    team = await db.get_team(team_id)
    member_count = len(team_data.get("selected_members", []))

    await db.log_action(uid, "create_team", f"ثبت تیم: {team_data.get('name')}", team_id)

    await update.message.reply_text(
        f"{box('✅ تیم ' + team_data['name'] + ' ثبت شد')}\n\n"
        f"🔑 کد تیم: `{team['team_code']}`\n"
        f"🎯 شعار: _{team_data.get('slogan') or '—'}_\n"
        f"👥 اعضا: `{member_count}` نفر\n"
        f"🙋 درخواست‌دهنده: {requester}\n"
        f"⏱️ `{now_shamsi()}`",
        reply_markup=kb.kb_back("teams_list"),
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def teams_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if uid != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    keys = ["team_mode_enabled", "team_registration_enabled", "managers_can_create_teams"]
    settings = {k: await db.get_setting(k, "0") for k in keys}

    def tog(k):
        return "✅" if settings.get(k) == "1" else "❌"

    await safe_edit_message_text(query, 
        f"{box('⚙️ تنظیمات تیم')}\n\n📌 گزینه‌ای را تغییر دهید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🏆 وضعیت تیمی {tog('team_mode_enabled')}", callback_data="setting_team_mode"),
             InlineKeyboardButton(f"📝 ثبت‌نام با تیم {tog('team_registration_enabled')}", callback_data="setting_team_reg")],
            [InlineKeyboardButton(f"👤 مدیران سازنده تیم {tog('managers_can_create_teams')}", callback_data="setting_mgr_team")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="teams_menu")],
        ]),
        parse_mode="Markdown"
    )
