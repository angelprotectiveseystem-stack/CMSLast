import jdatetime
import pytz
from datetime import datetime
from telegram.error import BadRequest
from config import BAR_LENGTH, PISHVA_ID
import database as db
import logging
import json

logger = logging.getLogger(__name__)
TEHRAN_TZ = pytz.timezone("Asia/Tehran")

# ─── Date/Time ───────────────────────────────────────────────
def now_shamsi() -> str:
    now = datetime.now(TEHRAN_TZ)
    jd = jdatetime.datetime.fromgregorian(datetime=now)
    return jd.strftime("%Y/%m/%d — %H:%M:%S")

def today_shamsi() -> str:
    now = datetime.now(TEHRAN_TZ)
    jd = jdatetime.datetime.fromgregorian(datetime=now)
    return jd.strftime("%Y/%m/%d")

def today_gregorian() -> str:
    return datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")

# ─── Progress Bars ───────────────────────────────────────────
def progress_bar(percent: float, length: int = BAR_LENGTH) -> str:
    percent = max(0, min(100, percent))
    filled = int(length * percent / 100)
    half = length - filled
    bar = "█" * filled + ("▒" if half > 0 else "") + "░" * max(0, half - 1)
    return f"[{bar}] {int(percent)}٪"

def warning_bar_player(warnings: int, max_w: int = 3) -> str:
    icons = ["🟢", "🟠", "🔴"]
    result = []
    for i in range(max_w):
        result.append(icons[i] if i < warnings else "░")
    return "[ " + " ".join(result) + " ]"

def warning_bar_admin(warnings: int, max_w: int = 5) -> str:
    filled = "💀" * min(warnings, max_w)
    empty = "░" * max(0, max_w - warnings)
    return f"⚠️ [{filled}{empty}]"

def power_bar(wins: int, losses: int, draws: int) -> str:
    total = wins + losses + draws
    if total == 0:
        return progress_bar(0)
    score = (wins + draws * 0.5) / total * 100
    return progress_bar(score)

def rank_bar(wins: int, total: int) -> str:
    if total == 0:
        return progress_bar(0)
    return progress_bar(wins / total * 100)

# ─── Box Headers ─────────────────────────────────────────────
def box(title: str) -> str:
    border = "═" * (len(title) + 4)
    return f"╔{border}╗\n║  {title}  ║\n╚{border}╝"

def separator(label: str = "") -> str:
    if label:
        return f"╼╼╼╼╼╼ {label} ╾╾╾╾╾╾"
    return "╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼"

def escape_md_legacy(text: str) -> str:
    """فرار دادن کاراکترهای خاص Markdown قدیمی تلگرام (_ * ` [) توی متن‌های دینامیک
    (نام‌ها، دلایل، توضیح لاگ‌ها) که کاربر/ادمین وارد کرده، تا با تعداد فرد
    این کاراکترها (مثلاً یه زیرخط توی 'ai_access') تلگرام خطای
    'can't find end of the entity' ندهد."""
    if not text:
        return text
    for ch in ("\\", "_", "*", "`", "["):
        text = text.replace(ch, "\\" + ch)
    return text


def log_line(time_str: str, name: str, action: str) -> str:
    return f"⏱️ `{time_str}` | 👤 {escape_md_legacy(name)} ╼ {escape_md_legacy(action)} 📌"

# ─── Safe Telegram senders ────────────────────────────────────
# نکته: توی این پروژه در ده‌ها جای مختلف parse_mode="Markdown" با متن‌های
# دینامیک (نام کاربر، توضیح گزارش، متن فیدبک و ...) استفاده شده بدون اینکه
# escape بشن. کافیه همچین متنی یه زیرخط/ستاره/بک‌تیک فرد داشته باشه تا
# تلگرام با خطای "Can't parse entities: can't find end of the entity" کل
# ارسال پیام رو رد کنه — و چون خیلی از این نقطه‌ها try/except نداشتن،
# این خطا مستقیم می‌رفت بالا و توسط global_error_handler قاپیده می‌شد
# (دقیقاً همون خطایی که موقع دیدن گزارش‌ها/لاگ‌ها می‌گرفتی).
# به‌جای escape کردن دستی همه‌ی اون نقطه‌ها (ریسک بالا، جای خطای زیاد)،
# این توابع کمکی رو ساختیم: اول با Markdown امتحان می‌کنن، اگه تلگرام به
# خاطر پارس نشدن Markdown رد کرد، خودکار بدون parse_mode دوباره می‌فرستن —
# یعنی دیگه هیچ پیامی به خاطر یه کاراکتر خاص گم/بی‌جواب نمی‌مونه.
def _is_entity_parse_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "can't parse entities" in msg or "can't find end of the entity" in msg

