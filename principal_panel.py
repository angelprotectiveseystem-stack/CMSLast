"""
principal_panel.py — پنل فقط‌خواندنیِ مدیر مدرسه.

این ماژول هیچ نوشتنی روی دیتابیس نداره؛ فقط SELECT. مستقل از منطق ربات
و از admin_panel.py هست، ولی درست مثل همون، روی همون اپلیکیشن aiohttp ای
که game_server.py می‌سازه سوار میشه (نه یک سرور جدا).

احراز هویت: بدون فرم ورود و بدون رمز — فقط یک کلید ثابت (env: PRINCIPAL_KEY)
که در خودِ لینک به‌صورت ?k=... قرار می‌گیره. هر درخواستی (چه صفحه، چه API)
باید این کلید رو با پارامتر k بفرسته.
"""

import hmac
import json
import logging
import os
import asyncio
from datetime import datetime, timedelta

from aiohttp import web

import database as db

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

PANEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp_principal")

# ─── کلید دسترسی ────────────────────────────────────────────────
PRINCIPAL_KEY = os.environ.get("PRINCIPAL_KEY", "")


def _authed(request) -> bool:
    if not PRINCIPAL_KEY:
        # اگر کلیدی تنظیم نشده باشه، به‌خاطر امنیت هیچ درخواستی معتبر شمرده نمیشه.
        return False
    k = request.query.get("k", "")
    return hmac.compare_digest(k, PRINCIPAL_KEY)


async def _panel_enabled() -> bool:
    return (await db.get_setting("principal_panel_enabled", "1")) == "1"


def _require_auth(request):
    if not _authed(request):
        raise web.HTTPUnauthorized(
            text=json.dumps({"ok": False, "error": "unauthorized"}),
            content_type="application/json",
        )


async def _require_enabled(request):
    """اگر مدیر ارشد این پنل رو از داخل ربات خاموش کرده باشه، حتی با کلیدِ
    درست هم نه صفحه باز میشه نه هیچ API‌ای جواب میده."""
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


# ─── صفحه اصلی و فایل‌های استاتیک ────────────────────────────────
def _asset_version():
    try:
        mtimes = [
            os.path.getmtime(os.path.join(PANEL_DIR, f))
            for f in os.listdir(PANEL_DIR)
            if os.path.isfile(os.path.join(PANEL_DIR, f))
        ]
        return str(int(max(mtimes))) if mtimes else "0"
    except Exception:
        return "0"


