from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import (box, separator, now_shamsi, broadcast_to_admins,
    notify_pishva, pishva_display, log_line)
from config import (PISHVA_ID, STATUS_NORMAL, STATUS_BAD, STATUS_DANGER, STATUS_APS,
    ST_TOURNAMENT_NAME, ST_PISHVA_NAME_CHANGE, ST_ADMIN_NAME_CHANGE,
    ST_NEW_YEAR_CONFIRM, ST_NEW_YEAR_PASSWORD, ST_REPAIR_REASON,
    ST_GROUP_ID, ST_CHANNEL_ID, ST_UPDATE_VERSION, ST_UPDATE_DESC,
    NEW_YEAR_PASSWORD)
import io

# ─── Status Management ────────────────────────────────────────
async def pishva_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط پیشوا.", show_alert=True)
        return
    await query.answer()
    current = await db.get_setting("system_status", STATUS_NORMAL)
    status_labels = {STATUS_NORMAL: "🟢 نرمال", STATUS_BAD: "🟡 بد",
        STATUS_DANGER: "🔴 خطرناک", STATUS_APS: "🪽 APS"}
    await query.edit_message_text(
        f"{box('🚦 مدیریت وضعیت سیستم')}\n\n"
        f"⚡ وضعیت فعلی: *{status_labels.get(current, current)}*\n\n"
        f"📌 وضعیت جدید را انتخاب کنید:",
        reply_markup=kb.kb_status_select(current),
        parse_mode="Markdown"
    )

async def set_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    new_status = query.data.split("_")[-1]
    await db.set_setting("system_status", new_status)
    await db.log_action(PISHVA_ID, "set_status", f"تغییر وضعیت به: {new_status}")
    status_labels = {STATUS_NORMAL: "🟢 نرمال", STATUS_BAD: "🟡 بد",
        STATUS_DANGER: "🔴 خطرناک", STATUS_APS: "🪽 APS"}
    pname = await pishva_display()
    ts = now_shamsi()
    if new_status == STATUS_DANGER:
        notif = (
            f"{box('🔴 هشدار — وضعیت بحرانی')}\n\n"
            f"⚠️ سیستم وارد وضعیت خطرناک شد.\n"
            f"🛡️ پروتکل امنیتی فعال است.\n"
            f"🔒 دسترسی شما موقتاً معلق شد.\n"
            f"⏱️ `{ts}`\n\n"
            f"منتظر دستور {pname} باشید."
        )
        await broadcast_to_admins(ctx.bot, notif)
    elif new_status == STATUS_APS:
        notif = (
            f"{box('🪽 حالت امنیتی APS')}\n\n"
            f"🔐 امنیت به سیستم APS واگذار شده.\n"
            f"🔒 دسترسی همه قطع شده است.\n"
            f"⏱️ `{ts}`"
        )
        await broadcast_to_admins(ctx.bot, notif)
    elif new_status == STATUS_NORMAL:
        notif = (
            f"🟢 سیستم به وضعیت نرمال بازگشت.\n"
            f"✅ دسترسی شما فعال است.\n"
            f"⏱️ `{ts}`"
        )
        await broadcast_to_admins(ctx.bot, notif)
    await query.edit_message_text(
        f"✅ وضعیت به *{status_labels.get(new_status, new_status)}* تغییر یافت.",
        reply_markup=kb.kb_back("pishva_status"),
        parse_mode="Markdown"
    )

# ─── Settings ─────────────────────────────────────────────────
async def pishva_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    keys = ["notifications_enabled", "communications_enabled", "help_enabled",
        "match_registration_enabled", "admin_login_enabled", "bot_active_for_admins",
        "team_mode_enabled", "team_registration_enabled", "managers_can_create_teams"]
    settings = {}
    for k in keys:
        settings[k] = await db.get_setting(k, "1")
    await query.edit_message_text(
        f"{box('⚙️ تنظیمات ربات')}\n\n📌 گزینه موردنظر را تغییر دهید:",
        reply_markup=kb.kb_pishva_settings_simple(settings),
        parse_mode="Markdown"
    )

