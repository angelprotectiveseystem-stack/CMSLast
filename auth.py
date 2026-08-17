from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import now_shamsi, box, separator, pishva_display, broadcast_to_admins, notify_pishva, progress_bar
from config import (PISHVA_ID, PISHVA_PASSWORD, ROLE_PISHVA,
                    ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER,
                    ST_ROLE_SELECT, ST_PISHVA_PASSWORD, ST_ADMIN_USERNAME,
                    ST_ADMIN_FULLNAME, ST_ADMIN_ROLE_SELECT, ST_ACCESS_REQUEST_MSG)


def _make_header(icon, title, subtitle=""):
    line = "═" * 32
    h = "╔" + line + "╗\n"
    h += "║  " + icon + " " + title[:24].ljust(26) + "║\n"
    if subtitle:
        h += "║  " + subtitle[:28].ljust(28) + "  ║\n"
    h += "╚" + line + "╝"
    return h


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == PISHVA_ID:
        return await show_pishva_welcome(update, ctx)
    admin = await db.get_admin(uid)
    if admin and admin["is_active"]:
        await db.update_admin_activity(uid)
        return await show_admin_welcome(update, ctx, admin)
    bot_active = await db.get_setting("bot_active_for_admins", "1")
    admin_login = await db.get_setting("admin_login_enabled", "1")
    if admin_login != "1":
        await update.message.reply_text("🔒 ورود ادمین‌ها در حال حاضر غیرفعال است.")
        return ConversationHandler.END
    ts = now_shamsi()
    text = (
        "╔══════════════════════════════════╗\n"
        "║  ⚔️  سیستم فرماندهی شطرنج  ⚔️  ║\n"
        "║      🏰 مدرسه — نسخه ۱.۰        ║\n"
        "╚══════════════════════════════════╝\n\n"
        "🔮 سیستم آنلاین است.\n"
        "🛰️ اتصال برقرار شد.\n"
        "⏱️ `" + ts + "`\n\n"
        + separator("🪪 احراز هویت") + "\n"
        "نقش خود را انتخاب کنید:"
    )
    await update.message.reply_text(text, reply_markup=kb.kb_role_select(), parse_mode="Markdown")
    return ST_ROLE_SELECT


async def show_pishva_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await db.log_action(PISHVA_ID, "login", "ورود پیشوا")
    ts = now_shamsi()
    pname = await pishva_display()

    try:
        admins = await db.get_active_admins()
        today_matches = await db.get_matches_by_filter("today")
        all_matches = await db.get_matches_by_filter("all")
        default_t = await db.get_default_tournament()
        pending = await db.get_pending_requests()
        all_players = await db.get_all_players()
        active_players = await db.get_continuing_players()
        pending_matches = await db.get_pending_matches()
        tasks_all = await db.get_all_tasks()
        pending_tasks = [t for t in tasks_all if t["status"] == "pending"]
        status = await db.get_setting("system_status", "normal")
        wh = await db.get_setting("working_hours_active", "0")
        status_map = {
            "normal": "🟢 نرمال", "bad": "🟡 احتیاطی",
            "danger": "🔴 خطرناک", "aps": "🪽 APS"
        }
        wh_txt = "🟢 باز" if wh == "1" else "🔴 بسته"
        done_matches = [m for m in all_matches if m["result"]]
        pct = int(len(done_matches) / len(all_matches) * 100) if all_matches else 0
        bar = progress_bar(pct)
        sorted_p = sorted(all_players, key=lambda p: p["wins"], reverse=True)
        top_player = sorted_p[0]["full_name"] if sorted_p and sorted_p[0]["wins"] > 0 else "—"
        top_wins = sorted_p[0]["wins"] if sorted_p else 0
        tourn_name = default_t["name"] if default_t else "ندارد"

        lines = [
            "╔══════════════════════════════╗",
            "║   👑 پنل فرماندهی پیشوا     ║",
            "╚══════════════════════════════╝",
            "",
            "🔱 خوش آمدید، *" + pname + "*",
            "⏱️ `" + ts + "`",
            "",
            separator("🚦 وضعیت سیستم"),
            "📡 سیستم: " + status_map.get(status, status),
            "🕐 ساعت کاری: " + wh_txt,
            "📥 درخواست جدید: `" + str(len(pending)) + "`",
            "",
            separator("👥 ادمین‌ها"),
            "✅ فعال: `" + str(len(admins)) + "` نفر",
            "📋 وظایف در انتظار: `" + str(len(pending_tasks)) + "`",
            "",
            separator("♟️ مسابقات"),
            "🏅 تورنمنت: *" + tourn_name + "*",
            "🎮 امروز: `" + str(len(today_matches)) + "` | ⏳ بی‌نتیجه: `" + str(len(pending_matches)) + "`",
            "🏁 پیشرفت: `" + bar + "`",
            "",
            separator("👤 بازیکنان"),
            "👥 کل: `" + str(len(all_players)) + "` | ✅ فعال: `" + str(len(active_players)) + "`",
            "🌟 برترین: *" + top_player + "* (" + str(top_wins) + " برد)",
            separator(),
        ]
        text = "\n".join(lines)

    except Exception:
        text = (
            "╔══════════════════════════════╗\n"
            "║   👑 پنل فرماندهی پیشوا     ║\n"
            "╚══════════════════════════════╝\n\n"
            "🔱 خوش آمدید، *" + pname + "*\n"
            "⏱️ `" + ts + "`\n\n"
            "🛰️ سیستم آماده دریافت دستورات است."
        )

    if update.message:
        await update.message.reply_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    return ConversationHandler.END


