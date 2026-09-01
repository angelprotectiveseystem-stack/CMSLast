"""
game_server.py
سرور وب مینی‌اپ شطرنج — سرو کردن فایل‌های استاتیک وب‌اپ و API بازی زنده.
این سرور به‌صورت هم‌زمان با ربات (در همان event loop) با aiohttp اجرا می‌شود.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from urllib.parse import parse_qsl

import asyncio

import chess as pychess
from aiohttp import web
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

import database as db
from chess_ai import AI_ID, choose_move, evaluate_fen
from config import BOT_TOKEN, WEBAPP_PORT, PISHVA_ID

logger = logging.getLogger(__name__)

LIVE_CHESS_LOCKED_MSG = "شطرنج زنده در حال حاضر غیرفعال است."

# ─── نمونه‌ی ربات برای اطلاع‌رسانیِ پایانِ بازی ───────────────────
# این سرور aiohttp جدا از event handlerهای python-telegram-bot اجرا می‌شود
# و به ctx.bot دسترسی ندارد؛ برای همین نمونه‌ی bot یک‌بار موقع بالاآمدنِ
# سرور (در bot.py) اینجا ذخیره می‌شود تا بشود از داخل مسیرهای API هم پیام
# فرستاد/ویرایش کرد.
BOT = None


def set_bot(bot):
    global BOT
    BOT = bot


# ─── آدرسِ عکسِ پروفایلِ تلگرامیِ بازیکن‌ها ──────────────────────
# فقط با شیِ BOT می‌شود این را گرفت (نیاز به یک درخواستِ get_user_profile_photos
# + یک get_file دارد)، پس سمتِ سرور محاسبه و لینکِ مستقیمِ فایل به کلاینت
# فرستاده می‌شود (نه این‌که وب‌اپ خودش بخواهد به تلگرام وصل شود — از آن‌جا
# اصلاً به initData/بات دسترسی ندارد). چون این دو درخواست به تلگرام هر بار
# کمی طول می‌کشند و عکسِ پروفایلِ افراد در حدِ چند دقیقه تغییر نمی‌کند، با
# یک کشِ ساده‌ی حافظه‌ای (TTL) از زدنِ درخواستِ تکراری در هر poll جلوگیری
# می‌شود.
_avatar_cache = {}  # user_id -> (url_or_None, monotonic_expiry)
_AVATAR_CACHE_TTL = 300       # ثانیه — برای نتیجه‌ی موفق (عکس پیدا شد)
_AVATAR_CACHE_TTL_EMPTY = 30  # ثانیه — برای نتیجه‌ی خالی/خطا
# نتیجه‌ی «عکس ندارد یا خطا خورد» فقط ۳۰ ثانیه کش می‌شود (نه ۵ دقیقه‌ی
# کامل)، چون این حالت می‌تواند موقتی باشد (کاربر تازه با بات چت را شروع
# کرده و privacy هنوز رفرش نشده، یا یک خطای شبکه‌ی گذرا)؛ TTL کوتاه‌تر
# یعنی در بازیِ در حالِ اجرا، حتی اگر اولین تلاش شکست خورد، طیِ چند
# poll بعدی خودش را اصلاح می‌کند، بدون این‌که فشار زیادی به تلگرام وارد
# شود (که TTLِ بلندِ ۵-دقیقه‌ای برای همان منظور بود).


async def _resolve_avatar_url(user_id):
    if not user_id or BOT is None:
        return None
    cached = _avatar_cache.get(user_id)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    url = None
    try:
        photos = await BOT.get_user_profile_photos(user_id, limit=1)
        if photos and photos.photos:
            # کوچک‌ترین سایزِ موجود کافی است چون آواتار در وب‌اپ خیلی کوچک
            # نمایش داده می‌شود؛ حجمِ کمتر یعنی دانلودِ سریع‌تر روی موبایل.
            file_id = photos.photos[0][0].file_id
            tg_file = await BOT.get_file(file_id)
            url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{tg_file.file_path}"
        else:
            # حالتِ رایج‌ترین: کاربر اصلاً عکسِ پروفایل ندارد یا privacy
            # settings تلگرامش اجازه‌ی دیدنش به بات‌ها را نمی‌دهد. این یک
            # خطا نیست، پس با سطحِ debug (نه warning/error) لاگ می‌شود —
            # صرفاً برای این‌که موقعِ عیب‌یابی بشود فرق گذاشت بینِ «عکس
            # واقعاً وجود ندارد» و «درخواست خطا خورد».
            logger.debug("No profile photo available for user %s", user_id)
    except TelegramError as e:
        logger.warning("Telegram error resolving avatar for user %s: %s", user_id, e)
        url = None
    except Exception:
        logger.exception("Failed to resolve avatar for user %s", user_id)
        url = None
    ttl = _AVATAR_CACHE_TTL if url else _AVATAR_CACHE_TTL_EMPTY
    _avatar_cache[user_id] = (url, time.monotonic() + ttl)
    return url


def _kb_after_game() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 بازی جدید", callback_data="chess_menu")],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")],
    ])


_RESULT_LABELS = {
    "checkmate": "با کیش و مات",
    "draw": "با تساوی",
    "draw_agreement": "با توافق دو طرف بر تساوی",
    "stalemate": "با تساوی (پات — بازیکنِ نوبت‌دار هیچ حرکتِ مجازی نداشت)",
    "insufficient_material": "با تساوی (مهره‌های باقی‌مانده برای مات‌کردن کافی نبود)",
    "draw_75moves": "با تساوی (۷۵ حرکت بدون پیشروی پیاده یا گرفتنِ مهره)",
    "draw_repetition": "با تساوی (تکرارِ سه‌باره‌ی یک موقعیت)",
    "resigned": "با تسلیم یکی از طرفین",
    "timeout": "با اتمام زمان یکی از طرفین",
}

# مجموعه‌ی همه‌ی وضعیت‌هایی که از دیدِ منطقِ بازی «تساوی» محسوب می‌شوند —
# برای این‌که هر جای دیگری از کد که قبلاً فقط status == "draw" چک می‌کرد
# (مثلاً محاسبه‌ی Elo که مساوی را winner_id=None می‌داند) با انواعِ جدیدِ
# دقیق‌ترِ تساوی هم درست کار کند.
DRAW_STATUSES = {"draw", "draw_agreement", "stalemate", "insufficient_material", "draw_75moves", "draw_repetition"}


def _classify_draw_reason(board) -> str:
    """علتِ دقیقِ تساوی را از رویِ Board برمی‌گرداند. ترتیبِ چک‌ها مهم است:
    is_stalemate و is_insufficient_material دو حالتِ جداگانه‌اند، ولی
    ۷۵-حرکت و تکرارِ سه‌بار می‌توانند هم‌زمان با یکدیگر (یا با پات) درست
    باشند؛ در آن صورت دلیلِ «قانونیِ اولیه‌تر» (پات/کمبودِ مهره) در اولویت
    است چون علیّ‌تر و قابلِ‌فهم‌تر برای بازیکن است."""
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "insufficient_material"
    if board.is_seventyfive_moves():
        return "draw_75moves"
    if board.is_repetition(3):
        return "draw_repetition"
    return "draw"


async def _notify_players_game_finished(game, status, winner_id):
    """رفعِ باگِ «دکمه‌ی ورود به بازیِ قدیمی برای همیشه در چت می‌ماند»:
    وقتی بازی (به هر دلیلی) تمام می‌شود، همان پیامی که دکمه‌ی «ورود به
    بازی» را داشت به یک پنل «بازی جدید / منوی اصلی» ویرایش می‌شود. اگر
    ویرایش ممکن نبود (پیام پاک شده/خیلی قدیمی)، به‌جایش یک پیام تازه
    فرستاده می‌شود تا کاربر هرگز با یک دکمه‌ی مرده تنها نماند."""
    if BOT is None:
        return
    label = _RESULT_LABELS.get(status, status)
    # برای تسلیم، «یکی از طرفین» کافی نیست — دقیقاً بگوییم چه کسی تسلیم شد
    # (بازنده = کسی که winner_id نیست)، چون خودِ گیرنده‌ی پیام هم می‌تواند
    # برنده یا بازنده باشد و نباید حدس بزند.
    if status == "resigned" and winner_id:
        loser_id = game["black_id"] if str(winner_id) == str(game["white_id"]) else game["white_id"]
        loser_name = game["black_name"] if loser_id == game["black_id"] else game["white_name"]
        label = f"با تسلیمِ {loser_name}"
    elif status == "timeout" and winner_id:
        loser_id = game["black_id"] if str(winner_id) == str(game["white_id"]) else game["white_id"]
        loser_name = game["black_name"] if loser_id == game["black_id"] else game["white_name"]
        label = f"با اتمامِ زمانِ {loser_name}"
    pairs = ((game["white_id"], game["white_msg_id"]), (game["black_id"], game["black_msg_id"]))
    for side_id, msg_id in pairs:
        if not side_id or side_id == AI_ID:
            continue
        if winner_id is None:
            result_line = f"🤝 بازی مساوی شد ({label})."
        elif str(winner_id) == str(side_id):
            result_line = f"🏆 شما بردید! ({label})"
        else:
            result_line = f"😔 این بازی را باختید ({label})."
        text = (
            f"{'♟️ بازی به پایان رسید'}\n\n{result_line}\n\n"
            "می‌توانید یک بازی جدید شروع کنید یا به منوی اصلی برگردید."
        )
        edited = False
        if msg_id:
            try:
                await BOT.edit_message_text(
                    chat_id=side_id, message_id=msg_id, text=text,
                    reply_markup=_kb_after_game(), parse_mode=ParseMode.MARKDOWN,
                )
                edited = True
            except TelegramError:
                edited = False
        if not edited:
            try:
                await BOT.send_message(
                    chat_id=side_id, text=text,
                    reply_markup=_kb_after_game(), parse_mode=ParseMode.MARKDOWN,
                )
            except TelegramError:
                logger.exception("Failed to notify %s about finished chess game", side_id)


async def _game_locked_for_viewing(game) -> bool:
    """قفل شطرنج زنده برای درخواست‌های بدون احراز هویت (مثل /api/state):
    در وضعیت خطرناک/APS برای همه (حتی مدیر ارشد) قفل است؛ سوییچ دستیِ
    مدیر ارشد هم قفل می‌کند مگر این‌که خودِ مدیر ارشد یکی از دو بازیکن باشد."""
    if await db.is_chess_locked_by_status():
        return True
    if await db.is_chess_admin_switch_off():
        if PISHVA_ID not in (game["white_id"], game["black_id"]):
            return True
    return False

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")
INIT_DATA_MAX_AGE = 24 * 3600  # ثانیه


def _verify_init_data(init_data: str):
    """اعتبارسنجی امضای initData تلگرام طبق مستندات رسمی WebApp.
    اگر معتبر باشد، دیکشنری user را برمی‌گرداند؛ در غیر این صورت None."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    recv_hash = pairs.pop("hash", None)
    if not recv_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, recv_hash):
        return None
    auth_date = int(pairs.get("auth_date", "0"))
    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        return None
    user_raw = pairs.get("user")
    if not user_raw:
        return None
    try:
        return json.loads(user_raw)
    except Exception:
        return None


