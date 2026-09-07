"""
هشدار حذف مشکوک
────────────────
وقتی یک ادمین توی یه بازه‌ی زمانیِ کوتاه، تعداد زیادی اقدام مخرب (اخراج/
تعلیق/حذف بازیکن از مسابقه، حذف مسابقه، حذف تیم، حذف تورنمنت) انجام بده،
فوری به مدیر ارشد هشدار داده می‌شه — با سه گزینه: خنثی‌سازیِ کل اقدام‌های
همون ادمین در همون روز، خاموش‌کردنِ ربات برای اون ادمین (اخراج فوری)، یا
تایید اینکه مشکلی نیست.

شمارش توی حافظه (نه دیتابیس) انجام می‌شه: چون خودِ ربات یک پردازش تکی
(single-process) است، این هم سریع‌تره و هم از رِیسِ «لاگ هنوز کامل ثبت
نشده» (چون log_action خودش fire-and-forget است) کاملاً بی‌نیازه.
"""
import time
from collections import defaultdict, deque

from telegram import Update
from telegram.ext import ContextTypes

import database as db
import keyboards as kb
from config import PISHVA_ID
from helpers import box, now_shamsi, today_gregorian, notify_pishva, safe_edit_message_text

# ─── اقدام‌هایی که «مخرب» حساب می‌شن و توی شمارشِ هشدار وارد می‌شن ───
DESTRUCTIVE_ACTIONS = {
    "kick_player", "eliminate_player", "suspend_player",
    "delete_match", "delete_team", "delete_tournament",
}

# admin_id -> deque[زمانِ وقوعِ هر اقدامِ مخرب (monotonic)]
_recent_destructive = defaultdict(deque)
# admin_id -> زمانِ آخرین هشدارِ ارسالی، برای جلوگیری از مزاحمتِ تکراری
# تا وقتی مدیر ارشد روی هشدارِ قبلی تصمیم نگرفته
_last_alert_at = {}


async def record_destructive_action(bot, admin_id: int, action_type: str):
    """بعد از ثبتِ هر اقدامِ مخرب (توسط یک ادمینِ عادی، نه خودِ مدیر ارشد)
    صدا زده می‌شه. اگه تعداد این اقدام‌ها توی بازه‌ی زمانیِ تنظیم‌شده از
    آستانه بیشتر بشه، فوری به مدیر ارشد هشدار می‌ده."""
    if admin_id == PISHVA_ID or action_type not in DESTRUCTIVE_ACTIONS:
        return

    enabled = await db.get_setting("suspicious_alert_enabled", "1")
    if enabled != "1":
        return

    try:
        threshold = int(await db.get_setting("suspicious_deletion_threshold", "5"))
        window_min = int(await db.get_setting("suspicious_deletion_window_minutes", "10"))
    except (TypeError, ValueError):
        threshold, window_min = 5, 10
    window_sec = max(window_min, 1) * 60

    now = time.monotonic()
    dq = _recent_destructive[admin_id]
    dq.append(now)
    while dq and now - dq[0] > window_sec:
        dq.popleft()

    if len(dq) < threshold:
        return

    # به ازای هر بازه، حداکثر یک هشدار — تا مدیر ارشد یکی از سه گزینه رو
    # انتخاب کنه، دوباره مزاحمش نمی‌شیم حتی اگه ادمین به حذف ادامه بده.
    last = _last_alert_at.get(admin_id, 0)
    if now - last < window_sec:
        return
    _last_alert_at[admin_id] = now

    admin = await db.get_admin(admin_id)
    admin_name = (admin["display_name"] or admin["full_name"]) if admin else str(admin_id)
    date_str = today_gregorian()
    date_compact = date_str.replace("-", "")

    text = (
        f"{box('🚨 هشدار — فعالیت مشکوک ادمین')}\n\n"
        f"👤 ادمین: *{admin_name}*\n"
        f"🆔 آیدی: `{admin_id}`\n"
        f"🗑️ تعداد اقدام مخرب: `{len(dq)}` در `{window_min}` دقیقه‌ی اخیر\n"
        f"⏱️ `{now_shamsi()}`\n\n"
        f"📌 یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    await notify_pishva(bot, text, reply_markup=kb.kb_suspicious_alert(admin_id, date_compact))


def _parse_alert_data(data: str):
    """'sadel_undo_<admin_id>_<yyyymmdd>' یا 'sadel_disable_<admin_id>' یا
    'sadel_dismiss_<admin_id>_<yyyymmdd>' رو پارس می‌کنه."""
    parts = data.split("_")
    admin_id = int(parts[2])
    date_compact = parts[3] if len(parts) > 3 else None
    date_str = f"{date_compact[0:4]}-{date_compact[4:6]}-{date_compact[6:8]}" if date_compact else None
    return admin_id, date_str


async def suspicious_undo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    admin_id, date_str = _parse_alert_data(query.data)
    admin = await db.get_admin(admin_id)
    admin_name = (admin["display_name"] or admin["full_name"]) if admin else str(admin_id)
    reverted, skipped = await db.undo_admin_actions(admin_id, date_str)
    await db.log_action(PISHVA_ID, "undo_admin_actions",
                         f"خنثی‌سازی اقدامات {admin_name} در {date_str}: {len(reverted)} مورد")
    old_text = query.message.text or ""
    text = (
        f"{old_text}\n\n"
        f"↩️ *خنثی‌سازی انجام شد*\n"
        f"✅ برگردانده‌شده: `{len(reverted)}`\n"
        f"⏭️ ردشده (بدون امکان بازگشت خودکار): `{len(skipped)}`"
    )
    await safe_edit_message_text(query, text, reply_markup=kb.kb_back("menu_pishva"))


async def suspicious_disable(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer()
    admin_id, _ = _parse_alert_data(query.data)
    admin = await db.get_admin(admin_id)
    admin_name = (admin["display_name"] or admin["full_name"]) if admin else str(admin_id)
    await db.kick_admin(admin_id)
    await db.log_action(PISHVA_ID, "kick_admin",
                         f"خاموشی خودکار بابت فعالیت مشکوک: {admin_name}", admin_id)
    try:
        await ctx.bot.send_message(
            chat_id=admin_id,
            text="🚫 دسترسی شما به ربات به دلیل فعالیت مشکوک توسط مدیر ارشد قطع شد."
        )
    except Exception:
        pass
    old_text = query.message.text or ""
    await safe_edit_message_text(
        query,
        f"{old_text}\n\n🔇 *ادمین «{admin_name}» غیرفعال شد.*",
        reply_markup=kb.kb_back("menu_pishva")
    )


async def suspicious_dismiss(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    await query.answer("✅ ثبت شد.")
    old_text = query.message.text or ""
    await safe_edit_message_text(
        query,
        f"{old_text}\n\n✅ *مدیر ارشد این هشدار را بررسی و تایید کرد که مشکلی نیست.*",
        reply_markup=kb.kb_back("menu_pishva")
    )