async def show_admin_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE, admin):
    ts = now_shamsi()
    role_label = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    role_icon = "🏆" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️"
    _aname = admin["display_name"] or admin["full_name"]

    try:
        pending_matches = await db.get_pending_matches()
        active_players = await db.get_continuing_players()
        tasks = await db.get_tasks_for(admin["telegram_id"])
        pending_tasks = [t for t in tasks if t["status"] == "pending"]
        all_players = await db.get_all_players()
        warned = [p for p in all_players if p["warnings"] > 0]
        default_t = await db.get_default_tournament()
        today_matches = await db.get_matches_by_filter("today")
        done_today = [m for m in today_matches if m["result"]]
        all_matches = await db.get_matches_by_filter("all")
        status = await db.get_setting("system_status", "normal")
        status_map = {
            "normal": "🟢 نرمال", "bad": "🟡 احتیاطی",
            "danger": "🔴 خطرناک", "aps": "🪽 APS"
        }
        tourn_name = default_t["name"] if default_t else "ندارد"

        # Last result
        last_txt = ""
        for m in reversed(all_matches):
            if m["result"]:
                if m["result"] == "white":
                    last_txt = "\n" + separator("🏆 آخرین نتیجه") + "\n🥇 *" + m["white_name"] + "* برنده شد"
                elif m["result"] == "black":
                    last_txt = "\n" + separator("🏆 آخرین نتیجه") + "\n🥇 *" + m["black_name"] + "* برنده شد"
                else:
                    last_txt = "\n" + separator("🏆 آخرین نتیجه") + "\n🤝 تساوی"
                break

        lines = [
            "╔══════════════════════════════╗",
            "║  " + role_icon + " پنل — " + _aname[:18] + "  ║",
            "╚══════════════════════════════╝",
            "",
            "⏱️ ورود: `" + ts + "`",
            "💼 سمت: " + role_label,
            "🚦 وضعیت: " + status_map.get(status, status),
            "🏅 تورنمنت: *" + tourn_name + "*",
            "",
            separator("📊 وضعیت لحظه‌ای"),
            "♟️ مسابقات بی‌نتیجه: `" + str(len(pending_matches)) + "`",
            "✅ بازیکنان فعال: `" + str(len(active_players)) + "`",
            "⚠️ بازیکنان با اخطار: `" + str(len(warned)) + "`",
            "📋 وظایف در انتظار: `" + str(len(pending_tasks)) + "`",
            "🎮 نتایج امروز: `" + str(len(done_today)) + "`",
        ]
        if last_txt:
            lines.append(last_txt)
        lines.append(separator())
        text = "\n".join(lines)

    except Exception:
        text = (
            "╔══════════════════════════════╗\n"
            "║  " + role_icon + " پنل — " + _aname[:18] + "  ║\n"
            "╚══════════════════════════════╝\n\n"
            "✅ دسترسی تأیید شد.\n"
            "⏱️ `" + ts + "`\n"
            "💼 " + role_label
        )

    markup = kb.kb_tournament_manager_main() if admin["role"] == ROLE_TOURNAMENT_MANAGER else kb.kb_security_manager_main()
    if update.message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    return ConversationHandler.END


async def on_role_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "role_pishva":
        uid = query.from_user.id
        if uid == PISHVA_ID:
            return await show_pishva_welcome(update, ctx)
        await query.edit_message_text("🔐 رمز پیشوا را وارد کنید:")
        ctx.user_data["pending_role"] = ROLE_PISHVA
        return ST_PISHVA_PASSWORD
    role = ROLE_TOURNAMENT_MANAGER if data == "role_tournament" else ROLE_SECURITY_MANAGER
    ctx.user_data["pending_role"] = role
    await query.edit_message_text(
        "👤 لطفاً یوزرنیم تلگرام خود را وارد کنید:\n_(باید با @ شروع شود و شامل حروف باشد)_",
        parse_mode="Markdown"
    )
    return ST_ADMIN_USERNAME