async def _resolve_user_id(request_json):
    """کاربر فراخوان را از initData استخراج می‌کند. برای تست محلی، اگر initData
    خالی بود و DEBUG_ALLOW_UNSAFE فعال بود، user_id مستقیم را می‌پذیرد (فقط توسعه)."""
    init_data = request_json.get("init_data") or ""
    user = _verify_init_data(init_data)
    if user and "id" in user:
        return user["id"], user.get("first_name") or user.get("username") or "بازیکن"
    return None, None


async def _game_to_state(game, viewer_id):
    pgn = game["pgn"] or ""
    # هر دو عکسِ پروفایل موازی گرفته می‌شوند (نه پشتِ‌سرِهم) تا تاخیرِ
    # اضافه‌شده به هر درخواستِ /api/state حداکثر برابرِ یکی از این دو
    # فراخوانی باشد، نه مجموعِ هر دو.
    white_avatar, black_avatar = await asyncio.gather(
        _resolve_avatar_url(game["white_id"]),
        _resolve_avatar_url(game["black_id"]),
    )
    return {
        "fen": game["fen"],
        "status": game["status"],
        "white_id": game["white_id"],
        "black_id": game["black_id"],
        "white_name": game["white_name"],
        "black_name": game["black_name"],
        "white_avatar": white_avatar,
        "black_avatar": black_avatar,
        "white_time": game["white_time"],
        "black_time": game["black_time"],
        "winner_id": game["winner_id"],
        "last_move": (
            {"from": game["last_move_from"], "to": game["last_move_to"]}
            if game["last_move_from"] else None
        ),
        "moves": pgn.split(",") if pgn else [],
        "draw_offer_by": game["draw_offer_by"],
        "white_elo_change": game["white_elo_change"],
        "black_elo_change": game["black_elo_change"],
        "you_id": viewer_id,
    }


