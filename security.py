from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import ApplicationHandlerStop

import database as db
import keyboards as kb
from helpers import safe_edit_message_text, box
from config import PISHVA_ID


BLOCK_MESSAGE = (
    "🚫 *دسترسی محدود شده*\n\n"
    "دسترسی شما به این ربات توسط واحد امنیتی APS به‌طور دائم محدود شده است.\n"
    "هرگونه تلاش مجدد برای استفاده از ربات ثبت و به مسئولین گزارش می‌شود."
)

QUEUE_MESSAGE = (
    "⏳ *در صف انتظار امنیتی*\n\n"
    "درخواست شما در حال بررسی توسط واحد امنیتی APS است.\n"
    "تا اطلاع ثانویه امکان ارسال درخواست جدید برای شما وجود ندارد. لطفاً صبور باشید."
)


# ─── دروازه‌ی امنیتی (روی هر آپدیت اجرا می‌شود) ────────────────
async def block_gate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """اگر کاربر بلاک باشد، هر پیام/دکمه‌ای که بفرستد همینجا متوقف می‌شود
    و به بقیه‌ی هندلرها اصلاً نمی‌رسد."""
    user = update.effective_user
    if user is None:
        return
    blocked = await db.get_blocked_user(user.id)
    if not blocked:
        return
    try:
        if update.callback_query:
            await update.callback_query.answer(
                "🚫 دسترسی شما توسط واحد امنیتی APS محدود شده است.", show_alert=True
            )
        if update.effective_message:
            await update.effective_message.reply_text(BLOCK_MESSAGE, parse_mode="Markdown")
    except Exception:
        pass
    raise ApplicationHandlerStop()


# ─── پنل امنیتی ─────────────────────────────────────────────────
async def security_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد به این بخش دسترسی دارد.", show_alert=True)
        return
    await query.answer()
    queued = await db.get_queued_requests()
    blocked = await db.get_all_blocked()
    text = (
        f"{box('🛡️ پنل امنیتی APS')}\n\n"
        f"⏳ در صف انتظار: `{len(queued)}` نفر\n"
        f"🚫 بلاک‌شده: `{len(blocked)}` نفر\n\n"
        "📌 یک بخش را انتخاب کنید:"
    )
    await safe_edit_message_text(query, text, reply_markup=kb.kb_security_panel(), parse_mode="Markdown")


# ─── صف انتظار ────────────────────────────────────────────────
async def security_queue_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    queued = await db.get_queued_requests()
    if not queued:
        await safe_edit_message_text(query, f"{box('⏳ صف انتظار')}\n\n❗ صف انتظار خالی است.",
                                       reply_markup=kb.kb_security_panel(), parse_mode="Markdown")
        return
    await safe_edit_message_text(query, f"{box('⏳ صف انتظار')}\n\n👥 تعداد: `{len(queued)}`\n\nروی هرکدام بزنید تا جزئیات کامل را ببینید:",
                                   reply_markup=kb.kb_queue_list(queued), parse_mode="Markdown")


async def security_queue_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.split("_")[-1])
    r = await db.get_access_request(req_id)
    if not r:
        await safe_edit_message_text(query, "❗ این درخواست دیگر وجود ندارد.", reply_markup=kb.kb_security_panel())
        return
    role_map = {"tournament_manager": "🏆 مدیر مسابقات", "security_manager": "🛡️ مدیر امنیتی"}
    role_label = role_map.get(r["role"], r["role"])
    username_line = f"@{r['username']}" if r["username"] else "—"
    text = (
        f"{box('⏳ جزئیات صف انتظار')}\n\n"
        f"👤 نام کامل: {r['full_name'] or '—'}\n"
        f"🪪 یوزرنیم: {username_line}\n"
        f"🆔 آیدی عددی: `{r['telegram_id']}`\n"
        f"💼 نقش درخواستی: {role_label}\n"
        f"📝 پیام درخواست: {r['message'] or '—'}\n"
        f"⏱️ زمان درخواست: `{r['requested_at']}`"
    )
    await safe_edit_message_text(query, text, reply_markup=kb.kb_queue_item_actions(req_id), parse_mode="Markdown")


async def request_to_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """از روی نوتیفیکیشن درخواست دسترسی: شخص را به صف انتظار می‌فرستد."""
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    req_id = int(query.data.split("_")[-1])
    r = await db.get_access_request(req_id)
    if not r or r["status"] != "pending":
        await query.answer("این درخواست قبلاً پردازش شده.", show_alert=True)
        return
    await db.set_request_status(req_id, "queued")
    await db.log_action(PISHVA_ID, "queue_request", f"صف انتظار: {r['full_name']}", r["telegram_id"])
    try:
        await ctx.bot.send_message(chat_id=r["telegram_id"], text=QUEUE_MESSAGE, parse_mode="Markdown")
    except Exception:
        pass
    old_text = query.message.text or ""
    await safe_edit_message_text(query, old_text + "\n\n⏳ *این شخص به صف انتظار منتقل شد.*", parse_mode="Markdown")


