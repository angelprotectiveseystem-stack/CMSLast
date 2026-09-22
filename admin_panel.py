"""
admin_panel.py — پنل مدیریتی وب (داشبورد زنده) برای مدیریت مسابقات شطرنج

این ماژول کاملاً مستقل از ربات تلگرام اجرا می‌شه (نه از bot.py و نه از
game_server.py استفاده می‌کنه) و روی سرور aiohttp خودش، در پروسه‌ی جدای
خودش، سرو می‌شه — با panel_server.py اجرا کن. تنها وابستگی‌اش دیتابیسِ
مشترک (Turso) از طریق database.py/turso_db.py هست.
تقریباً هیچ کوئری‌ای که این پنل می‌زنه چیزی رو توی دیتابیس تغییر نمی‌ده —
فقط SELECT — با یک استثنا: بخشِ «نفرات برتر» توی تبِ تنظیمات، که وقتی
حالتِ نمایش روی دستی باشه، انتخابِ همون پنج نفر از همین‌جا نوشته می‌شه
(این بخش قبلاً توی پنل مدیر مدرسه بود، به اینجا منتقل شده).

بخشِ «ارسال اعلان» هم می‌نویسه: اعلان‌هایی که از این‌جا ساخته/ویرایش/حذف
می‌شن، توی «زنگوله»ی پنل مدیر مدرسه دیده می‌شن و (اگه مدیر مدرسه اجازه داده
باشه) روی گوشی‌ش هم پوش می‌شن (push_notify.py).

احراز هویت: یک توکن ساده (رمز پنل از env، یا رمز پیشوا) که در
localStorage مرورگر ذخیره می‌شه و با هر درخواست به‌صورت هدر فرستاده می‌شه.
"""

import hashlib
import hmac
import json
import logging
import os
import time
import asyncio
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


async def _panel_enabled() -> bool:
    return (await db.get_setting("admin_webpanel_enabled", "1")) == "1"


async def _require_enabled(request):
    """اگر مدیر ارشد این پنل رو از داخل ربات خاموش کرده باشه، نه صفحه باز
    میشه، نه ورود، نه هیچ API‌ای — حتی با توکنِ معتبر."""
    if not await _panel_enabled():
        raise web.HTTPServiceUnavailable(
            text=json.dumps({"ok": False, "error": "panel_disabled"}),
            content_type="application/json",
        )


def _disabled_page():
    html = (
        "<!doctype html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        "<title>پنل غیرفعال است</title>"
        "<style>body{font-family:Tahoma,sans-serif;background:#111;color:#eee;"
        "display:flex;align-items:center;justify-content:center;height:100vh;margin:0;"
        "text-align:center;padding:20px}</style></head><body>"
        "<div>🔒 این پنل توسط مدیر ارشد غیرفعال شده است.<br>"
        "لطفاً بعداً دوباره تلاش کنید.</div></body></html>"
    )
    return web.Response(text=html, content_type="text/html", charset="utf-8", status=503)


