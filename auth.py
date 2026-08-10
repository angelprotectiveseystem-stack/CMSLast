from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import now_shamsi, box, separator, pishva_display, broadcast_to_admins, notify_pishva
from config import (PISHVA_ID, PISHVA_PASSWORD, ROLE_PISHVA,
                    ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER,
                    ST_ROLE_SELECT, ST_PISHVA_PASSWORD, ST_ADMIN_USERNAME,
                    ST_ADMIN_FULLNAME, ST_ADMIN_ROLE_SELECT, ST_ACCESS_REQUEST_MSG)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # Check if already registered
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
        f"{box('⚔️  سیستم فرماندهی شطرنج  ⚔️')}\n"
        f"🏰 مدرسه — نسخه ۱.۰\n\n"
        f"🔮 سیستم آنلاین است.\n"
        f"🛰️ اتصال برقرار شد.\n"
        f"⏱️ `{ts}`\n\n"
        f"{separator('🪪 احراز هویت')}\n"
        f"نقش خود را انتخاب کنید:"
    )
    await update.message.reply_text(text, reply_markup=kb.kb_role_select(), parse_mode="Markdown")
    return ST_ROLE_SELECT


async def show_pishva_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await db.log_action(PISHVA_ID, "login", "ورود پیشوا")
    ts = now_shamsi()
    pname = await pishva_display()
    admins = await db.get_active_admins()
    today_matches = await db.get_matches_by_filter("today")
    default_t = await db.get_default_tournament()
    pending = await db.get_pending_requests()

    text = (
        f"{box(f'👑 پنل فرماندهی {pname}')}\n\n"
        f"🔱 خوش آمدید، {pname}.\n"
        f"⏱️ ورود: `{ts}`\n\n"
        f"{separator('📡 وضعیت سیستم')}\n"
        f"🟢 وضعیت: نرمال\n"
        f"👥 ادمین‌های فعال: `{len(admins)}`\n"
        f"♟️ مسابقات امروز: `{len(today_matches)}`\n"
        f"🏅 تورنمنت فعال: `{default_t['name'] if default_t else 'ندارد'}`\n"
        f"📥 درخواست‌های جدید: `{len(pending)}`\n"
        f"{separator()}"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    return ConversationHandler.END


async def show_admin_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE, admin):
    ts = now_shamsi()
    role_label = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    _aname = admin["display_name"] or admin["full_name"]
    text = (
        f"{box('پنل مدیریت — ' + _aname)}\n\n"
        f"✅ دسترسی تأیید شد.\n"
        f"⏱️ ورود: `{ts}`\n"
        f"💼 سمت: {role_label}\n\n"
        f"سیستم آماده دریافت دستورات است. 🛰️"
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
        # Grant temp access — but this isn't the real pishva so just show error
        await update.message.reply_text("❌ این حساب کاربری مجاز نیست.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ رمز اشتباه است.")
        return ConversationHandler.END


async def on_admin_username(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    if not username.startswith("@") or not any(c.isalpha() for c in username[1:]):
        await update.message.reply_text(
            "❌ یوزرنیم باید با @ شروع شود و حاوی حروف باشد.\nدوباره وارد کنید:"
        )
        return ST_ADMIN_USERNAME
    ctx.user_data["reg_username"] = username
    await update.message.reply_text("✍️ نام و نام‌خانوادگی خود را وارد کنید:")
    return ST_ADMIN_FULLNAME


async def on_admin_fullname(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    ctx.user_data["reg_fullname"] = full_name
    await update.message.reply_text("📝 یک پیام/توضیح برای پیشوا بنویسید (اختیاری):\n_(یا /skip برای رد کردن)_",
                                    parse_mode="Markdown")
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
        f"📥 *درخواست دسترسی جدید*\n\n"
        f"👤 نام: {full_name}\n"
        f"🔗 یوزرنیم: {username}\n"
        f"💼 نقش: {role_label}\n"
        f"📝 پیام: {msg or '—'}\n"
        f"⏱️ زمان: `{ts}`"
    )
    await notify_pishva(ctx.bot, notif, reply_markup=kb.kb_access_request(req_id))

    await update.message.reply_text(
        "✅ درخواست شما ارسال شد.\nپس از تأیید پیشوا، دسترسی خواهید داشت."
    )
    return ConversationHandler.END


# ─── Approve / Reject Access Request (global callback) ────────
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
        f"{box('✅ درخواست تأیید شد')}\n\n"
        f"🎉 {req['full_name']} عزیز،\n"
        f"درخواست دسترسی شما تأیید شد.\n"
        f"💼 سمت: {role_label}\n"
        f"⏱️ زمان: `{ts}`\n\n"
        f"/start بزنید تا وارد شوید."
    )
    try:
        await ctx.bot.send_message(chat_id=req["telegram_id"], text=approval_text, parse_mode="Markdown")
    except Exception:
        pass

    await query.edit_message_text(
        query.message.text + f"\n\n✅ *تأیید شد توسط پیشوا*",
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
        f"{box('❌ درخواست رد شد')}\n\n"
        f"{req['full_name']} عزیز،\n"
        f"متأسفانه درخواست دسترسی شما رد شد.\n"
        f"⏱️ زمان: `{ts}`\n\n"
        f"برای اطلاعات بیشتر با پیشوا تماس بگیرید."
    )
    try:
        await ctx.bot.send_message(chat_id=req["telegram_id"], text=rejection_text, parse_mode="Markdown")
    except Exception:
        pass

    await query.edit_message_text(
        query.message.text + f"\n\n❌ *رد شد توسط پیشوا*",
        parse_mode="Markdown"
    )
    await query.answer("❌ درخواست رد شد.")
