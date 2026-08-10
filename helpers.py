import jdatetime
import pytz
from datetime import datetime
from config import BAR_LENGTH, PISHVA_ID
import database as db
import logging

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
    filled = int(length * percent / 100)
    half = length - filled
    bar = "█" * filled + "▒" * min(1, half) + "░" * max(0, half - 1)
    return f"[{bar}] {int(percent)}٪"

def warning_bar_player(warnings: int, max_w: int = 3) -> str:
    icons = ["🟢", "🟠", "🔴"]
    result = []
    for i in range(max_w):
        result.append(icons[i] if i < warnings else "░")
    return "[ " + " ".join(result) + " ]"

def warning_bar_admin(warnings: int, max_w: int = 5) -> str:
    filled = "💀" * warnings
    empty = "░" * (max_w - warnings)
    return f"⚠️ [{filled}{empty}]"

def power_bar(wins: int, losses: int, draws: int) -> str:
    total = wins + losses + draws
    if total == 0:
        return progress_bar(0)
    score = (wins + draws * 0.5) / total * 100
    return progress_bar(score)

# ─── Box Headers ─────────────────────────────────────────────
def box(title: str) -> str:
    line = "═" * (len(title) + 4)
    return f"╔{line}╗\n║  {title}  ║\n╚{line}╝"

def separator(label: str = "") -> str:
    if label:
        return f"╼╼╼╼╼╼ {label} ╾╾╾╾╾╾"
    return "╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼╼"

def panel_line() -> str:
    return "┌───────────────────┐\n└───────────────────┘"

# ─── Telemetry log line ──────────────────────────────────────
def log_line(time_str: str, name: str, action: str) -> str:
    return f"⏱️ `{time_str}` | 👤 {name} ╼ {action} 📌"

# ─── Notification sender ─────────────────────────────────────
async def send_notification(bot, user_id: int, text: str, reply_markup=None):
    notif_on = await db.get_setting("notifications_enabled", "1")
    if notif_on != "1":
        return
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)
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
        perm_notif = True
        try:
            import json
            perms = json.loads(admin["permissions"])
            perm_notif = perms.get("notifications", True)
        except Exception:
            pass
        if not perm_notif:
            continue
        try:
            await bot.send_message(chat_id=tid, text=text, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception as e:
            logger.warning(f"Broadcast failed for {tid}: {e}")
    # Also send to group if configured
    if group_id:
        try:
            await bot.send_message(chat_id=int(group_id), text=text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Group broadcast failed: {e}")

async def notify_pishva(bot, text: str, reply_markup=None):
    await send_notification(bot, PISHVA_ID, text, reply_markup)

# ─── System Status Gate ──────────────────────────────────────
async def check_status_gate(query, action_name: str = "") -> bool:
    """Returns True if access is blocked. Call answer_callback with show_alert."""
    status = await db.get_setting("system_status", "normal")
    user_id = query.from_user.id
    bot_active = await db.get_setting("bot_active_for_admins", "1")
    update_mode = await db.get_setting("bot_update_mode", "0")

    if user_id == PISHVA_ID:
        if status == "aps":
            # Pishva only has access to pishva panel in APS
            return False
        return False

    if update_mode == "1":
        await query.answer("🔄 ربات در حال آپدیت است. لطفاً منتظر بمانید.", show_alert=True)
        return True

    if bot_active != "1":
        await query.answer("💤 ربات توسط پیشوا خاموش شده است.", show_alert=True)
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
        # Bad status: block certain actions
        blocked = ["match_delete", "match_edit", "warning", "ban_player", "msg_admin", "view_players"]
        for b in blocked:
            if b in action_name:
                await query.answer(
                    f"🟡 سیستم در وضعیت احتیاطی است؛ عملیات «{action_name}» موقتاً غیرفعال شده.",
                    show_alert=True
                )
                return True

    return False

# ─── Role / Permission Checkers ──────────────────────────────
async def is_pishva(user_id: int) -> bool:
    return user_id == PISHVA_ID

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

# ─── Shamsi date validator ────────────────────────────────────
def validate_date(date_str: str) -> bool:
    try:
        parts = date_str.replace("/", "-").split("-")
        if len(parts) == 3:
            return True
    except Exception:
        pass
    return False

# ─── Lottery (smart random) ──────────────────────────────────
import random

async def smart_lottery(players: list) -> tuple:
    """Pick two players who haven't played each other if possible."""
    if len(players) < 2:
        return None, None, False

    player_ids = [p["id"] for p in players]
    random.shuffle(player_ids)

    # Try to find a pair that hasn't played
    for i in range(len(player_ids)):
        for j in range(i + 1, len(player_ids)):
            if not await db.have_played_before(player_ids[i], player_ids[j]):
                p1 = next(p for p in players if p["id"] == player_ids[i])
                p2 = next(p for p in players if p["id"] == player_ids[j])
                return p1, p2, False  # False = no warning needed

    # All have played each other
    random.shuffle(player_ids)
    p1 = next(p for p in players if p["id"] == player_ids[0])
    p2 = next(p for p in players if p["id"] == player_ids[1])
    return p1, p2, True  # True = all have played warning