async def _finish_with_elo(token, status, game, winner_id):
    """بازی را با محاسبه‌ی تغییر امتیاز Elo هر دو مدیر تمام می‌کند."""
    result = "draw" if winner_id is None else (
        "white" if winner_id == game["white_id"] else "black"
    )
    chg_w = chg_b = None
    # بازی‌های «هوش مصنوعی» جزو رتبه‌بندی Elo محسوب نمی‌شوند — فقط تمرینِ
    # شخصی‌اند و نباید جدولِ امتیازِ مدیران واقعی را آلوده کنند.
    if AI_ID not in (game["white_id"], game["black_id"]):
        try:
            from elo import ensure_chess_elo_table, update_chess_elo_after_game
            await ensure_chess_elo_table()
            _, _, chg_w, chg_b = await update_chess_elo_after_game(
                game["white_id"], game["white_name"], game["black_id"], game["black_name"], result
            )
        except Exception:
            logger.exception("Chess Elo update failed for game %s", token)
    await db.finish_chess_game(token, status, winner_id, chg_w, chg_b)
    try:
        await _notify_players_game_finished(game, status, winner_id)
    except Exception:
        logger.exception("Failed to send post-game panel for %s", token)


def _load_board(game):
    """بازسازیِ کاملِ Board از رویِ تاریخچه‌ی حرکت‌ها — نه فقط از رویِ FENِ لحظه‌ی فعلی.

    باگِ «قوانینِ پایانِ بازی مثلِ سه‌حرکتِ تکراری اعمال نمی‌شوند»: در همه‌جای
    این فایل با pychess.Board(game["fen"]) یک Boardِ تازه فقط از رویِ FENِ
    فعلی ساخته می‌شد. FEN صرفاً چیدمانِ فعلیِ مهره‌ها را نگه می‌دارد و هیچ
    اطلاعی از حرکت‌های قبلیِ همین بازی در آن نیست. python-chess برای تشخیصِ
    سه‌حرکتِ تکراری (is_repetition) دقیقاً به move_stack همان شیِ Board نگاه
    می‌کند (شمارشِ موقعیت‌های تکراری‌ای که این Board واقعاً از سرشان گذشته)،
    نه به خودِ FEN. پس با ساختن Board فقط از رویِ FEN، این Board همیشه یک
    move_stackِ تقریباً خالی داشت (حداکثر همان یک حرکتِ تازه‌ای که خودِ همین
    تابع بلافاصله push می‌کرد) و در نتیجه is_repetition(3) عملاً هیچ‌وقت True
    برنمی‌گشت — حتی وقتی در واقعیتِ بازی یک موقعیت واقعاً سه بار تکرار شده
    بود، چون از دیدِ این Boardِ تازه‌ساز، آن تکرارها اصلاً «اتفاق نیفتاده»
    بودند.

    راه‌حل: بازی‌ها همیشه از وضعیتِ شروعِ استانداردِ شطرنج آغاز می‌شوند
    (START_FEN در chess_challenge.py)، و تاریخچه‌ی کاملِ حرکت‌ها به‌صورتِ
    SANِ کاما-جدا در game[\"pgn\"] ذخیره شده است. با replay کاملِ همین
    لیست رویِ یک Boardِ تازه، همان موقعیتِ نهایی به‌دست می‌آید — ولی این‌بار
    با move_stackِ واقعیِ کاملِ بازی، پس is_repetition و بقیه‌ی قوانینِ
    مبتنی‌بر-تاریخچه درست کار می‌کنند."""
    board = pychess.Board()
    pgn = game.get("pgn") or ""
    if pgn:
        for san in pgn.split(","):
            if not san:
                continue
            try:
                board.push_san(san)
            except Exception:
                logger.exception(
                    "بازسازیِ تاریخچه‌ی حرکت‌ها ناموفق بود (san=%r) — بازگشت به FEN فعلی", san
                )
                return pychess.Board(game["fen"])
    return board


