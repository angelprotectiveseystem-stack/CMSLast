from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import keyboards as kb
from helpers import (now_shamsi, box, separator, progress_bar,
                     broadcast_to_admins, notify_pishva, check_status_gate)
from config import (PISHVA_ID, ST_TOURNAMENT_NAME, ST_TOURNAMENT_EDIT)


async def tourn_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{box('🏅 مدیریت تورنمنت')}\n\n📌 بخش موردنظر را انتخاب کنید:",
        reply_markup=kb.kb_tournament_menu(),
        parse_mode="Markdown"
    )


async def tourn_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{box('➕ افزودن تورنمنت')}\n\n📝 نام تورنمنت را وارد کنید:",
        parse_mode="Markdown"
    )
    return ST_TOURNAMENT_NAME


async def tourn_add_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ نام خالی است. دوباره وارد کنید:")
        return ST_TOURNAMENT_NAME
    tid = await db.create_tournament(name)
    await db.log_action(update.effective_user.id, "create_tournament", f"ایجاد تورنمنت: {name}", tid)
    await update.message.reply_text(
        f"✅ تورنمنت *{name}* با موفقیت ساخته شد!\n\n"
        f"🆔 شناسه: `{tid}`\n"
        f"⏱️ `{now_shamsi()}`",
        reply_markup=kb.kb_tournament_menu(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def tourn_manage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tournaments = await db.get_all_tournaments()
    active = [t for t in tournaments if t["status"] != "deleted"]
    if not active:
        await query.edit_message_text(
            f"{box('⚙️ مدیریت تورنمنت')}\n\n❗ هیچ تورنمنتی وجود ندارد.",
            reply_markup=kb.kb_back("tournament"),
            parse_mode="Markdown"
        )
        return
    await query.edit_message_text(
        f"{box('⚙️ مدیریت تورنمنت')}\n\n📌 یک تورنمنت انتخاب کنید:",
        reply_markup=kb.kb_tournament_list(active),
        parse_mode="Markdown"
    )


async def tourn_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    t = await db.get_tournament(tid)
    if not t:
        await query.answer("تورنمنت یافت نشد.", show_alert=True)
        return

    status_icon = {"active": "🟢", "ended": "🔴", "paused": "⏸️", "deleted": "🗑️"}.get(t["status"], "❓")
    stats = await db.get_tournament_stats(tid)
    pct = int(stats["done"] / stats["total"] * 100) if stats["total"] > 0 else 0
    bar = progress_bar(pct)

    text = (
        f"{box('🏅 تورنمنت: ' + t['name'])}\n\n"
        f"📌 وضعیت: {status_icon} {t['status']}\n"
        f"{'✅ پیش‌فرض فعلی' if t['is_default'] else ''}\n\n"
        f"🏁 پیشرفت: {bar}\n"
        f"📊 مسابقات: `{stats['done']}` / `{stats['total']}`\n"
        f"⏱️ ساخته‌شده: `{str(t['created_at'] or '')[:10]}`"
    )
    is_pishva = query.from_user.id == PISHVA_ID
    await query.edit_message_text(
        text,
        reply_markup=kb.kb_tournament_actions(tid, is_pishva),
        parse_mode="Markdown"
    )


async def tourn_edit_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split("_")[-1])
    ctx.user_data["editing_tournament"] = tid
    t = await db.get_tournament(tid)
    await query.edit_message_text(
        f"✏️ نام جدید برای تورنمنت *{t['name']}* را وارد کنید:",
        parse_mode="Markdown"
    )
    return ST_TOURNAMENT_EDIT


async def tourn_edit_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    tid = ctx.user_data.get("editing_tournament")
    if tid and new_name:
        await db.update_tournament(tid, name=new_name)
        await db.log_action(update.effective_user.id, "edit_tournament", f"تغییر نام تورنمنت به: {new_name}", tid)
        await update.message.reply_text(
            f"✅ نام تورنمنت به *{new_name}* تغییر یافت.",
            reply_markup=kb.kb_tournament_menu(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END


async def tourn_end(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ پایان دادن به تورنمنت فقط توسط پیشوا مجاز است.", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    t = await db.get_tournament(tid)
    await db.update_tournament(tid, status="ended", is_default=0)
    await db.log_action(query.from_user.id, "end_tournament", f"پایان تورنمنت: {t['name']}", tid)
    await query.edit_message_text(
        f"🔴 تورنمنت *{t['name']}* پایان یافت.\n"
        f"داده‌ها حفظ شده‌اند. فعال‌سازی مجدد فقط توسط پیشوا.",
        reply_markup=kb.kb_tournament_menu(),
        parse_mode="Markdown"
    )


async def tourn_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ تعویق تورنمنت فقط توسط پیشوا مجاز است.", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    t = await db.get_tournament(tid)
    await db.update_tournament(tid, status="paused")
    await db.log_action(query.from_user.id, "pause_tournament", f"تعویق تورنمنت: {t['name']}", tid)
    await query.edit_message_text(
        f"⏸️ تورنمنت *{t['name']}* به تعویق افتاد.\n"
        f"از سرگیری فقط توسط پیشوا ممکن است.",
        reply_markup=kb.kb_tournament_menu(),
        parse_mode="Markdown"
    )


async def tourn_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if uid != PISHVA_ID:
        await query.answer("⛔ حذف تورنمنت فقط توسط پیشوا ممکن است.", show_alert=True)
        return
    await query.answer()
    tid = int(query.data.split("_")[-1])
    t = await db.get_tournament(tid)
    await db.update_tournament(tid, status="deleted", is_default=0)
    await db.log_action(uid, "delete_tournament", f"حذف تورنمنت: {t['name']}", tid)
    await query.edit_message_text(
        f"🗑️ تورنمنت *{t['name']}* حذف شد.",
        reply_markup=kb.kb_tournament_menu(),
        parse_mode="Markdown"
    )


async def tourn_setdefault(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    tid = int(query.data.split("_")[-1])
    t = await db.get_tournament(tid)
    await db.set_default_tournament(tid)
    await db.log_action(uid, "set_default_tournament", f"تورنمنت پیش‌فرض: {t['name']}", tid)

    # Notify others
    pname = await db.get_setting("pishva_display_name", "پیشوا")
    ts = now_shamsi()
    notif_text = (
        f"📌 *تورنمنت پیش‌فرض تغییر کرد*\n\n"
        f"🏅 تورنمنت جدید: *{t['name']}*\n"
        f"⏱️ `{ts}`"
    )
    await broadcast_to_admins(ctx.bot, notif_text, exclude_id=uid)
    if uid != PISHVA_ID:
        await notify_pishva(ctx.bot, notif_text)

    await query.edit_message_text(
        f"✅ تورنمنت *{t['name']}* به‌عنوان پیش‌فرض تنظیم شد.",
        reply_markup=kb.kb_tournament_menu(),
        parse_mode="Markdown"
    )


async def tourn_default(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show/change default tournament"""
    query = update.callback_query
    await query.answer()
    default_t = await db.get_default_tournament()
    tournaments = await db.get_all_tournaments()
    active = [t for t in tournaments if t["status"] == "active"]

    lines = []
    if default_t:
        lines.append(f"📌 تورنمنت پیش‌فرض فعلی: *{default_t['name']}*\n")
    else:
        lines.append("❗ هیچ تورنمنت پیش‌فرضی تنظیم نشده.\n")

    lines.append("برای تغییر، یکی را انتخاب کنید:")

    # Buttons for each active tournament
    rows = []
    for i in range(0, len(active), 2):
        row = []
        for t in active[i:i+2]:
            icon = "✅ " if default_t and t["id"] == default_t["id"] else ""
            from telegram import InlineKeyboardButton
            row.append(InlineKeyboardButton(
                f"{icon}{t['name']}",
                callback_data=f"tourn_setdefault_{t['id']}"
            ))
        rows.append(row)
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_tournament")])
    await query.edit_message_text(
        f"{box('📌 تورنمنت پیش‌فرض')}\n\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown"
    )


async def tourn_details(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    t = await db.get_default_tournament()
    if not t:
        await query.edit_message_text(
            f"{box('📊 جزئیات تورنمنت')}\n\n❗ هیچ تورنمنت فعالی وجود ندارد.",
            reply_markup=kb.kb_back("tournament"),
            parse_mode="Markdown"
        )
        return

    stats = await db.get_tournament_stats(t["id"])
    pct = int(stats["done"] / stats["total"] * 100) if stats["total"] > 0 else 0
    bar = progress_bar(pct)

    # Top players
    players = await db.get_all_players()
    sorted_players = sorted(players, key=lambda p: p["wins"], reverse=True)[:5]
    top_lines = "\n".join(
        [f"  `{i+1}.` {p['full_name']} — {p['wins']}W/{p['draws']}D/{p['losses']}L"
         for i, p in enumerate(sorted_players)]
    ) or "  _هنوز مسابقه‌ای انجام نشده_"

    text = (
        f"{box('📊 جزئیات: ' + t['name'])}\n\n"
        f"🏅 نام: *{t['name']}*\n"
        f"🟢 وضعیت: فعال\n"
        f"👥 بازیکنان: `{len(players)}`\n\n"
        f"🏁 پیشرفت:\n`{bar}`\n"
        f"📊 مسابقات انجام‌شده: `{stats['done']}` از `{stats['total']}`\n\n"
        f"{separator('🌟 بازیکنان برتر')}\n"
        f"{top_lines}"
    )
    await query.edit_message_text(text, reply_markup=kb.kb_back("tournament"), parse_mode="Markdown")


async def tourn_deleted(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tournaments = await db.get_all_tournaments()
    deleted = [t for t in tournaments if t["status"] == "deleted"]
    if not deleted:
        await query.edit_message_text(
            f"{box('🗂️ تورنمنت‌های حذف‌شده')}\n\n❗ هیچ تورنمنت حذف‌شده‌ای وجود ندارد.",
            reply_markup=kb.kb_back("tournament"),
            parse_mode="Markdown"
        )
        return
    lines = "\n".join([f"🗑️ {t['name']} — {str(t['created_at'] or '')[:10]}" for t in deleted])
    await query.edit_message_text(
        f"{box('🗂️ تورنمنت‌های حذف‌شده')}\n\n{lines}",
        reply_markup=kb.kb_back("tournament"),
        parse_mode="Markdown"
    )