async def toggle_setting(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    key_map = {
        "setting_notifications": "notifications_enabled",
        "setting_communications": "communications_enabled",
        "setting_help": "help_enabled",
        "setting_match_reg": "match_registration_enabled",
        "setting_admin_login": "admin_login_enabled",
        "setting_bot_active": "bot_active_for_admins",
        "setting_team_mode": "team_mode_enabled",
        "setting_team_reg": "team_registration_enabled",
        "setting_mgr_team": "managers_can_create_teams",
    }
    key = key_map.get(query.data)
    if key:
        current = await db.get_setting(key, "1")
        new_val = "0" if current == "1" else "1"
        await db.set_setting(key, new_val)
        await db.log_action(PISHVA_ID, "toggle_setting", f"{key} -> {new_val}")
    keys = ["notifications_enabled", "communications_enabled", "help_enabled",
        "match_registration_enabled", "admin_login_enabled", "bot_active_for_admins",
        "team_mode_enabled", "team_registration_enabled", "managers_can_create_teams"]
    settings = {k: await db.get_setting(k, "1") for k in keys}
    await query.edit_message_text(
        f"{box('⚙️ تنظیمات ربات')}\n\n📌 گزینه موردنظر را تغییر دهید:",
        reply_markup=kb.kb_pishva_settings_simple(settings),
        parse_mode="Markdown"
    )

# ─── Action Logs ─────────────────────────────────────────────
async def pishva_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        f"{box('🔍 پیگیری اقدامات')}\n\n📌 بازه زمانی را انتخاب کنید:",
        reply_markup=kb.kb_logs_filter(),
        parse_mode="Markdown"
    )

async def show_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.split("_")[-1]
    logs = await db.get_action_logs(period)
    admins = {a["telegram_id"]: (a["display_name"] or a["full_name"]) for a in await db.get_all_admins()}
    pname = await pishva_display()
    if not logs:
        await query.edit_message_text("❗ هیچ اقدامی در این بازه ثبت نشده.", reply_markup=kb.kb_logs_filter())
        return
    lines = []
    for log in logs[:20]:
        name = pname if log["admin_id"] == PISHVA_ID else admins.get(log["admin_id"], str(log["admin_id"]))
        t = str(log["logged_at"] or "")[:16]
        lines.append(log_line(t, name, log["action_type"] + ": " + (log["description"] or "")))
    text = f"{box('🔍 لاگ اقدامات')}\n\n" + "\n".join(lines)
    await query.edit_message_text(text, reply_markup=kb.kb_logs_filter(), parse_mode="Markdown")

# ─── Access Requests ─────────────────────────────────────────
async def pishva_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    reqs = await db.get_pending_requests()
    if not reqs:
        await query.edit_message_text(
            f"{box('📥 درخواست‌های دسترسی')}\n\n✅ هیچ درخواست جدیدی وجود ندارد.",
            reply_markup=kb.kb_back("pishva_panel"),
            parse_mode="Markdown"
        )
        return
    for req in reqs:
        role_label = "🏆 مدیر مسابقات" if req["role"] == "tournament_manager" else "🛡️ مدیر امنیتی"
        text = (
            f"📥 *درخواست دسترسی*\n\n"
            f"👤 نام: {req['full_name']}\n"
            f"🔗 یوزرنیم: {req['username']}\n"
            f"💼 نقش: {role_label}\n"
            f"📝 پیام: {req['message'] or '—'}\n"
            f"⏱️ زمان: `{str(req['requested_at'])[:19]}`"
        )
        try:
            await query.message.reply_text(text, reply_markup=kb.kb_access_request(req["id"]), parse_mode="Markdown")
        except Exception:
            pass
    await query.edit_message_text(
        f"📥 {len(reqs)} درخواست نمایش داده شد.",
        reply_markup=kb.kb_back("pishva_panel"),
        parse_mode="Markdown"
    )

# ─── Backup ───────────────────────────────────────────────────
async def pishva_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        f"{box('💾 سیستم پشتیبان‌گیری')}\n\n📌 بازه زمانی را انتخاب کنید:",
        reply_markup=kb.kb_backup_main(),
        parse_mode="Markdown"
    )