def _apply_clock_decay(game):
    """قبل از پاسخ‌دادن، زمان طرف نوبت‌دار را بر اساس فاصله از آخرین حرکت کم می‌کند
    تا کلاک‌ها بدون نیاز به تایمر سمت سرور جداگانه به‌روز بمانند."""
    if game["status"] != "active":
        return dict(game)
    # اینجا فقط نوبتِ فعلی (board.turn) لازم است که مستقیماً از رویِ خودِ
    # FEN هم درست خوانده می‌شود؛ برخلافِ is_repetition، به تاریخچه‌ی کاملِ
    # حرکت‌ها نیاز ندارد، پس برای جلوگیری از overhead روی مسیرِ پرتکرارِ
    # poll همان ساختِ سبکِ قبلی نگه داشته شده (نه _load_board).
    board = pychess.Board(game["fen"])
    elapsed = 0
    try:
        from datetime import datetime
        last = datetime.fromisoformat(game["last_move_at"])
        elapsed = max(0, (datetime.now() - last).total_seconds())
    except Exception:
        elapsed = 0
    g = dict(game)
    if board.turn == pychess.WHITE:
        g["white_time"] = max(0, game["white_time"] - elapsed)
    else:
        g["black_time"] = max(0, game["black_time"] - elapsed)
    return g


routes = web.RouteTableDef()