async def safe_send_message(bot, chat_id, text: str, reply_markup=None, parse_mode="Markdown"):
    """جایگزین امن bot.send_message: اگه پارس Markdown خطا بده، متن خام می‌فرسته."""
    try:
        return await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if parse_mode and _is_entity_parse_error(e):
            logger.warning(f"Markdown parse failed for chat {chat_id}, resending as plain text: {e}")
            return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        raise

async def safe_reply_text(message, text: str, reply_markup=None, parse_mode="Markdown"):
    """جایگزین امن message.reply_text."""
    try:
        return await message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if parse_mode and _is_entity_parse_error(e):
            logger.warning(f"Markdown parse failed on reply, resending as plain text: {e}")
            return await message.reply_text(text, reply_markup=reply_markup)
        raise

async def safe_edit_message_text(query, text: str, reply_markup=None, parse_mode="Markdown"):
    """جایگزین امن query.edit_message_text."""
    try:
        return await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if parse_mode and _is_entity_parse_error(e):
            logger.warning(f"Markdown parse failed on edit, resending as plain text: {e}")
            return await query.edit_message_text(text, reply_markup=reply_markup)
        raise

# ─── Notification sender ─────────────────────────────────────
async def send_notification(bot, user_id: int, text: str, reply_markup=None):
    notif_on = await db.get_setting("notifications_enabled", "1")
    if notif_on != "1":
        return
    try:
        await safe_send_message(bot, user_id, text, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Failed to notify {user_id}: {e}")

async def broadcast_to_admins(bot, text: str, exclude_id: int = None, reply_markup=None):
    notif_on = await db.get_setting("notifications_enabled", "1")
    if notif_on != "1":
        return
    admins = await db.get_active_admins()
    group_id = await db.get_setting("announcement_group_id", "")

    for admin in admins:
        tid = admin["telegram_id"]
        if tid == exclude_id:
            continue
        try:
            perms = json.loads(admin["permissions"])
            if not perms.get("notifications", True):
                continue
        except Exception:
            pass
        try:
            await safe_send_message(bot, tid, text, reply_markup=reply_markup)
        except Exception as e:
            logger.warning(f"Broadcast failed for {tid}: {e}")

    if group_id:
        try:
            await safe_send_message(bot, int(group_id), text)
        except Exception as e:
            logger.warning(f"Group broadcast failed: {e}")

async def notify_pishva(bot, text: str, reply_markup=None):
    await send_notification(bot, PISHVA_ID, text, reply_markup)

# ─── System Status Gate ──────────────────────────────────────
async def check_status_gate(query, action_name: str = "") -> bool:
    status = await db.get_setting("system_status", "normal")
    user_id = query.from_user.id
    bot_active = await db.get_setting("bot_active_for_admins", "1")
    update_mode = await db.get_setting("bot_update_mode", "0")
    working_hours = await db.get_setting("working_hours_active", "0")

    if user_id == PISHVA_ID:
        if status == "aps":
            return False
        return False

    # Update mode blocks everyone except pishva
    if update_mode == "1":
        await query.answer("🔄 ربات در حال آپدیت است. لطفاً منتظر بمانید.", show_alert=True)
        return True

    # Bot inactive for admins
    if bot_active != "1":
        await query.answer("💤 ربات توسط پیشوا خاموش شده است.", show_alert=True)
        return True

    # Working hours check — if working hours system is on and not active, block
    if working_hours == "0":
        wh_system = await db.get_setting("working_hours_system_enabled", "0")
        if wh_system == "1":
            await query.answer("🕐 ساعت کاری پایان یافته است. منتظر دستور پیشوا باشید.", show_alert=True)
            return True

    if status == "aps":
        await query.answer(
            "🪽 وضعیت APS در حال اجرا است؛ دسترسی به این بخش محدود شده.\n"
            "لطفاً تا برقراری امنیت شکیبا باشید یا با پیشوا در ارتباط باشید.",
            show_alert=True
        )
        return True

    if status == "danger":
        await query.answer(
            "🔴 سیستم در وضعیت خطرناک قرار دارد؛ تمام عملیات ادمین‌ها متوقف شده است.",
            show_alert=True
        )
        return True

    if status == "bad":
        blocked = ["match_delete", "match_edit", "warning", "ban_player", "msg_admin", "view_players"]
        for b in blocked:
            if b in action_name:
                await query.answer(
                    f"🟡 سیستم در وضعیت احتیاطی است؛ این عملیات موقتاً غیرفعال شده.",
                    show_alert=True
                )
                return True

    return False

# ─── Role / Permission Checkers ──────────────────────────────
async def get_user_role(user_id: int) -> str:
    if user_id == PISHVA_ID:
        return "pishva"
    admin = await db.get_admin(user_id)
    if admin and admin["is_active"]:
        return admin["role"]
    return ""

async def pishva_display() -> str:
    return await db.get_setting("pishva_display_name", "پیشوا")

async def admin_display(admin) -> str:
    if admin and admin["display_name"]:
        return admin["display_name"]
    return admin["full_name"] if admin else "نامشخص"

# ─── Date validator ──────────────────────────────────────────
def validate_date(date_str: str) -> bool:
    try:
        parts = date_str.replace("/", "-").split("-")
        return len(parts) == 3
    except Exception:
        return False

# ─── Smart Lottery ───────────────────────────────────────────
import random

async def smart_lottery(players: list) -> tuple:
    if len(players) < 2:
        return None, None, False
    player_ids = [p["id"] for p in players]
    random.shuffle(player_ids)
    for i in range(len(player_ids)):
        for j in range(i + 1, len(player_ids)):
            if not await db.have_played_before(player_ids[i], player_ids[j]):
                p1 = next(p for p in players if p["id"] == player_ids[i])
                p2 = next(p for p in players if p["id"] == player_ids[j])
                return p1, p2, False
    random.shuffle(player_ids)
    p1 = next(p for p in players if p["id"] == player_ids[0])
    p2 = next(p for p in players if p["id"] == player_ids[1])
    return p1, p2, True

# ─── Player rank label ───────────────────────────────────────
def get_rank_label(wins: int, total: int) -> str:
    if total == 0:
        return "🔰 تازه‌کار"
    pct = wins / total * 100
    if pct >= 80:
        return "👑 افسانه‌ای"
    elif pct >= 65:
        return "💎 الماس"
    elif pct >= 50:
        return "🥇 طلا"
    elif pct >= 35:
        return "🥈 نقره"
    elif pct >= 20:
        return "🥉 برنز"
    else:
        return "🔰 مبتدی"


# ─── Permission Gate ─────────────────────────────────────────
async def check_perm(query, perm: str, default: bool = True) -> bool:
    """
    اگر کاربر پیشوا باشه: همیشه False (یعنی pass).
    اگر ادمین فعال باشه: permission رو از دیتابیس چک میکنه.
    اگر اصلاً ادمین نباشه: بلاک می‌کنه (True برمیگردونه).
    مقدار True برمیگردونه یعنی «بلاک شو».

    FIX: قبلاً اگه user اصلاً ادمین نبود، default=True بود و pass می‌شد.
         حالا non-admin همیشه بلاک می‌شه.
    """
    uid = query.from_user.id
    if uid == PISHVA_ID:
        return False

    admin = await db.get_admin(uid)

    # ── کاربر اصلاً ادمین نیست یا غیرفعاله ──────────────────
    if not admin or not admin["is_active"]:
        await query.answer(
            "⛔ شما مجوز دسترسی به این بخش را ندارید.\n"
            "این عملیات فقط برای مدیران ثبت‌شده مجاز است.",
            show_alert=True
        )
        return True

    # ── ادمین فعال: بررسی permission خاص ────────────────────
    import json
    try:
        perms = json.loads(admin["permissions"])
        allowed = perms.get(perm, default)
    except Exception:
        allowed = default

    if not allowed:
        await query.answer("⛔ شما اجازه انجام این عملیات را ندارید.", show_alert=True)
        return True

    return False
