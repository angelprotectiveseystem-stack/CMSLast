import re
import platform
from telegram import Update
from telegram.ext import ContextTypes
import database as db
import keyboards as kb
from helpers import box, separator, now_shamsi
from config import PISHVA_ID, ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER

ADMIN_KEYWORDS = {"تنظیم مدیر", "تنظیم مدیر امنیتی", "حذف مدیر", "حذف مدیر امنیتی"}

# کلمه‌ی گفته‌شده -> نام یکتای عملیات (برای پشتیبانی از مترادف‌ها)
SIMPLE_KEYWORDS = {
    "پنل": "panel",
    "داشبورد": "dashboard",
    "وظیفه": "tasks",
    "مسابقه": "matches",
    "بازیکن": "players",
    "مخابره": "comms",
    "امنیت": "security",
    "وضعیت": "status",
    "کلاس": "classes",
    "تیم": "teams",
    "بکاپ": "backup",
    "درخواست": "requests",
    "لاگ": "logs",
    "گزارش": "logs",
    "راهنما": "help",
    "کمک": "help",
    "قرعه": "lottery",
    "جدول": "elo",
    "رتبه": "elo",
    "قهرمانان": "champions",
    "یادآور": "reminders",
    "تنظیمات": "settings",
    "فیدبک": "feedback",
    "انتقاد": "feedback",
    "شروع": "restart",
}

PISHVA_ONLY_ACTIONS = {
    "security", "status", "backup", "requests", "logs", "reminders", "settings",
}


