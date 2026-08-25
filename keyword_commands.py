import re
import json
import platform
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    # ─── کلمات جدید ───
    "پیشوا": "pishva_panel",       # فقط برای پیشوا پنلش رو باز می‌کنه
    "اطلاعات": "reply_info",       # ریپلای روی یه پیام → جزئیات کاربر
    "درباره": "reply_info",        # مترادف اطلاعات
    "کیه": "reply_info",           # مترادف اطلاعات
    "آنلاین": "online_admins",     # لیست ادمین‌های آنلاین/فعال
    "ادمین‌ها": "admin_list",      # لیست همه ادمین‌ها
    "ادمینا": "admin_list",
    "مدیران": "admin_list",
    "آمار": "quick_stats",         # آمار سریع بازیکنان و مسابقات
    "نتایج": "recent_results",     # آخرین نتایج مسابقات
    "اخطارها": "warnings_list",    # لیست بازیکنان با اخطار
}

PISHVA_ONLY_ACTIONS = {
    "security", "status", "backup", "requests", "logs", "reminders", "settings",
    "pishva_panel",
}


# ─── محافظت از مالکیت پنل ────────────────────────────────────
async def panel_ownership_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    اگه کسی روی پنل یه نفر دیگه دست بزنه، هشدار بده و متوقف کن.
    فقط در گروه/سوپرگروه فعاله.
    """
    from telegram.ext import ApplicationHandlerStop
    query = update.callback_query
    if not query:
        return

    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    msg = query.message
    if not msg:
        return

    msg_key = f"panel_owner_{msg.message_id}"
    owner_id = ctx.chat_data.get(msg_key) if ctx.chat_data is not None else None

    if owner_id is None:
        return

    requester_id = query.from_user.id
    if requester_id == owner_id or requester_id == PISHVA_ID:
        return

    await query.answer(
        "⛔ این پنل متعلق به شما نیست!\n"
        "برای باز کردن پنل خودتان، کلمه «پنل» را بفرستید.",
        show_alert=True
    )
    raise ApplicationHandlerStop()


async def register_panel_owner(update: Update, ctx: ContextTypes.DEFAULT_TYPE, msg_id: int):
    """صاحب پنل رو ثبت می‌کنه"""
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return
    uid = update.effective_user.id if update.effective_user else None
    if uid and ctx.chat_data is not None:
        ctx.chat_data[f"panel_owner_{msg_id}"] = uid


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

    # ─── پنل پیشوا (کلمه «پیشوا») ───
    if action == "pishva_panel":
        sent = await update.message.reply_text(
            box("👑 پنل پیشوا"), reply_markup=kb.kb_pishva_main(), parse_mode="Markdown"
        )
        await register_panel_owner(update, ctx, sent.message_id)
        return

    # ─── پنل ───
    if action == "panel":
        if is_pishva:
            sent = await update.message.reply_text(
                box("👑 پنل پیشوا"), reply_markup=kb.kb_pishva_main(), parse_mode="Markdown"
            )
        else:
            markup = (kb.kb_tournament_manager_main() if admin["role"] == ROLE_TOURNAMENT_MANAGER
                      else kb.kb_security_manager_main())
            role_label = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
            sent = await update.message.reply_text(
                box("📋 پنل — " + role_label), reply_markup=markup, parse_mode="Markdown"
            )
        await register_panel_owner(update, ctx, sent.message_id)
        return

    # ─── داشبورد ───
    if action == "dashboard":
        from dashboard import build_dashboard_pishva_text, build_dashboard_admin_text
        if is_pishva:
            dtext = await build_dashboard_pishva_text()
            sent = await update.message.reply_text(dtext, reply_markup=kb.kb_dashboard_pishva(), parse_mode="Markdown")
        else:
            dtext = await build_dashboard_admin_text(uid)
            sent = await update.message.reply_text(dtext, reply_markup=kb.kb_dashboard_admin(), parse_mode="Markdown")
        await register_panel_owner(update, ctx, sent.message_id)
        return

    # ─── اطلاعات/درباره/کیه — ریپلای روی پیام ───
    if action == "reply_info":
        target_id, target_name, target_username = _extract_reply_target(update)
        if not target_id:
            await update.message.reply_text(
                "❗ برای دیدن اطلاعات، روی پیام شخص موردنظر ریپلای کنید و «اطلاعات» بنویسید."
            )
            return
        text_lines = await _build_user_info(target_id, target_name, target_username)
        await update.message.reply_text("\n".join(text_lines), parse_mode="Markdown")
        return

    # ─── آنلاین (ادمین‌های فعال اخیر) ───
    if action == "online_admins":
        admins_all = await db.get_active_admins()
        from datetime import datetime, timedelta
        now_dt = datetime.now()
        lines = [box("🟢 ادمین‌های فعال اخیر")]
        found = False
        for a in admins_all:
            last = a.get("last_active")
            if last:
                try:
                    last_dt = datetime.fromisoformat(str(last))
                    diff = now_dt - last_dt
                    if diff < timedelta(hours=24):
                        mins = int(diff.total_seconds() // 60)
                        if mins < 60:
                            ago = f"{mins} دقیقه پیش"
                        else:
                            ago = f"{int(mins//60)} ساعت پیش"
                        name = a["display_name"] or a["full_name"]
                        role_lbl = "🏆" if a["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️"
                        lines.append(f"{role_lbl} {name} — `{ago}`")
                        found = True
                except Exception:
                    pass
        if not found:
            lines.append("❗ هیچ ادمینی در ۲۴ ساعت اخیر فعال نبوده.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ─── لیست مدیران ───
    if action == "admin_list":
        admins_all = await db.get_active_admins()
        lines = [box(f"👥 مدیران فعال — {len(admins_all)} نفر")]
        for a in admins_all:
            name = a["display_name"] or a["full_name"]
            uname = f"@{a['username']}" if a.get("username") else "—"
            role_lbl = "🏆 مدیر مسابقات" if a["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
            lines.append(f"• {name} ({uname}) — {role_lbl}")
        if not admins_all:
            lines.append("❗ هیچ مدیر فعالی ثبت نشده.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ─── آمار سریع ───
    if action == "quick_stats":
        all_players = await db.get_all_players()
        active_players = await db.get_continuing_players()
        all_matches = await db.get_matches_by_filter("all")
        done_matches = [m for m in all_matches if m["result"]]
        warned = [p for p in all_players if p["warnings"] > 0]
        today_m = await db.get_matches_by_filter("today")
        lines = [
            box("📊 آمار سریع"),
            separator("👤 بازیکنان"),
            f"کل: `{len(all_players)}` | فعال: `{len(active_players)}` | با اخطار: `{len(warned)}`",
            separator("♟️ مسابقات"),
            f"کل: `{len(all_matches)}` | با نتیجه: `{len(done_matches)}` | امروز: `{len(today_m)}`",
            separator(),
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ─── آخرین نتایج ───
    if action == "recent_results":
        all_matches = await db.get_matches_by_filter("all")
        done = [m for m in all_matches if m["result"]][-10:]
        done.reverse()
        if not done:
            await update.message.reply_text("❗ هنوز مسابقه‌ای با نتیجه ثبت نشده.")
            return
        lines = [box("🏆 آخرین نتایج")]
        for m in done:
            if m["result"] == "white":
                res = f"🥇 {m['white_name']} برنده"
            elif m["result"] == "black":
                res = f"🥇 {m['black_name']} برنده"
            else:
                res = "🤝 تساوی"
            lines.append(f"• {m['white_name']} vs {m['black_name']} — {res}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ─── لیست اخطارها ───
    if action == "warnings_list":
        all_players = await db.get_all_players()
        warned = sorted([p for p in all_players if p["warnings"] > 0],
                        key=lambda p: p["warnings"], reverse=True)
        if not warned:
            await update.message.reply_text("✅ هیچ بازیکنی اخطار فعال ندارد.")
            return
        lines = [box(f"⚠️ بازیکنان با اخطار — {len(warned)} نفر")]
        for p in warned:
            bar = "🔴" * min(p["warnings"], 3) + "⚪" * max(0, 3 - p["warnings"])
            lines.append(f"• {p['full_name']} — {bar} ({p['warnings']} اخطار)")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ─── وظیفه ───
    if action == "tasks":
        if is_pishva:
            sent = await update.message.reply_text(box("📋 وظایف"), reply_markup=kb.kb_tasks_pishva(), parse_mode="Markdown")
        else:
            sent = await update.message.reply_text(box("📋 وظایف"), reply_markup=kb.kb_tasks_admin(), parse_mode="Markdown")
        await register_panel_owner(update, ctx, sent.message_id)
        return

    # ─── مسابقه ───
    if action == "matches":
        sent = await update.message.reply_text(
            box("♟️ مدیریت مسابقات"), reply_markup=kb.kb_matches_menu(), parse_mode="Markdown"
        )
        await register_panel_owner(update, ctx, sent.message_id)
        return

    # ─── بازیکن ───
    if action == "players":
        role_key = "pishva" if is_pishva else admin["role"]
        sent = await update.message.reply_text(
            box("👤 مدیریت بازیکنان"), reply_markup=kb.kb_players_menu(role_key), parse_mode="Markdown"
        )
        await register_panel_owner(update, ctx, sent.message_id)
        return

    # ─── مخابره ───
    if action == "comms":
        if is_pishva:
            sent = await update.message.reply_text(box("📡 مخابرات"), reply_markup=kb.kb_comms_pishva(), parse_mode="Markdown")
        else:
            sent = await update.message.reply_text(box("📡 مخابرات"), reply_markup=kb.kb_comms_admin(), parse_mode="Markdown")
        await register_panel_owner(update, ctx, sent.message_id)
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
        sent = await update.message.reply_text(
            box("🏫 مدیریت کلاس‌ها"), reply_markup=kb.kb_class_manage(), parse_mode="Markdown"
        )
        await register_panel_owner(update, ctx, sent.message_id)
        return

    # ─── تیم ───
    if action == "teams":
        team_mode = await db.get_setting("team_mode_enabled", "0")
        if team_mode != "1":
            await update.message.reply_text("❗ حالت تیمی در حال حاضر غیرفعال است.")
            return
        sent = await update.message.reply_text(
            box("🏆 مدیریت تیم‌ها"), reply_markup=kb.kb_teams_menu(), parse_mode="Markdown"
        )
        await register_panel_owner(update, ctx, sent.message_id)
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
        sent = await update.message.reply_text(
            f"{box('🎲 قرعه‌کشی هوشمند')}\n\n📌 محدوده بازیکنان:",
            reply_markup=kb.kb_lottery_scope(), parse_mode="Markdown"
        )
        await register_panel_owner(update, ctx, sent.message_id)
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
            "team_mode_enabled", "team_registration_enabled", "managers_can_create_teams",
            "admin_dashboard_enabled"]
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


# ─── اطلاعات کاربر هنگام ریپلای ────────────────────────────
async def _build_user_info(target_id: int, target_name: str, target_username: str) -> list:
    from datetime import datetime, timedelta
    lines = [box(f"🔍 اطلاعات — {target_name}")]

    # یوزرنیم
    uname_txt = target_username if target_username else "—"
    lines.append(f"🪪 یوزرنیم: {uname_txt}")
    lines.append(f"🆔 آیدی: `{target_id}`")
    lines.append("")

    # پیشواست؟
    if target_id == PISHVA_ID:
        pname = await db.get_setting("pishva_display_name", "پیشوا")
        lines.append(f"👑 *نقش: پیشوا ({pname})*")
        lines.append("🔓 دسترسی: همه چیز")
        return lines

    # ادمینه؟
    admin = await db.get_admin(target_id)
    if admin and admin["is_active"]:
        role_lbl = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
        lines.append(f"💼 *نقش: {role_lbl}*")
        lines.append(f"✅ وضعیت: فعال")

        # آخرین فعالیت
        last = admin.get("last_active")
        if last:
            try:
                last_dt = datetime.fromisoformat(str(last))
                diff = datetime.now() - last_dt
                mins = int(diff.total_seconds() // 60)
                if mins < 2:
                    ago = "🟢 همین الان"
                elif mins < 60:
                    ago = f"🟡 {mins} دقیقه پیش"
                elif mins < 1440:
                    ago = f"🟠 {int(mins//60)} ساعت پیش"
                else:
                    ago = f"🔴 {int(mins//1440)} روز پیش"
                lines.append(f"⏱️ آخرین فعالیت: {ago}")
            except Exception:
                pass

        # تاریخ عضویت
        joined = admin.get("joined_at")
        if joined:
            lines.append(f"📅 عضویت: `{str(joined)[:10]}`")

        # دسترسی‌ها
        lines.append("")
        lines.append(separator("🔐 دسترسی‌ها"))
        try:
            perms = json.loads(admin.get("permissions") or "{}")
            perm_labels = {
                "match_management": "♟️ مسابقات",
                "view_players": "👤 مشاهده بازیکنان",
                "issue_warning": "⚠️ صدور اخطار",
                "request_ban": "🚫 درخواست اخراج",
                "direct_ban": "❌ اخراج مستقیم",
                "edit_delete_match": "✏️ ویرایش مسابقه",
                "communications": "📡 مخابرات",
                "notifications": "🔔 اعلانات",
                "news": "📰 اخبار",
                "assign_task": "📋 وظیفه",
                "report": "🚨 گزارش",
                "senior_admin": "🌟 ارشد",
                "settings_access": "⚙️ تنظیمات",
            }
            active_perms = [lbl for k, lbl in perm_labels.items() if perms.get(k, True)]
            inactive_perms = [lbl for k, lbl in perm_labels.items() if not perms.get(k, True)]
            if active_perms:
                lines.append("✅ " + " | ".join(active_perms))
            if inactive_perms:
                lines.append("❌ " + " | ".join(inactive_perms))
        except Exception:
            lines.append("دسترسی‌ها: نامشخص")

        # اخطارها
        warns = admin.get("warnings", 0)
        if warns:
            lines.append(f"\n⚠️ اخطارهای مدیریتی: `{warns}`")
    else:
        # نه پیشوا، نه ادمین
        lines.append("👤 نقش: کاربر عادی")
        lines.append("❌ در سیستم ثبت نشده")

        # شاید بلاک باشه
        blocked = await db.get_blocked_user(target_id)
        if blocked:
            lines.append(f"\n🚫 *این کاربر توسط APS بلاک شده است*")
            lines.append(f"📝 دلیل: {blocked.get('reason', '—')}")

    return lines
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