# ─── Real-time push برای رفعِ ریشه‌ای «لگ» (نه سکته‌ی انیمیشن، خودِ تاخیر) ──
# تا این‌جا حرکت حریف فقط با poll هر ۱.۵ ثانیه‌ی کلاینت کشف می‌شد؛ یعنی
# صرف‌نظر از این‌که خودِ انیمیشن چقدر روان باشد، حریف حرکتش را می‌بیند اما
# تا ۱.۵ ثانیه + رفت‌وبرگشتِ شبکه طول می‌کشید تا شما اصلاً شروعِ حرکت را
# ببینید — این خودِ حسِ «لگ» است، نه سکته‌ی تصویری. راه‌حل ریشه‌ای: سرور با
# WebSocket به هر دو طرفِ یک بازی وصل می‌ماند و همان لحظه‌ای که حرکت/تسلیم/
# پیشنهاد تساوی در دیتابیس ثبت می‌شود، یک پیام کوچک به هر دو کلاینت پوش
# می‌کند تا بلافاصله (بدون صبر برای دور بعدیِ poll) وضعیت تازه را بگیرند.
# poll دوره‌ای همچنان به‌عنوان شبکه‌ی ایمنی (اگر WebSocket قطع/مسدود بود)
# نگه داشته می‌شود، فقط دیگر تنها راه نیست.
_ws_clients = {}  # token -> set(WebSocketResponse)


async def _notify_state_changed(token):
    clients = _ws_clients.get(token)
    if not clients:
        return
    dead = []
    for ws in list(clients):
        try:
            await ws.send_str("update")
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)
    if not clients:
        _ws_clients.pop(token, None)


@routes.get("/ws/{token}")
async def ws_handler(request):
    token = request.match_info["token"]
    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(request)
    _ws_clients.setdefault(token, set()).add(ws)
    try:
        async for _msg in ws:
            pass  # کلاینت پیامی نمی‌فرستد؛ این حلقه فقط اتصال را زنده نگه می‌دارد
    finally:
        clients = _ws_clients.get(token)
        if clients:
            clients.discard(ws)
            if not clients:
                _ws_clients.pop(token, None)
    return ws

# ─── Cache-busting برای فایل‌های استاتیک وب‌اپ ───────────────────────
# ریشه‌ی باگ «حرکت مهره‌ها بدون انیمیشن/سکته‌دار حتی بعد از فیکس شدن کد»:
# app.js / chess.min.js / style.css همیشه با همان آدرس ثابت (بدون شماره‌
# نسخه) درخواست می‌شدند و پاسخ سرور هم هیچ Cache-Control ای نداشت. نتیجه
# این‌که WebView تلگرام (به‌خصوص روی اندروید) بعد از اولین بار باز کردن
# مینی‌اپ، app.js را به‌صورت تهاجمی کش می‌کند و حتی بعد از دیپلوی نسخه‌ی
# جدید و درست‌شده روی سرور، همچنان همان app.js قدیمیِ باگ‌دار را از کش خودش
# اجرا می‌کند — یعنی کاربر هیچ‌وقت متوجه نمی‌شود که مشکل حل شده، چون کدی که
# در دستگاهش اجرا می‌شود اصلاً به‌روز نمی‌شود.
#
# راه‌حل: هر بار که index.html سرو می‌شود، به src/href سه فایل اصلی یک
# ?v=<زمان آخرین تغییرِ فایل‌ها> اضافه می‌کنیم. با هر دیپلویِ واقعی، این
# زمان عوض می‌شود، آدرس فایل‌ها عوض می‌شود، و WebView مجبور است نسخه‌ی
# تازه را واقعاً از سرور بگیرد (چون از نظرش این یک URL کاملاً جدید است، نه
# همان URL قدیمی). خودِ index.html هم با Cache-Control: no-cache سرو می‌شود
# تا این عدد نسخه هیچ‌وقت خودش کهنه نماند.
def _asset_version():
    try:
        mtimes = [
            os.path.getmtime(os.path.join(WEBAPP_DIR, f))
            for f in ("app.js", "chess.min.js", "style.css")
            if os.path.isfile(os.path.join(WEBAPP_DIR, f))
        ]
        return str(int(max(mtimes))) if mtimes else "0"
    except Exception:
        return "0"


