"""
Combined handlers for: tasks, admin management, feedback, help, teams, slash commands
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import (box, separator, now_shamsi, broadcast_to_admins,
                     notify_pishva, pishva_display, warning_bar_admin,
                     power_bar, send_notification, check_perm, check_status_gate)
from config import (PISHVA_ID, ST_TASK_SELECT_ADMIN, ST_TASK_TITLE,
                    ST_TASK_DESC, ST_TASK_DONE_REASON, ST_FEEDBACK_TEXT,
                    ST_SUGGESTION_TEXT, ST_FEATURE_TITLE, ST_FEATURE_DESC,
                    ST_PRAISE_TEXT, ST_ADMIN_TASK_SS, ST_ADMIN_WARNING_REASON,
                    ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER)
import json


# ══════════════════════════════════════════
# TASKS
# ══════════════════════════════════════════

async def task_assign_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    admins = await db.get_active_admins()
    if not admins:
        await query.edit_message_text("❗ هیچ مدیری برای اعطای وظیفه وجود ندارد.")
        return
    rows = []
    for i in range(0, len(admins), 2):
        row = [InlineKeyboardButton(
            f"👤 {a['display_name'] or a['full_name']}",
            callback_data=f"task_to_{a['telegram_id']}"
        ) for a in admins[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_tasks")])
    await query.edit_message_text(
        f"{box('📋 اعطای وظیفه')}\n\nبه کدام مدیر وظیفه می‌دهید؟",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )
    return ST_TASK_SELECT_ADMIN


async def task_to_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    ctx.user_data["task_admin"] = tid
    admin = await db.get_admin(tid)
    await query.edit_message_text(f"📝 عنوان وظیفه برای *{admin['display_name'] or admin['full_name']}*:",
                                   parse_mode="Markdown")
    return ST_TASK_TITLE


async def task_title_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["task_title"] = update.message.text.strip()
    await update.message.reply_text("📋 توضیحات وظیفه را وارد کنید:")
    return ST_TASK_DESC


async def task_desc_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    title = ctx.user_data.get("task_title", "")
    desc = update.message.text.strip()
    tid = ctx.user_data.get("task_admin")
    uid = update.effective_user.id

    task_id = await db.create_task(tid, uid, title, desc)
    admin = await db.get_admin(tid)
    pname = await pishva_display()
    ts = now_shamsi()

    notif = (
        f"{box('📋 وظیفه جدید')}\n\n"
        f"👤 {admin['display_name'] or admin['full_name']} عزیز،\n"
        f"یک وظیفه جدید به شما اعطا شد.\n\n"
        f"📌 عنوان: *{title}*\n"
        f"📝 توضیح: _{desc}_\n"
        f"⏱️ زمان اعطا: `{ts}`"
    )
    try:
        await ctx.bot.send_message(
            chat_id=tid, text=notif,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ مشاهده وظیفه", callback_data=f"task_view_{task_id}"),
                 InlineKeyboardButton("✅ تأیید دریافت", callback_data=f"task_ack_{task_id}")]
            ]),
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await db.log_action(uid, "assign_task", f"اعطای وظیفه: {title}", tid)
    await update.message.reply_text(f"✅ وظیفه *{title}* برای {admin['display_name'] or admin['full_name']} ارسال شد.",
                                     parse_mode="Markdown")
    return ConversationHandler.END


async def task_track(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    tasks = await db.get_tasks_for(uid)
    if not tasks:
        await query.edit_message_text("📌 هیچ وظیفه‌ای دارید.", reply_markup=kb.kb_back("tasks"))
        return
    rows = []
    for t in tasks[:15]:
        icon = "✅" if t["status"] == "done" else "❌" if t["status"] == "failed" else "⏳"
        rows.append([InlineKeyboardButton(f"{icon} {t['title']}", callback_data=f"task_view_{t['id']}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_tasks")])
    await query.edit_message_text(
        f"{box('📌 وظایف شما')}\n\n📌 یک وظیفه انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )


async def task_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    t = await db.get_task(task_id)
    if not t:
        await query.answer("وظیفه یافت نشد.", show_alert=True)
        return
    status_label = {"pending": "⏳ در انتظار", "done": "✅ انجام‌شده", "failed": "❌ انجام‌نشده"}.get(t["status"], t["status"])
    text = (
        f"{box('📋 جزئیات وظیفه')}\n\n"
        f"📌 عنوان: *{t['title']}*\n"
        f"📝 توضیح: _{t['description']}_\n"
        f"📊 وضعیت: {status_label}\n"
        f"⏱️ اعطا: `{str(t['assigned_at'])[:19]}`\n"
        f"{'❌ دلیل عدم انجام: ' + t['fail_reason'] if t['fail_reason'] else ''}"
    )
    markup = kb.kb_task_status(task_id) if t["status"] == "pending" else kb.kb_back("task_track")
    await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")


async def task_ack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ تأیید شد.")


async def task_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    await db.update_task_status(task_id, "done")
    t = await db.get_task(task_id)
    await notify_pishva(ctx.bot, f"✅ وظیفه «{t['title']}» توسط مدیر انجام شد.\n⏱️ `{now_shamsi()}`")
    await query.edit_message_text("✅ وظیفه به‌عنوان انجام‌شده ثبت شد.", reply_markup=kb.kb_back("task_track"))


async def task_fail_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    ctx.user_data["failing_task"] = task_id
    await query.edit_message_text("❌ دلیل عدم انجام وظیفه را بنویسید:")
    return ST_TASK_DONE_REASON


async def task_fail_reason(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    task_id = ctx.user_data.get("failing_task")
    if task_id:
        await db.update_task_status(task_id, "failed", reason)
        t = await db.get_task(task_id)
        uid = update.effective_user.id
        admin = await db.get_admin(uid)
        name = admin["display_name"] or admin["full_name"] if admin else str(uid)
        await notify_pishva(
            ctx.bot,
            f"❌ وظیفه «{t['title']}» انجام نشد.\n"
            f"👤 توسط: {name}\n"
            f"📋 دلیل: {reason}\n"
            f"⏱️ `{now_shamsi()}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 پیگیری علت", callback_data=f"task_followup_{task_id}")]
            ])
        )
        await update.message.reply_text("❌ ثبت شد و پیشوا مطلع شد.")
    return ConversationHandler.END


async def task_followup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    t = await db.get_task(task_id)
    await query.edit_message_text(
        f"🔍 پیگیری وظیفه: *{t['title']}*\n📋 دلیل: {t['fail_reason']}",
        reply_markup=kb.kb_back("menu_tasks"),
        parse_mode="Markdown"
    )


async def task_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{box('📜 تاریخچه وظایف')}\n\n📌 فیلتر را انتخاب کنید:",
        reply_markup=kb.kb_task_history_filter(),
        parse_mode="Markdown"
    )


async def task_history_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    f_type = query.data.replace("thistory_", "")
    tasks = await db.get_all_tasks()
    if f_type == "done":
        tasks = [t for t in tasks if t["status"] == "done"]
    elif f_type == "pending":
        tasks = [t for t in tasks if t["status"] == "pending"]
    rows = []
    for t in tasks[:15]:
        icon = "✅" if t["status"] == "done" else "❌" if t["status"] == "failed" else "⏳"
        rows.append([InlineKeyboardButton(f"{icon} {t['title']}", callback_data=f"task_view_{t['id']}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="task_history")])
    await query.edit_message_text(
        f"{box('📜 وظایف')}\n\nتعداد: `{len(tasks)}`",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )


# ══════════════════════════════════════════
# ADMIN MANAGEMENT
# ══════════════════════════════════════════

async def admin_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    admin = await db.get_admin(tid)
    if not admin:
        await query.answer("مدیر یافت نشد.", show_alert=True)
        return

    tasks = await db.get_tasks_for(tid)
    logs = await db.get_action_logs("all", tid)
    warn_bar = warning_bar_admin(admin["warnings"])
    role_label = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"

    _name = admin["display_name"] or admin["full_name"]
    text = (
        f"{box("👤 پروفایل: " + _name + "")}\n\n"
        f"🔗 یوزرنیم: {admin['username']}\n"
        f"💼 نقش: {role_label}\n"
        f"🆔 آیدی: `{admin['telegram_id']}`\n"
        f"📅 تاریخ ثبت: `{str(admin['joined_at'])[:10]}`\n"
        f"⏱️ آخرین فعالیت: `{str(admin['last_active'] or '')[:16]}`\n"
        f"📊 اقدامات: `{len(logs)}`\n"
        f"📋 وظایف: `{len(tasks)}`\n"
        f"{'✅ فعال' if admin['is_active'] else '🔴 غیرفعال'}\n\n"
        f"{separator('⚠️ اخطارها')}\n"
        f"{warn_bar}"
    )
    await query.edit_message_text(text, reply_markup=kb.kb_admin_actions(tid), parse_mode="Markdown")


async def admin_perms(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    admin = await db.get_admin(tid)
    try:
        perms = json.loads(admin["permissions"])
    except Exception:
        perms = {}
    _name = admin["display_name"] or admin["full_name"]
    await query.edit_message_text(
        f"{box("⬆️ دسترسی‌های " + _name + "")}\n\n"
        f"📌 دسترسی‌ها را تغییر دهید:",
        reply_markup=kb.kb_admin_permissions(tid, perms),
        parse_mode="Markdown"
    )


async def perm_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    parts = query.data.split("_")
    tid = int(parts[1])
    perm_name = "_".join(parts[2:])
    admin = await db.get_admin(tid)
    if not admin:
        await query.answer("مدیر یافت نشد.", show_alert=True)
        return
    try:
        perms = json.loads(admin["permissions"])
    except Exception:
        perms = {}
    perms[perm_name] = not perms.get(perm_name, False)
    await db.set_admin_permission(tid, perm_name, perms[perm_name])
    await db.log_action(PISHVA_ID, "toggle_perm", perm_name + ": " + str(perms[perm_name]), tid)
    status_txt = "فعال ✅" if perms[perm_name] else "غیرفعال ❌"
    icon = "⬆️" if perms[perm_name] else "⬇️"
    try:
        await ctx.bot.send_message(chat_id=tid,
            text=icon + " دسترسی *" + perm_name + "* " + status_txt + " شد.",
            parse_mode="Markdown")
    except Exception:
        pass
    admin2 = await db.get_admin(tid)
    try:
        perms2 = json.loads(admin2["permissions"])
    except Exception:
        perms2 = perms
    await query.edit_message_text(
        "⬆️ *دسترسی‌های مدیر*\n\n📌 دسترسی‌ها را تغییر دهید:",
        reply_markup=kb.kb_admin_permissions(tid, perms2),
        parse_mode="Markdown"
    )


async def admin_warn_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    ctx.user_data["warn_admin_tid"] = tid
    admin = await db.get_admin(tid)
    await query.edit_message_text(f"⚠️ دلیل اخطار برای *{admin['display_name'] or admin['full_name']}*:",
                                   parse_mode="Markdown")
    return ST_ADMIN_WARNING_REASON


async def admin_warn_reason(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    tid = ctx.user_data.get("warn_admin_tid")
    if not tid:
        return ConversationHandler.END

    await db.add_admin_warning(tid, reason, PISHVA_ID)
    admin = await db.get_admin(tid)
    warn_bar = warning_bar_admin(admin["warnings"])
    ts = now_shamsi()

    notif = (
        f"{box('⚠️ اخطار رسمی')}\n\n"
        f"👤 {admin['display_name'] or admin['full_name']} عزیز،\n"
        f"شما یک اخطار رسمی دریافت کردید.\n"
        f"⏱️ زمان: `{ts}`\n"
        f"📋 دلیل: {reason}\n\n"
        f"⚠️ وضعیت اخطار:\n{warn_bar}"
    )
    try:
        await ctx.bot.send_message(chat_id=tid, text=notif, parse_mode="Markdown")
    except Exception:
        pass

    await db.log_action(PISHVA_ID, "admin_warning", f"اخطار به مدیر {tid}: {reason}", tid)
    await update.message.reply_text(f"✅ اخطار ثبت شد. مجموع اخطارها: {admin['warnings']}")
    return ConversationHandler.END


async def admin_kick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    admin = await db.get_admin(tid)
    await db.kick_admin(tid)
    await db.log_action(PISHVA_ID, "kick_admin", f"اخراج مدیر: {admin['full_name']}", tid)
    try:
        await ctx.bot.send_message(chat_id=tid, text="🚫 دسترسی شما به ربات توسط پیشوا لغو شد.")
    except Exception:
        pass
    await query.edit_message_text(f"🚫 مدیر *{admin['full_name']}* اخراج شد.", reply_markup=kb.kb_back("menu_admins"), parse_mode="Markdown")


async def admin_msg_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    ctx.user_data["msg_target"] = tid
    admin = await db.get_admin(tid)
    await query.edit_message_text(f"✍️ پیام به *{admin['display_name'] or admin['full_name']}*:", parse_mode="Markdown")
    return ST_SEND_MSG_TEXT


async def admin_task_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    ctx.user_data["task_admin"] = tid
    admin = await db.get_admin(tid)
    await query.edit_message_text(f"📝 عنوان وظیفه برای *{admin['display_name'] or admin['full_name']}*:",
                                   parse_mode="Markdown")
    return ST_TASK_TITLE


async def admin_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    await admin_view(update, ctx)


# ─── /ss command (quick task assignment) ─────────────────────
async def cmd_ss(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != PISHVA_ID:
        return
    admins = await db.get_active_admins()
    if not admins:
        await update.message.reply_text("❗ هیچ مدیری وجود ندارد.")
        return ConversationHandler.END
    rows = []
    for i in range(0, len(admins), 2):
        row = [InlineKeyboardButton(
            f"👤 {a['display_name'] or a['full_name']}",
            callback_data=f"task_to_{a['telegram_id']}"
        ) for a in admins[i:i+2]]
        rows.append(row)
    await update.message.reply_text(
        "📋 به کدام مدیر وظیفه می‌دهید؟",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return ST_TASK_SELECT_ADMIN


# ══════════════════════════════════════════
# FEEDBACK
# ══════════════════════════════════════════

async def fb_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fb_type = query.data.replace("fb_", "")
    ctx.user_data["fb_type"] = fb_type
    prompts = {
        "critique": "📝 انتقاد خود را بنویسید:",
        "suggestion": "💡 پیشنهاد خود را بنویسید:",
        "praise": "🏆 پیام تقدیر خود را بنویسید:",
        "feature": "🔧 عنوان قابلیت پیشنهادی را بنویسید:",
    }
    await query.edit_message_text(prompts.get(fb_type, "📝 متن را وارد کنید:"))
    return ST_FEEDBACK_TEXT


async def fb_text_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    fb_type = ctx.user_data.get("fb_type", "critique")
    uid = update.effective_user.id

    if fb_type == "feature":
        ctx.user_data["feature_title"] = text
        await update.message.reply_text("📋 توضیحات بیشتر را وارد کنید:")
        return ST_FEATURE_DESC

    await db.create_feedback(uid, fb_type, "", text)
    pname = await pishva_display()
    admin = await db.get_admin(uid)
    sender = admin["display_name"] or admin["full_name"] if admin else str(uid)
    type_labels = {"critique": "📝 انتقاد", "suggestion": "💡 پیشنهاد", "praise": "🏆 تقدیر"}

    await notify_pishva(
        ctx.bot,
        f"{type_labels.get(fb_type, '📋')} از *{sender}*:\n\n_{text}_\n\n⏱️ `{now_shamsi()}`"
    )
    await update.message.reply_text("✅ ارسال شد. ممنون!", reply_markup=kb.kb_back("menu_feedback"))
    return ConversationHandler.END


async def fb_feature_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    title = ctx.user_data.get("feature_title", "")
    uid = update.effective_user.id
    await db.create_feedback(uid, "feature", title, desc)
    admin = await db.get_admin(uid)
    sender = admin["display_name"] or admin["full_name"] if admin else str(uid)
    await notify_pishva(
        ctx.bot,
        f"🔧 *درخواست قابلیت* از *{sender}*:\n📌 {title}\n📝 {desc}\n\n⏱️ `{now_shamsi()}`"
    )
    await update.message.reply_text("✅ درخواست ارسال شد!", reply_markup=kb.kb_back("menu_feedback"))
    return ConversationHandler.END


async def fb_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    fb_type = query.data.replace("fb_view_", "")
    feedbacks = await db.get_all_feedback()
    if fb_type != "all":
        feedbacks = [f for f in feedbacks if f["fb_type"] == fb_type]
    if not feedbacks:
        await query.edit_message_text("❗ موردی وجود ندارد.", reply_markup=kb.kb_back("menu_feedback"))
        return
    type_icons = {"critique": "📝", "suggestion": "💡", "praise": "🏆", "feature": "🔧", "report": "🚨"}
    lines = []
    for f in feedbacks[:15]:
        icon = type_icons.get(f["fb_type"], "📋")
        lines.append(f"{icon} `{str(f['sent_at'])[:10]}`: {f['content'][:80]}")
    await query.edit_message_text(
        f"{box('📋 انتقادات و پیشنهادات')}\n\n" + "\n\n".join(lines),
        reply_markup=kb.kb_back("menu_feedback"),
        parse_mode="Markdown"
    )


# ══════════════════════════════════════════
# HELP
# ══════════════════════════════════════════

HELP_TEXTS = {
    "tournament": (
        "🏅 *راهنمای مدیریت تورنمنت*\n\n"
        "• افزودن تورنمنت: فقط نام کافی است.\n"
        "• مدیریت: ویرایش، پایان، تعویق و حذف.\n"
        "• پیش‌فرض: تورنمنتی که مسابقات به آن اضافه می‌شوند.\n"
        "• حذف فقط توسط پیشوا ممکن است."
    ),
    "players": (
        "👤 *راهنمای مدیریت بازیکنان*\n\n"
        "• ابتدا کلاس بسازید، سپس بازیکن ثبت کنید.\n"
        "• اخطار ۳: بازیکن باید تعلیق یا حذف شود.\n"
        "• احیا: بازگشت بازیکن به لیست فعال.\n"
        "• ⛔ نشانه حذف در مسابقه است."
    ),
    "matches": (
        "♟️ *راهنمای مدیریت مسابقات*\n\n"
        "• بازیکن سفید و سیاه از لیست ادامه‌دهندگان انتخاب شود.\n"
        "• قرعه‌کشی هوشمند: اولویت با زوج‌هایی که قبلاً بازی نکرده‌اند.\n"
        "• پس از ثبت نتیجه می‌توان بازنده را حذف کرد."
    ),
    "comms": (
        "📡 *راهنمای مخابرات*\n\n"
        "• پیشوا می‌تواند بیانیه، خبر و پیام مستقیم بفرستد.\n"
        "• ادمین‌ها می‌توانند به پیشوا و یکدیگر پیام دهند.\n"
        "• پیام‌های مشکوک قابل گزارش هستند."
    ),
    "warnings": (
        "⚠️ *راهنمای سیستم اخطار*\n\n"
        "بازیکنان: حداکثر ۳ اخطار\n"
        "• اخطار ۳: پیشوا تصمیم می‌گیرد.\n\n"
        "ادمین‌ها: حداکثر ۵ اخطار\n"
        "• اخطار ۳: هشدار + رصد\n"
        "• اخطار ۴: کاهش دسترسی\n"
        "• اخطار ۵: تصمیم پیشوا"
    ),
    "tasks": (
        "📋 *راهنمای وظایف*\n\n"
        "• پیشوا وظیفه تعیین می‌کند.\n"
        "• ادمین پس از دریافت باید تأیید کند.\n"
        "• انجام‌شده یا انجام‌نشده گزارش دهید.\n"
        "• عدم انجام + دلیل = اطلاع‌رسانی به پیشوا."
    ),
    "faq": (
        "❓ *سوالات متداول*\n\n"
        "Q: چطور بازیکن حذف‌شده را برگردانم؟\n"
        "A: از پنل بازیکن، دکمه 🔄 احیا را بزنید.\n\n"
        "Q: چطور تورنمنت پیش‌فرض را عوض کنم؟\n"
        "A: از بخش تورنمنت → پیش‌فرض فعلی.\n\n"
        "Q: قرعه‌کشی چطور کار می‌کند؟\n"
        "A: سیستم سعی می‌کند بازیکنانی انتخاب کند که قبلاً با هم بازی نداشته‌اند."
    ),
    "errors": (
        "🛠️ *کدهای خطا*\n\n"
        "```\n"
        "❌ ERROR_CODE: 001\n"
        "```\n"
        "دو بازیکن برای شروع وجود ندارد.\n\n"
        "```\n"
        "❌ ERROR_CODE: 002\n"
        "```\n"
        "هیچ کلاسی ثبت نشده است.\n\n"
        "```\n"
        "❌ ERROR_CODE: 003\n"
        "```\n"
        "تورنمنت پیش‌فرض تنظیم نشده.\n\n"
        "```\n"
        "❌ ERROR_CODE: 004\n"
        "```\n"
        "دسترسی در وضعیت فعلی غیرفعال است."
    ),
}


async def help_section(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    section = query.data.replace("help_", "")
    text = HELP_TEXTS.get(section, "❗ راهنمایی برای این بخش موجود نیست.")
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ صفحه قبل", callback_data="menu_help"),
             InlineKeyboardButton("▶️ صفحه بعد", callback_data="menu_help")],
            [InlineKeyboardButton("🔙 بازگشت به راهنما", callback_data="menu_help")],
        ]),
        parse_mode="Markdown"
    )


# ══════════════════════════════════════════
# TEAMS (additional handlers)
# ══════════════════════════════════════════

async def teams_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    team_mode = await db.get_setting("team_mode_enabled", "0")
    if team_mode != "1":
        await query.answer("🏆 حالت تیمی غیرفعال است. از تنظیمات پیشوا فعال کنید.", show_alert=True)
        return
    await query.edit_message_text(
        f"{box('🏆 بخش تیم‌ها')}\n\n📌 بخش موردنظر را انتخاب کنید:",
        reply_markup=kb.kb_teams_menu(),
        parse_mode="Markdown"
    )


async def teams_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    teams = await db.get_all_teams()
    if not teams:
        await query.edit_message_text(
            f"{box('📋 تیم‌ها')}\n\n❗ هیچ تیمی ثبت نشده.",
            reply_markup=kb.kb_back("teams_menu"),
            parse_mode="Markdown"
        )
        return
    await query.edit_message_text(
        f"{box('📋 تیم‌ها')}\n\n📌 یک تیم انتخاب کنید:",
        reply_markup=kb.kb_team_list(teams),
        parse_mode="Markdown"
    )


async def team_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    team = await db.get_team(tid)
    if not team:
        await query.answer("تیم یافت نشد.", show_alert=True)
        return
    members = await db.get_team_members(tid)
    stats = await db.get_team_stats(tid)
    classes = list(set(m["class_name"] for m in members if m["class_name"]))
    captain_name = "تعیین نشده"
    if team["captain_id"]:
        p = await db.get_player(team["captain_id"])
        captain_name = p["full_name"] if p else "تعیین نشده"

    elite_count = sum(1 for m in members if m.get("is_elite"))
    special_count = sum(1 for m in members if m.get("is_special"))
    total = stats["wins"] + stats["losses"] + stats["draws"]
    win_pct = int(stats["wins"] / total * 100) if total > 0 else 0
    from helpers import progress_bar, warning_bar_admin
    power = progress_bar(win_pct)
    warn_bar = warning_bar_admin(team["warnings"], 3)

    text = (
        f"{box('🏆 پنل تیم: ' + team['name'])}\n\n"
        f"🎯 شعار: _{team['slogan'] or '—'}_\n"
        f"🔑 کد تیم: `{team['team_code']}`\n"
        f"📅 تاریخ ثبت: `{str(team['created_at'])[:10]}`\n"
        f"🙋 درخواست‌دهنده: {team['requester_name'] or '—'}\n"
        f"👑 سرگروه: {captain_name}\n\n"
        f"{separator('📊 آمار')}\n"
        f"👥 تعداد اعضا: `{len(members)}`\n"
        f"🏫 کلاس‌ها: {', '.join(classes) or '—'}\n"
        f"✅ برد: `{stats['wins']}` | ❌ باخت: `{stats['losses']}` | 🤝 مساوی: `{stats['draws']}`\n"
        f"🌟 بازیکنان ستاره: `{elite_count}` | ⚡ نیروهای ویژه: `{special_count}`\n"
        f"⚡ سطح قدرت: `{power}`\n"
        f"⚠️ اخطارهای تیم: {warn_bar}"
    )
    await query.edit_message_text(text, reply_markup=kb.kb_team_actions(tid), parse_mode="Markdown")


async def team_members_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    members = await db.get_team_members(tid)
    team = await db.get_team(tid)
    if not members:
        await query.edit_message_text(
            f"👥 اعضای تیم *{team['name']}*:\n\n❗ هیچ عضوی ندارد.",
            reply_markup=kb.kb_back(f"team_view_{tid}"),
            parse_mode="Markdown"
        )
        return
    rows = []
    for m in members:
        icon = "🟢" if m["player_status"] == "active" else "🔴"
        rows.append([
            InlineKeyboardButton(
                f"{icon} {m['full_name']} [{m['class_name'] or ''}]",
                callback_data=f"tmember_{tid}_{m['player_id']}"
            )
        ])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"team_view_{tid}")])
    await query.edit_message_text(
        f"👥 اعضای تیم *{team['name']}* ({len(members)} نفر):",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )


async def team_member_actions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    tid = int(parts[1])
    pid = int(parts[2])
    p = await db.get_player(pid)
    await query.edit_message_text(
        f"👤 *{p['full_name']}*\n\nعملیات:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ حذف از تیم", callback_data=f"tremove_{tid}_{pid}"),
             InlineKeyboardButton("👑 سرگروه", callback_data=f"tcaptain_set_{tid}_{pid}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data=f"team_members_{tid}")],
        ]),
        parse_mode="Markdown"
    )


async def team_remove_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_perm(query, "match_management"):
        return
    await query.answer()
    parts = query.data.split("_")
    tid = int(parts[-2])
    pid = int(parts[-1])
    await db.remove_team_member(tid, pid)
    p = await db.get_player(pid)
    await query.edit_message_text(
        f"✅ *{p['full_name']}* از تیم حذف شد.",
        reply_markup=kb.kb_back(f"team_members_{tid}"),
        parse_mode="Markdown"
    )


async def team_captain_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_perm(query, "match_management"):
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    members = await db.get_team_members(tid)
    if not members:
        await query.edit_message_text("❗ تیم عضوی ندارد.", reply_markup=kb.kb_back(f"team_view_{tid}"))
        return
    rows = []
    for i in range(0, len(members), 2):
        row = [InlineKeyboardButton(f"👤 {m['full_name']}", callback_data=f"tcaptain_set_{tid}_{m['player_id']}") for m in members[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"team_view_{tid}")])
    await query.edit_message_text("👑 سرگروه را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(rows))


async def team_captain_set(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_perm(query, "match_management"):
        return
    await query.answer()
    parts = query.data.split("_")
    tid = int(parts[-2])
    pid = int(parts[-1])
    await db.update_team(tid, captain_id=pid)
    p = await db.get_player(pid)
    await query.edit_message_text(
        f"👑 *{p['full_name']}* به‌عنوان سرگروه تنظیم شد.",
        reply_markup=kb.kb_back(f"team_view_{tid}"),
        parse_mode="Markdown"
    )


async def team_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # حذف تیم فقط برای پیشواست
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ حذف تیم فقط توسط پیشوا مجاز است.", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    team = await db.get_team(tid)
    await db.delete_team(tid)
    await db.log_action(query.from_user.id, "delete_team", f"حذف تیم: {team['name']}", tid)
    await query.edit_message_text(f"🗑️ تیم *{team['name']}* حذف شد.", reply_markup=kb.kb_back("teams_list"), parse_mode="Markdown")


async def team_warnings_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    team = await db.get_team(tid)
    from helpers import warning_bar_admin
    warn_bar = warning_bar_admin(team["warnings"], 3)
    await query.edit_message_text(
        f"⚠️ اخطارهای تیم *{team['name']}*:\n\n{warn_bar}\n\nمجموع: `{team['warnings']}`",
        reply_markup=kb.kb_back(f"team_view_{tid}"),
        parse_mode="Markdown"
    )


# ══════════════════════════════════════════
# SLASH COMMANDS
# ══════════════════════════════════════════

async def cmd_panic(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != PISHVA_ID:
        return
    await db.set_setting("system_status", "danger")
    ts = now_shamsi()
    pname = await pishva_display()
    notif = (
        f"{box('🔴 هشدار اضطراری')}\n\n"
        f"🚨 فرمان PANIC صادر شد!\n"
        f"🔒 تمام دسترسی‌ها قطع شد.\n"
        f"⏱️ `{ts}`\n"
        f"منتظر دستور {pname} باشید."
    )
    await broadcast_to_admins(ctx.bot, notif)
    await db.log_action(PISHVA_ID, "panic", "فرمان اضطراری PANIC")
    await update.message.reply_text("🔴 PANIC فعال شد. تمام دسترسی‌ها قطع.")


async def cmd_unpanic(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != PISHVA_ID:
        return
    await db.set_setting("system_status", "normal")
    ts = now_shamsi()
    await broadcast_to_admins(ctx.bot, f"🟢 سیستم به وضعیت نرمال بازگشت.\n⏱️ `{ts}`")
    await db.log_action(PISHVA_ID, "unpanic", "بازگشت از PANIC")
    await update.message.reply_text("🟢 PANIC غیرفعال شد.")


async def cmd_freeze_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != PISHVA_ID:
        return
    await db.set_setting("system_status", "aps")
    ts = now_shamsi()
    await broadcast_to_admins(ctx.bot, f"{box('🪽 حالت APS')}\n\n🔐 کنترل به APS واگذار شد.\n⏱️ `{ts}`")
    await db.log_action(PISHVA_ID, "freeze_all", "فعال‌سازی APS")
    await update.message.reply_text("🪽 APS فعال شد.")


async def cmd_terminal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != PISHVA_ID:
        return
    import os
    admins = await db.get_active_admins()
    status = await db.get_setting("system_status", "normal")
    default_t = await db.get_default_tournament()
    players = await db.get_all_players()
    matches = await db.get_matches_by_filter("all")
    db_size = os.path.getsize("chess_bot.db") / 1024 if os.path.exists("chess_bot.db") else 0

    text = (
        f"```\n"
        f"╔═══════════════════════╗\n"
        f"║  🖥️  SYSTEM TERMINAL   ║\n"
        f"╚═══════════════════════╝\n"
        f"TIME    : {now_shamsi()}\n"
        f"STATUS  : {status.upper()}\n"
        f"ADMINS  : {len(admins)} active\n"
        f"PLAYERS : {len(players)}\n"
        f"MATCHES : {len(matches)}\n"
        f"TOURNEY : {default_t['name'] if default_t else 'NONE'}\n"
        f"DB SIZE : {db_size:.1f} KB\n"
        f"```"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_backup_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != PISHVA_ID:
        return
    await update.message.reply_text("⏳ در حال تهیه بکاپ...")
    try:
        from backup_utils import generate_excel_backup
        buf = await generate_excel_backup("all")
        await ctx.bot.send_document(
            chat_id=PISHVA_ID,
            document=buf,
            filename=f"emergency_backup_{now_shamsi().replace('/', '-').replace(' ', '_')}.xlsx",
            caption=f"💾 بکاپ اضطراری — {now_shamsi()}"
        )
        await db.log_action(PISHVA_ID, "backup_now", "بکاپ اضطراری")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")


async def cmd_override_strike(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != PISHVA_ID:
        return
    parts = (update.message.text or "").split()
    if len(parts) < 3:
        await update.message.reply_text("❌ فرمت: /override_strike [admin_id] [count]")
        return
    try:
        admin_id = int(parts[1])
        count = int(parts[2])
        async with __import__("aiosqlite").connect(__import__("config").DB_PATH) as d:
            await d.execute("UPDATE admins SET warnings=? WHERE telegram_id=?", (count, admin_id))
            await d.commit()
        await update.message.reply_text(f"✅ اخطارهای مدیر {admin_id} به {count} تغییر یافت.")
        await db.log_action(PISHVA_ID, "override_strike", f"تغییر اخطار مدیر {admin_id} به {count}", admin_id)
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == PISHVA_ID:
        text = (
            "👑 *دستورات پیشوا:*\n\n"
            "/panic — وضعیت خطرناک اضطراری\n"
            "/unpanic — بازگشت به نرمال\n"
            "/freeze\\_all — حالت APS\n"
            "/terminal — تله‌متری سیستم\n"
            "/backup\\_now — بکاپ اضطراری\n"
            "/override\\_strike [id] [count] — تغییر اخطار\n"
            "/ss — اعطای سریع وظیفه\n"
            "/start — منوی اصلی"
        )
    else:
        admin = await db.get_admin(uid)
        if admin and admin["role"] == ROLE_TOURNAMENT_MANAGER:
            text = (
                "🏆 *دستورات مدیر مسابقات:*\n\n"
                "/start — منوی اصلی\n"
                "/help — این راهنما"
            )
        elif admin and admin["role"] == ROLE_SECURITY_MANAGER:
            text = (
                "🛡️ *دستورات مدیر امنیتی:*\n\n"
                "/start — منوی اصلی\n"
                "/help — این راهنما"
            )
        else:
            text = "⛔ شما دسترسی ندارید."
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_open(update: Update, ctx):
    if update.effective_user.id != PISHVA_ID:
        return
    import database as db
    from helpers import broadcast_to_admins, now_shamsi, box
    await db.set_setting("bot_active_for_admins", "1")
    await db.set_setting("working_hours_active", "1")
    ts = now_shamsi()
    notif = (
        f"{box('🟢 آغاز ساعت کاری')}\n\n"
        f"درود بر شما،\n"
        f"⏱️ ساعت کاری از `{ts}`\n"
        f"   توسط پیشوا آغاز شد.\n\n"
        f"✅ دسترسی شما به ربات فعال است.\n"
        f"سیستم آماده دریافت فرمان. 🛰️"
    )
    await broadcast_to_admins(ctx.bot, notif)
    await db.log_action(PISHVA_ID, "workhour_start", f"آغاز ساعت کاری: {ts}")
    await update.message.reply_text(f"🟢 ساعت کاری آغاز شد و به همه اطلاع داده شد.\n⏱️ `{ts}`", parse_mode="Markdown")


async def cmd_close(update: Update, ctx):
    if update.effective_user.id != PISHVA_ID:
        return
    import database as db
    from helpers import broadcast_to_admins, now_shamsi, box
    await db.set_setting("bot_active_for_admins", "0")
    await db.set_setting("working_hours_active", "0")
    ts = now_shamsi()
    notif = (
        f"{box('🔴 پایان ساعت کاری')}\n\n"
        f"خسته نباشید! 🌙\n"
        f"⏱️ ساعت کاری در `{ts}`\n"
        f"   به پایان رسید.\n\n"
        f"🔒 دسترسی شما موقتاً قطع شد.\n"
        f"ممنون از زحمات شما! 🏆"
    )
    await broadcast_to_admins(ctx.bot, notif)
    await db.log_action(PISHVA_ID, "workhour_end", f"پایان ساعت کاری: {ts}")
    await update.message.reply_text(f"🔴 ساعت کاری پایان یافت و به همه اطلاع داده شد.\n⏱️ `{ts}`", parse_mode="Markdown")
