import re
import platform
from telegram import Update
from telegram.ext import ContextTypes
import database as db
import keyboards as kb
from helpers import box, separator, now_shamsi
from config import PISHVA_ID, ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER

ADMIN_KEYWORDS = {"تنظیم مدیر", "تنظیم مدیر امنیتی", "حذف مدیر", "حذف مدیر امنیتی"}
SIMPLE_KEYWORDS = {"پنل", "داشبورد", "وظیفه", "مسابقه", "بازیکن", "مخابره", "امنیت", "وضعیت"}


async def handle_keyword_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if text not in SIMPLE_KEYWORDS and text not in ADMIN_KEYWORDS:
        return

    uid = update.effective_user.id if update.effective_user else None
    if not uid:
        return
    is_pishva = (uid == PISHVA_ID)
    admin = await db.get_admin(uid)
    is_admin = bool(admin and admin["is_active"])

    if not (is_pishva or is_admin):
        return

    # ─── پنل ───
    if text == "پنل":
        if is_pishva:
            await update.message.reply_text(
                box("👑 پنل پیشوا"), reply_markup=kb.kb_pishva_main(), parse_mode="Markdown"
            )
        else:
            markup = (kb.kb_tournament_manager_main() if admin["role"] == ROLE_TOURNAMENT_MANAGER
                      else kb.kb_security_manager_main())
            role_label = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
            await update.message.reply_text(
                box("📋 پنل — " + role_label), reply_markup=markup, parse_mode="Markdown"
            )
        return

    # ─── داشبورد ───
    if text == "داشبورد":
        from dashboard import build_dashboard_pishva_text, build_dashboard_admin_text
        if is_pishva:
            dtext = await build_dashboard_pishva_text()
            await update.message.reply_text(dtext, reply_markup=kb.kb_dashboard_pishva(), parse_mode="Markdown")
        else:
            dtext = await build_dashboard_admin_text(uid)
            await update.message.reply_text(dtext, reply_markup=kb.kb_dashboard_admin(), parse_mode="Markdown")
        return

    # ─── وظیفه ───
    if text == "وظیفه":
        if is_pishva:
            await update.message.reply_text(box("📋 وظایف"), reply_markup=kb.kb_tasks_pishva(), parse_mode="Markdown")
        else:
            await update.message.reply_text(box("📋 وظایف"), reply_markup=kb.kb_tasks_admin(), parse_mode="Markdown")
        return

    # ─── مسابقه ───
    if text == "مسابقه":
        await update.message.reply_text(
            box("♟️ مدیریت مسابقات"), reply_markup=kb.kb_matches_menu(), parse_mode="Markdown"
        )
        return

    # ─── بازیکن ───
    if text == "بازیکن":
        role_key = "pishva" if is_pishva else admin["role"]
        await update.message.reply_text(
            box("👤 مدیریت بازیکنان"), reply_markup=kb.kb_players_menu(role_key), parse_mode="Markdown"
        )
        return

    # ─── مخابره ───
    if text == "مخابره":
        if is_pishva:
            await update.message.reply_text(box("📡 مخابرات"), reply_markup=kb.kb_comms_pishva(), parse_mode="Markdown")
        else:
            await update.message.reply_text(box("📡 مخابرات"), reply_markup=kb.kb_comms_admin(), parse_mode="Markdown")
        return

    # ─── امنیت (فقط پیشوا) ───
    if text == "امنیت":
        if not is_pishva:
            await update.message.reply_text("⛔ این دستور فقط برای پیشواست.")
            return
        current = await db.get_setting("system_status", "normal")
        await update.message.reply_text(
            f"{box('🚦 وضعیت سیستم')}\n\nوضعیت فعلی را انتخاب کنید:",
            reply_markup=kb.kb_status_select(current), parse_mode="Markdown"
        )
        return

    # ─── وضعیت (گزارش کامل سیستم) ───
    if text == "وضعیت":
        if not (is_pishva or is_admin):
            return
        report = await _build_system_status_report()
        await update.message.reply_text(report, parse_mode="Markdown")
        return

    # ─── تنظیم/حذف مدیر (فقط پیشوا، با ریپلای) ───
    if text in ADMIN_KEYWORDS:
        if not is_pishva:
            await update.message.reply_text("⛔ این دستور فقط برای پیشواست.")
            return
        target_id, target_name, target_username = _extract_reply_target(update)
        if not target_id:
            await update.message.reply_text(
                "❗ برای این دستور باید روی پیام شخص موردنظر (یا پیامی حاوی آیدی عددی او) ریپلای کنید."
            )
            return
        if target_id == PISHVA_ID:
            await update.message.reply_text("❗ نمی‌توانید پیشوا را به‌عنوان مدیر تنظیم/حذف کنید.")
            return

        if text == "تنظیم مدیر":
            await _set_admin(target_id, target_username, target_name, ROLE_TOURNAMENT_MANAGER)
            await update.message.reply_text(f"✅ {target_name} به‌عنوان 🏆 مدیر مسابقات تنظیم شد.")
        elif text == "تنظیم مدیر امنیتی":
            await _set_admin(target_id, target_username, target_name, ROLE_SECURITY_MANAGER)
            await update.message.reply_text(f"✅ {target_name} به‌عنوان 🛡️ مدیر امنیتی تنظیم شد.")
        elif text in ("حذف مدیر", "حذف مدیر امنیتی"):
            existing = await db.get_admin(target_id)
            if not existing or not existing["is_active"]:
                await update.message.reply_text("❗ این فرد در حال حاضر مدیر فعال نیست.")
                return
            await db.kick_admin(target_id)
            await db.log_action(PISHVA_ID, "kick_admin_keyword", f"حذف مدیر: {target_name}", target_id)
            await update.message.reply_text(f"✅ دسترسی مدیریت {target_name} حذف شد.")
        return