def _render_index_html():
    path = os.path.join(WEBAPP_DIR, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    v = _asset_version()
    html = html.replace('src="app.js"', f'src="app.js?v={v}"')
    html = html.replace('src="chess.min.js"', f'src="chess.min.js?v={v}"')
    html = html.replace('href="style.css"', f'href="style.css?v={v}"')
    return html


def _index_response():
    return web.Response(
        text=_render_index_html(),
        content_type="text/html",
        charset="utf-8",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@routes.get("/webapp/{tail:.*}")
async def static_files(request):
    tail = request.match_info["tail"] or "index.html"
    if tail == "index.html":
        return _index_response()
    path = os.path.normpath(os.path.join(WEBAPP_DIR, tail))
    if not path.startswith(WEBAPP_DIR):
        raise web.HTTPForbidden()
    if os.path.isdir(path):
        return _index_response()
    if not os.path.isfile(path):
        raise web.HTTPNotFound()
    resp = web.FileResponse(path)
    if "v" in request.query:
        # آدرس نسخه‌دار است؛ محتوایش دیگر هرگز عوض نمی‌شود (هر تغییر واقعی،
        # نسخه‌ی جدیدی می‌گیرد)، پس می‌تواند طولانی‌مدت و بی‌نیاز از بازبینی
        # کش شود — سریع‌تر لود می‌شود و دیگر مشکل کش‌شدنِ نسخه‌ی قدیمی هم رخ
        # نمی‌دهد.
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        # درخواست بدون شماره‌نسخه (مثلاً یک WebView که هنوز خودِ HTML قدیمی
        # را کش کرده و لینک بدون ?v می‌فرستد) — این حالت را کش نمی‌کنیم تا
        # حداقل با یک بازبینی، به نسخه‌ی درست برسد.
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@routes.get("/webapp")
async def webapp_root(request):
    return _index_response()


@routes.get("/api/state")
async def api_state(request):
    token = request.query.get("token")
    game = await db.get_chess_game(token) if token else None
    if not game:
        return web.json_response({"ok": False, "error": "بازی پیدا نشد یا منقضی شده است."})
    if await _game_locked_for_viewing(game):
        return web.json_response({"ok": False, "error": LIVE_CHESS_LOCKED_MSG})
    viewer_id = request.query.get("uid")
    game = _apply_clock_decay(game)
    if game["status"] == "active":
        loser = None
        if game["white_time"] <= 0:
            loser, winner = game["white_id"], game["black_id"]
        elif game["black_time"] <= 0:
            loser, winner = game["black_id"], game["white_id"]
        if loser:
            await _finish_with_elo(token, "timeout", game, winner)
            game["status"] = "timeout"
            game["winner_id"] = winner
            await _notify_state_changed(token)
    return web.json_response({"ok": True, "state": await _game_to_state(game, viewer_id)})


@routes.post("/api/move")
async def api_move(request):
    body = await request.json()
    token = body.get("token")
    user_id, _ = await _resolve_user_id(body)
    game = await db.get_chess_game(token) if token else None
    if not game:
        return web.json_response({"ok": False, "error": "بازی پیدا نشد."})
    if game["status"] != "active":
        return web.json_response({"ok": False, "error": "بازی تمام شده است."})
    if user_id is None:
        return web.json_response({"ok": False, "error": "احراز هویت ناموفق بود."})
    if user_id not in (game["white_id"], game["black_id"]):
        return web.json_response({"ok": False, "error": "شما در این بازی نیستید."})
    if not await db.can_use_live_chess(user_id):
        return web.json_response({"ok": False, "error": LIVE_CHESS_LOCKED_MSG})

    game = _apply_clock_decay(game)
    # از _load_board (نه ساختِ Board فقط از رویِ FEN) استفاده می‌شود چون
    # پایین‌تر is_repetition(3) صدا زده می‌شود که برای کارکردِ درست به
    # move_stack کاملِ بازی نیاز دارد؛ توضیحِ کامل در تعریفِ _load_board.
    board = _load_board(game)
    is_white_turn = board.turn == pychess.WHITE
    turn_id = game["white_id"] if is_white_turn else game["black_id"]
    if user_id != turn_id:
        return web.json_response({"ok": False, "error": "نوبت شما نیست."})

    frm, to, promo = body.get("from"), body.get("to"), body.get("promotion")
    uci = frm + to + (promo if promo else "")
    try:
        move = pychess.Move.from_uci(uci)
    except Exception:
        return web.json_response({"ok": False, "error": "حرکت نامعتبر."})
    if move not in board.legal_moves:
        return web.json_response({"ok": False, "error": "حرکت غیرمجاز است."})

    san = board.san(move)
    board.push(move)
    status, winner = "active", None
    if board.is_checkmate():
        status = "checkmate"
        winner = user_id
    elif board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_repetition(3):
        status = _classify_draw_reason(board)

    # باگِ «تاریخچه ناقص»: قبلاً فقط سانِ همین یک حرکت (san) به‌عنوانِ pgn
    # ذخیره می‌شد، یعنی هر حرکتِ جدید کل تاریخچه‌ی قبلی را توی دیتابیس پاک
    # می‌کرد. اینجا سانِ جدید را به رشته‌ی pgn موجود (کاما-جدا) اضافه می‌کنیم
    # تا کل تاریخچه انباشته بماند — همان چیزی که _game_to_state با pgn.split(",")
    # می‌خواند و به کلاینت می‌فرستد.
    prev_pgn = game.get("pgn") or ""
    new_pgn = (prev_pgn + "," + san) if prev_pgn else san

    await db.update_chess_game_move(
        token, board.fen(), new_pgn, frm, to,
        game["white_time"], game["black_time"]
    )
    if status != "active":
        await _finish_with_elo(token, status, game, winner)
    else:
        # اگر حریف هوش مصنوعی باشد، بلافاصله (همین درخواست) حرکتِ جواب را
        # هم بازی می‌کند تا کاربر مجبور به صبر برای دور بعدیِ poll نباشد.
        await maybe_play_ai_move(token)

    fresh = await db.get_chess_game(token)
    await _notify_state_changed(token)
    return web.json_response({"ok": True, "state": await _game_to_state(fresh, user_id)})


@routes.post("/api/resign")
async def api_resign(request):
    body = await request.json()
    token = body.get("token")
    user_id, _ = await _resolve_user_id(body)
    game = await db.get_chess_game(token) if token else None
    if not game or game["status"] != "active":
        return web.json_response({"ok": False, "error": "بازی فعالی یافت نشد."})
    if user_id not in (game["white_id"], game["black_id"]):
        return web.json_response({"ok": False, "error": "شما در این بازی نیستید."})
    if not await db.can_use_live_chess(user_id):
        return web.json_response({"ok": False, "error": LIVE_CHESS_LOCKED_MSG})
    winner = game["black_id"] if user_id == game["white_id"] else game["white_id"]
    await _finish_with_elo(token, "resigned", game, winner)
    fresh = await db.get_chess_game(token)
    await _notify_state_changed(token)
    return web.json_response({"ok": True, "state": await _game_to_state(fresh, user_id)})


@routes.post("/api/draw_offer")
async def api_draw_offer(request):
    body = await request.json()
    token = body.get("token")
    user_id, _ = await _resolve_user_id(body)
    game = await db.get_chess_game(token) if token else None
    if not game or game["status"] != "active":
        return web.json_response({"ok": False})
    if user_id not in (game["white_id"], game["black_id"]):
        return web.json_response({"ok": False, "error": "شما در این بازی نیستید."})
    if not await db.can_use_live_chess(user_id):
        return web.json_response({"ok": False, "error": LIVE_CHESS_LOCKED_MSG})
    await db.set_chess_draw_offer(token, user_id)

    if AI_ID in (game["white_id"], game["black_id"]):
        # هوش مصنوعی بلافاصله به پیشنهادِ تساوی پاسخ می‌دهد: فقط وقتی
        # موقعیتش به‌وضوح بد باشد قبول می‌کند، وگرنه رد می‌کند.
        ai_is_white = game["white_id"] == AI_ID
        score = evaluate_fen(game["fen"])
        ai_score = score if ai_is_white else -score
        if ai_score < -150:
            await _finish_with_elo(token, "draw_agreement", game, None)
        else:
            await db.clear_chess_draw_offer(token)
            ai_name = game["white_name"] if ai_is_white else game["black_name"]
            try:
                await db.add_chess_chat_message(token, AI_ID, ai_name, "🤖 پیشنهاد تساوی را رد می‌کنم.")
            except Exception:
                logger.exception("Failed to log AI draw-decline chat message for %s", token)

    fresh = await db.get_chess_game(token)
    await _notify_state_changed(token)
    return web.json_response({"ok": True, "state": await _game_to_state(fresh, user_id)})


@routes.post("/api/draw_response")
async def api_draw_response(request):
    """پاسخ به پیشنهاد تساوی: قبول یا رد. قبلاً این مسیر اصلاً وجود نداشت،
    برای همین پیشنهاد تساوی ثبت می‌شد ولی هیچ‌وقت به نتیجه نمی‌رسید."""
    body = await request.json()
    token = body.get("token")
    accept = bool(body.get("accept"))
    user_id, _ = await _resolve_user_id(body)
    game = await db.get_chess_game(token) if token else None
    if not game or game["status"] != "active":
        return web.json_response({"ok": False, "error": "بازی فعالی یافت نشد."})
    if user_id not in (game["white_id"], game["black_id"]):
        return web.json_response({"ok": False, "error": "شما در این بازی نیستید."})
    if not await db.can_use_live_chess(user_id):
        return web.json_response({"ok": False, "error": LIVE_CHESS_LOCKED_MSG})
    offerer = game["draw_offer_by"]
    if not offerer or offerer == user_id:
        return web.json_response({"ok": False, "error": "پیشنهاد تساوی معتبری برای پاسخ وجود ندارد."})

    if accept:
        await _finish_with_elo(token, "draw_agreement", game, None)
    else:
        await db.clear_chess_draw_offer(token)
    fresh = await db.get_chess_game(token)
    await _notify_state_changed(token)
    return web.json_response({"ok": True, "state": await _game_to_state(fresh, user_id)})


@routes.post("/api/game_over")
async def api_game_over(request):
    # فقط تاییدیه سمت کلاینت برای نمایش سریع‌تر مودال؛ وضعیت واقعی
    # از روی حرکت آخر در /api/move محاسبه و ذخیره شده است.
    return web.json_response({"ok": True})


_last_chat_at = {}  # token -> {user_id: monotonic_time}, ساده و در حافظه (کافی برای این حجم)
CHAT_MAX_LEN = 300
CHAT_MIN_INTERVAL = 1.5  # ثانیه بین دو پیام هر کاربر


@routes.post("/api/chat")
async def api_chat_send(request):
    body = await request.json()
    token = body.get("token")
    user_id, fallback_name = await _resolve_user_id(body)
    game = await db.get_chess_game(token) if token else None
    if not game:
        return web.json_response({"ok": False, "error": "بازی پیدا نشد."})
    if user_id is None:
        return web.json_response({"ok": False, "error": "احراز هویت ناموفق بود."})
    if not await db.can_use_live_chess(user_id):
        return web.json_response({"ok": False, "error": LIVE_CHESS_LOCKED_MSG})

    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "error": "پیام خالی است."})
    if len(text) > CHAT_MAX_LEN:
        text = text[:CHAT_MAX_LEN]

    now = time.monotonic()
    bucket = _last_chat_at.setdefault(token, {})
    last = bucket.get(user_id, 0)
    if now - last < CHAT_MIN_INTERVAL:
        return web.json_response({"ok": False, "error": "کمی آرام‌تر ✋"})
    bucket[user_id] = now

    if user_id == game["white_id"]:
        sender_name = game["white_name"]
    elif user_id == game["black_id"]:
        sender_name = game["black_name"]
    else:
        sender_name = f"👁 {fallback_name}" if fallback_name else "👁 تماشاگر"
    msg_id = await db.add_chess_chat_message(token, user_id, sender_name, text)
    return web.json_response({"ok": True, "id": msg_id})