def _render_index(request):
    index_path = os.path.join(PANEL_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("{{V}}", _asset_version())
    # کلید همون‌طور که هست (حتی اگه خالی/غلط باشه) توی صفحه جاگذاری میشه؛
    # درخواست‌های API خودشون کلید غلط رو رد می‌کنن.
    html = html.replace("{{KEY}}", request.query.get("k", ""))
    resp = web.Response(text=html, content_type="text/html", charset="utf-8")
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@routes.get("/principal/{tail:.*}")
async def principal_static(request):
    if not await _panel_enabled():
        return _disabled_page()
    tail = request.match_info["tail"] or "index.html"
    path = os.path.normpath(os.path.join(PANEL_DIR, tail))
    if not path.startswith(PANEL_DIR):
        raise web.HTTPForbidden()
    if os.path.isdir(path) or not os.path.isfile(path) or path.endswith("index.html"):
        return _render_index(request)
    resp = web.FileResponse(path)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@routes.get("/principal")
async def principal_root(request):
    if not await _panel_enabled():
        return _disabled_page()
    return _render_index(request)


@routes.get("/principal-assets/{tail:.*}")
async def principal_assets(request):
    if not await _panel_enabled():
        raise web.HTTPServiceUnavailable()
    tail = request.match_info["tail"]
    path = os.path.normpath(os.path.join(PANEL_DIR, tail))
    if not path.startswith(PANEL_DIR) or not os.path.isfile(path):
        raise web.HTTPNotFound()
    resp = web.FileResponse(path)
    if "v" in request.query:
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


# ─── کمکی‌ها ─────────────────────────────────────────────────────
def _result_fa(m):
    r = m["result"]
    if r == "white":
        return f"برد {m['white_name'] or '—'}"
    if r == "black":
        return f"برد {m['black_name'] or '—'}"
    if r == "draw":
        return "تساوی"
    if r == "cancelled":
        return "لغو شده"
    return "بدون نتیجه"


# ─── خلاصه کلی ────────────────────────────────────────────────────
@routes.get("/api/principal/overview")
async def principal_overview(request):
    _require_auth(request)
    await _require_enabled(request)
    # قبلاً این ۵ کوئری پشتِ‌سرِهم (نه هم‌زمان) اجرا می‌شدن — یعنی ۵ رفت‌وبرگشتِ
    # کاملِ شبکه‌ای به Turso، یکی بعد از اون یکی. چون کاملاً مستقل از همدیگه‌ن،
    # با gather هم‌زمان اجرا می‌شن و کل زمانِ انتظار برابرِ کندترین‌شون می‌شه،
    # نه مجموعِ همه‌شون.
    classes, players, tournaments, matches_all, matches_week = await asyncio.gather(
        db.get_all_classes(),
        db.get_all_players(),
        db.get_all_tournaments(),
        db.get_matches_by_filter("all"),
        db.get_matches_by_filter("week"),
    )
    classes = classes or []
    players = players or []
    tournaments = tournaments or []
    matches_all = matches_all or []
    matches_week = matches_week or []

    players_active = sum(1 for p in players if p and p["status"] == "active")
    decided = [m for m in matches_all if m and m["result"] in ("white", "black", "draw")]
    active_tournaments = [t for t in tournaments if t and t["status"] == "active"]

    return _json({
        "ok": True,
        "stats": {
            "classes_total": len(classes),
            "players_total": len(players),
            "players_active": players_active,
            "matches_total": len(matches_all),
            "matches_this_week": len(matches_week),
            "matches_decided": len(decided),
            "tournaments_active": len(active_tournaments),
        },
    })


# ─── کلاس‌ها ──────────────────────────────────────────────────────
@routes.get("/api/principal/classes")
async def principal_classes(request):
    _require_auth(request)
    await _require_enabled(request)
    # قبلاً برای هر کلاس یک کوئری جدا (get_players_by_class) زده می‌شد — یعنی
    # با N کلاس، N رفت‌وبرگشتِ شبکه‌ایِ اضافه، پشتِ‌سرِهم. چون get_all_players
    # همه‌ی بازیکن‌ها رو با class_id برمی‌گردونه (و الان کش هم می‌شه)، به‌جاش
    # یک‌بار همه رو می‌گیریم و خودمون توی پایتون بر اساس کلاس گروه‌بندی می‌کنیم.
    classes, players = await asyncio.gather(db.get_all_classes(), db.get_all_players())
    classes = classes or []
    players = players or []
    by_class = {}
    for p in players:
        by_class.setdefault(p["class_id"], []).append(p)
    out = []
    for c in classes:
        cplayers = by_class.get(c["id"], [])
        out.append({
            "name": c["name"],
            "player_count": len(cplayers),
            "wins": sum((p["wins"] or 0) for p in cplayers),
            "draws": sum((p["draws"] or 0) for p in cplayers),
            "losses": sum((p["losses"] or 0) for p in cplayers),
        })
    return _json({"ok": True, "classes": out})


# ─── بازیکنان ─────────────────────────────────────────────────────
@routes.get("/api/principal/players")
async def principal_players(request):
    _require_auth(request)
    await _require_enabled(request)
    players = await db.get_all_players() or []
    out = []
    for p in players:
        games = (p["wins"] or 0) + (p["losses"] or 0) + (p["draws"] or 0)
        out.append({
            "full_name": p["full_name"],
            "class_name": p["class_name"] or "بدون کلاس",
            "status": p["status"],
            "games": games,
            "wins": p["wins"] or 0,
            "draws": p["draws"] or 0,
            "losses": p["losses"] or 0,
            "is_elite": bool(p["is_elite"]),
        })
    return _json({"ok": True, "players": out})


# ─── مسابقات ──────────────────────────────────────────────────────
@routes.get("/api/principal/matches")
async def principal_matches(request):
    _require_auth(request)
    await _require_enabled(request)
    period = request.query.get("period", "all")
    matches = await db.get_matches_by_filter(period) or []
    out = []
    for m in matches:
        out.append({
            "white": m["white_name"] or "—",
            "black": m["black_name"] or "—",
            "result": m["result"],
            "result_fa": _result_fa(m),
            "match_date": m["match_date"],
            "created_at": m["created_at"],
        })
    return _json({"ok": True, "matches": out})


# ─── نفرات برتر (هفته/ماه/کل) ─────────────────────────────────────
@routes.get("/api/principal/top")
async def principal_top(request):
    _require_auth(request)
    await _require_enabled(request)
    period = request.query.get("period", "week")
    matches, players = await asyncio.gather(
        db.get_matches_by_filter(period), db.get_all_players()
    )
    matches = matches or []
    players = players or []
    meta = {p["id"]: {"full_name": p["full_name"], "class_name": p["class_name"] or "بدون کلاس"} for p in players}

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

    rows = []
    for pid, s in stats.items():
        m = meta.get(pid, {"full_name": "بازیکن حذف‌شده", "class_name": "—"})
        rows.append({**m, **s})
    rows.sort(key=lambda r: (-r["score"], -r["wins"]))
    return _json({"ok": True, "leaderboard": rows[:50]})


# ─── روندها (نمودارها) ─────────────────────────────────────────────
@routes.get("/api/principal/trends")
async def principal_trends(request):
    _require_auth(request)
    await _require_enabled(request)
    import turso_db as _a

    now = datetime.now()

    async with _a.connect(db.DB_PATH) as conn:
        conn.row_factory = _a.Row

        # این ۴ کوئری کاملاً مستقلن (فقط SELECT، هیچ‌کدوم به نتیجه‌ی بقیه
        # نیاز نداره)؛ قبلاً پشتِ‌سرِهم اجرا می‌شدن، الان هم‌زمان.
        daily_cur, week_cur, class_cur, result_cur = await asyncio.gather(
            conn.execute(
                """SELECT substr(created_at,1,10) as d, COUNT(*) as cnt
                   FROM matches WHERE created_at IS NOT NULL
                   GROUP BY d ORDER BY d DESC LIMIT 30"""
            ),
            conn.execute(
                "SELECT created_at FROM matches WHERE created_at >= ?",
                ((now - timedelta(days=56)).isoformat(),),
            ),
            conn.execute(
                """SELECT c.name as cname, COUNT(p.id) as cnt
                   FROM classes c LEFT JOIN players p ON p.class_id = c.id
                   GROUP BY c.id ORDER BY cnt DESC"""
            ),
            conn.execute(
                "SELECT result, COUNT(*) as cnt FROM matches WHERE result IS NOT NULL GROUP BY result"
            ),
        )
        daily_rows = await daily_cur.fetchall()
        week_rows = await week_cur.fetchall()
        class_rows = await class_cur.fetchall()
        result_rows = await result_cur.fetchall()

    # سطل‌بندی هفتگی (۸ هفته اخیر، از قدیم به جدید)
    buckets = [0] * 8
    for r in week_rows:
        try:
            dt = datetime.fromisoformat(r["created_at"])
        except Exception:
            continue
        idx = (now - dt).days // 7
        if 0 <= idx < 8:
            buckets[7 - idx] += 1
    week_labels = [(now - timedelta(days=7 * (7 - i))).strftime("%m-%d") for i in range(8)]
    matches_by_week = [{"label": week_labels[i], "value": buckets[i]} for i in range(8)]

    result_fa_map = {"white": "برد سفید", "black": "برد سیاه", "draw": "تساوی", "cancelled": "لغو شده"}

    return _json({
        "ok": True,
        "matches_by_day": [{"label": r["d"], "value": r["cnt"]} for r in reversed(daily_rows)],
        "matches_by_week": matches_by_week,
        "players_by_class": [{"label": r["cname"] or "بدون کلاس", "value": r["cnt"]} for r in class_rows],
        "results_distribution": [
            {"label": result_fa_map.get(r["result"], r["result"]), "value": r["cnt"]} for r in result_rows
        ],
    })


def register_principal_routes(app: web.Application):
    """این تابع رو از game_server.py صدا بزن تا مسیرهای پنل مدیر مدرسه
    به همون اپلیکیشنِ aiohttp اضافه بشن (دقیقاً مثل register_panel_routes)."""
    app.add_routes(routes)
    logger.info("Principal panel routes registered at /principal")
