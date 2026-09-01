import random
from datetime import datetime, timezone, timedelta

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import database as db
import keyboards as kb
from helpers import safe_edit_message_text, now_shamsi, box, separator, pishva_display, notify_pishva
from config import (PISHVA_ID, PISHVA_PASSWORD, ROLE_PISHVA,
                     ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER,
                     ST_ROLE_SELECT, ST_PISHVA_PASSWORD, ST_ADMIN_USERNAME,
                     ST_ADMIN_FULLNAME, ST_ACCESS_REQUEST_MSG)

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None


# ─── زمان و خوش‌آمدگویی هوشمند و خودمونی (ساعت واقعی ایران) ────
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


# ─── فاز واقعی ماه بر اساس چرخه‌ی سینودیکی (۲۹.530588861 روزه) ─
_MOON_REF_NEW = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)  # ماه نوی مرجع
_SYNODIC_MONTH = 29.530588861  # طول متوسط یک چرخه‌ی کامل ماه (روز)


def moon_phase_emoji() -> str:
    """اموجی فاز فعلی ماه، محاسبه‌شده از زمان (نه موقعیت جغرافیایی).

    phase = (روزهای گذشته از ماه نوی مرجع mod طول چرخه) / طول چرخه
    عددی بین ۰ تا ۱ که ۰/۱ = ماه نو، ۰.۲۵ = تربیع اول،
    ۰.۵ = بدر کامل، ۰.۷۵ = تربیع آخر.
    """
    now = datetime.now(timezone.utc)
    days_since_new = (now - _MOON_REF_NEW).total_seconds() / 86400.0
    phase = (days_since_new % _SYNODIC_MONTH) / _SYNODIC_MONTH

    if phase < 0.0625 or phase >= 0.9375:
        return "🌑"  # ماه نو
    elif phase < 0.1875:
        return "🌒"  # هلال رو به رشد
    elif phase < 0.3125:
        return "🌓"  # تربیع اول
    elif phase < 0.4375:
        return "🌔"  # محدب رو به رشد
    elif phase < 0.5625:
        return "🌕"  # بدر کامل
    elif phase < 0.6875:
        return "🌖"  # محدب رو به کاهش
    elif phase < 0.8125:
        return "🌗"  # تربیع آخر
    else:
        return "🌘"  # هلال رو به کاهش


_GREETINGS = {
    "late_night": [  # 23:00 - 4:00
        "{moon} شب به‌خیر، *{name} عزیز*! الان که خیلی دیروقته، تا صبح بیداری؟",
        "{moon} *{name} عزیز*، این‌موقع شب هنوز بیداری؟ استراحتم خوبه ها 😄",
    ],
    "dawn": [  # 4:00 - 7:00
        "🌄 سحر بخیر، *{name} عزیز*! امروز عجب سحرخیز شدی‌ها",
        "🌄 *{name} عزیز*، هنوز آفتاب نزده و تو بیداری، دمت گرم!",
    ],
    "morning": [  # 7:00 - 11:00
        "☀️ صبح بخیر، *{name} عزیز*! روزت پرانرژی باشه",
        "☀️ *{name} عزیز* صبح بخیر، وقت شروع یه روز خوبه",
    ],
    "noon": [  # 11:00 - 14:00
        "🌞 ظهر بخیر، *{name} عزیز*! ناهار یادت نره",
        "🌞 *{name} عزیز* ظهر بخیر، وسط روزی و بازم سرحالی",
    ],
    "afternoon": [  # 14:00 - 17:00
        "🌤️ عصر بخیر، *{name} عزیز*",
        "🌤️ *{name} عزیز*، عصر شیرینی داشته باشی",
    ],
    "evening": [  # 17:00 - 19:00
        "🌇 غروب بخیر، *{name} عزیز*",
        "🌇 *{name} عزیز*، وقت یه چای عصرونه‌ست",
    ],
    "night": [  # 19:00 - 23:00
        "{moon} شب بخیر، *{name} عزیز*",
        "{moon} *{name} عزیز*، شب خوبی داشته باشی",
    ],
}


def time_greeting(name: str) -> str:
    """خوش‌آمدگویی خودمونی و متنوع بر اساس ساعت روز — اسم همیشه بولد."""
    hour = datetime.now(IRAN_TZ).hour
    if hour >= 23 or hour < 4:
        bucket = "late_night"
    elif hour < 7:
        bucket = "dawn"
    elif hour < 11:
        bucket = "morning"
    elif hour < 14:
        bucket = "noon"
    elif hour < 17:
        bucket = "afternoon"
    elif hour < 19:
        bucket = "evening"
    else:
        bucket = "night"

    template = random.choice(_GREETINGS[bucket])
    if bucket in ("late_night", "night"):
        return template.format(name=name, moon=moon_phase_emoji())
    return template.format(name=name)


# ─── آب‌وهوای واقعی سرپل‌ذهاب (بدون نیاز به کلید API) ──────────
SARPOL_LAT = 34.4597
SARPOL_LON = 45.8646

