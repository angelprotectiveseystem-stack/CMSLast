from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import now_shamsi, box, separator, pishva_display, notify_pishva
from config import (PISHVA_ID, PISHVA_PASSWORD, ROLE_PISHVA,
                    ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER,
                    ST_ROLE_SELECT, ST_PISHVA_PASSWORD, ST_ADMIN_USERNAME,
                    ST_ADMIN_FULLNAME, ST_ACCESS_REQUEST_MSG)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == PISHVA_ID:
        return await show_pishva_welcome(update, ctx)
    admin = await db.get_admin(uid)
    if admin and admin["is_active"]:
        await db.update_admin_activity(uid)
        return await show_admin_welcome(update, ctx, admin)
    admin_login = await db.get_setting("admin_login_enabled", "1")
    if admin_login != "1":
        await update.message.reply_text("🔒 ورود ادمین‌ها غیرفعال است.")
        return ConversationHandler.END
    text = "⚔️ *سیستم فرماندهی شطرنج*\n\n🪪 نقش خود را انتخاب کنید:"
    await update.message.reply_text(text, reply_markup=kb.kb_role_select(), parse_mode="Markdown")
    return ST_ROLE_SELECT


async def show_pishva_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await db.log_action(PISHVA_ID, "login", "ورود پیشوا")
    ts = now_shamsi()
    pname = await pishva_display()

    # فقط خلاصه کوتاه — آمار تفصیلی در پنل پیشوا
    try:
        admins = await db.get_active_admins()
        pending = await db.get_pending_requests()
        pending_matches = await db.get_pending_matches()
        pending_tasks = [t for t in await db.get_all_tasks() if t["status"] == "pending"]
        status = await db.get_setting("system_status", "normal")
        status_map = {"normal": "🟢 نرمال", "bad": "🟡 احتیاطی", "danger": "🔴 خطرناک", "aps": "🪽 APS"}
        wh = await db.get_setting("working_hours_active", "0")
        wh_txt = "🟢 باز" if wh == "1" else "🔴 بسته" db_stat = await db.get_setting("db_manual_status", "1")
        db_txt = "🟢 دیتابیس: فعال" if db_stat == "1" else "⚠️ دیتابیس: غیرفعال"

        text = (
            "👑 *خوش آمدید، " + pname + "*\n"
            "⏱️ `" + ts + "`\n\n"
            "📡 " + status_map.get(status, status) + " | 🕐 " + wh_txt + "\n"
            "👥 ادمین: `" + str(len(admins)) + "` | "
            "📥 درخواست: `" + str(len(pending)) + "` | "
            "⏳ بی‌نتیجه: `" + str(len(pending_matches)) + "` | "
            "📋 وظایف: `" + str(len(pending_tasks)) + "`"
        )
    except Exception:
        text = "👑 *خوش آمدید، " + pname + "*\n⏱️ `" + ts + "`"

    if update.message:
        await update.message.reply_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    return ConversationHandler.END


async def show_admin_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE, admin):
    ts = now_shamsi()
    role_label = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    _aname = admin["display_name"] or admin["full_name"]

    # خلاصه کوتاه — آمار تفصیلی در پنل مدیریت
    try:
        pending_matches = await db.get_pending_matches()
        pending_tasks = [t for t in await db.get_tasks_for(admin["telegram_id"]) if t["status"] == "pending"]
        warned = [p for p in await db.get_all_players() if p["warnings"] > 0]
        status = await db.get_setting("system_status", "normal")
        status_map = {"normal": "🟢 نرمال", "bad": "🟡 احتیاطی", "danger": "🔴 خطرناک", "aps": "🪽 APS"}

        text = (
            role_label + " | *" + _aname + "*\n"
            "⏱️ `" + ts + "`\n"
            "🚦 " + status_map.get(status, status) + "\n\n"
            "⏳ بی‌نتیجه: `" + str(len(pending_matches)) + "` | "
            "⚠️ با اخطار: `" + str(len(warned)) + "` | "
            "📋 وظایف: `" + str(len(pending_tasks)) + "`"
        )
    except Exception:
        text = role_label + " | *" + _aname + "*\n⏱️ `" + ts + "`"

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
        "👤 یوزرنیم تلگرام خود را وارد کنید:\n_(باید با @ شروع شود و شامل حروف باشد)_",
        parse_mode="Markdown"
    )
    return ST_ADMIN_USERNAME


async def on_pishva_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ این حساب مجاز نیست.")
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
    ctx.user_data["reg_fullname"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 یک پیام برای پیشوا بنویسید (یا /skip):",
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
        "👤 " + full_name + " | " + username + "\n"
        "💼 " + role_label + "\n"
        "📝 " + (msg or "—") + "\n"
        "⏱️ `" + ts + "`"
    )
    await notify_pishva(ctx.bot, notif, reply_markup=kb.kb_access_request(req_id))
    await update.message.reply_text("✅ درخواست ارسال شد. منتظر تأیید پیشوا باشید.")
    return ConversationHandler.END


async def on_approve_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط پیشوا.", show_alert=True)
        return
    req_id = int(query.data.split("_")[-1])
    req = await db.get_access_request(req_id)
    if not req or req["status"] != "pending":
        await query.answer("قبلاً پردازش شده.", show_alert=True)
        return
    await db.update_access_request(req_id, "approved")
    await db.create_admin(req["telegram_id"], req["username"], req["full_name"], req["role"])
    role_label = "🏆 مدیر مسابقات" if req["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    try:
        await ctx.bot.send_message(
            chat_id=req["telegram_id"],
            text="✅ *دسترسی تأیید شد*\n💼 " + role_label + "\n\n/start بزنید.",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await query.edit_message_text(query.message.text + "\n\n✅ *تأیید شد*", parse_mode="Markdown")
    await query.answer("✅ تأیید شد.")


async def on_reject_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط پیشوا.", show_alert=True)
        return
    req_id = int(query.data.split("_")[-1])
    req = await db.get_access_request(req_id)
    if not req or req["status"] != "pending":
        await query.answer("قبلاً پردازش شده.", show_alert=True)
        return
    await db.update_access_request(req_id, "rejected")
    try:
        await ctx.bot.send_message(
            chat_id=req["telegram_id"],
            text="❌ درخواست دسترسی شما رد شد.\nبرای اطلاعات بیشتر با پیشوا تماس بگیرید."
        )
    except Exception:
        pass
    await query.edit_message_text(query.message.text + "\n\n❌ *رد شد*", parse_mode="Markdown")
    await query.answer("❌ رد شد.")