@routes.get("/api/chat")
async def api_chat_fetch(request):
    token = request.query.get("token")
    after = int(request.query.get("after") or 0)
    game = await db.get_chess_game(token) if token else None
    if not game:
        return web.json_response({"ok": False, "error": "بازی پیدا نشد."})
    rows = await db.get_chess_chat_messages(token, after)
    messages = [
        {
            "id": r["id"],
            "sender_id": r["sender_id"],
            "sender_name": r["sender_name"],
            "text": r["text"],
            "sent_at": r["sent_at"],
        }
        for r in rows
    ]
    return web.json_response({"ok": True, "messages": messages})


async def maybe_play_ai_move(token: str):
    """اگر بازی مقابل هوش مصنوعی باشد و نوبتِ فعلی متعلق به آن باشد،
    حرکتش را (در یک ترد جدا، چون CPU-bound است) محاسبه و اعمال می‌کند.
    از /api/move (بعد از حرکت انسان) و از chess_challenge.py (وقتی خودِ
    هوش مصنوعی سفید است و باید اولین حرکت را بزند) صدا زده می‌شود."""
    game = await db.get_chess_game(token)
    if not game or game["status"] != "active":
        return
    if AI_ID not in (game["white_id"], game["black_id"]):
        return
    # همان دلیلِ استفاده از _load_board در api_move: پایین‌تر is_repetition(3)
    # صدا زده می‌شود که به تاریخچه‌ی کاملِ حرکت‌ها نیاز دارد، نه فقط FEN فعلی.
    board = _load_board(game)
    ai_is_white = game["white_id"] == AI_ID
    if board.turn != (pychess.WHITE if ai_is_white else pychess.BLACK):
        return  # نوبتِ طرفِ انسانی است

    level = game["ai_level"] or "medium"
    move = await asyncio.to_thread(choose_move, board, level)
    if move is None:
        return

    frm = pychess.square_name(move.from_square)
    to = pychess.square_name(move.to_square)
    san = board.san(move)
    board.push(move)

    status, winner = "active", None
    if board.is_checkmate():
        status = "checkmate"
        winner = AI_ID
    elif board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_repetition(3):
        status = _classify_draw_reason(board)

    prev_pgn = game.get("pgn") or ""
    new_pgn = (prev_pgn + "," + san) if prev_pgn else san

    await db.update_chess_game_move(
        token, board.fen(), new_pgn, frm, to, game["white_time"], game["black_time"]
    )
    if status != "active":
        fresh = await db.get_chess_game(token)
        await _finish_with_elo(token, status, fresh, winner)
    await _notify_state_changed(token)


def new_game_token():
    return uuid.uuid4().hex + secrets.token_hex(4)


async def start_game_server(bot=None):
    if bot is not None:
        set_bot(bot)
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBAPP_PORT)
    await site.start()
    logger.info(f"Chess mini-app server running on port {WEBAPP_PORT}")
    return runner
