from datetime import datetime, timezone, timedelta

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import database as db
import keyboards as kb
from helpers import now_shamsi, box, separator, pishva_display, notify_pishva
from config import (PISHVA_ID, PISHVA_PASSWORD, ROLE_PISHVA,
                     ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER,
                     ST_ROLE_SELECT, ST_PISHVA_PASSWORD, ST_ADMIN_USERNAME,
                     ST_ADMIN_FULLNAME, ST_ACCESS_REQUEST_MSG)

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None


# ─── زمان و خوش‌آمدگویی هوشمند (ساعت واقعی ایران) ──────────────
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# ─── فاز واقعی ماه (بر پایه‌ی ماه سینودیکی، مستقل از API) ──────
_KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
_SYNODIC_MONTH = 29.530588861  # روز


def moon_phase_emoji(dt: datetime | None = None) -> str:
    """اموجی واقعیِ فاز ماه بر اساس تاریخ/ساعت واقعی (چرخه‌ی سینودیکی ماه).
    دقت این محاسبه در حد چند ساعت است و برای نمایش در پیام کاملاً کافی‌ست."""
    if dt is None:
        dt = datetime.now(IRAN_TZ)
    dt_utc = dt.astimezone(timezone.utc)
    days_since_new = (dt_utc - _KNOWN_NEW_MOON).total_seconds() / 86400
    phase = (days_since_new % _SYNODIC_MONTH) / _SYNODIC_MONTH  # 0..1

    if phase < 0.03 or phase >= 0.97:
        return "🌑"  # ماه نو
    elif phase < 0.22:
        return "🌒"  # هلال رو به رشد
    elif phase < 0.28:
        return "🌓"  # تربیع اول
    elif phase < 0.47:
        return "🌔"  # ماه محدب رو به رشد
    elif phase < 0.53:
        return "🌕"  # ماه کامل (بدر)
    elif phase < 0.72:
        return "🌖"  # ماه محدب رو به کاهش
    elif phase < 0.78:
        return "🌗"  # تربیع آخر
    else:
        return "🌘"  # هلال رو به کاهش


def time_greeting(name: str) -> str:
    now = datetime.now(IRAN_TZ)
    hour = now.hour
    if 4 <= hour < 7:
        g = "🌄 سحر بخیر"
    elif 7 <= hour < 11:
        g = "☀️ صبح بخیر"
    elif 11 <= hour < 14:
        g = "🌞 ظهر بخیر"
    elif 14 <= hour < 17:
        g = "🌤️ عصر بخیر"
    elif 17 <= hour < 19:
        g = "🌇 غروب خوبی داشته باشید"
    elif 19 <= hour < 23:
        g = f"{moon_phase_emoji(now)} شب بخیر"
    else:
        g = f"{moon_phase_emoji(now)} شب به‌خیر"
    return f"{g}، {name} عزیز"


# ─── آب‌وهوای واقعی سرپل‌ذهاب (بدون نیاز به کلید API) ──────────
SARPOL_LAT = 34.4597
SARPOL_LON = 45.8646

_WEATHER_CODE_FA = {
    0: "صاف و آفتابی", 1: "کمی ابری", 2: "نیمه‌ابری", 3: "ابری",
    45: "مه‌آلود", 48: "مه یخ‌زده",
    51: "نم‌نم باران", 53: "باران ملایم", 55: "باران",
    56: "باران یخ‌زده سبک", 57: "باران یخ‌زده",
    61: "باران سبک", 63: "باران متوسط", 65: "باران شدید",
    66: "باران یخ‌زده", 67: "باران یخ‌زده شدید",
    71: "برف سبک", 73: "برف متوسط", 75: "برف شدید", 77: "دانه‌های برف",
    80: "رگبار سبک", 81: "رگبار", 82: "رگبار شدید",
    85: "رگبار برف سبک", 86: "رگبار برف شدید",
    95: "رعد و برق", 96: "رعد و برق با تگرگ سبک", 99: "رعد و برق با تگرگ شدید",
}


def _temp_feel_fa(temp: float) -> str:
    if temp <= 5:
        return "خیلی سرد"
    if temp <= 14:
        return "سرد"
    if temp <= 21:
        return "خنک"
    if temp <= 29:
        return "معتدل و مطبوع"
    if temp <= 36:
        return "گرم"
    return "خیلی گرم"