# هر کد آب‌وهوا چند برداشتِ کوتاه و متفاوت داره تا هربار یه‌شکل نباشه
_WEATHER_MOOD = {
    0: ["صاف و آفتابی", "بی‌ابر و روشن"],
    1: ["تقریباً صاف", "کمی ابری"],
    2: ["نیمه‌ابری", "ترکیبی از آفتاب و ابر"],
    3: ["ابری و دلگیر", "یکدست ابری"],
    45: ["مه‌آلود", "با دید کم به‌خاطر مه"],
    48: ["مه یخ‌زده و سرد"],
    51: ["نم‌نم بارونی"],
    53: ["بارونیِ ملایم"],
    55: ["بارونیِ نسبتاً شدید"],
    56: ["بارونِ یخ‌زده‌ی سبک، لغزنده"],
    57: ["بارونِ یخ‌زده، پرخطر"],
    61: ["بارونیِ سبک"],
    63: ["بارونیِ متوسط"],
    65: ["بارونیِ شدید"],
    66: ["بارونِ یخ‌زده، جاده‌ها لغزنده"],
    67: ["بارونِ یخ‌زده‌ی شدید"],
    71: ["برفیِ سبک"],
    73: ["برفیِ متوسط"],
    75: ["برفیِ سنگین"],
    77: ["با دانه‌های ریز برف"],
    80: ["با رگبار ناگهانی"],
    81: ["با رگبارهای پیاپی"],
    82: ["با رگبار شدید"],
    85: ["با رگبار برف سبک"],
    86: ["با رگبار برف شدید"],
    95: ["طوفانی و رعدوبرقی"],
    96: ["طوفانی همراه با تگرگ سبک"],
    99: ["طوفانی و پرتگرگ"],
}

_STORM_CODES = {95, 96, 99}
_SNOW_CODES = {71, 73, 75, 77, 85, 86}
_ICE_CODES = {56, 57, 66, 67}
_PRECIP_CODES = {51, 53, 55, 61, 63, 65, 80, 81, 82} | _ICE_CODES | _STORM_CODES
_FOG_CODES = {45, 48}


def _weather_emoji(code: int, is_day: int) -> str:
    if code in (0, 1):
        return "☀️" if is_day else "🌕"
    if code == 2:
        return "⛅" if is_day else "☁️"
    if code == 3:
        return "☁️"
    if code in _FOG_CODES:
        return "🌫️"
    if code in _STORM_CODES:
        return "⛈️"
    if code in _SNOW_CODES:
        return "❄️"
    if code in _ICE_CODES:
        return "🌧️❄️"
    if code in _PRECIP_CODES:
        return "🌧️"
    return "🌡️"


async def get_weather_line() -> str:
    """یک جمله‌ی کوتاه و خودمونی درباره‌ی آب‌وهوای سرپل‌ذهاب.
    نوعِ توصیف صرفاً بر اساس دما نیست؛ کدِ واقعیِ آب‌وهوا تعیین‌کننده‌ست.
    اگر در دسترس نبود، رشته‌ی خالی برمی‌گرداند."""
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
            wind = cw.get("windspeed")
            is_day = cw.get("is_day", 1)
            if temp is None:
                return ""

            emoji = _weather_emoji(code, is_day)
            mood = random.choice(_WEATHER_MOOD.get(code, ["نامشخص"]))
            time_word = "امروز" if is_day else "امشب"

            line = f"{emoji} سرپل‌ذهاب {time_word} {mood} به‌نظر می‌رسه! (`{temp:.0f}°C`)"
            if wind is not None and wind >= 35:
                line += f" 💨 بادش هم شدیده"
            return line
    except Exception:
        return ""


