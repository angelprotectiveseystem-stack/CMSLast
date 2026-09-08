"""
admin_panel.py — پنل مدیریتی وب (داشبورد زنده) برای مدیریت مسابقات شطرنج

این ماژول کاملاً مستقل از ربات تلگرام اجرا می‌شه (نه از bot.py و نه از
game_server.py استفاده می‌کنه) و روی سرور aiohttp خودش، در پروسه‌ی جدای
خودش، سرو می‌شه — با panel_server.py اجرا کن. تنها وابستگی‌اش دیتابیسِ
مشترک (Turso) از طریق database.py/turso_db.py هست.
هیچ کوئری‌ای که این پنل می‌زنه، چیزی رو توی دیتابیس تغییر نمی‌ده — فقط
SELECT — پس هیچ ریسکی برای منطق ربات یا کندی‌ای براش نداره.

احراز هویت: یک توکن ساده (رمز پنل از env، یا رمز پیشوا) که در
localStorage مرورگر ذخیره می‌شه و با هر درخواست به‌صورت هدر فرستاده می‌شه.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timedelta

from aiohttp import web

import database as db
from config import PISHVA_ID, PISHVA_PASSWORD, WEBAPP_PORT

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

PANEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp_admin")

# ─── توکن پنل ──────────────────────────────────────────────────
# رمز ورود پنل: یا از env (PANEL_PASSWORD) یا همون رمز پیشوا (PISHVA_PASSWORD)
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "") or PISHVA_PASSWORD
_SECRET = hashlib.sha256((PANEL_PASSWORD + "::panel-secret").encode()).hexdigest()


def _make_session_token() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(_SECRET.encode(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def _verify_session_token(token: str) -> bool:
    if not token or "." not in token:
        return False
    ts, sig = token.split(".", 1)
    expected = hmac.new(_SECRET.encode(), ts.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        issued = int(ts)
    except ValueError:
        return False
    # نشست ۷ روز معتبره
    return (time.time() - issued) < 7 * 24 * 3600


def _authed(request) -> bool:
    token = request.headers.get("X-Panel-Token") or request.query.get("token")
    return _verify_session_token(token or "")


def _require_auth(request):
    if not _authed(request):
        raise web.HTTPUnauthorized(text=json.dumps({"ok": False, "error": "unauthorized"}),
                                    content_type="application/json")


def _json(data):
    return web.json_response(data, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


# ─── ورود ──────────────────────────────────────────────────────
@routes.post("/api/panel/login")
async def panel_login(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    password = (body.get("password") or "").strip()
    if not password or not hmac.compare_digest(password, PANEL_PASSWORD):
        return _json({"ok": False, "error": "رمز عبور اشتباه است."})
    return _json({"ok": True, "token": _make_session_token()})


# ─── صفحه اصلی و فایل‌های استاتیک پنل ──────────────────────────
def _asset_version():
    try:
        mtimes = [os.path.getmtime(os.path.join(PANEL_DIR, f)) for f in os.listdir(PANEL_DIR)
                   if os.path.isfile(os.path.join(PANEL_DIR, f))]
        return str(int(max(mtimes))) if mtimes else "0"
    except Exception:
        return "0"


@routes.get("/panel/{tail:.*}")
async def panel_static(request):
    tail = request.match_info["tail"] or "index.html"
    path = os.path.normpath(os.path.join(PANEL_DIR, tail))
    if not path.startswith(PANEL_DIR):
        raise web.HTTPForbidden()
    if os.path.isdir(path) or not os.path.isfile(path):
        path = os.path.join(PANEL_DIR, "index.html")
    resp = web.FileResponse(path)
    if path.endswith("index.html"):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    else:
        resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@routes.get("/panel")
async def panel_root(request):
    return web.FileResponse(os.path.join(PANEL_DIR, "index.html"))


# ─── کمکی: آنلاین بودن ─────────────────────────────────────────
def _is_online(last_active_iso, minutes=5) -> bool:
    if not last_active_iso:
        return False
    try:
        t = datetime.fromisoformat(last_active_iso)
    except Exception:
        return False
    return (datetime.now() - t) < timedelta(minutes=minutes)


# ─── overview / خلاصه کلی صفحه خانه ─────────────────────────────
@routes.get("/api/panel/overview")
async def panel_overview(request):
    _require_auth(request)
    players = await db.get_all_players()
    admins = await db.get_all_admins()
    matches = await db.get_matches_by_filter("all")
    tournaments = await db.get_all_tournaments()

    try:
        live_games = await _fetch_live_games_raw()
    except Exception:
        live_games = []

    online_admins = [a for a in admins if _is_online(a["last_active"] if a else None)]
    active_tournaments = [t for t in tournaments if (t["status"] if t else None) == "active"]

    total_matches = len(matches) if matches else 0
    decided = [m for m in matches if m and m["result"]] if matches else []

    return _json({
        "ok": True,
        "stats": {
            "players_total": len(players) if players else 0,
            "admins_total": len(admins) if admins else 0,
            "admins_online": len(online_admins),
            "matches_total": total_matches,
            "matches_pending": total_matches - len(decided),
            "tournaments_active": len(active_tournaments),
            "live_games": len(live_games),
        },
        "online_admins": [
            {"telegram_id": a["telegram_id"], "name": a["display_name"] or a["full_name"], "role": a["role"]}
            for a in online_admins
        ],
    })


async def _fetch_live_games_raw():
    import turso_db as _a
    async with _a.connect(db.DB_PATH) as conn:
        conn.row_factory = _a.Row
        async with conn.execute("SELECT * FROM chess_games WHERE status='active' ORDER BY id DESC") as cur:
            return await cur.fetchall()


# ─── مسابقات شطرنج (کلاسیک، ثبت‌شده توسط ادمین) ─────────────────
@routes.get("/api/panel/matches")
async def panel_matches(request):
    _require_auth(request)
    period = request.query.get("period", "all")
    matches = await db.get_matches_by_filter(period)
    out = []
    for m in matches or []:
        out.append({
            "id": m["id"],
            "white": m["white_name"] or "—",
            "black": m["black_name"] or "—",
            "result": m["result"],
            "match_date": m["match_date"],
            "created_at": m["created_at"],
            "is_pinned": bool(m["is_pinned"]),
        })
    return _json({"ok": True, "matches": out})


# ─── شطرنج زنده ─────────────────────────────────────────────────
@routes.get("/api/panel/live-chess")
async def panel_live_chess(request):
    _require_auth(request)
    games = await _fetch_live_games_raw()
    out = []
    for g in games:
        out.append({
            "token": g["token"],
            "white_name": g["white_name"],
            "black_name": g["black_name"],
            "status": g["status"],
            "white_time": g["white_time"],
            "black_time": g["black_time"],
            "last_move_at": g["last_move_at"],
            "created_at": g["created_at"],
        })
    return _json({"ok": True, "games": out})


# ─── مدیران ──────────────────────────────────────────────────────
@routes.get("/api/panel/admins")
async def panel_admins(request):
    _require_auth(request)
    admins = await db.get_all_admins()
    out = []
    for a in admins or []:
        out.append({
            "telegram_id": a["telegram_id"],
            "username": a["username"],
            "name": a["display_name"] or a["full_name"],
            "role": a["role"],
            "is_active": bool(a["is_active"]),
            "warnings": a["warnings"],
            "joined_at": a["joined_at"],
            "last_active": a["last_active"],
            "online": _is_online(a["last_active"]),
        })
    return _json({"ok": True, "admins": out})


# ─── آنلاین‌ها (ادمین‌های فعال اخیر) ─────────────────────────────
@routes.get("/api/panel/online")
async def panel_online(request):
    _require_auth(request)
    admins = await db.get_all_admins()
    online = [a for a in (admins or []) if _is_online(a["last_active"])]
    out = [{
        "telegram_id": a["telegram_id"],
        "name": a["display_name"] or a["full_name"],
        "role": a["role"],
        "last_active": a["last_active"],
    } for a in online]
    return _json({"ok": True, "online": out})


# ─── پیام‌های ارسال‌شده (اطلاعیه‌ها + اخبار) ─────────────────────
@routes.get("/api/panel/messages")
async def panel_messages(request):
    _require_auth(request)
    import asyncio
    ann, news, fb = await asyncio.gather(
        db.get_all_announcements(), db.get_all_news(), db.get_all_feedback()
    )
    return _json({
        "ok": True,
        "announcements": [{"id": a["id"], "text": a["text"], "sent_at": a["sent_at"],
                             "is_pinned": bool(a["is_pinned"])} for a in (ann or [])],
        "news": [{"id": n["id"], "text": n["text"], "sent_at": n["sent_at"]} for n in (news or [])],
        "feedback": [{"id": f["id"], "type": f["fb_type"], "title": f["title"],
                        "content": f["content"], "sent_at": f["sent_at"]} for f in (fb or [])],
    })


# ─── فعالیت‌ها (لاگ اقدامات) ─────────────────────────────────────
@routes.get("/api/panel/activity")
async def panel_activity(request):
    _require_auth(request)
    page = int(request.query.get("page", "0"))
    logs, total = await db.get_action_logs(period="all", page=page, page_size=30)
    admins = {a["telegram_id"]: (a["display_name"] or a["full_name"]) for a in (await db.get_all_admins() or [])}
    out = []
    for l in logs or []:
        out.append({
            "id": l["id"],
            "admin": admins.get(l["admin_id"], str(l["admin_id"])),
            "action_type": l["action_type"],
            "description": l["description"],
            "logged_at": l["logged_at"],
        })
    return _json({"ok": True, "activity": out, "total": total, "page": page})


# ─── بازیکنان / مسابقه‌دهنده‌ها ───────────────────────────────────
@routes.get("/api/panel/players")
async def panel_players(request):
    _require_auth(request)
    players = await db.get_all_players()
    out = []
    for p in players or []:
        out.append({
            "id": p["id"],
            "full_name": p["full_name"],
            "class_name": p["class_name"],
            "status": p["status"],
            "wins": p["wins"],
            "losses": p["losses"],
            "draws": p["draws"],
            "warnings": p["warnings"],
            "is_elite": bool(p["is_elite"]),
            "created_at": p["created_at"],
        })
    return _json({"ok": True, "players": out})


# ─── سطح پیشرفت / ELO ────────────────────────────────────────────
@routes.get("/api/panel/elo")
async def panel_elo(request):
    _require_auth(request)
    from elo import get_elo_leaderboard
    try:
        rows = await get_elo_leaderboard(100)
    except Exception:
        rows = []
    out = []
    for r in rows or []:
        out.append({
            "player_id": r["player_id"],
            "full_name": r["full_name"],
            "class_name": r["class_name"],
            "rating": r["rating"],
            "peak_rating": r["peak_rating"],
            "games_played": r["games_played"],
            "wins": r["elo_wins"],
            "losses": r["elo_losses"],
            "draws": r["elo_draws"],
        })
    return _json({"ok": True, "leaderboard": out})


# ─── داده‌های نمودارها (میله‌ای + خط شکسته) ──────────────────────
@routes.get("/api/panel/charts")
async def panel_charts(request):
    _require_auth(request)
    import turso_db as _a

    # میله‌ای: تعداد مسابقات هر تورنومنت
    async with _a.connect(db.DB_PATH) as conn:
        conn.row_factory = _a.Row
        async with conn.execute("""
            SELECT t.name as tname, COUNT(m.id) as cnt
            FROM tournaments t LEFT JOIN matches m ON m.tournament_id = t.id
            GROUP BY t.id ORDER BY cnt DESC LIMIT 12
        """) as cur:
            tourn_rows = await cur.fetchall()

        # خط شکسته: تعداد مسابقات ثبت‌شده به تفکیک روز (۳۰ روز اخیر)
        async with conn.execute("""
            SELECT substr(created_at,1,10) as d, COUNT(*) as cnt
            FROM matches
            WHERE created_at IS NOT NULL
            GROUP BY d ORDER BY d DESC LIMIT 30
        """) as cur:
            daily_rows = await cur.fetchall()

        # کلاس‌ها: توزیع بازیکنان
        async with conn.execute("""
            SELECT c.name as cname, COUNT(p.id) as cnt
            FROM classes c LEFT JOIN players p ON p.class_id = c.id
            GROUP BY c.id ORDER BY cnt DESC
        """) as cur:
            class_rows = await cur.fetchall()

    return _json({
        "ok": True,
        "matches_by_tournament": [{"label": r["tname"] or "بدون تورنومنت", "value": r["cnt"]} for r in tourn_rows],
        "matches_by_day": [{"label": r["d"], "value": r["cnt"]} for r in reversed(daily_rows)],
        "players_by_class": [{"label": r["cname"] or "بدون کلاس", "value": r["cnt"]} for r in class_rows],
    })


# ─── تنظیمات سیستم ────────────────────────────────────────────────
@routes.get("/api/panel/settings")
async def panel_settings(request):
    _require_auth(request)
    import turso_db as _a
    async with _a.connect(db.DB_PATH) as conn:
        conn.row_factory = _a.Row
        async with conn.execute("SELECT * FROM system_settings") as cur:
            rows = await cur.fetchall()
    return _json({"ok": True, "settings": [{"key": r["key"], "value": r["value"]} for r in rows]})


# ─── دستیار (تاریخچه چت هوش مصنوعی) ────────────────────────────────
@routes.get("/api/panel/assistant")
async def panel_assistant(request):
    _require_auth(request)
    import turso_db as _a
    async with _a.connect(db.DB_PATH) as conn:
        conn.row_factory = _a.Row
        async with conn.execute("""
            SELECT s.id, s.title, s.started_at, s.last_message_at, s.user_id,
                   (SELECT COUNT(*) FROM ai_chat_messages m WHERE m.session_id = s.id) as msg_count
            FROM ai_chat_sessions s
            ORDER BY s.last_message_at DESC LIMIT 30
        """) as cur:
            rows = await cur.fetchall()
    return _json({"ok": True, "sessions": [dict(r) for r in rows]})


def register_panel_routes(app: web.Application):
    """این تابع رو صدا بزن تا route های پنل به یک اپلیکیشنِ aiohttp اضافه
    بشن. panel_server.py این تابع رو روی اپلیکیشنِ مستقلِ خودش صدا می‌زنه —
    این ماژول دیگه به سرورِ ربات (game_server.py) وصل نیست."""
    app.add_routes(routes)
    logger.info("Admin panel routes registered at /panel")
