from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import (box, separator, now_shamsi, broadcast_to_admins,
                     notify_pishva, pishva_display, send_notification)
from config import (PISHVA_ID, ST_SEND_MSG_SELECT_ADMIN, ST_SEND_MSG_TEXT,
                    ST_ANNOUNCEMENT_TEXT, ST_ANNOUNCEMENT_FILE, ST_NEWS_TEXT)


# ─── Send message to admin (Pishva) ──────────────────────────
async def comms_msg_admin_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    admins = await db.get_active_admins()
    if not admins:
        await query.edit_message_text("❗ هیچ مدیر فعالی وجود ندارد.", reply_markup=kb.kb_back("comms_pishva"))
        return
    rows = []
    for i in range(0, len(admins), 2):
        row = [InlineKeyboardButton(
            f"👤 {a['display_name'] or a['full_name']}",
            callback_data=f"cmsg_{a['telegram_id']}"
        ) for a in admins[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_comms")])
    await query.edit_message_text(
        "💬 به کدام مدیر پیام می‌فرستید؟",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return ST_SEND_MSG_SELECT_ADMIN


async def comms_msg_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    ctx.user_data["msg_target"] = tid
    admin = await db.get_admin(tid)
    await query.edit_message_text(
        f"✍️ پیام به *{admin['display_name'] or admin['full_name']}*:",
        parse_mode="Markdown"
    )
    return ST_SEND_MSG_TEXT


async def comms_msg_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    tid = ctx.user_data.get("msg_target")
    uid = update.effective_user.id
    pname = await pishva_display()

    if tid and text:
        await db.send_message_db(uid, tid, text)
        ts = now_shamsi()
        notif = (
            f"{box('📨 پیام جدید')}\n\n"
            f"📬 شما یک پیام جدید دارید.\n"
            f"👤 از: {pname if uid == PISHVA_ID else 'پیشوا'}\n"
            f"⏱️ `{ts}`\n\n"
            f"💬 متن: _{text}_"
        )
        try:
            await ctx.bot.send_message(
                chat_id=tid, text=notif,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تأیید مطالعه", callback_data="msg_ack")]
                ]),
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await update.message.reply_text("✅ پیام ارسال شد.")
    return ConversationHandler.END


# ─── Send msg to Pishva (Admin) ───────────────────────────────
async def comms_msg_pishva_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["msg_target"] = PISHVA_ID
    pname = await pishva_display()
    await query.edit_message_text(f"✍️ پیام به *{pname}*:", parse_mode="Markdown")
    return ST_SEND_MSG_TEXT


# ─── Send msg to other admin ──────────────────────────────────
async def comms_msg_other_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    admins = await db.get_active_admins()
    others = [a for a in admins if a["telegram_id"] != uid]
    if not others:
        await query.edit_message_text("❗ هیچ مدیر دیگری فعال نیست.", reply_markup=kb.kb_back("comms_admin"))
        return
    rows = []
    for i in range(0, len(others), 2):
        row = [InlineKeyboardButton(
            f"👤 {a['display_name'] or a['full_name']}",
            callback_data=f"cmsg_{a['telegram_id']}"
        ) for a in others[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_comms")])
    await query.edit_message_text("💬 به کدام مدیر پیام می‌فرستید؟", reply_markup=InlineKeyboardMarkup(rows))
    return ST_SEND_MSG_SELECT_ADMIN


async def comms_inbox(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    msgs = await db.get_messages_for(uid)
    if not msgs:
        await query.edit_message_text("📭 هیچ پیامی دریافت نکرده‌اید.", reply_markup=kb.kb_back("comms"))
        return

    pname = await pishva_display()
    admins = {a["telegram_id"]: (a["display_name"] or a["full_name"]) for a in await db.get_all_admins()}

    lines = []
    for m in msgs[:15]:
        sender_name = pname if m["sender_id"] == PISHVA_ID else admins.get(m["sender_id"], "ربات")
        read_icon = "✅" if m["is_read"] else "🔵"
        lines.append(f"{read_icon} از {sender_name}: _{str(m['text'])[:80]}_")

    await query.edit_message_text(
        f"{box('📨 پیام‌های دریافتی')}\n\n" + "\n\n".join(lines),
        reply_markup=kb.kb_back("comms"),
        parse_mode="Markdown"
    )


async def comms_all_msgs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    msgs = await db.get_all_messages()
    admins = {a["telegram_id"]: (a["display_name"] or a["full_name"]) for a in await db.get_all_admins()}
    pname = await pishva_display()

    lines = []
    for m in msgs[:20]:
        sn = pname if m["sender_id"] == PISHVA_ID else admins.get(m["sender_id"], str(m["sender_id"]))
        rn = pname if m["receiver_id"] == PISHVA_ID else admins.get(m["receiver_id"], str(m["receiver_id"]))
        lines.append(f"👤 {sn} → {rn}: _{str(m['text'])[:60]}_")

    await query.edit_message_text(
        f"{box('👁️ پیام ادمین‌ها')}\n\n" + "\n\n".join(lines) if lines else "❗ پیامی وجود ندارد.",
        reply_markup=kb.kb_back("comms"),
        parse_mode="Markdown"
    )


# ─── Announcements ────────────────────────────────────────────
async def comms_announce_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text("📢 متن بیانیه را وارد کنید:")
    return ST_ANNOUNCEMENT_TEXT


async def comms_announce_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ctx.user_data["announce_text"] = text
    await update.message.reply_text(
        "آیا فایلی برای پیوست دارید؟",
        reply_markup=kb.kb_announce_file()
    )
    return ST_ANNOUNCEMENT_FILE


async def comms_announce_no_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = ctx.user_data.get("announce_text", "")
    await _send_announcement(ctx.bot, text, "", "")
    await query.edit_message_text("✅ بیانیه ارسال شد.", reply_markup=kb.kb_back("comms"))
    return ConversationHandler.END


async def comms_announce_with_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📎 فایل موردنظر را ارسال کنید (عکس، سند، ویدیو یا صوت):")
    return ST_ANNOUNCEMENT_FILE


async def comms_announce_file_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = ctx.user_data.get("announce_text", "")
    file_id = ""
    file_type = ""

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = "photo"
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
    elif update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
    elif update.message.audio or update.message.voice:
        obj = update.message.audio or update.message.voice
        file_id = obj.file_id
        file_type = "audio"

    await _send_announcement(ctx.bot, text, file_id, file_type)
    await update.message.reply_text("✅ بیانیه با پیوست ارسال شد.", reply_markup=kb.kb_back("comms"))
    return ConversationHandler.END


async def _send_announcement(bot, text: str, file_id: str, file_type: str):
    ann_id = await db.create_announcement(text, file_id, file_type)
    pname = await db.get_setting("pishva_display_name", "پیشوا")
    ts = now_shamsi()
    full_text = f"📢 *بیانیه رسمی*\n\n{text}\n\n⏱️ `{ts}`\n👑 {pname}"

    notif_on = await db.get_setting("notifications_enabled", "1")
    if notif_on != "1":
        return

    admins = await db.get_active_admins()
    group_id = await db.get_setting("announcement_group_id", "")
    targets = [a["telegram_id"] for a in admins] + ([int(group_id)] if group_id else [])

    for tid in targets:
        try:
            if file_id:
                if file_type == "photo":
                    await bot.send_photo(chat_id=tid, photo=file_id, caption=full_text, parse_mode="Markdown")
                elif file_type == "document":
                    await bot.send_document(chat_id=tid, document=file_id, caption=full_text, parse_mode="Markdown")
                elif file_type == "video":
                    await bot.send_video(chat_id=tid, video=file_id, caption=full_text, parse_mode="Markdown")
                elif file_type == "audio":
                    await bot.send_audio(chat_id=tid, audio=file_id, caption=full_text, parse_mode="Markdown")
            else:
                await bot.send_message(chat_id=tid, text=full_text, parse_mode="Markdown")
        except Exception:
            pass


async def comms_ann_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anns = await db.get_all_announcements()
    if not anns:
        await query.edit_message_text("📭 هیچ بیانیه‌ای وجود ندارد.", reply_markup=kb.kb_back("comms"))
        return

    rows = []
    for a in anns[:15]:
        rows.append([
            InlineKeyboardButton(
                f"📜 {str(a['sent_at'])[:10]}: {str(a['text'])[:30]}...",
                callback_data=f"ann_view_{a['id']}"
            )
        ])
    if query.from_user.id == PISHVA_ID:
        pass  # delete options added in ann_view
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_comms")])
    await query.edit_message_text(
        f"{box('📜 تاریخچه بیانیات')}\n\n📌 یک بیانیه انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )


async def ann_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ann_id = int(query.data.split("_")[-1])
    anns = await db.get_all_announcements()
    ann = next((a for a in anns if a["id"] == ann_id), None)
    if not ann:
        await query.answer("بیانیه یافت نشد.", show_alert=True)
        return

    rows = []
    if query.from_user.id == PISHVA_ID:
        rows.append([InlineKeyboardButton("🗑️ حذف بیانیه", callback_data=f"ann_delete_{ann_id}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="comms_ann_history")])
    await query.edit_message_text(
        f"📢 *بیانیه*\n\n{ann['text']}\n\n⏱️ `{str(ann['sent_at'])[:19]}`\n"
        f"{'📎 دارای پیوست' if ann['file_id'] else ''}",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )


async def ann_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    ann_id = int(query.data.split("_")[-1])
    await db.delete_announcement(ann_id)
    await query.edit_message_text("🗑️ بیانیه حذف شد.", reply_markup=kb.kb_back("comms"))


# ─── News ─────────────────────────────────────────────────────
async def comms_news_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text("📰 متن خبر فوری را وارد کنید:")
    return ST_NEWS_TEXT


async def comms_news_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ts = now_shamsi()
    pname = await pishva_display()
    news_text = f"✨ *خبر فوری از سیستم✨*\n\n{text}\n\n⏱️ `{ts}`"
    await db.create_news(text)
    await broadcast_to_admins(ctx.bot, news_text)
    await update.message.reply_text("✅ خبر فوری برای همه ارسال شد.")
    return ConversationHandler.END


async def comms_news_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    news = await db.get_all_news()
    if not news:
        await query.edit_message_text("📭 هیچ خبری ثبت نشده.", reply_markup=kb.kb_back("comms"))
        return
    lines = [f"📰 `{str(n['sent_at'])[:10]}` — {n['text'][:80]}" for n in news[:20]]
    await query.edit_message_text(
        f"{box('📰 اخبار')}\n\n" + "\n\n".join(lines),
        reply_markup=kb.kb_back("comms"),
        parse_mode="Markdown"
    )


async def comms_notifs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msgs = await db.get_all_news()
    anns = await db.get_all_announcements()
    combined = [(n["sent_at"], "📰 خبر", n["text"]) for n in msgs[:5]]
    combined += [(a["sent_at"], "📢 بیانیه", a["text"]) for a in anns[:5]]
    combined.sort(key=lambda x: x[0], reverse=True)
    lines = [f"{t} `{str(d)[:10]}`: {txt[:60]}" for d, t, txt in combined[:15]]
    await query.edit_message_text(
        f"{box('🔔 اعلانات اخیر')}\n\n" + ("\n\n".join(lines) or "❗ اعلانی وجود ندارد."),
        reply_markup=kb.kb_back("comms"),
        parse_mode="Markdown"
    )


async def comms_reports(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔", show_alert=True)
        return
    await query.answer()
    feedbacks = await db.get_all_feedback()
    reports = [f for f in feedbacks if f["fb_type"] == "report"]
    if not reports:
        await query.edit_message_text("📊 هیچ گزارشی دریافت نشده.", reply_markup=kb.kb_back("comms"))
        return
    lines = [f"🚨 {r['content'][:80]}" for r in reports[:15]]
    await query.edit_message_text(
        f"{box('📊 گزارشات')}\n\n" + "\n\n".join(lines),
        reply_markup=kb.kb_back("comms"),
        parse_mode="Markdown"
    )


async def msg_ack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ پیام خوانده شد.")