def _status_line(status: str) -> str:
    status_map = {
        "normal": "🟢 نرمال",
        "bad": "🟡 احتیاطی",
        "danger": "🔴 خطرناک",
        "aps": "🪽 حالت APS",
    }
    return status_map.get(status, status)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    is_pishva = (uid == PISHVA_ID)
    admin = None if is_pishva else await db.get_admin(uid)
    is_admin = bool(admin and admin["is_active"])

    # ─── دیپ‌لینک پنل (وقتی از دکمه‌ی «🔒 پیوی» در گروه اومده) ───
    # لینک به‌صورت https://t.me/<bot>?start=panel_<action> ساخته می‌شه؛
    # تلگرام این پارامتر رو به‌عنوان context.args[0] می‌فرسته.
    args = ctx.args if ctx.args else []
    payload = args[0] if args else None

    if payload and payload.startswith("panel_") and (is_pishva or is_admin):
        action = payload[len("panel_"):]
        if is_admin:
            await db.update_admin_activity(uid)

        if action == "restart":
            if is_pishva:
                return await show_pishva_welcome(update, ctx)
            return await show_admin_welcome(update, ctx, admin)

        from keyword_commands import _panel_content, PISHVA_ONLY_ACTIONS
        if action in PISHVA_ONLY_ACTIONS and not is_pishva:
            await update.message.reply_text("⛔ این دستور فقط برای مدیر ارشد است.")
            return ConversationHandler.END

        text, markup, err = await _panel_content(action, uid, is_pishva, admin)
        if text is None:
            await update.message.reply_text(err or "❗ این پنل در دسترس نیست.")
        else:
            await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
        return ConversationHandler.END

    if is_pishva:
        return await show_pishva_welcome(update, ctx)
    if is_admin:
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
    await db.log_action(PISHVA_ID, "login", "ورود مدیر ارشد")
    pname = await pishva_display()
    greeting = time_greeting(pname)
    weather = await get_weather_line()

    try:
        admins = await db.get_active_admins()
        pending = await db.get_pending_requests()
        pending_matches = await db.get_pending_matches()
        pending_tasks = [t for t in await db.get_all_tasks() if t["status"] == "pending"]
        status = await db.get_setting("system_status", "normal")
        wh = await db.get_setting("working_hours_active", "0")
        wh_txt = "🟢 باز" if wh == "1" else "🔴 بسته"
        db_stat = await db.get_setting("db_manual_status", "1")
        db_txt = "🔗 فعال" if db_stat == "1" else "⚠️ غیرفعال"
        ai_on = await db.get_setting("ai_online", "1")
        ai_txt = "🟢 آنلاین" if ai_on == "1" else "🔴 آفلاین"

        text = (
            f"👑 *پنل مدیر ارشد*\n"
            f"{greeting}\n"
            f"🕰 `{now_shamsi()}`\n"
        )
        if weather:
            text += f"\n{weather}\n"
        text += (
            f"\n📡 {_status_line(status)} | 🕐 کاری: {wh_txt} | 🗄️ دیتابیس: {db_txt} | 🤖 AI: {ai_txt}\n"
            f"👥 ادمین: `{len(admins)}` | 📥 درخواست: `{len(pending)}` | "
            f"⏳ بی‌نتیجه: `{len(pending_matches)}` | 📋 وظایف: `{len(pending_tasks)}`"
        )
    except Exception:
        text = greeting
        if weather:
            text += "\n" + weather

    if update.message:
        await update.message.reply_text(text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    else:
        await safe_edit_message_text(update.callback_query, text, reply_markup=kb.kb_pishva_main(), parse_mode="Markdown")
    return ConversationHandler.END


async def show_admin_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE, admin):
    role_label = "🏆 مدیر مسابقات" if admin["role"] == ROLE_TOURNAMENT_MANAGER else "🛡️ مدیر امنیتی"
    _aname = admin["display_name"] or admin["full_name"]
    greeting = time_greeting(_aname)
    weather = await get_weather_line()

    try:
        pending_matches = await db.get_pending_matches()
        pending_tasks = [t for t in await db.get_tasks_for(admin["telegram_id"]) if t["status"] == "pending"]
        warned = [p for p in await db.get_all_players() if p["warnings"] > 0]
        status = await db.get_setting("system_status", "normal")
        wh = await db.get_setting("working_hours_active", "0")
        wh_txt = "🟢 باز" if wh == "1" else "🔴 بسته"
        ai_on = await db.get_setting("ai_online", "1")
        ai_txt = "🟢 آنلاین" if ai_on == "1" else "🔴 آفلاین (فعلا در دسترس نیست)"

        text = (
            f"{role_label}\n"
            f"{greeting}\n"
            f"🕰 `{now_shamsi()}`\n"
        )
        if weather:
            text += f"\n{weather}\n"
        text += (
            f"\n📡 {_status_line(status)} | 🕐 کاری: {wh_txt} | 🤖 AI: {ai_txt}\n"
            f"⏳ بی‌نتیجه: `{len(pending_matches)}` | ⚠️ اخطار: `{len(warned)}` | "
            f"📋 وظایف: `{len(pending_tasks)}`"
        )
    except Exception:
        text = role_label + "\n" + greeting
        if weather:
            text += "\n" + weather

    markup = kb.kb_tournament_manager_main() if admin["role"] == ROLE_TOURNAMENT_MANAGER else kb.kb_security_manager_main()
    if update.message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await safe_edit_message_text(update.callback_query, text, reply_markup=markup, parse_mode="Markdown")
    return ConversationHandler.END


async def on_role_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "role_pishva":
        uid = query.from_user.id
        if uid == PISHVA_ID:
            return await show_pishva_welcome(update, ctx)
        await safe_edit_message_text(query, "🔐 رمز مدیر ارشد را وارد کنید:")
        ctx.user_data["pending_role"] = ROLE_PISHVA
        return ST_PISHVA_PASSWORD
    role = ROLE_TOURNAMENT_MANAGER if data == "role_tournament" else ROLE_SECURITY_MANAGER
    ctx.user_data["pending_role"] = role
    await safe_edit_message_text(query, 
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
        "📝 یک پیام برای مدیر ارشد بنویسید (یا /skip):",
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
    await safe_edit_message_text(query, query.message.text + "\n\n✅ *تأیید شد*", parse_mode="Markdown")
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
    await safe_edit_message_text(query, query.message.text + "\n\n❌ *رد شد*", parse_mode="Markdown")
    await query.answer("❌ رد شد.")