def _extract_reply_target(update: Update):
    msg = update.message
    if not msg.reply_to_message:
        return None, None, None
    replied = msg.reply_to_message
    if replied.from_user and not replied.from_user.is_bot:
        u = replied.from_user
        name = " ".join(filter(None, [u.first_name, u.last_name])) or (u.username or str(u.id))
        username = f"@{u.username}" if u.username else ""
        return u.id, name, username
    if replied.text:
        m = re.search(r"\d{5,}", replied.text)
        if m:
            tid = int(m.group())
            return tid, f"کاربر {tid}", ""
    return None, None, None


async def _set_admin(telegram_id: int, username: str, full_name: str, role: str):
    existing = await db.get_admin(telegram_id)
    if existing:
        await db.update_admin_role_active(telegram_id, role)
    else:
        await db.create_admin(telegram_id, username, full_name, role)
    await db.log_action(PISHVA_ID, "set_admin_keyword", f"{full_name} -> {role}", telegram_id)


async def _build_system_status_report() -> str:
    try:
        import resource
        mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mem_mb = round(mem_kb / 1024, 1)
        mem_txt = f"`{mem_mb}` مگابایت"
    except Exception:
        mem_txt = "نامشخص"

    status = await db.get_setting("system_status", "normal")
    status_map = {"normal": "🟢 نرمال", "bad": "🟡 احتیاطی", "danger": "🔴 خطرناک", "aps": "🪽 APS"}
    wh = await db.get_setting("working_hours_active", "0")
    db_manual = await db.get_setting("db_manual_status", "1")
    repair = await db.get_setting("repair_mode", "0")

    all_players = await db.get_all_players()
    all_matches = await db.get_matches_by_filter("all")
    all_admins = await db.get_all_admins()
    all_tasks = await db.get_all_tasks()
    all_classes = await db.get_all_classes()
    try:
        all_teams = await db.get_all_teams()
    except Exception:
        all_teams = []

    lines = [
        box("🗄️ وضعیت کامل سیستم"),
        "⏱️ `" + now_shamsi() + "`",
        "",
        separator("🚦 وضعیت‌ها"),
        "📡 سیستم: " + status_map.get(status, status),
        "🕐 ساعت کاری: " + ("🟢 باز" if wh == "1" else "🔴 بسته"),
        "🗄️ دیتابیس (دستی): " + ("🟢 فعال" if db_manual == "1" else "⚠️ غیرفعال"),
        "🔧 حالت تعمیر: " + ("🔧 فعال" if repair == "1" else "✅ عادی"),
        "",
        separator("💾 حافظه و اجرا"),
        "🧠 مصرف حافظه: " + mem_txt,
        "🐍 نسخه پایتون: `" + platform.python_version() + "`",
        "",
        separator("📊 آمار دیتا"),
        "🏫 کلاس‌ها: `" + str(len(all_classes)) + "`",
        "👤 بازیکنان: `" + str(len(all_players)) + "`",
        "♟️ مسابقات: `" + str(len(all_matches)) + "`",
        "👥 مدیران (کل): `" + str(len(all_admins)) + "`",
        "📋 وظایف: `" + str(len(all_tasks)) + "`",
        "🏆 تیم‌ها: `" + str(len(all_teams)) + "`",
        separator(),
    ]
    return "\n".join(lines)