async def get_weather_line() -> str:
    """آب‌وهوای واقعیِ سرپل‌ذهاب از Open-Meteo (رایگان، بدون کلید).
    اگر به هر دلیل در دسترس نبود، رشته‌ی خالی برمی‌گرداند و چیزی نمایش داده نمی‌شود."""
    if httpx is None:
        return ""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": SARPOL_LAT,
                    "longitude": SARPOL_LON,
                    "current_weather": "true",
                }
            )
            data = resp.json()
            cw = data.get("current_weather", {})
            temp = cw.get("temperature")
            code = cw.get("weathercode")
            if temp is None:
                return ""
            feel = _temp_feel_fa(temp)
            desc = _WEATHER_CODE_FA.get(code, "")
            line = f"🌤️ سرپل‌ذهاب امروز {feel} به نظر می‌رسه"
            if desc:
                line += f" ({desc})"
            line += f" — دما: {temp:.0f}°C"
            return line
    except Exception:
        return ""


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == PISHVA_ID:
        return await show_pishva_welcome(update, ctx)
    admin = await db.get_admin(uid)
    if admin and admin["is_active"]:
        await db.update_admin_activity(uid)
        return await show_admin_welcome(update, ctx, admin)

    # ⏳ اگر این شخص در صف انتظار امنیتی است، اجازه‌ی درخواست جدید نمی‌دهیم
    queued = await db.get_queued_request_by_uid(uid)
    if queued:
        await update.message.reply_text(
            "⏳ *در صف انتظار امنیتی*\n\n"
            "درخواست شما در حال بررسی توسط واحد امنیتی APS است.\n"
            "تا اطلاع ثانویه امکان ارسال درخواست جدید برای شما وجود ندارد. لطفاً صبور باشید.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    admin_login = await db.get_setting("admin_login_enabled", "1")
    if admin_login != "1":
        await update.message.reply_text("🔒 ورود ادمین‌ها غیرفعال است.")
        return ConversationHandler.END
    text = "⚔️ *سیستم فرماندهی شطرنج*\n\n🪪 نقش خود را انتخاب کنید:"
    await update.message.reply_text(text, reply_markup=kb.kb_role_select(), parse_mode="Markdown")
    return ST_ROLE_SELECT


async def show_pishva_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await db.log_action(PISHVA_ID, "login", "ورود پیشوا")
    pname = await pishva_display()
    greeting = time_greeting(pname)
    weather = await get_weather_line()

    # فقط خلاصه کوتاه — آمار تفصیلی در پنل پیشوا
    try:
        admins = await db.get_active_admins()
        pending = await db.get_pending_requests()
        pending_matches = await db.get_pending_matches()
        pending_tasks = [t for t in await db.get_all_tasks() if t["status"] == "pending"]
        status = await db.get_setting("system_status", "normal")
        status_map = {"normal": "🟢 نرمال", "bad": "🟡 احتیاطی", "danger": "🔴 خطرناک", "aps": "🪽 APS"}
        wh = await db.get_setting("working_hours_active", "0")
        wh_txt = "🟢 باز" if wh == "1" else "🔴 بسته"
        db_stat = await db.get_setting("db_manual_status", "1")
        db_txt = "🔗 دیتابیس: فعال" if db_stat == "1" else "⚠️ دیتابیس: غیرفعال"

        text = greeting + "\n"
        if weather:
            text += weather + "\n"
        text += (
            "\n"
            "📡 " + status_map.get(status, status) + " | 🕐 " + wh_txt + "\n" + db_txt + "\n"
            "👥 ادمین: `" + str(len(admins)) + "` | "
            "📥 درخواست: `" + str(len(pending)) + "` | "
            "⏳ بی‌نتیجه: `" + str(len(pending_matches)) + "` | "
            "📋 وظایف: `" + str(len(pending_tasks)) + "`"
        )
    except Exception:
        text = greeting
        if weather:
            text += "\n" + weather

    if update.message:
        await update.message.reply_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    return ConversationHandler.END


async def show_admin_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE, admin):
    role_label = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    _aname = admin["display_name"] or admin["full_name"]
    greeting = time_greeting(_aname)
    weather = await get_weather_line()

    # خلاصه کوتاه — آمار تفصیلی در پنل مدیریت
    try:
        pending_matches = await db.get_pending_matches()
        pending_tasks = [t for t in await db.get_tasks_for(admin["telegram_id"]) if t["status"] == "pending"]
        warned = [p for p in await db.get_all_players() if p["warnings"] > 0]
        status = await db.get_setting("system_status", "normal")
        status_map = {"normal": "🟢 نرمال", "bad": "🟡 احتیاطی", "danger": "🔴 خطرناک", "aps": "🪽 APS"}

        text = role_label + "\n" + greeting + "\n"
        if weather:
            text += weather + "\n"
        text += (
            "🚦 " + status_map.get(status, status) + "\n\n"
            "⏳ بی‌نتیجه: `" + str(len(pending_matches)) + "` | "
            "⚠️ با اخطار: `" + str(len(warned)) + "` | "
            "📋 وظایف: `" + str(len(pending_tasks)) + "`"
        )
    except Exception:
        text = role_label + "\n" + greeting
        if weather:
            text += "\n" + weather

    markup = kb.kb_tournament_manager_main() if admin["role"] == ROLE_TOURNAMENT_MANAGER else kb.kb_security_manager_main()
    if update.message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    return ConversationHandler.END