async def on_pishva_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == PISHVA_PASSWORD:
        await update.message.reply_text("❌ این حساب کاربری مجاز نیست.")
    else:
        await update.message.reply_text("❌ رمز اشتباه است.")
    return ConversationHandler.END


async def on_admin_username(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    if not username.startswith("@") or not any(c.isalpha() for c in username[1:]):
        await update.message.reply_text("❌ یوزرنیم باید با @ شروع شود و حاوی حروف باشد.\nدوباره وارد کنید:")
        return ST_ADMIN_USERNAME
    ctx.user_data["reg_username"] = username
    await update.message.reply_text("✍️ نام و نام‌خانوادگی خود را وارد کنید:")
    return ST_ADMIN_FULLNAME


async def on_admin_fullname(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    ctx.user_data["reg_fullname"] = full_name
    await update.message.reply_text(
        "📝 یک پیام/توضیح برای پیشوا بنویسید (اختیاری):\n_(یا /skip برای رد کردن)_",
        parse_mode="Markdown"
    )
    return ST_ACCESS_REQUEST_MSG


async def on_access_request_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = ""
    if update.message.text and update.message.text != "/skip":
        msg = update.message.text.strip()
    uid = update.effective_user.id
    username = ctx.user_data.get("reg_username", "")
    full_name = ctx.user_data.get("reg_fullname", "")
    role = ctx.user_data.get("pending_role", ROLE_TOURNAMENT_MANAGER)
    req_id = await db.create_access_request(uid, username, full_name, role, msg)
    role_label = "🏆 مدیر مسابقات" if role == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    ts = now_shamsi()
    notif = (
        "📥 *درخواست دسترسی جدید*\n\n"
        "👤 نام: " + full_name + "\n"
        "🔗 یوزرنیم: " + username + "\n"
        "💼 نقش: " + role_label + "\n"
        "📝 پیام: " + (msg or "—") + "\n"
        "⏱️ زمان: `" + ts + "`"
    )
    await notify_pishva(ctx.bot, notif, reply_markup=kb.kb_access_request(req_id))
    await update.message.reply_text("✅ درخواست شما ارسال شد.\nپس از تأیید پیشوا، دسترسی خواهید داشت.")
    return ConversationHandler.END


async def on_approve_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط پیشوا می‌تواند این کار را انجام دهد.", show_alert=True)
        return
    req_id = int(query.data.split("_")[-1])
    req = await db.get_access_request(req_id)
    if not req or req["status"] != "pending":
        await query.answer("این درخواست قبلاً پردازش شده.", show_alert=True)
        return
    await db.update_access_request(req_id, "approved")
    await db.create_admin(req["telegram_id"], req["username"], req["full_name"], req["role"])
    role_label = "🏆 مدیر مسابقات" if req["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    ts = now_shamsi()
    approval_text = (
        box("✅ درخواست تأیید شد") + "\n\n"
        "🎉 " + req["full_name"] + " عزیز،\n"
        "درخواست دسترسی شما تأیید شد.\n"
        "💼 سمت: " + role_label + "\n"
        "⏱️ زمان: `" + ts + "`\n\n"
        "/start بزنید تا وارد شوید."
    )
    try:
        await ctx.bot.send_message(chat_id=req["telegram_id"], text=approval_text, parse_mode="Markdown")
    except Exception:
        pass
    await query.edit_message_text(
        query.message.text + "\n\n✅ *تأیید شد توسط پیشوا*",
        parse_mode="Markdown"
    )
    await query.answer("✅ دسترسی تأیید شد.")


async def on_reject_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط پیشوا می‌تواند این کار را انجام دهد.", show_alert=True)
        return
    req_id = int(query.data.split("_")[-1])
    req = await db.get_access_request(req_id)
    if not req or req["status"] != "pending":
        await query.answer("این درخواست قبلاً پردازش شده.", show_alert=True)
        return
    await db.update_access_request(req_id, "rejected")
    ts = now_shamsi()
    rejection_text = (
        box("❌ درخواست رد شد") + "\n\n"
        + req["full_name"] + " عزیز،\n"
        "متأسفانه درخواست دسترسی شما رد شد.\n"
        "⏱️ زمان: `" + ts + "`\n\n"
        "برای اطلاعات بیشتر با پیشوا تماس بگیرید."
    )
    try:
        await ctx.bot.send_message(chat_id=req["telegram_id"], text=rejection_text, parse_mode="Markdown")
    except Exception:
        pass
    await query.edit_message_text(
        query.message.text + "\n\n❌ *رد شد توسط پیشوا*",
        parse_mode="Markdown"
    )
    await query.answer("❌ درخواست رد شد.")