async def queue_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    req_id = int(query.data.split("_")[-1])
    r = await db.get_access_request(req_id)
    if not r:
        await query.answer("یافت نشد.", show_alert=True)
        return
    await db.set_request_status(req_id, "approved")
    await db.create_admin(r["telegram_id"], r["username"], r["full_name"], r["role"])
    await db.log_action(PISHVA_ID, "approve_from_queue", f"تأیید از صف انتظار: {r['full_name']}", r["telegram_id"])
    role_map = {"tournament_manager": "🏆 مدیر مسابقات", "security_manager": "🛡️ مدیر امنیتی"}
    role_label = role_map.get(r["role"], r["role"])
    try:
        await ctx.bot.send_message(
            chat_id=r["telegram_id"],
            text=f"✅ *دسترسی شما تأیید شد*\n💼 نقش: {role_label}\n\nبرای شروع /start را بزنید.",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await security_queue_list(update, ctx)


async def queue_release(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    req_id = int(query.data.split("_")[-1])
    r = await db.get_access_request(req_id)
    if r:
        await db.set_request_status(req_id, "rejected")
        await db.log_action(PISHVA_ID, "release_from_queue", f"خروج از صف: {r['full_name']}", r["telegram_id"])
        try:
            await ctx.bot.send_message(
                chat_id=r["telegram_id"],
                text="🔓 از صف انتظار امنیتی خارج شدید. در صورت نیاز می‌توانید دوباره درخواست دسترسی ارسال کنید."
            )
        except Exception:
            pass
    await security_queue_list(update, ctx)


async def queue_block_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    req_id = int(query.data.split("_")[-1])
    r = await db.get_access_request(req_id)
    if not r:
        await query.answer("یافت نشد.", show_alert=True)
        return
    await safe_edit_message_text(query, 
        f"⚠️ آیا از بلاک دائم *{r['full_name']}* مطمئن هستید؟\nاین شخص برای همیشه دسترسی خود به ربات را از دست می‌دهد.",
        reply_markup=kb.kb_block_confirm(f"req_{req_id}", back_cb=f"queueview_{req_id}"),
        parse_mode="Markdown"
    )


async def request_block_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """از روی نوتیفیکیشن درخواست دسترسی."""
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    req_id = int(query.data.split("_")[-1])
    r = await db.get_access_request(req_id)
    if not r:
        await query.answer("یافت نشد.", show_alert=True)
        return
    await safe_edit_message_text(query, 
        f"⚠️ آیا از بلاک دائم *{r['full_name']}* مطمئن هستید؟\nاین شخص برای همیشه دسترسی خود به ربات را از دست می‌دهد.",
        reply_markup=kb.kb_block_confirm(f"req_{req_id}", back_cb="menu_pishva"),
        parse_mode="Markdown"
    )


# ─── بلاک دائم ────────────────────────────────────────────────
async def block_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    token = query.data.split("_", 1)[-1]  # "req_12" یا یک آیدی عددی خام

    if token.startswith("req_"):
        req_id = int(token.split("_")[-1])
        r = await db.get_access_request(req_id)
        if not r:
            await safe_edit_message_text(query, "❗ یافت نشد.", reply_markup=kb.kb_security_panel())
            return
        telegram_id, username, full_name = r["telegram_id"], r["username"], r["full_name"]
        await db.set_request_status(req_id, "blocked")
    else:
        telegram_id = int(token)
        b = await db.get_blocked_user(telegram_id)
        username = b["username"] if b else ""
        full_name = b["full_name"] if b else str(telegram_id)

    await db.block_user(telegram_id, username or "", full_name or "", "بلاک توسط مدیر ارشد", PISHVA_ID)
    await db.log_action(PISHVA_ID, "block_user", f"بلاک: {full_name} ({telegram_id})", telegram_id)
    try:
        await ctx.bot.send_message(chat_id=telegram_id, text=BLOCK_MESSAGE, parse_mode="Markdown")
    except Exception:
        pass
    await safe_edit_message_text(query, f"🚫 *{full_name or telegram_id}* با موفقیت بلاک شد.",
                                   reply_markup=kb.kb_security_panel(), parse_mode="Markdown")


# ─── لیست بلاک‌شده‌ها ──────────────────────────────────────────
async def security_blocked_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    blocked = await db.get_all_blocked()
    if not blocked:
        await safe_edit_message_text(query, f"{box('🚫 لیست بلاک‌شده‌ها')}\n\n❗ فعلاً کسی بلاک نیست.",
                                       reply_markup=kb.kb_security_panel(), parse_mode="Markdown")
        return
    await safe_edit_message_text(query, f"{box('🚫 لیست بلاک‌شده‌ها')}\n\n👥 تعداد: `{len(blocked)}`",
                                   reply_markup=kb.kb_blocked_list(blocked), parse_mode="Markdown")


async def security_blocked_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    b = await db.get_blocked_user(tid)
    if not b:
        await safe_edit_message_text(query, "❗ یافت نشد.", reply_markup=kb.kb_security_panel())
        return
    text = (
        f"{box('🚫 جزئیات بلاک')}\n\n"
        f"👤 نام: {b['full_name'] or '—'}\n"
        f"🪪 یوزرنیم: {('@' + b['username']) if b['username'] else '—'}\n"
        f"🆔 آیدی عددی: `{b['telegram_id']}`\n"
        f"📝 دلیل: {b['reason'] or '—'}\n"
        f"⏱️ زمان بلاک: `{b['blocked_at']}`"
    )
    await safe_edit_message_text(query, text, reply_markup=kb.kb_blocked_item_actions(tid), parse_mode="Markdown")


async def unblock_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    b = await db.get_blocked_user(tid)
    name = b["full_name"] if b else str(tid)
    await db.unblock_user(tid)
    await db.log_action(PISHVA_ID, "unblock_user", f"آنبلاک: {name} ({tid})", tid)
    try:
        await ctx.bot.send_message(chat_id=tid, text="✅ دسترسی شما به ربات مجدداً فعال شد.")
    except Exception:
        pass
    await security_blocked_list(update, ctx)