async def on_role_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "role_pishva":
        uid = query.from_user.id
        if uid == PISHVA_ID:
            return await show_pishva_welcome(update, ctx)
        await query.edit_message_text("🔐 رمز پیشوا را وارد کنید:")
        ctx.user_data["pending_role"] = ROLE_PISHVA
        return ST_PISHVA_PASSWORD
    role = ROLE_TOURNAMENT_MANAGER if data == "role_tournament" else ROLE_SECURITY_MANAGER
    ctx.user_data["pending_role"] = role
    await query.edit_message_text(
        "👤 یوزرنیم تلگرام خود را وارد کنید:\n_(باید با @ شروع شود و شامل حروف باشد)_",
        parse_mode="Markdown"
    )
    return ST_ADMIN_USERNAME


async def on_pishva_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ این حساب مجاز نیست.")
    return ConversationHandler.END


async def on_admin_username(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    if not username.startswith("@") or not any(c.isalpha() for c in username[1:]):
        await update.message.reply_text("❌ یوزرنیم باید با @ شروع شود و حاوی حروف باشد.\nدوباره وارد کنید:")
        return ST_ADMIN_USERNAME
    ctx.user_data["reg_username"] = username
    await update.message.reply_text("✍️ نام و نام‌خانوادگی خود را وارد کنید:")
    return ST_ADMIN_FULLNAME


async def on_admin_fullname(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["reg_fullname"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 یک پیام برای پیشوا بنویسید (یا /skip):",
        parse_mode="Markdown"
    )
    return ST_ACCESS_REQUEST_MSG


async def on_access_request_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = ""
    if update.message.text and update.message.text != "/skip":
        msg = update.message.text.strip()
    uid = update.effective_user.id
    username = ctx.user_data.get("reg_username", "")
    full_name = ctx.user_data.get("reg_fullname", "")
    role = ctx.user_data.get("pending_role", ROLE_TOURNAMENT_MANAGER)
    req_id = await db.create_access_request(uid, username, full_name, role, msg)
    role_label = "🏆 مدیر مسابقات" if role == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    ts = now_shamsi()
    notif = (
        "📥 *درخواست دسترسی جدید*\n\n"
        "👤 " + full_name + " | " + username + "\n"
        "💼 " + role_label + "\n"
        "📝 " + (msg or "—") + "\n"
        "⏱️ `" + ts + "`"
    )
    await notify_pishva(ctx.bot, notif, reply_markup=kb.kb_access_request(req_id))
    await update.message.reply_text("✅ درخواست ارسال شد. منتظر تأیید مدیر ارشد باشید.")
    return ConversationHandler.END


async def on_approve_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    req_id = int(query.data.split("_")[-1])
    req = await db.get_access_request(req_id)
    if not req or req["status"] != "pending":
        await query.answer("قبلاً پردازش شده.", show_alert=True)
        return
    await db.update_access_request(req_id, "approved")
    await db.create_admin(req["telegram_id"], req["username"], req["full_name"], req["role"])
    role_label = "🏆 مدیر مسابقات" if req["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    try:
        await ctx.bot.send_message(
            chat_id=req["telegram_id"],
            text="✅ *دسترسی تأیید شد*\n💼 " + role_label + "\n\n/start بزنید.",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await query.edit_message_text(query.message.text + "\n\n✅ *تأیید شد*", parse_mode="Markdown")
    await query.answer("✅ تأیید شد.")


async def on_reject_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != PISHVA_ID:
        await query.answer("⛔ فقط مدیر ارشد.", show_alert=True)
        return
    req_id = int(query.data.split("_")[-1])
    req = await db.get_access_request(req_id)
    if not req or req["status"] != "pending":
        await query.answer("قبلاً پردازش شده.", show_alert=True)
        return
    await db.update_access_request(req_id, "rejected")
    try:
        await ctx.bot.send_message(
            chat_id=req["telegram_id"],
            text="❌ درخواست دسترسی شما رد شد.\nبرای اطلاعات بیشتر با مدیر ارشد تماس بگیرید."
        )
    except Exception:
        pass
    await query.edit_message_text(query.message.text + "\n\n❌ *رد شد*", parse_mode="Markdown")
    await query.answer("❌ رد شد.")