def _json(data):
    return web.json_response(data, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


# ─── ورود ──────────────────────────────────────────────────────
@routes.post("/api/panel/login")
async def panel_login(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _panel_enabled():
        return _json({"ok": False, "error": "پنل توسط مدیر ارشد غیرفعال شده است."})
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


def _render_index():
    """index.html رو می‌خونه و {{V}} رو با نسخه‌ی واقعی assetها جایگزین می‌کنه
    تا مرورگر/CDN بعد از هر تغییر توی style.css یا app.js، فایل جدید رو
    بگیره نه نسخه‌ی کش‌شده‌ی قدیمی رو (همون چیزی که باعث می‌شد اصلاحات ظاهری
    و رفع سکته‌ی پولینگ، حتی بعد از دیپلوی، توی مرورگر کاربر دیده نشه)."""
    index_path = os.path.join(PANEL_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("{{V}}", _asset_version())
    resp = web.Response(text=html, content_type="text/html", charset="utf-8")
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@routes.get("/panel/{tail:.*}")
async def panel_static(request):
    if not await _panel_enabled():
        return _disabled_page()
    tail = request.match_info["tail"] or "index.html"
    path = os.path.normpath(os.path.join(PANEL_DIR, tail))
    if not path.startswith(PANEL_DIR):
        raise web.HTTPForbidden()
    if os.path.isdir(path) or not os.path.isfile(path) or path.endswith("index.html"):
        return _render_index()
    resp = web.FileResponse(path)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@routes.get("/panel")
async def panel_root(request):
    if not await _panel_enabled():
        return _disabled_page()
    return _render_index()


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
    await _require_enabled(request)
    # قبلاً این ۴ کوئری + گرفتنِ بازی‌های زنده پشتِ‌سرِهم اجرا می‌شدن — یعنی
    # هر بار باز شدنِ صفحه‌ی خانه‌ی پنلِ وب (که هر ۴ ثانیه هم پولینگ می‌شه)
    # چند رفت‌وبرگشتِ سریالی به Turso. کاملاً مستقلن، پس هم‌زمان اجرا می‌شن.
    async def _live_games_safe():
        try:
            return await _fetch_live_games_raw()
        except Exception:
            return []

    players, admins, matches, tournaments, live_games = await asyncio.gather(
        db.get_all_players(),
        db.get_all_admins(),
        db.get_matches_by_filter("all"),
        db.get_all_tournaments(),
        _live_games_safe(),
    )

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
    await _require_enabled(request)
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
    await _require_enabled(request)
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
    await _require_enabled(request)
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
    await _require_enabled(request)
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
    await _require_enabled(request)
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
    await _require_enabled(request)
    page = int(request.query.get("page", "0"))
    (logs, total), admins_rows = await asyncio.gather(
        db.get_action_logs(period="all", page=page, page_size=30),
        db.get_all_admins(),
    )
    admins = {a["telegram_id"]: (a["display_name"] or a["full_name"]) for a in (admins_rows or [])}
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
    await _require_enabled(request)
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
    await _require_enabled(request)
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
    await _require_enabled(request)
    import turso_db as _a

    # هر سه کوئری مستقلن — هم‌زمان اجرا می‌شن.
    async with _a.connect(db.DB_PATH) as conn:
        conn.row_factory = _a.Row
        tourn_cur, daily_cur, class_cur = await asyncio.gather(
            conn.execute("""
                SELECT t.name as tname, COUNT(m.id) as cnt
                FROM tournaments t LEFT JOIN matches m ON m.tournament_id = t.id
                GROUP BY t.id ORDER BY cnt DESC LIMIT 12
            """),
            conn.execute("""
                SELECT substr(created_at,1,10) as d, COUNT(*) as cnt
                FROM matches
                WHERE created_at IS NOT NULL
                GROUP BY d ORDER BY d DESC LIMIT 30
            """),
            conn.execute("""
                SELECT c.name as cname, COUNT(p.id) as cnt
                FROM classes c LEFT JOIN players p ON p.class_id = c.id
                GROUP BY c.id ORDER BY cnt DESC
            """),
        )
        tourn_rows = await tourn_cur.fetchall()
        daily_rows = await daily_cur.fetchall()
        class_rows = await class_cur.fetchall()

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
    await _require_enabled(request)
    import turso_db as _a
    async with _a.connect(db.DB_PATH) as conn:
        conn.row_factory = _a.Row
        async with conn.execute("SELECT * FROM system_settings") as cur:
            rows = await cur.fetchall()
    return _json({"ok": True, "settings": [{"key": r["key"], "value": r["value"]} for r in rows]})


# ─── نفراتِ برتر: انتخابِ دستی (منتقل‌شده از پنل مدیر مدرسه) ────────────
# حالتِ خودکار/دستی خودش فقط از تلگرام (منوی تنظیماتِ پیشوا) عوض می‌شه؛
# این پنل فقط همون حالت رو می‌خونه و، وقتی دستی‌ست، انتخابِ خودِ پنج نفر
# از همین‌جا نوشته می‌شه.
TOP_PLAYERS_MODE_KEY = "top_players_mode"       # "auto" | "manual"
TOP_PLAYERS_MANUAL_KEY = "top_players_manual"   # JSON: [{"rank":1,"player_id":12}, ...]

# شناسه‌ی نمادین برای لاگِ اقدامات؛ این پنل به کاربرِ تلگرامیِ خاصی وصل
# نیست (فقط با توکنِ نشست احراز هویت می‌شه)، پس آی‌دیِ واقعی‌ای نداریم.
_ADMIN_PANEL_LOG_ID = 0


async def _top_mode() -> str:
    val = await db.get_setting(TOP_PLAYERS_MODE_KEY, "auto")
    return val if val in ("auto", "manual") else "auto"


async def _manual_list() -> list:
    raw = await db.get_setting(TOP_PLAYERS_MANUAL_KEY, "[]")
    try:
        data = json.loads(raw) or []
    except Exception:
        data = []
    out = []
    for item in data:
        try:
            out.append({"rank": int(item["rank"]), "player_id": int(item["player_id"])})
        except Exception:
            continue
    out.sort(key=lambda x: x["rank"])
    return out


async def _save_manual_list(items: list):
    items = sorted(items, key=lambda x: x["rank"])
    await db.set_setting(TOP_PLAYERS_MANUAL_KEY, json.dumps(items, ensure_ascii=False))


async def _top_candidates_stats():
    """برای همه‌ی مسابقاتِ ثبت‌شده (بدون محدودیتِ بازه)، برای هر بازیکنی که
    مسابقه داشته آمار (بازی/برد/تساوی/باخت/امتیاز) حساب می‌کنه — پایه‌ی
    رتبه‌بندیِ پیشنهادیِ ربات برای وقتی که از این پنل نفراتِ برتر دستی
    انتخاب می‌شن."""
    matches, players = await asyncio.gather(
        db.get_matches_by_filter("all"), db.get_all_players()
    )
    matches = matches or []
    players = players or []
    meta = {
        p["id"]: {
            "full_name": p["full_name"],
            "class_name": p["class_name"] or "بدون کلاس",
            "status": p["status"],
        }
        for p in players
    }
    stats = {}
    for m in matches:
        if not m or m["result"] not in ("white", "black", "draw"):
            continue
        w_id, b_id = m["white_player_id"], m["black_player_id"]
        for pid in (w_id, b_id):
            stats.setdefault(pid, {"games": 0, "wins": 0, "draws": 0, "losses": 0, "score": 0.0})
        stats[w_id]["games"] += 1
        stats[b_id]["games"] += 1
        if m["result"] == "white":
            stats[w_id]["wins"] += 1
            stats[w_id]["score"] += 1
            stats[b_id]["losses"] += 1
        elif m["result"] == "black":
            stats[b_id]["wins"] += 1
            stats[b_id]["score"] += 1
            stats[w_id]["losses"] += 1
        else:
            stats[w_id]["draws"] += 1
            stats[w_id]["score"] += 0.5
            stats[b_id]["draws"] += 1
            stats[b_id]["score"] += 0.5
    return meta, stats


@routes.get("/api/panel/top-mode")
async def panel_top_mode(request):
    _require_auth(request)
    await _require_enabled(request)
    return _json({"ok": True, "top_players_mode": await _top_mode()})


@routes.get("/api/panel/top-candidates")
async def panel_top_candidates(request):
    """فهرستِ بازیکن‌های فعال، به ترتیبِ همون رتبه‌بندیِ خودکارِ ربات (بهترین
    نامزدها اول) — تا از بینِ همین ترتیب، پنج نفر برتر دستی انتخاب بشن.
    برای هرکدوم، رتبه‌ی دستیِ فعلی‌شون (اگه از قبل گرفته شده) هم همراهش
    می‌آد تا توی پنل با تیک نشون داده بشه."""
    _require_auth(request)
    await _require_enabled(request)
    meta, stats = await _top_candidates_stats()
    manual = await _manual_list()
    manual_rank = {item["player_id"]: item["rank"] for item in manual}

    rows = []
    for pid, m in meta.items():
        if m["status"] != "active":
            continue
        s = stats.get(pid, {"games": 0, "wins": 0, "draws": 0, "losses": 0, "score": 0.0})
        rows.append({
            "id": pid,
            "full_name": m["full_name"],
            "class_name": m["class_name"],
            **s,
            "manual_rank": manual_rank.get(pid),
        })
    rows.sort(key=lambda r: (-r["score"], -r["wins"], r["full_name"] or ""))
    return _json({"ok": True, "players": rows})


@routes.get("/api/panel/top-manual")
async def panel_top_manual_get(request):
    _require_auth(request)
    await _require_enabled(request)
    manual = await _manual_list()
    players = await db.get_all_players() or []
    meta = {p["id"]: {"full_name": p["full_name"], "class_name": p["class_name"] or "بدون کلاس"} for p in players}
    rows = []
    for item in manual:
        m = meta.get(item["player_id"])
        rows.append({
            "rank": item["rank"],
            "player_id": item["player_id"],
            "full_name": m["full_name"] if m else "بازیکن حذف‌شده",
            "class_name": m["class_name"] if m else "—",
        })
    return _json({"ok": True, "list": rows})


@routes.post("/api/panel/top-manual-set")
async def panel_top_manual_set(request):
    """این شخص از پنج نفر برتر چندم باشه — rank باید بینِ ۱ تا ۵ باشه. اگه
    قبلاً کسِ دیگه‌ای همون رتبه رو داشته، جاش عوض می‌شه؛ اگه خودِ این بازیکن
    قبلاً رتبه‌ی دیگه‌ای داشته، اون یکی برداشته می‌شه (هر بازیکن حداکثر یک
    رتبه)."""
    _require_auth(request)
    await _require_enabled(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        player_id = int(body.get("player_id"))
        rank = int(body.get("rank"))
    except Exception:
        return _json({"ok": False, "error": "invalid_input"})
    if rank < 1 or rank > 5:
        return _json({"ok": False, "error": "invalid_rank"})

    player = await db.get_player(player_id)
    if not player or player["status"] != "active":
        return _json({"ok": False, "error": "player_not_found"})

    items = await _manual_list()
    items = [i for i in items if i["player_id"] != player_id and i["rank"] != rank]
    items.append({"rank": rank, "player_id": player_id})
    await _save_manual_list(items)
    await db.log_action(_ADMIN_PANEL_LOG_ID, "top_manual_set",
                         f"رتبه {rank} برای بازیکنِ #{player_id} (از پنل ادمین)")
    return await panel_top_manual_get(request)


@routes.post("/api/panel/top-manual-remove")
async def panel_top_manual_remove(request):
    _require_auth(request)
    await _require_enabled(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        player_id = int(body.get("player_id"))
    except Exception:
        return _json({"ok": False, "error": "invalid_input"})
    items = await _manual_list()
    items = [i for i in items if i["player_id"] != player_id]
    await _save_manual_list(items)
    await db.log_action(_ADMIN_PANEL_LOG_ID, "top_manual_remove",
                         f"حذفِ بازیکنِ #{player_id} از نفراتِ برتر (از پنل ادمین)")
    return await panel_top_manual_get(request)


# ─── دستیار (تاریخچه چت هوش مصنوعی) ────────────────────────────────
# گفتگوهای دو منبع اینجا دیده می‌شن (هر دو فقط‌خواندنی):
#   • «مدیر مدرسه» — از دستیارِ پنل مدیر مدرسه (role = principal)
#   • «ادمین‌ها»   — از دستیارِ داخل ربات تلگرام (مدیر ارشد و مدیران)
async def _assistant_owner_names() -> dict:
    admins_rows, pishva_name = await asyncio.gather(
        db.get_all_admins(),
        db.get_setting("pishva_display_name", "مدیر ارشد"),
    )
    names = {a["telegram_id"]: (a["display_name"] or a["full_name"]) for a in (admins_rows or [])}
    names[PISHVA_ID] = pishva_name or "مدیر ارشد"
    return names


def _assistant_source(role) -> str:
    return "principal" if role == db.AI_ROLE_PRINCIPAL else "admin"


def _assistant_owner(row, names: dict) -> str:
    if row["role"] == db.AI_ROLE_PRINCIPAL:
        return "مدیر مدرسه"
    return names.get(row["user_id"], str(row["user_id"]))


@routes.get("/api/panel/assistant")
async def panel_assistant(request):
    _require_auth(request)
    await _require_enabled(request)
    source = request.query.get("source", "all")
    if source not in ("all", "principal", "admins"):
        source = "all"
    q = request.query.get("q", "")
    rows, names = await asyncio.gather(
        db.ai_list_sessions_overview(source=source, q=q, limit=100),
        _assistant_owner_names(),
    )
    sessions = [{
        "id": r["id"],
        "title": r["title"],
        "started_at": r["started_at"],
        "last_message_at": r["last_message_at"],
        "msg_count": r["msg_count"],
        "source": _assistant_source(r["role"]),
        "owner": _assistant_owner(r, names),
    } for r in (rows or [])]
    return _json({"ok": True, "sessions": sessions})


@routes.get("/api/panel/assistant/{session_id}")
async def panel_assistant_session(request):
    _require_auth(request)
    await _require_enabled(request)
    try:
        sid = int(request.match_info["session_id"])
    except ValueError:
        raise web.HTTPBadRequest(text=json.dumps({"ok": False, "error": "bad_session_id"}),
                                 content_type="application/json")
    sess = await db.ai_get_session(sid)
    if not sess:
        raise web.HTTPNotFound(text=json.dumps({"ok": False, "error": "not_found"}),
                               content_type="application/json")
    msgs, names = await asyncio.gather(db.ai_get_messages(sid, limit=1000), _assistant_owner_names())
    return _json({
        "ok": True,
        "session": {
            "id": sess["id"],
            "title": sess["title"],
            "started_at": sess["started_at"],
            "last_message_at": sess["last_message_at"],
            "source": _assistant_source(sess["role"]),
            "owner": _assistant_owner(sess, names),
        },
        "messages": [{"id": m["id"], "sender": m["sender"], "text": m["text"],
                      "sent_at": m["sent_at"]} for m in (msgs or [])],
    })


# ─── دستگاه‌های پنل مدیر مدرسه (لاگ ورود + بلاک/آنبلاک/حذف) ────────
# پنل مدیر مدرسه حساب‌کاربری نداره (فقط یک کلیدِ ثابت در لینک)، برای همین
# «دستگاه» چیزی جز ترکیبِ IP+User-Agent نیست (device_id، در
# principal_panel.py ساخته می‌شه). این بخش فقط‌خواندنی نیست: تنها جایی از
# پنل ادمینه که واقعاً روی دیتابیس می‌نویسه (بلاک/آنبلاک/حذفِ لاگ).
@routes.get("/api/panel/principal-devices")
async def panel_principal_devices(request):
    _require_auth(request)
    await _require_enabled(request)
    devices = await db.get_principal_devices()
    out = [{
        "device_id": d["device_id"],
        "ip": d["ip"],
        "browser": d["browser"],
        "os": d["os"],
        "device_type": d["device_type"],
        "city": d["city"],
        "region": d["region"],
        "country": d["country"],
        "visits": d["visits"],
        "first_seen": d["first_seen"],
        "last_seen": d["last_seen"],
        "is_blocked": bool(d["is_blocked"]),
        "block_reason": d["block_reason"],
        "blocked_at": d["blocked_at"],
    } for d in (devices or [])]
    return _json({"ok": True, "devices": out})


# ─── لاگ خامِ ورودها (برای دیدنِ جزئیاتِ هر بازدید، نه فقط خلاصه‌ی دستگاه) ──
@routes.get("/api/panel/principal-log")
async def panel_principal_log(request):
    _require_auth(request)
    await _require_enabled(request)
    page = int(request.query.get("page", "0"))
    device_id = request.query.get("device_id") or None
    logs, total = await db.get_principal_access_log(page=page, page_size=40, device_id=device_id)
    out = [{
        "id": l["id"],
        "device_id": l["device_id"],
        "ip": l["ip"],
        "browser": l["browser"],
        "os": l["os"],
        "device_type": l["device_type"],
        "city": l["city"],
        "region": l["region"],
        "country": l["country"],
        "path": l["path"],
        "allowed": bool(l["allowed"]),
        "created_at": l["created_at"],
    } for l in (logs or [])]
    return _json({"ok": True, "log": out, "total": total, "page": page})


@routes.post("/api/panel/principal-devices/block")
async def panel_principal_device_block(request):
    _require_auth(request)
    await _require_enabled(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = (body.get("device_id") or "").strip()
    reason = (body.get("reason") or "").strip() or "بدون دلیلِ ثبت‌شده"
    if not device_id:
        return _json({"ok": False, "error": "invalid_input"})
    devices = await db.get_principal_devices()
    match = next((d for d in (devices or []) if d["device_id"] == device_id), None)
    if not match:
        return _json({"ok": False, "error": "device_not_found"})
    await db.block_principal_device(
        device_id, match["ip"], match["user_agent"], match["browser"], match["os"], reason
    )
    await db.log_action(_ADMIN_PANEL_LOG_ID, "principal_device_block",
                         f"بلاکِ دستگاهِ #{device_id} در پنل مدیر مدرسه — دلیل: {reason} (از پنل ادمین)")
    return _json({"ok": True})


@routes.post("/api/panel/principal-devices/unblock")
async def panel_principal_device_unblock(request):
    _require_auth(request)
    await _require_enabled(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = (body.get("device_id") or "").strip()
    if not device_id:
        return _json({"ok": False, "error": "invalid_input"})
    await db.unblock_principal_device(device_id)
    await db.log_action(_ADMIN_PANEL_LOG_ID, "principal_device_unblock",
                         f"آنبلاکِ دستگاهِ #{device_id} در پنل مدیر مدرسه (از پنل ادمین)")
    return _json({"ok": True})


@routes.post("/api/panel/principal-devices/delete")
async def panel_principal_device_delete(request):
    """«حذفِ دسترسی»: فقط سوابقِ لاگِ این دستگاه از فهرست پاک می‌شه، بدونِ
    بلاک‌کردنش — برای پاک‌سازیِ فهرست، نه محدودکردنِ دسترسیِ آینده."""
    _require_auth(request)
    await _require_enabled(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = (body.get("device_id") or "").strip()
    if not device_id:
        return _json({"ok": False, "error": "invalid_input"})
    await db.delete_principal_device_log(device_id)
    await db.log_action(_ADMIN_PANEL_LOG_ID, "principal_device_delete",
                         f"حذفِ سوابقِ دستگاهِ #{device_id} از لاگِ پنل مدیر مدرسه (از پنل ادمین)")
    return _json({"ok": True})


# ─── ارسال اعلان به پنل مدیر مدرسه ───────────────────────────────────
# ساخت/ویرایش/حذفِ اعلان فقط از این‌جاست. مدیر مدرسه فقط می‌خونه و خوانده/
# نخوانده علامت می‌زنه (principal_panel.py).
def _admin_notif_out(r) -> dict:
    return {
        "id": r["id"],
        "title": r["title"],
        "body": r["body"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "is_read": bool(r["is_read"]),
        "read_at": r["read_at"],
    }


def _clean_notif_fields(body: dict):
    """(title, body_text, error) — فاصله‌های اضافیِ دو سر گرفته می‌شه؛ خطوطِ
    متنِ اعلان دست‌نخورده می‌مونن."""
    title = (body.get("title") or "").strip()
    text = (body.get("body") or "").strip()
    if not title:
        return None, None, "عنوانِ اعلان را وارد کنید."
    if not text:
        return None, None, "متنِ اعلان را وارد کنید."
    if len(title) > db.PRINCIPAL_NOTIF_TITLE_MAX:
        return None, None, f"عنوان نباید بیشتر از {db.PRINCIPAL_NOTIF_TITLE_MAX} نویسه باشد."
    if len(text) > db.PRINCIPAL_NOTIF_BODY_MAX:
        return None, None, f"متن نباید بیشتر از {db.PRINCIPAL_NOTIF_BODY_MAX} نویسه باشد."
    return title, text, None


@routes.get("/api/panel/notifications")
async def panel_notifications(request):
    _require_auth(request)
    await _require_enabled(request)
    import push_notify
    rows, subs = await asyncio.gather(
        db.get_principal_notifications(), db.count_push_subscriptions()
    )
    return _json({
        "ok": True,
        "items": [_admin_notif_out(r) for r in (rows or [])],
        "subscribers": subs,
        "push_available": push_notify.is_available(),
        "max_title": db.PRINCIPAL_NOTIF_TITLE_MAX,
        "max_body": db.PRINCIPAL_NOTIF_BODY_MAX,
    })


@routes.post("/api/panel/notifications/send")
async def panel_notification_send(request):
    _require_auth(request)
    await _require_enabled(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    title, text, err = _clean_notif_fields(body)
    if err:
        return _json({"ok": False, "error": err})

    import push_notify
    notif_id = await db.create_principal_notification(title, text)
    await db.log_action(_ADMIN_PANEL_LOG_ID, "principal_notification_send",
                         f"ارسالِ اعلانِ #{notif_id} به پنل مدیر مدرسه: «{title}» (از پنل ادمین)")
    # ثبتِ اعلان اولویت داره؛ نتیجه‌ی پوش فقط برای اطلاعِ ادمینه.
    push = await push_notify.broadcast(notif_id, title, text, push_notify.subject_for(request))
    return _json({"ok": True, "id": notif_id, "push": push})


@routes.post("/api/panel/notifications/update")
async def panel_notification_update(request):
    _require_auth(request)
    await _require_enabled(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        notif_id = int(body.get("id"))
    except Exception:
        return _json({"ok": False, "error": "شناسه‌ی اعلان نامعتبر است."})
    title, text, err = _clean_notif_fields(body)
    if err:
        return _json({"ok": False, "error": err})
    if not await db.get_principal_notification(notif_id):
        return _json({"ok": False, "error": "این اعلان دیگر وجود ندارد."})
    await db.update_principal_notification(notif_id, title, text)
    await db.log_action(_ADMIN_PANEL_LOG_ID, "principal_notification_edit",
                         f"ویرایشِ اعلانِ #{notif_id} پنل مدیر مدرسه: «{title}» (از پنل ادمین)")
    return _json({"ok": True})


@routes.post("/api/panel/notifications/delete")
async def panel_notification_delete(request):
    _require_auth(request)
    await _require_enabled(request)
    try:
        body = await request.json()
        notif_id = int(body.get("id"))
    except Exception:
        return _json({"ok": False, "error": "شناسه‌ی اعلان نامعتبر است."})
    existing = await db.get_principal_notification(notif_id)
    if not existing:
        return _json({"ok": False, "error": "این اعلان دیگر وجود ندارد."})
    await db.delete_principal_notification(notif_id)
    await db.log_action(_ADMIN_PANEL_LOG_ID, "principal_notification_delete",
                         f"حذفِ اعلانِ #{notif_id} از پنل مدیر مدرسه: «{existing['title']}» (از پنل ادمین)")
    return _json({"ok": True})


def register_panel_routes(app: web.Application):
    """این تابع رو صدا بزن تا route های پنل به یک اپلیکیشنِ aiohttp اضافه
    بشن. panel_server.py این تابع رو روی اپلیکیشنِ مستقلِ خودش صدا می‌زنه —
    این ماژول دیگه به سرورِ ربات (game_server.py) وصل نیست."""
    app.add_routes(routes)
    logger.info("Admin panel routes registered at /panel")
