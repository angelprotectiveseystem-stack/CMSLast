"""
dashboard.py — داشبورد تفصیلی برای پیشوا و ادمین‌ها
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from helpers import box, separator, now_shamsi, progress_bar, power_bar, warning_bar_admin
from config import PISHVA_ID, ROLE_TOURNAMENT_MANAGER


async def dashboard_pishva(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 در حال بارگذاری...")

    try:
        admins = await db.get_active_admins()
        all_players = await db.get_all_players()
        active_players = await db.get_continuing_players()
        all_matches = await db.get_matches_by_filter("all")
        today_matches = await db.get_matches_by_filter("today")
        pending_matches = await db.get_pending_matches()
        done_matches = [m for m in all_matches if m["result"]]
        pending_tasks = [t for t in await db.get_all_tasks() if t["status"] == "pending"]
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

        # برترین بازیکن
        sorted_p = sorted(all_players, key=lambda p: p["wins"], reverse=True)
        top_player = sorted_p[0]["full_name"] if sorted_p and sorted_p[0]["wins"] > 0 else "—"
        top_wins = sorted_p[0]["wins"] if sorted_p else 0

        # آخرین نتیجه
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

        lines = [
            box("📊 داشبورد پیشوا"),
            "⏱️ `" + now_shamsi() + "`",
            "",
            separator("🚦 سیستم"),
            "📡 وضعیت: " + status_map.get(status, status),
            "🕐 ساعت کاری: " + wh_txt,
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
            "🌟 برترین: *" + top_player + "* (" + str(top_wins) + " برد)",
            separator(),
        ]
        text = "\n".join(lines)

    except Exception as e:
        text = "❌ خطا در بارگذاری داشبورد:\n`" + str(e) + "`"

    from keyboards import kb_dashboard_pishva
    await query.edit_message_text(text, reply_markup=kb_dashboard_pishva(), parse_mode="Markdown")


async def dashboard_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 در حال بارگذاری...")
    uid = query.from_user.id

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

        # آخرین نتیجه
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
            separator("👤 بازیکنان"),
            "✅ فعال: `" + str(len(active_players)) + "` | ⚠️ با اخطار: `" + str(len(warned)) + "`",
            "",
            separator("📋 وظایف من"),
            "⏳ در انتظار: `" + str(len(pending_tasks)) + "` | ✅ انجام‌شده: `" + str(len(done_tasks)) + "`",
            separator(),
        ]
        text = "\n".join(lines)

    except Exception as e:
        text = "❌ خطا در بارگذاری داشبورد:\n`" + str(e) + "`"

    from keyboards import kb_dashboard_admin
    await query.edit_message_text(text, reply_markup=kb_dashboard_admin(), parse_mode="Markdown")