async def backup_period_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.split("_")[-1]
    ctx.user_data["backup_period"] = period
    await query.edit_message_text(
        f"📊 فرمت فایل را انتخاب کنید:",
        reply_markup=kb.kb_backup_format()
    )

async def backup_format_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data.split("_")[-1]
    period = ctx.user_data.get("backup_period", "all")
    await query.edit_message_text("⏳ در حال تهیه بکاپ، لطفاً صبر کنید...")
    try:
        from backup_utils import send_backup
        await send_backup(ctx.bot, PISHVA_ID, period, fmt)
        await db.log_action(PISHVA_ID, "backup", f"تهیه بکاپ {fmt} — {period}")
        await query.edit_message_text(
            f"✅ بکاپ با موفقیت تهیه و ارسال شد.\n📁 فرمت: {fmt} | بازه: {period}",
            reply_markup=kb.kb_back("pishva_panel")
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ خطا در تهیه بکاپ:\n`{str(e)}`",
            reply_markup=kb.kb_back("pishva_panel"),
            parse_mode="Markdown"
        )

# ─── Working Hours ────────────────────────────────────────────
async def pishva_workhours(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        f"{box('🕐 ساعت کاری')}\n\n📌 عملیات را انتخاب کنید:",
        reply_markup=kb.kb_workhours(),
        parse_mode="Markdown"
    )

async def workhour_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.set_setting("bot_active_for_admins", "1")
    await db.set_setting("working_hours_active", "1")
    ts = now_shamsi()
    notif = (
        f"{box('🟢 آغاز ساعت کاری')}\n\n"
        f"درود بر شما،\n"
        f"⏱️ ساعت کاری از `{ts}`\n"
        f" توسط پیشوا آغاز شد.\n\n"
        f"✅ دسترسی شما به ربات فعال است.\n"
        f"سیستم آماده دریافت فرمان. 🛰️"
    )
    await broadcast_to_admins(ctx.bot, notif)
    await db.log_action(PISHVA_ID, "workhour_start", f"آغاز ساعت کاری: {ts}")
    await query.edit_message_text(f"🟢 ساعت کاری آغاز شد و اعلان برای همه ارسال شد.", reply_markup=kb.kb_back("pishva_panel"))

