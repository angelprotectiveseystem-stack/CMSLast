"""
dashboard.py — داشبورد تفصیلی برای مدیر ارشد و ادمین‌ها
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from helpers import safe_edit_message_text, box, separator, now_shamsi, progress_bar, power_bar, warning_bar_admin
from config import PISHVA_ID, ROLE_TOURNAMENT_MANAGER


async def build_dashboard_pishva_text() -> str:
    try:
        admins = await db.get_active_admins()
        all_players = await db.get_all_players()
        active_players = await db.get_continuing_players()
        all_matches = await db.get_matches_by_filter("all")
        today_matches = await db.get_matches_by_filter("today")
        pending_matches = await db.get_pending_matches()
        done_matches = [m for m in all_matches if m["result"]]
        all_tasks = await db.get_all_tasks()
        pending_tasks = [t for t in all_tasks if t["status"] == "pending"]
        pending_req = await db.get_pending_requests()
        default_t = await db.get_default_tournament()
        status = await db.get_setting("system_status", "normal")
        wh = await db.get_setting("working_hours_active", "0")
        status_map = {
            "normal": "🟢 نرمال", "bad": "🟡 احتیاطی",
            "danger": "🔴 خطرناک", "aps": "🪽 APS"
        }
        wh_txt = "🟢 باز" if wh == "1" else "🔴 بسته"
        pct = int(len(done_matches) / len(all_matches) * 100) if all_matches else 0
        bar = progress_bar(pct)

        sorted_p = sorted(all_players, key=lambda p: p["wins"], reverse=True)
        top_player = sorted_p[0]["full_name"] if sorted_p and sorted_p[0]["wins"] > 0 else "—"
        top_wins = sorted_p[0]["wins"] if sorted_p else 0

        warned_players = [p for p in all_players if p["warnings"] > 0]

        last_txt = "—"
        for m in reversed(all_matches):
            if m["result"]:
                if m["result"] == "white":
                    last_txt = "🥇 " + m["white_name"] + " برنده شد"
                elif m["result"] == "black":
                    last_txt = "🥇 " + m["black_name"] + " برنده شد"
                else:
                    last_txt = "🤝 تساوی"
                break

        elo_lines = ["_هنوز مسابقه‌ای ثبت نشده_"]
        try:
            from elo import get_elo_leaderboard, get_elo_title
            elo_top = await get_elo_leaderboard(3)
            if elo_top:
                medals = ["🥇", "🥈", "🥉"]
                elo_lines = [
                    f"{medals[i]} {p['full_name']} — `{int(p['rating'])}` ({get_elo_title(p['rating'])})"
                    for i, p in enumerate(elo_top)
                ]
        except Exception:
            pass

        champ_lines = ["_داده کافی نیست_"]
        try:
            from features import _get_best_player_since
            from datetime import datetime, timedelta
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            month_ago = (datetime.now() - timedelta(days=30)).isoformat()
            weekly = await _get_best_player_since(week_ago)
            monthly = await _get_best_player_since(month_ago)
            champ_lines = [
                f"🌟 هفته: {weekly['name'] + ' (' + str(weekly['wins']) + ' برد)' if weekly else '—'}",
                f"👑 ماه: {monthly['name'] + ' (' + str(monthly['wins']) + ' برد)' if monthly else '—'}",
            ]
        except Exception:
            pass

        group_id = await db.get_setting("announcement_group_id", "")
        channel_id = await db.get_setting("announcement_channel_id", "")
        group_txt = "✅ تنظیم شده" if group_id else "❌ تنظیم نشده"
        channel_txt = "✅ تنظیم شده" if channel_id else "❌ تنظیم نشده"

        reminder_master = await db.get_setting("reminder_master_enabled", "1")
        reminder_keys = ["reminder_match_enabled", "reminder_task_enabled",
            "reminder_db_enabled", "reminder_admin_enabled"]
        reminder_on_count = 0
        for k in reminder_keys:
            if (await db.get_setting(k, "1")) == "1":
                reminder_on_count += 1
        reminder_txt = (
            f"🟢 فعال ({reminder_on_count}/۴ نوع روشن)"
            if reminder_master == "1" else "🔴 غیرفعال"
        )

        auto_backup_on = await db.get_setting("auto_backup_enabled", "0")
        auto_backup_interval = await db.get_setting("auto_backup_interval", "24")
        backup_txt = (
            f"🟢 فعال (هر {auto_backup_interval} ساعت)"
            if auto_backup_on == "1" else "🔴 غیرفعال"
        )

        db_manual = await db.get_setting("db_manual_status", "1")
        db_manual_txt = "🟢 فعال" if db_manual == "1" else "⚠️ غیرفعال"
        repair_mode = await db.get_setting("repair_mode", "0")
        repair_txt = "🔧 در حال تعمیر" if repair_mode == "1" else "✅ عادی"

        try:
            all_ann = await db.get_all_announcements()
            all_news = await db.get_all_news()
            all_fb = await db.get_all_feedback()
            reports_pending = [f for f in all_fb if f["fb_type"] == "report"]
        except Exception:
            all_ann, all_news, reports_pending = [], [], []

        team_mode = await db.get_setting("team_mode_enabled", "1")
        team_mode_txt = "🟢 فعال" if team_mode == "1" else "🔴 غیرفعال"

        lines = [
            box("📊 داشبورد مدیر ارشد"),
            "⏱️ `" + now_shamsi() + "`",
            "",
            separator("🚦 سیستم"),
            "📡 وضعیت: " + status_map.get(status, status),
            "🕐 ساعت کاری: " + wh_txt,
            "🗄️ دیتابیس (دستی): " + db_manual_txt,
            "🔧 حالت تعمیر: " + repair_txt,
            "📥 درخواست جدید: `" + str(len(pending_req)) + "`",
            "",
            separator("👥 ادمین‌ها"),
            "✅ فعال: `" + str(len(admins)) + "` نفر",
            "📋 وظایف در انتظار: `" + str(len(pending_tasks)) + "`",
            "",
            separator("♟️ مسابقات"),
            "🏅 تورنمنت: *" + (default_t["name"] if default_t else "ندارد") + "*",
            "🎮 امروز: `" + str(len(today_matches)) + "` | ⏳ بی‌نتیجه: `" + str(len(pending_matches)) + "`",
            "📊 کل: `" + str(len(all_matches)) + "` | ✅ با نتیجه: `" + str(len(done_matches)) + "`",
            "🏁 پیشرفت: `" + bar + "`",
            "🏆 آخرین: " + last_txt,
            "",
            separator("👤 بازیکنان"),
            "👥 کل: `" + str(len(all_players)) + "` | ✅ فعال: `" + str(len(active_players)) + "`",
            "⚠️ با اخطار: `" + str(len(warned_players)) + "`",
            "🌟 برترین (برد): *" + top_player + "* (" + str(top_wins) + " برد)",
            "",
            separator("📈 جدول Elo — برترین‌ها"),
            *elo_lines,
            "",
            separator("🏆 قهرمانان"),
            *champ_lines,
            "",
            separator("🏆 حالت تیمی"),
            team_mode_txt,
            "",
            separator("📡 پخش خودکار"),
            "📢 گروه اعلانات: " + group_txt,
            "📣 کانال اعلانات: " + channel_txt,
            "⏰ یادآورها: " + reminder_txt,
            "",
            separator("💾 بکاپ"),
            "🔄 بکاپ خودکار: " + backup_txt,
            "",
            separator("📨 مخابرات"),
            "📢 بیانیه‌های ثبت‌شده: `" + str(len(all_ann)) + "`",
            "📰 اخبار ثبت‌شده: `" + str(len(all_news)) + "`",
            "🚨 گزارش‌های در انتظار: `" + str(len(reports_pending)) + "`",
            separator(),
        ]
        return "\n".join(lines)
    except Exception as e:
        return "❌ خطا در بارگذاری داشبورد:\n`" + str(e) + "`"


async def build_dashboard_admin_text(uid: int) -> str:
    try:
        admin = await db.get_admin(uid)
        _aname = admin["display_name"] or admin["full_name"] if admin else str(uid)
        role_label = "🏆 مدیر مسابقات" if (admin and admin["role"] == ROLE_TOURNAMENT_MANAGER) else "🛡️ مدیر امنیتی"
        pending_matches = await db.get_pending_matches()
        active_players = await db.get_continuing_players()
        all_players = await db.get_all_players()
        warned = [p for p in all_players if p["warnings"] > 0]
        tasks = await db.get_tasks_for(uid)
        pending_tasks = [t for t in tasks if t["status"] == "pending"]
        done_tasks = [t for t in tasks if t["status"] == "done"]
        today_matches = await db.get_matches_by_filter("today")
        done_today = [m for m in today_matches if m["result"]]
        all_matches = await db.get_matches_by_filter("all")
        default_t = await db.get_default_tournament()
        status = await db.get_setting("system_status", "normal")
        status_map = {
            "normal": "🟢 نرمال", "bad": "🟡 احتیاطی",
            "danger": "🔴 خطرناک", "aps": "🪽 APS"
        }

        last_txt = "—"
        for m in reversed(all_matches):
            if m["result"]:
                if m["result"] == "white":
                    last_txt = "🥇 " + m["white_name"] + " برنده شد"
                elif m["result"] == "black":
                    last_txt = "🥇 " + m["black_name"] + " برنده شد"
                else:
                    last_txt = "🤝 تساوی"
                break

        elo_lines = ["_هنوز مسابقه‌ای ثبت نشده_"]
        try:
            from elo import get_elo_leaderboard
            elo_top = await get_elo_leaderboard(3)
            if elo_top:
                medals = ["🥇", "🥈", "🥉"]
                elo_lines = [
                    f"{medals[i]} {p['full_name']} — `{int(p['rating'])}`"
                    for i, p in enumerate(elo_top)
                ]
        except Exception:
            pass

        lines = [
            box("📊 داشبورد — " + _aname),
            "💼 " + role_label,
            "⏱️ `" + now_shamsi() + "`",
            "🚦 " + status_map.get(status, status),
            "🏅 تورنمنت: *" + (default_t["name"] if default_t else "ندارد") + "*",
            "",
            separator("♟️ مسابقات"),
            "⏳ بی‌نتیجه: `" + str(len(pending_matches)) + "`",
            "🎮 نتایج امروز: `" + str(len(done_today)) + "`",
            "🏆 آخرین: " + last_txt,
            "",
            separator("📈 جدول Elo — برترین‌ها"),
            *elo_lines,
            "",
            separator("👤 بازیکنان"),
            "✅ فعال: `" + str(len(active_players)) + "` | ⚠️ با اخطار: `" + str(len(warned)) + "`",
            "",
            separator("📋 وظایف من"),
            "⏳ در انتظار: `" + str(len(pending_tasks)) + "` | ✅ انجام‌شده: `" + str(len(done_tasks)) + "`",
            separator(),
        ]
        return "\n".join(lines)
    except Exception as e:
        return "❌ خطا در بارگذاری داشبورد:\n`" + str(e) + "`"


async def dashboard_pishva(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 در حال بارگذاری...")
    text = await build_dashboard_pishva_text()
    from keyboards import kb_dashboard_pishva
    await safe_edit_message_text(query, text, reply_markup=kb_dashboard_pishva(), parse_mode="Markdown")


async def dashboard_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id

    # ─── چک امنیتی: وضعیت سیستم و تنظیم داشبورد ادمین ────────────────
    status = await db.get_setting("system_status", "normal")
    dashboard_enabled = await db.get_setting("admin_dashboard_enabled", "1")

    if status in ("danger", "aps"):
        await query.answer(
            "🔴 در وضعیت امنیتی فعلی دسترسی به داشبورد ادمین‌ها مسدود است.",
            show_alert=True
        )
        return

    if dashboard_enabled != "1":
        await query.answer(
            "📊 داشبورد ادمین‌ها توسط مدیر ارشد غیرفعال شده است.",
            show_alert=True
        )
        return

    await query.answer("🔄 در حال بارگذاری...")
    text = await build_dashboard_admin_text(uid)
    from keyboards import kb_dashboard_admin
    await safe_edit_message_text(query, text, reply_markup=kb_dashboard_admin(), parse_mode="Markdown")
