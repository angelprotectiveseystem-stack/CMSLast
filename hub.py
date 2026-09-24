"""
hub.py — «پنل من»: مینی‌اپِ تلگرامیِ مشترکِ مدیران و مدیر ارشد.

برخلافِ admin_panel.py (رمزعبور در مرورگر) و principal_panel.py (کلید در
URL)، این یک Telegram Mini App واقعی‌ست: از همان دکمه‌ی کنارِ چتِ ربات
(«پنل من» — menu button) باز می‌شود و احرازِ هویتش initData ِ امضاشده‌ی
تلگرام است (همان الگوریتمِ game_server._verify_init_data، برای شطرنجِ
زنده) — نه رمز، نه کلید در URL.

دسترسی: initData باید معتبر باشد (۴۰۱ اگر نه) و کاربر باید یا مدیرِ
فعال در جدولِ admins باشد یا خودِ PISHVA_ID باشد (۴۰۳ اگر نه). PISHVA_ID
ردیفی در admins ندارد — در کل پروژه با ثابتِ config.PISHVA_ID شناخته
می‌شود، برای همین این ماژول همه‌جا این حالت را جدا مدیریت می‌کند.

نوشتن روی دیتابیس فقط در یک مسیر: PUT /hub/api/profile (هرکس فقط
پروفایلِ خودش را می‌نویسد). بقیه‌ی مسیرها فقط SELECT هستند.

سوارشدن روی سرور: دقیقاً مثلِ admin_panel/principal_panel — نه سرورِ
جدا، بلکه register_hub_routes(app) از game_server.start_game_server
صدا زده می‌شود.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from urllib.parse import parse_qsl

from aiohttp import web

import database as db
import elo
from config import (BOT_TOKEN, PISHVA_ID, ROLE_TOURNAMENT_MANAGER,
                    ROLE_SECURITY_MANAGER)

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

HUB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub")
INIT_DATA_MAX_AGE = 24 * 3600  # ثانیه، هم‌راستا با game_server.py

# نقش‌هایی که اجازه‌ی ورود به هاب را دارند. مدیر ارشد (PISHVA_ID) جدا و با
# آی‌دی چک می‌شود (ردیفی در admins ندارد)، پس اینجا فقط دو نقشِ دیگر است.
# هر مقدارِ ناشناخته‌ای در ستونِ role → ۴۰۳ (لیستِ سفید، نه لیستِ سیاه).
HUB_ALLOWED_ROLES = frozenset({ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER})


# ─── احرازِ هویتِ initData تلگرام ───────────────────────────────────
def _verify_init_data(init_data: str):
    """همان الگوریتمِ رسمیِ WebApp تلگرام؛ عیناً هم‌راستا با
    game_server._verify_init_data تا رفتارِ دو مینی‌اپ یکی باشد."""
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


def _err(status_cls, code):
    return status_cls(text=json.dumps({"ok": False, "error": code}, ensure_ascii=False),
                       content_type="application/json")


async def _identify(request):
    """initData را از هدرِ X-Tg-Init-Data می‌خواند و کاربر را برمی‌گرداند.
    فقط تشخیصِ هویت — چک نمی‌کند که ادمین است یا نه (آن کارِ _require_admin
    است). خروجی: dict خامِ user تلگرام، یا None."""
    init_data = request.headers.get("X-Tg-Init-Data", "")
    return _verify_init_data(init_data)


async def _require_admin(request):
    """۴۰۱ اگر initData نامعتبر/خالی باشد؛ ۴۰۳ اگر کاربرِ معتبرِ تلگرام
    باشد ولی نه پیشوا، نه مدیرِ فعالِ یکی از نقش‌های مجاز (مسئول مسابقات /
    مسئول انتظامات)، یا در لیست بلاک باشد.
    برمی‌گرداند: (is_pishva, admin_row_or_None, tg_user).

    هویت فقط از initData امضاشده‌ی تلگرام (HMAC با توکنِ ربات) می‌آید؛ آی‌دی
    یا یوزرنیمِ ربات به‌تنهایی هیچ دسترسی‌ای نمی‌دهد."""
    user = await _identify(request)
    if not user or "id" not in user:
        raise _err(web.HTTPUnauthorized, "unauthorized")
    try:
        uid = int(user["id"])
    except (TypeError, ValueError):
        raise _err(web.HTTPUnauthorized, "unauthorized")
    if uid == PISHVA_ID:
        return True, None, user
    if await db.get_blocked_user(uid):
        raise _err(web.HTTPForbidden, "forbidden")
    admin = await db.get_admin(uid)
    if not admin or not admin["is_active"] or admin["role"] not in HUB_ALLOWED_ROLES:
        raise _err(web.HTTPForbidden, "forbidden")
    # اسمِ تلگرامِ مدیر ممکنه بعد از ثبت‌نام عوض شده باشه؛ همین‌جا هم‌گامش کن.
    try:
        tg_name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
        await db.sync_admin_identity(uid, user.get("username"), tg_name)
        admin = await db.get_admin(uid) or admin
    except Exception:
        logger.exception("hub: sync_admin_identity failed for %s", uid)
    return False, admin, user


def _json(data):
    return web.json_response(data, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


# ─── کمکی‌های نمایش/تبدیل ───────────────────────────────────────
def _role_label(role: str) -> str:
    return {
        "pishva": "مدیر ارشد",
        "tournament_manager": "مسئول مسابقات",
        "security_manager": "مسئول انتظامات",
    }.get(role, "مدیر")


def _avatar_path(telegram_id) -> str:
    return f"/api/avatar/{telegram_id}" if telegram_id else None


def _admin_details(admin) -> list:
    try:
        raw = json.loads(admin["details"] or "[]")
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [{"k": str(d["k"])[:20], "v": str(d["v"])[:60]}
            for d in raw[:5] if isinstance(d, dict) and d.get("k") and d.get("v")]


async def _me_public(is_pishva, admin):
    """شکلِ عمومیِ «خودِ من» — چه پیشوا باشم چه مدیرِ معمولی — دقیقاً
    فیلدهایی که profileBody در hub.js انتظار دارد."""
    if is_pishva:
        p = await db.get_pishva_profile_fields()
        my = await db.get_admin_match_stats(PISHVA_ID)
        return {
            "id": PISHVA_ID, "name": p["name"], "role": "pishva", "role_label": "مدیر ارشد",
            "title": p["title"], "city": p["city"], "bio": p["bio"], "details": p["details"],
            "avatar": _avatar_path(PISHVA_ID), "joined_at": None, "last_active": None, "my": my,
        }
    my = await db.get_admin_match_stats(admin["telegram_id"])
    return {
        "id": admin["telegram_id"], "name": admin["display_name"] or admin["full_name"] or "مدیر",
        "role": admin["role"], "role_label": _role_label(admin["role"]),
        "title": admin["title"] or "", "city": admin["city"] or "", "bio": admin["bio"] or "",
        "details": _admin_details(admin),
        "avatar": _avatar_path(admin["telegram_id"]),
        "joined_at": admin["joined_at"], "last_active": admin["last_active"], "my": my,
    }


def _teammate_public(admin) -> dict:
    return {
        "id": admin["telegram_id"], "name": admin["display_name"] or admin["full_name"] or "مدیر",
        "role": admin["role"], "role_label": _role_label(admin["role"]),
        "title": admin["title"] or "", "city": admin["city"] or "", "bio": admin["bio"] or "",
        "details": _admin_details(admin),
        "avatar": _avatar_path(admin["telegram_id"]),
        "joined_at": admin["joined_at"], "last_active": admin["last_active"],
    }


async def _pishva_teammate_public():
    p = await db.get_pishva_profile_fields()
    return {
        "id": PISHVA_ID, "name": p["name"], "role": "pishva", "role_label": "مدیر ارشد",
        "title": p["title"], "city": p["city"], "bio": p["bio"], "details": p["details"],
        "avatar": _avatar_path(PISHVA_ID), "joined_at": None, "last_active": None,
    }


# ─── بوت‌استرپ (خانه، آیکونِ تبِ پروفایل، تیمِ مدیران) ────────────────
@routes.get("/hub/api/bootstrap")
async def hub_bootstrap(request):
    is_pishva, admin, user = await _require_admin(request)
    now_iso = datetime.now().isoformat()

    all_players = await db.get_all_players()
    active_players = [p for p in all_players if (p["status"] or "active") == "active"]
    elite_n = sum(1 for p in active_players if p["is_elite"])
    special_n = sum(1 for p in active_players if p["is_special"])

    tours = await db.get_tournaments_with_counts()
    active_tours = sum(1 for t in tours if t["status"] == "active")

    m_summary = await db.get_hub_matches_summary()
    trend = await db.get_hub_trend(7)

    top = await _top_players(active_players)

    me = await _me_public(is_pishva, admin)

    # تیمِ مدیران: پیشوا همیشه اول (اگر خودِ بیننده پیشوا نیست)، بعد بقیه‌ی
    # مدیرانِ فعال بجز خودِ بیننده.
    team = []
    if not is_pishva:
        team.append(await _pishva_teammate_public())
    for a in await db.get_active_admins():
        if is_pishva or a["telegram_id"] != admin["telegram_id"]:
            team.append(_teammate_public(a))

    return _json({
        "now": now_iso,
        "me": me,
        "team": team,
        "summary": {
            "players": {"active": len(active_players), "elite": elite_n, "special": special_n},
            "tournaments": {"active": active_tours, "total": len(tours)},
            "matches": m_summary,
        },
        "top": top,
        "trend": trend,
        "tournaments": tours,
    })


async def _top_players(active_players, limit=5):
    """چند نفرِ برتر بر اساسِ Elo، برای کارتِ «برترین‌ها»ی خانه‌ی هاب.
    یک کوئریِ واحد برای Elo همه‌ی بازیکنان (نه N تا کوئریِ جدا)."""
    elo_map = await db.get_all_player_elo()
    ranked = []
    for p in active_players:
        e = elo_map.get(p["id"])
        rating = e["rating"] if e else elo.ELO_DEFAULT
        ranked.append((rating, p))
    ranked.sort(key=lambda x: -x[0])
    out = []
    for rating, p in ranked[:limit]:
        out.append({
            "id": p["id"], "name": p["full_name"], "elo": round(rating),
            "cls": elo.get_elo_title(rating), "elite": bool(p["is_elite"]),
        })
    return out


# ─── بازیکنان ────────────────────────────────────────────────────
@routes.get("/hub/api/players")
async def hub_players(request):
    await _require_admin(request)
    all_players = await db.get_all_players()
    elo_map = await db.get_all_player_elo()
    cols = ["id", "name", "cls", "elo", "w", "d", "l", "warn", "elite", "special", "status", "games"]
    rows = []
    for p in all_players:
        e = elo_map.get(p["id"])
        rating = e["rating"] if e else elo.ELO_DEFAULT
        w, d, l = p["wins"] or 0, p["draws"] or 0, p["losses"] or 0
        rows.append([
            p["id"], p["full_name"], p["class_name"] or "", round(rating),
            w, d, l, p["warnings"] or 0,
            1 if p["is_elite"] else 0, 1 if p["is_special"] else 0,
            p["status"] or "active", w + d + l,
        ])
    return _json({"cols": cols, "rows": rows})


@routes.get("/hub/api/player/{id}")
async def hub_player_detail(request):
    await _require_admin(request)
    try:
        pid = int(request.match_info["id"])
    except (TypeError, ValueError):
        raise web.HTTPBadRequest()
    detail = await db.get_player_hub_detail(pid)
    rank = detail["rank_row"]["rank"] if detail["rank_row"] else None
    e = await elo.get_player_elo(pid)
    matches = []
    for m in detail["matches"]:
        matches.append({
            "wid": m["white_player_id"], "w": m["white_name"] or "؟", "b": m["black_name"] or "؟",
            "res": m["result"], "t": m["t_name"], "date": (m["match_date"] or "")[:10],
        })
    return _json({
        "elo": {"peak": round(e["peak_rating"])} if e["games_played"] else None,
        "rank": rank,
        "matches": matches,
    })


# ─── مسابقات ─────────────────────────────────────────────────────
@routes.get("/hub/api/tournament/{id}")
async def hub_tournament_detail(request):
    await _require_admin(request)
    try:
        tid = int(request.match_info["id"])
    except (TypeError, ValueError):
        raise web.HTTPBadRequest()
    data = await db.get_tournament_standings(tid)
    standings = []
    for name, s in data["standings"]:
        standings.append({
            "name": name, "p": s["played"], "w": s["win"], "d": s["draw"], "l": s["loss"], "pts": s["points"],
        })
    rows = await db.get_tournament_matches_named(tid)
    matches = [{
        "w": r["white_name"] or "؟", "b": r["black_name"] or "؟",
        "res": r["result"], "date": (r["match_date"] or "")[:10],
    } for r in rows]
    return _json({"standings": standings, "matches": matches})


# ─── پروفایل (تنها مسیرِ نوشتنی) ────────────────────────────────────
@routes.post("/hub/api/profile")
async def hub_update_profile(request):
    is_pishva, admin, user = await _require_admin(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    display_name = body.get("display_name", "")
    title = body.get("title", "")
    city = body.get("city", "")
    bio = body.get("bio", "")
    details = body.get("details", [])
    if not isinstance(details, list):
        details = []

    if is_pishva:
        p = await db.update_pishva_profile(display_name, title, city, bio, details)
    else:
        p = await db.update_admin_profile(admin["telegram_id"], display_name, title, city, bio, details)

    return _json({"profile": p})


# ─── دکمه‌ی «پنل من» کنارِ چت (menu button) ──────────────────────────
_BOT = None  # رفرنسِ ربات؛ در اولین sync_menu_buttons ست می‌شود


def _hub_button():
    from config import WEBAPP_URL
    if not WEBAPP_URL:
        return None
    try:
        from telegram import MenuButtonWebApp, WebAppInfo
    except ImportError:
        logger.warning("MenuButtonWebApp not available in this python-telegram-bot version.")
        return None
    return MenuButtonWebApp(text="CMS", web_app=WebAppInfo(url=f"{WEBAPP_URL}/hub/"))


async def sync_menu_button_for(bot, telegram_id: int):
    """دکمه‌ی «CMS» را برای *یک* نفر همین حالا هم‌گام می‌کند: اگر پیشوا یا
    مدیرِ فعالِ نقشِ مجاز است دکمه می‌گیرد، وگرنه دکمه‌ی پیش‌فرض برمی‌گردد
    (مثلاً بعد از اخراج). نیازی به صبر برای job ساعتی نیست."""
    if bot is None or not telegram_id:
        return
    try:
        from telegram import MenuButtonDefault
    except ImportError:
        return
    allowed = telegram_id == PISHVA_ID
    if not allowed:
        a = await db.get_admin(telegram_id)
        allowed = bool(a and a["is_active"] and a["role"] in HUB_ALLOWED_ROLES)
    try:
        if allowed:
            btn = _hub_button()
            if btn is None:
                return
            await bot.set_chat_menu_button(chat_id=telegram_id, menu_button=btn)
        else:
            await bot.set_chat_menu_button(chat_id=telegram_id, menu_button=MenuButtonDefault())
    except Exception:
        logger.warning("Could not sync hub menu button for %s", telegram_id, exc_info=True)


def schedule_menu_sync(telegram_id):
    """غیرمسدودکننده؛ از database.py بعد از افزودن/اخراج/تغییرِ نقشِ مدیر
    صدا زده می‌شود. اگر حلقه‌ی asyncio یا ربات هنوز آماده نباشد، بی‌صدا رد
    می‌شود (job ساعتی جبران می‌کند)."""
    if _BOT is None or not telegram_id:
        return
    try:
        asyncio.get_running_loop().create_task(sync_menu_button_for(_BOT, int(telegram_id)))
    except RuntimeError:
        pass


async def sync_menu_buttons(bot):
    """دکمه‌ی منویِ چتِ خودِ پیشوا + همه‌ی مدیرانِ فعالِ نقشِ مجاز را روی
    «پنل من» می‌گذارد. کاربرانِ دیگر دکمه‌ی پیش‌فرض را می‌بینند — و حتی اگر
    لینک را از جایی پیدا کنند، بدونِ initData امضاشده و ردیف در admins فقط
    ۴۰۱/۴۰۳ می‌گیرند. اگر WEBAPP_URL تنظیم نشده باشد کاری نمی‌کند."""
    global _BOT
    _BOT = bot
    button = _hub_button()
    if button is None:
        logger.info("WEBAPP_URL not set (or no MenuButtonWebApp); skipping hub menu-button sync.")
        return

    chat_ids = [PISHVA_ID]
    try:
        admins = await db.get_active_admins()
        chat_ids += [a["telegram_id"] for a in admins
                     if a["role"] in HUB_ALLOWED_ROLES and a["telegram_id"]]
    except Exception:
        logger.exception("Could not load active admins for hub menu-button sync.")

    ok, fail = 0, 0
    for cid in chat_ids:
        try:
            await bot.set_chat_menu_button(chat_id=cid, menu_button=button)
            ok += 1
        except Exception:
            fail += 1
    logger.info("Hub menu button synced for %s chats (%s failed).", ok, fail)


async def sync_menu_buttons_job(context):
    """پوششِ سازگار با job_queue برای sync_menu_buttons (اجرای دوره‌ای)."""
    await sync_menu_buttons(context.bot)


# ─── سرو کردنِ فایل‌های استاتیکِ هاب (index.html/hub.js/hub.css/clock.js) ──
# عیناً هم‌الگوی static_files در game_server.py برای /webapp — کشِ طولانی‌
# مدت فقط برای درخواست‌های نسخه‌دار (?v=...)، محافظت در برابرِ path
# traversal، و fallback به index.html برای مسیرِ ریشه.
def _hub_index_response():
    path = os.path.join(HUB_DIR, "index.html")
    if not os.path.isfile(path):
        raise web.HTTPNotFound()
    resp = web.FileResponse(path)
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@routes.get("/hub")
async def hub_root(request):
    return _hub_index_response()


@routes.get("/hub/{tail:.*}")
async def hub_static_files(request):
    tail = request.match_info["tail"] or "index.html"
    if tail.startswith("api/"):
        raise web.HTTPNotFound()  # از routeهای بالا رد شده، یعنی مسیرِ api نامعتبر است
    if tail == "index.html" or tail == "":
        return _hub_index_response()
    path = os.path.normpath(os.path.join(HUB_DIR, tail))
    if not path.startswith(HUB_DIR):
        raise web.HTTPForbidden()
    if os.path.isdir(path):
        return _hub_index_response()
    if not os.path.isfile(path):
        raise web.HTTPNotFound()
    resp = web.FileResponse(path)
    if "v" in request.query:
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


# ─── ثبتِ مسیرها روی اپِ اصلی ───────────────────────────────────────
def register_hub_routes(app: web.Application):
    app.add_routes(routes)
    logger.info("Hub (پنل من) routes registered.")