async def handle_keyword_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    action = SIMPLE_KEYWORDS.get(text)

    if action is None and text not in ADMIN_KEYWORDS:
        return

    uid = update.effective_user.id if update.effective_user else None
    if not uid:
        return
    is_pishva = (uid == PISHVA_ID)
    admin = await db.get_admin(uid)
    is_admin = bool(admin and admin["is_active"])

    if not (is_pishva or is_admin):
        return

    if action and action in PISHVA_ONLY_ACTIONS and not is_pishva:
        await update.message.reply_text("⛔ این دستور فقط برای پیشواست.")
        return

    # ─── پنل ───
    if action == "panel":
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
    if action == "dashboard":
        from dashboard import build_dashboard_pishva_text, build_dashboard_admin_text
        if is_pishva:
            dtext = await build_dashboard_pishva_text()
            await update.message.reply_text(dtext, reply_markup=kb.kb_dashboard_pishva(), parse_mode="Markdown")
        else:
            dtext = await build_dashboard_admin_text(uid)
            await update.message.reply_text(dtext, reply_markup=kb.kb_dashboard_admin(), parse_mode="Markdown")
        return

    # ─── وظیفه ───
    if action == "tasks":
        if is_pishva:
            await update.message.reply_text(box("📋 وظایف"), reply_markup=kb.kb_tasks_pishva(), parse_mode="Markdown")
        else:
            await update.message.reply_text(box("📋 وظایف"), reply_markup=kb.kb_tasks_admin(), parse_mode="Markdown")
        return

    # ─── مسابقه ───
    if action == "matches":
        await update.message.reply_text(
            box("♟️ مدیریت مسابقات"), reply_markup=kb.kb_matches_menu(), parse_mode="Markdown"
        )
        return

    # ─── بازیکن ───
    if action == "players":
        role_key = "pishva" if is_pishva else admin["role"]
        await update.message.reply_text(
            box("👤 مدیریت بازیکنان"), reply_markup=kb.kb_players_menu(role_key), parse_mode="Markdown"
        )
        return

    # ─── مخابره ───
    if action == "comms":
        if is_pishva:
            await update.message.reply_text(box("📡 مخابرات"), reply_markup=kb.kb_comms_pishva(), parse_mode="Markdown")
        else:
            await update.message.reply_text(box("📡 مخابرات"), reply_markup=kb.kb_comms_admin(), parse_mode="Markdown")
        return

    # ─── امنیت ───
    if action == "security":
        current = await db.get_setting("system_status", "normal")
        await update.message.reply_text(
            f"{box('🚦 وضعیت سیستم')}\n\nوضعیت فعلی را انتخاب کنید:",
            reply_markup=kb.kb_status_select(current), parse_mode="Markdown"
        )
        return

    # ─── وضعیت (گزارش کامل سیستم) ───
    if action == "status":
        report = await _build_system_status_report()
        await update.message.reply_text(report, parse_mode="Markdown")
        return

    # ─── کلاس ───
    if action == "classes":
        await update.message.reply_text(
            box("🏫 مدیریت کلاس‌ها"), reply_markup=kb.kb_class_manage(), parse_mode="Markdown"
        )
        return

    # ─── تیم ───
    if action == "teams":
        team_mode = await db.get_setting("team_mode_enabled", "0")
        if team_mode != "1":
            await update.message.reply_text("❗ حالت تیمی در حال حاضر غیرفعال است.")
            return
        await update.message.reply_text(
            box("🏆 مدیریت تیم‌ها"), reply_markup=kb.kb_teams_menu(), parse_mode="Markdown"
        )
        return

    # ─── بکاپ ───
    if action == "backup":
        await update.message.reply_text(
            f"{box('💾 سیستم پشتیبان‌گیری')}\n\n📌 بازه زمانی را انتخاب کنید:",
            reply_markup=kb.kb_backup_main(), parse_mode="Markdown"
        )
        return

    # ─── درخواست ───
    if action == "requests":
        reqs = await db.get_pending_requests()
        if not reqs:
            await update.message.reply_text(
                f"{box('📥 درخواست‌های دسترسی')}\n\n✅ هیچ درخواست جدیدی وجود ندارد.",
                parse_mode="Markdown"
            )
            return
        for req in reqs:
            role_label = "🏆 مدیر مسابقات" if req["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
            rtext = (
                f"📥 *درخواست دسترسی*\n\n"
                f"👤 نام: {req['full_name']}\n"
                f"🔗 یوزرنیم: {req['username']}\n"
                f"💼 نقش: {role_label}\n"
                f"📝 پیام: {req['message'] or '—'}\n"
                f"⏱️ زمان: `{str(req['requested_at'])[:19]}`"
            )
            await update.message.reply_text(
                rtext, reply_markup=kb.kb_access_request(req["id"]), parse_mode="Markdown"
            )
        return

    # ─── لاگ / گزارش ───
    if action == "logs":
        logs = await db.get_action_logs("today")
        admins_map = {a["telegram_id"]: (a["display_name"] or a["full_name"]) for a in await db.get_all_admins()}
        pname = await db.get_setting("pishva_display_name", "پیشوا")
        if not logs:
            await update.message.reply_text("❗ هیچ اقدامی امروز ثبت نشده.")
            return
        lines = [box("🔍 لاگ اقدامات — امروز")]
        for log in logs[:20]:
            name = pname if log["admin_id"] == PISHVA_ID else admins_map.get(log["admin_id"], str(log["admin_id"]))
            t = str(log["logged_at"] or "")[:16]
            lines.append(f"`{t}` — {name}: {log['action_type']} — {log['description'] or ''}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ─── راهنما / کمک ───
    if action == "help":
        from help_center import kb_help_main
        role = "pishva" if is_pishva else "admin"
        await update.message.reply_text(
            box("📚 مرکز راهنمای سیستم"), reply_markup=kb_help_main(role), parse_mode="Markdown"
        )
        return

    # ─── قرعه ───
    if action == "lottery":
        await update.message.reply_text(
            f"{box('🎲 قرعه‌کشی هوشمند')}\n\n📌 محدوده بازیکنان:",
            reply_markup=kb.kb_lottery_scope(), parse_mode="Markdown"
        )
        return

    # ─── جدول / رتبه (Elo) ───
    if action == "elo":
        try:
            from elo import get_elo_leaderboard, get_elo_title
            leaders = await get_elo_leaderboard(10)
        except Exception:
            leaders = []
        if not leaders:
            await update.message.reply_text("❗ هنوز مسابقه‌ای با نتیجه ثبت نشده.")
            return
        medals = ["🥇", "🥈", "🥉"]
        lines = [box("🏆 جدول رتبه‌بندی Elo")]
        for i, p in enumerate(leaders):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{medal} {p['full_name']} — `{int(p['rating'])}` ({get_elo_title(p['rating'])})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ─── قهرمانان ───
    if action == "champions":
        try:
            from features import _get_best_player_since
            from datetime import datetime, timedelta
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            month_ago = (datetime.now() - timedelta(days=30)).isoformat()
            weekly = await _get_best_player_since(week_ago)
            monthly = await _get_best_player_since(month_ago)
        except Exception:
            weekly = monthly = None
        lines = [
            box("🏆 قهرمانان"),
            "🌟 هفته: " + (f"{weekly['name']} ({weekly['wins']} برد)" if weekly else "—"),
            "👑 ماه: " + (f"{monthly['name']} ({monthly['wins']} برد)" if monthly else "—"),
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ─── یادآور ───
    if action == "reminders":
        import reminders as rem
        master = (await db.get_setting("reminder_master_enabled", "1")) == "1"
        items = []
        for rtype, conf in rem.REMINDER_TYPES.items():
            enabled = await rem._is_enabled(rtype)
            interval = await rem._get_interval_hours(rtype)
            items.append((rtype, conf["label"], enabled, interval))
        text = (
            "⏰ تنظیمات یادآورها\n\n"
            "در این بخش می‌توانید هر یادآور را جداگانه فعال یا غیرفعال کنید "
            "و بازه‌ی زمانی ارسال آن را تنظیم نمایید."
        )
        await update.message.reply_text(text, reply_markup=kb.kb_reminders_menu(master, items), parse_mode="Markdown")
        return

    # ─── تنظیمات ───
    if action == "settings":
        keys = ["notifications_enabled", "communications_enabled", "help_enabled",
            "match_registration_enabled", "admin_login_enabled", "bot_active_for_admins",
            "team_mode_enabled", "team_registration_enabled", "managers_can_create_teams"]
        settings = {k: await db.get_setting(k, "1") for k in keys}
        await update.message.reply_text(
            f"{box('⚙️ تنظیمات ربات')}\n\n📌 گزینه موردنظر را تغییر دهید:",
            reply_markup=kb.kb_pishva_settings_simple(settings), parse_mode="Markdown"
        )
        return

    # ─── فیدبک / انتقاد ───
    if action == "feedback":
        await update.message.reply_text(
            box("💡 انتقادات و پیشنهادات"), reply_markup=kb.kb_feedback_menu(), parse_mode="Markdown"
        )
        return

    # ─── شروع (فقط برای کاربران قبلاً ثبت‌شده — بدون فلوی ثبت‌نام) ───
    if action == "restart":
        from auth import show_pishva_welcome, show_admin_welcome
        if is_pishva:
            await show_pishva_welcome(update, ctx)
        else:
            await show_admin_welcome(update, ctx, admin)
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


# ─── ورودی گفتگوی مخابرات از طریق کلمه (برای comms_conv) ────────
async def kw_announce_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    from config import ST_ANNOUNCEMENT_TEXT
    if update.effective_user.id != PISHVA_ID:
        return ConversationHandler.END
    await update.message.reply_text("📢 متن بیانیه را وارد کنید:")
    return ST_ANNOUNCEMENT_TEXT


async def kw_news_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    from config import ST_NEWS_TEXT
    if update.effective_user.id != PISHVA_ID:
        return ConversationHandler.END
    await update.message.reply_text("📰 متن خبر فوری را وارد کنید:")
    return ST_NEWS_TEXT