async def workhour_end(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.set_setting("bot_active_for_admins", "0")
    await db.set_setting("working_hours_active", "0")
    ts = now_shamsi()
    notif = (
        f"{box('🔴 پایان ساعت کاری')}\n\n"
        f"خسته نباشید! 🌙\n"
        f"⏱️ ساعت کاری در `{ts}`\n"
        f" به پایان رسید.\n\n"
        f"🔒 دسترسی شما موقتاً قطع شد.\n"
        f"ممنون از زحمات شما! 🏆"
    )
    await broadcast_to_admins(ctx.bot, notif)
    await db.log_action(PISHVA_ID, "workhour_end", f"پایان ساعت کاری: {ts}")
    await query.edit_message_text(f"🔴 ساعت کاری پایان یافت.", reply_markup=kb.kb_back("pishva_panel"))

# ─── Repair Mode ──────────────────────────────────────────────
async def pishva_repair(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    repair_status = await db.get_setting("repair_mode", "0")
    status = "🔧 فعال" if repair_status == "1" else "✅ غیرفعال"
    await query.edit_message_text(
        f"{box('🔧 حالت تعمیر')}\n\nوضعیت فعلی: {status}",
        reply_markup=kb.kb_repair_menu(),
        parse_mode="Markdown"
    )

async def repair_on(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.set_setting("repair_mode", "1")
    await db.set_setting("bot_update_mode", "1")
    reason = await db.get_setting("repair_reason", "")
    ts = now_shamsi()
    notif = (
        f"{box('🔧 حالت تعمیر فعال شد')}\n\n"
        f"🛠️ ربات در حال تعمیر و بروزرسانی است.\n"
        f"⏱️ `{ts}`\n"
        f"{'📝 دلیل: ' + reason if reason else ''}\n\n"
        f"لطفاً منتظر بمانید."
    )
    await broadcast_to_admins(ctx.bot, notif)
    await db.log_action(PISHVA_ID, "repair_on", "فعال‌سازی حالت تعمیر")
    await query.edit_message_text("🔧 حالت تعمیر فعال شد.", reply_markup=kb.kb_back("pishva_repair"))

async def repair_off(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.set_setting("repair_mode", "0")
    await db.set_setting("bot_update_mode", "0")
    ts = now_shamsi()
    notif = f"✅ تعمیر پایان یافت. ربات آماده استفاده است.\n⏱️ `{ts}`"
    await broadcast_to_admins(ctx.bot, notif)
    await db.log_action(PISHVA_ID, "repair_off", "غیرفعال‌سازی حالت تعمیر")
    await query.edit_message_text("✅ حالت تعمیر غیرفعال شد.", reply_markup=kb.kb_back("pishva_repair"))

async def repair_reason_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 دلیل تعمیر را وارد کنید:")
    return ST_REPAIR_REASON

async def repair_reason_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    await db.set_setting("repair_reason", reason)
    await update.message.reply_text(f"✅ دلیل تعمیر ذخیره شد:\n_{reason}_", parse_mode="Markdown")
    return ConversationHandler.END

# ─── Database Status (Manual) ──────────────────────────────────
async def _render_dbstatus(query):
    current = await db.get_setting("db_manual_status", "1")
    label = "🟢 فعال" if current == "1" else "⚠️ غیرفعال"
    await query.edit_message_text(
        f"{box('🗄️ وضعیت دیتابیس')}\n\nوضعیت فعلی: {label}\n\n"
        f"این وضعیت کاملاً دستی است و مستقل از اتصال واقعی به دیتابیس.",
        reply_markup=kb.kb_dbstatus_menu(current),
        parse_mode="Markdown"
    )

async def pishva_dbstatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    await _render_dbstatus(query)

async def dbstatus_on(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.set_setting("db_manual_status", "1")
    await db.log_action(PISHVA_ID, "dbstatus_on", "تنظیم دستی وضعیت دیتابیس: فعال")
    await _render_dbstatus(query)

async def dbstatus_off(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.set_setting("db_manual_status", "0")
    await db.log_action(PISHVA_ID, "dbstatus_off", "تنظیم دستی وضعیت دیتابیس: غیرفعال")
    await _render_dbstatus(query)

# ─── Identity ─────────────────────────────────────────────────
async def pishva_identity(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    pname = await pishva_display()
    await query.edit_message_text(
        f"{box('🪪 تغییر هویت')}\n\nنام نمایشی فعلی پیشوا: *{pname}*",
        reply_markup=kb.kb_identity(),
        parse_mode="Markdown"
    )

async def identity_pishva_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 نام نمایشی جدید برای پیشوا را وارد کنید:")
    return ST_PISHVA_NAME_CHANGE

async def identity_pishva_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    await db.set_setting("pishva_display_name", new_name)
    await db.log_action(PISHVA_ID, "identity_change", f"نام پیشوا به: {new_name}")
    await update.message.reply_text(
        f"✅ نام نمایشی پیشوا به *{new_name}* تغییر یافت.\n"
        f"این تغییر در سراسر ربات اعمال شد.",
        reply_markup=kb.kb_back("pishva_identity"),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def identity_admin_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admins = await db.get_all_admins()
    if not admins:
        await query.edit_message_text("❗ هیچ مدیری ثبت نشده.", reply_markup=kb.kb_back("pishva_identity"))
        return
    rows = []
    for i in range(0, len(admins), 2):
        row = [InlineKeyboardButton(
            f"👤 {a['display_name'] or a['full_name']}",
            callback_data=f"identity_set_{a['telegram_id']}"
        ) for a in admins[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_identity")])
    await query.edit_message_text(
        "👥 مدیری که می‌خواهید نامش را تغییر دهید انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def identity_admin_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    ctx.user_data["identity_admin_tid"] = tid
    admin = await db.get_admin(tid)
    await query.edit_message_text(
        f"✏️ نام نمایشی جدید برای *{admin['full_name']}* را وارد کنید:",
        parse_mode="Markdown"
    )
    return ST_ADMIN_NAME_CHANGE

async def identity_admin_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    tid = ctx.user_data.get("identity_admin_tid")
    if tid:
        await db.update_admin_display_name(tid, new_name)
        await db.log_action(PISHVA_ID, "admin_identity_change", f"نام مدیر {tid} به: {new_name}")
    await update.message.reply_text(
        f"✅ نام نمایشی مدیر به *{new_name}* تغییر یافت.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ─── New Year ─────────────────────────────────────────────────
async def pishva_newyear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        f"{box('⚠️ هشدار جدی')}\n\n"
        f"این عملیات تمام اطلاعات سال تحصیلی جاری\n"
        f"(بازیکنان، تیم‌ها، مسابقات، رتبه‌بندی‌ها، اخطارها و آمار)\n"
        f"را آرشیو کرده و سیستم فعال را کاملاً پاک می‌کند.\n\n"
        f"آیا ادامه می‌دهید؟",
        reply_markup=kb.kb_newyear_confirm(),
        parse_mode="Markdown"
    )

async def newyear_yes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔐 رمز امنیتی را وارد کنید:")
    return ST_NEW_YEAR_PASSWORD

async def newyear_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pwd = update.message.text.strip()
    if pwd != NEW_YEAR_PASSWORD:
        await update.message.reply_text("❌ رمز اشتباه است. عملیات لغو شد.")
        return ConversationHandler.END
    await update.message.reply_text("⏳ در حال تهیه بکاپ و پاکسازی سیستم...")
    try:
        from backup_utils import generate_excel_backup
        from helpers import now_shamsi
        ts = now_shamsi()
        buf = await generate_excel_backup("all")
        await ctx.bot.send_document(
            chat_id=PISHVA_ID,
            document=buf,
            filename=f"newyear_backup_{ts.replace('/', '-').replace(' ', '_')}.xlsx",
            caption=f"📦 بکاپ سالانه — {ts}"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا در بکاپ: {e}")
    await db.reset_active_data()
    await db.log_action(PISHVA_ID, "new_year_reset", "ریست سال تحصیلی جدید")
    await update.message.reply_text(
        f"{box('✅ سال تحصیلی جدید آغاز شد')}\n\n"
        f"📦 بکاپ سال قبل با موفقیت ذخیره شد.\n"
        f"سیستم آماده ثبت اطلاعات جدید است.",
        reply_markup=kb.kb_back("pishva_panel"),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ─── Update Mode ──────────────────────────────────────────────
async def pishva_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        f"{box('🔄 آپدیت ربات')}\n\n📌 عملیات را انتخاب کنید:",
        reply_markup=kb.kb_update_menu(),
        parse_mode="Markdown"
    )

async def update_sleep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    update_mode = await db.get_setting("bot_update_mode", "0")
    if update_mode == "1":
        await db.set_setting("bot_update_mode", "0")
        await query.edit_message_text("✅ ربات از حالت آپدیت خارج شد.", reply_markup=kb.kb_back("pishva_update"))
    else:
        await db.set_setting("bot_update_mode", "1")
        ts = now_shamsi()
        notif = f"🔄 ربات در حال آپدیت است. لطفاً منتظر بمانید.\n⏱️ `{ts}`"
        await broadcast_to_admins(ctx.bot, notif)
        await query.edit_message_text("💤 ربات برای ادمین‌ها خاموش شد.", reply_markup=kb.kb_back("pishva_update"))

async def update_announce_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🚀 نام/شماره نسخه جدید را وارد کنید:")
    return ST_UPDATE_VERSION

async def update_version_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["update_version"] = update.message.text.strip()
    await update.message.reply_text("📝 توضیحات آپدیت را وارد کنید:")
    return ST_UPDATE_DESC

async def update_desc_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    version = ctx.user_data.get("update_version", "?")
    desc = update.message.text.strip()
    ts = now_shamsi()
    pname = await pishva_display()
    announce = (
        f"╔══════════════════════════════╗\n"
        f"║ 🚀 آپدیت جدید — نسخه {version} ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"✨ {desc}\n\n"
        f"⏱️ `{ts}`\n"
        f"👑 {pname}"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 بازخورد/انتقاد", callback_data="comms_msg_pishva"),
        InlineKeyboardButton("❓ پرسش", callback_data="comms_msg_pishva")],
    ])
    await broadcast_to_admins(ctx.bot, announce, reply_markup=markup)
    await update.message.reply_text(f"✅ اعلام آپدیت نسخه {version} برای همه ارسال شد.")
    return ConversationHandler.END

# ─── Announcement Group ───────────────────────────────────────
async def pishva_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    current = await db.get_setting("announcement_group_id", "")
    await query.edit_message_text(
        f"{box('📡 گروه اعلانات')}\n\n"
        f"گروه فعلی: `{current or 'تنظیم نشده'}`\n\n"
        f"آیدی یا لینک گروه را وارد کنید\n_(مثلاً @mygroupname یا -100123456789)_:",
        parse_mode="Markdown"
    )
    return ST_GROUP_ID

async def group_id_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.message.text.strip()
    await db.set_setting("announcement_group_id", gid)
    await db.log_action(PISHVA_ID, "set_group", f"تنظیم گروه اعلانات: {gid}")
    await update.message.reply_text(
        f"✅ گروه اعلانات تنظیم شد:\n`{gid}`",
        reply_markup=kb.kb_back("pishva_panel"),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ─── Announcement Channel (جدا از گروه) ────────────────────────
async def pishva_channel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    current = await db.get_setting("announcement_channel_id", "")
    await query.edit_message_text(
        f"{box('📢 کانال اعلانات')}\n\n"
        f"کانال فعلی: `{current or 'تنظیم نشده'}`\n\n"
        f"آیدی عددی کانال را وارد کنید\n_(مثلاً -1001234567890)_:",
        parse_mode="Markdown"
    )
    return ST_CHANNEL_ID

async def channel_id_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.message.text.strip()
    await db.set_setting("announcement_channel_id", cid)
    await db.log_action(PISHVA_ID, "set_channel", f"تنظیم کانال اعلانات: {cid}")
    await update.message.reply_text(
        f"✅ کانال اعلانات تنظیم شد:\n`{cid}`",
        reply_markup=kb.kb_back("pishva_panel"),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ─── پخش خودکار به گروه/کانال (۴ سوییچ جدا) ──────────────────
BROADCAST_ITEMS = [
    ("broadcast_announcement_enabled", "📢 بیانیه‌ها"),
    ("broadcast_result_enabled", "♟️ نتیجه مسابقات"),
    ("broadcast_champion_enabled", "🏆 قهرمان هفتگی"),
    ("reminder_master_enabled", "⏰ یادآورها"),
]

async def pishva_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    items = []
    for key, label in BROADCAST_ITEMS:
        val = await db.get_setting(key, "1")
        items.append((key, label, val == "1"))
    await query.edit_message_text(
        f"{box('📡 پخش خودکار به گروه/کانال')}\n\n"
        f"هرکدام را می‌توانید جداگانه فعال یا غیرفعال کنید:",
        reply_markup=kb.kb_broadcast_menu(items),
        parse_mode="Markdown"
    )

async def broadcast_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    key = query.data.replace("broadcast_toggle_", "")
    valid_keys = [k for k, _ in BROADCAST_ITEMS]
    if key in valid_keys:
        current = await db.get_setting(key, "1")
        new_val = "0" if current == "1" else "1"
        await db.set_setting(key, new_val)
        await db.log_action(PISHVA_ID, "broadcast_toggle", f"{key} -> {new_val}")
    await pishva_broadcast(update, ctx)

# ─── Vault ────────────────────────────────────────────────────
async def pishva_vault(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    players = await db.get_all_players()
    backups = await db.get_all_backups()
    rows = []
    for i in range(0, min(len(players), 20), 2):
        row = [InlineKeyboardButton(
            f"📂 {p['full_name']}",
            callback_data=f"player_view_{p['id']}"
        ) for p in players[i:i+2]]
        rows.append(row)
    backup_lines = "\n".join(
        [f"💾 {b['label'] or b['period']} | {b['format']} | {str(b['created_at'])[:10]}" for b in backups[:10]]
    ) or "_هیچ بکاپی وجود ندارد_"
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")])
    await query.edit_message_text(
        f"{box('🏦 خزانه پیشوا')}\n\n"
        f"📂 *پرونده بازیکنان:* `{len(players)}` بازیکن\n\n"
        f"{separator('🗄️ بکاپ‌ها')}\n"
        f"{backup_lines}",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )

# ─── Auto Backup Settings ─────────────────────────────────────
async def pishva_auto_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    enabled = await db.get_setting("auto_backup_enabled", "0")
    interval = await db.get_setting("auto_backup_interval", "24")
    fmt = await db.get_setting("auto_backup_format", "excel")
    period = await db.get_setting("auto_backup_period", "all")
    fmt_label = "Excel" if fmt == "excel" else "Word"
    period_fa = {"today": "امروز", "week": "هفته", "month": "ماه", "all": "کامل"}.get(period, period)
    status = "🟢 فعال" if enabled == "1" else "🔴 غیرفعال"
    text = (
        f"{box('🔄 بکاپ خودکار')}\n\n"
        f"📊 وضعیت: {status}\n"
        f"⏰ فاصله زمانی: هر {interval} ساعت\n"
        f"📁 فرمت: {fmt_label}\n"
        f"📅 بازه: {period_fa}\n\n"
        f"💡 بکاپ خودکار فایل را مستقیم برای پیشوا ارسال می‌کند."
    )
    from keyboards import kb_auto_backup_settings
    await query.edit_message_text(
        text,
        reply_markup=kb_auto_backup_settings(enabled, interval, fmt_label, period_fa),
        parse_mode="Markdown"
    )

async def auto_backup_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    current = await db.get_setting("auto_backup_enabled", "0")
    new_val = "0" if current == "1" else "1"
    await db.set_setting("auto_backup_enabled", new_val)
    if new_val == "1":
        interval = int(await db.get_setting("auto_backup_interval", "24"))
        from backup_utils import schedule_auto_backup
        schedule_auto_backup(ctx.application, interval)
        await query.answer("✅ بکاپ خودکار فعال شد", show_alert=True)
    else:
        try:
            jobs = ctx.application.job_queue.get_jobs_by_name("auto_backup")
            for job in jobs:
                job.schedule_removal()
        except Exception:
            pass
        await query.answer("❌ بکاپ خودکار غیرفعال شد", show_alert=True)
    await pishva_auto_backup(update, ctx)

async def auto_backup_interval_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from keyboards import kb_auto_backup_interval
    await query.edit_message_text(
        "⏰ فاصله زمانی بکاپ خودکار را انتخاب کنید:",
        reply_markup=kb_auto_backup_interval()
    )

async def auto_backup_set_interval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hours = int(query.data.split("_")[-1])
    await db.set_setting("auto_backup_interval", str(hours))
    enabled = await db.get_setting("auto_backup_enabled", "0")
    if enabled == "1":
        from backup_utils import schedule_auto_backup
        schedule_auto_backup(ctx.application, hours)
    await query.answer(f"✅ فاصله زمانی به {hours} ساعت تغییر یافت", show_alert=True)
    await pishva_auto_backup(update, ctx)

async def auto_backup_fmt_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current = await db.get_setting("auto_backup_format", "excel")
    new_fmt = "word" if current == "excel" else "excel"
    await db.set_setting("auto_backup_format", new_fmt)
    await pishva_auto_backup(update, ctx)

async def auto_backup_period_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    periods = ["all", "month", "week", "today"]
    current = await db.get_setting("auto_backup_period", "all")
    idx = periods.index(current) if current in periods else 0
    new_period = periods[(idx + 1) % len(periods)]
    await db.set_setting("auto_backup_period", new_period)
    await pishva_auto_backup(update, ctx)
